#!/usr/bin/env python3
"""
Chrome 书签整理工具 - 完整版 v2.0
整合所有常用书签管理功能。

用法:  python bookmark_tool.py <command> [options]

命令:
  scan      扫描所有书签
  categorize 按规则分类根目录书签
  move       移动匹配书签到指定文件夹
  flatten    展开文件夹到根目录
  dedup      查找并移除重复书签（同 URL）
  check      检测失效链接（HTTP 状态码）
  search     按关键词搜索书签
  merge      合并两个文件夹
  sort       对文件夹内书签排序
  clean      清理空文件夹
  stats      显示书签统计信息
  export     导出为 HTML 文件（Netscape 格式）
  domain     按域名分组统计
  prefix     批量添加前缀/后缀到书签名称
"""
import os, json, sys, copy, shutil, argparse, glob, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime
from collections import defaultdict, Counter

# ============================================================
# 配置
# ============================================================
BM_PATH = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'Google', 'Chrome', 'User Data', 'Default', 'Bookmarks'
)
PREF_PATH = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'Google', 'Chrome', 'User Data', 'Default', 'Preferences'
)

# ============================================================
# 工具函数
# ============================================================
def ts():
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def backup(suffix=''):
    bp = BM_PATH + f'.bak_{ts()}{suffix}'
    shutil.copy2(BM_PATH, bp)
    return bp

def load():
    with open(BM_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(data):
    with open(BM_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_ascii(s):
    try:
        s.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

def match_keywords(text, keywords):
    tl = text.lower()
    for kw in keywords:
        if is_ascii(kw):
            if kw.lower() in tl:
                return True
        else:
            if kw in text:
                return True
    return False

def remove_and_collect(items, match_fn):
    new_items = []
    removed = []
    for item in items:
        if item.get('type') == 'url':
            if match_fn(item.get('name', ''), item.get('url', '')):
                removed.append(copy.deepcopy(item))
            else:
                new_items.append(item)
        elif item.get('type') == 'folder':
            ic = copy.deepcopy(item)
            nc, rr = remove_and_collect(item.get('children', []), match_fn)
            ic['children'] = nc
            new_items.append(ic)
            removed.extend(rr)
        else:
            new_items.append(copy.deepcopy(item))
    return new_items, removed

def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        if item.get('url') and item['url'] not in seen:
            seen.add(item['url'])
            result.append(item)
    return result

def count_urls(items):
    c = 0
    for item in items:
        if item.get('type') == 'url':
            c += 1
        elif item.get('type') == 'folder':
            c += count_urls(item.get('children', []))
    return c

def make_folder(name, children):
    return {
        "date_added": "13325168000000000",
        "date_last_used": "0",
        "guid": f"bm-{hash(name) & 0xFFFFFFFF:08x}",
        "id": str(100000 + (hash(name) % 900000)),
        "name": name,
        "type": "folder",
        "children": children
    }

def write_result(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path

def scan_all(items, path='', results=None):
    if results is None:
        results = []
    for item in items:
        if item.get('type') == 'url':
            results.append({
                'name': item.get('name', ''),
                'url': item.get('url', ''),
                'parent_path': path,
                'item': copy.deepcopy(item)
            })
        elif item.get('type') == 'folder':
            scan_all(item.get('children', []), path + '>' + item.get('name', ''), results)
    return results

def get_all_bookmarks(data):
    results = []
    for rk, root in data['roots'].items():
        if isinstance(root, dict) and 'children' in root:
            scan_all(root['children'], rk, results)
    return results

def find_folder(data, folder_name, parent_path=None):
    """在根目录查找文件夹，返回 (folder_item, siblings_list, is_root)"""
    bar = data['roots']['bookmark_bar']['children']
    for i, item in enumerate(bar):
        if item.get('name') == folder_name and item.get('type') == 'folder':
            return item, bar, True
    return None, None, None

# ============================================================
# 命令 1: scan
# ============================================================
def cmd_scan(args):
    data = load()
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'bookmark_scan.txt')
    lines = []
    total = [0]
    by_folder = defaultdict(int)
    
    def scan(items, path=''):
        for item in items:
            if item.get('type') == 'url':
                total[0] += 1
                by_folder[path] += 1
                lines.append(f'{total[0]}. [{path}] {item["name"]}')
                lines.append(f'   {item["url"][:90]}')
            elif item.get('type') == 'folder':
                scan(item.get('children', []), path + '>' + item.get('name', ''))
    
    for rk, root in data['roots'].items():
        if isinstance(root, dict) and 'children' in root:
            scan(root['children'], rk)
    
    lines.insert(0, f'Total: {total[0]}\n')
    if args.stats:
        lines.append('\n=== 按文件夹统计 ===')
        for path, cnt in sorted(by_folder.items(), key=lambda x: -x[1]):
            lines.append(f'  {path}: {cnt}')
    
    write_result(out_path, lines)
    print(f'Scanned {total[0]} bookmarks -> {out_path}')
    return out_path

# ============================================================
# 命令 2: categorize
# ============================================================
def cmd_categorize(args):
    with open(args.rules, 'r', encoding='utf-8') as f:
        rules_data = json.load(f)
    rules = [(r['folder'], r['keywords']) for r in rules_data]
    
    bp = backup('_before_cat')
    print(f'Backup: {bp}')
    
    data = load()
    bar = data['roots']['bookmark_bar']
    
    url_items = []
    folder_items = []
    for item in bar.get('children', []):
        if item.get('type') == 'url':
            url_items.append(item)
        elif item.get('type') == 'folder':
            folder_items.append(item)
    
    categorized = {}
    for item in url_items:
        name = item.get('name', '')
        url = item.get('url', '')
        text = name + ' ' + url
        matched = False
        for folder_name, keywords in rules:
            if match_keywords(text, keywords):
                categorized.setdefault(folder_name, []).append(copy.deepcopy(item))
                matched = True
                break
        if not matched:
            categorized.setdefault('其他', []).append(copy.deepcopy(item))
    
    new_bar = list(folder_items)
    for folder_name, items in categorized.items():
        existing = None
        for fi in new_bar:
            if fi.get('name') == folder_name and fi.get('type') == 'folder':
                existing = fi
                break
        
        if existing:
            existing_urls = {c.get('url','') for c in existing.get('children',[]) if c.get('type')=='url'}
            added = 0
            for item in deduplicate(items):
                if item['url'] not in existing_urls:
                    existing['children'].append(item)
                    added += 1
            print(f'  [{folder_name}]: +{added} (total {len(existing["children"])})')
        else:
            deduped = deduplicate(items)
            new_bar.append(make_folder(folder_name, deduped))
            print(f'  [{folder_name}]: new folder with {len(deduped)} bookmarks')
    
    if not args.dry_run:
        bar['children'] = new_bar
        save(data)
        print('Done! Bookmarks written.')
    else:
        print('[DRY RUN] No changes written.')
    
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'categorize_result.txt')
    lines = [f'Total URLs categorized: {sum(len(v) for v in categorized.values())}\n']
    for fname, items in categorized.items():
        lines.append(f'{fname}: {len(items)}')
    write_result(out_path, lines)
    print(f'Result: {out_path}')

# ============================================================
# 命令 3: move
# ============================================================
def cmd_move(args):
    bp = backup('_before_move')
    print(f'Backup: {bp}')
    
    keywords = args.keywords
    target_folder = args.folder
    
    data = load()
    
    if args.root_only:
        bar = data['roots']['bookmark_bar']
        removed = []
        kept = []
        for item in bar.get('children', []):
            if item.get('type') == 'url' and match_keywords(item.get('name','')+' '+item.get('url',''), keywords):
                removed.append(item)
            else:
                kept.append(item)
        bar['children'] = kept
        removed = deduplicate(removed)
    else:
        def match_fn(name, url):
            return match_keywords(name + ' ' + url, keywords)
        removed = []
        for rk in data['roots']:
            nc, rr = remove_and_collect(data['roots'][rk].get('children', []), match_fn)
            data['roots'][rk]['children'] = nc
            removed.extend(rr)
        removed = deduplicate(removed)
    
    bar = data['roots']['bookmark_bar']
    target = None
    for item in bar.get('children', []):
        if item.get('name') == target_folder and item.get('type') == 'folder':
            target = item
            break
    
    if target is None:
        target = make_folder(target_folder, [])
        bar['children'].append(target)
    
    existing_urls = {c.get('url','') for c in target.get('children',[]) if c.get('type')=='url'}
    added = 0
    for item in removed:
        if item.get('type') == 'url' and item['url'] not in existing_urls:
            target['children'].append(item)
            added += 1
    
    save(data)
    print(f'Moved {added} bookmarks to [{target_folder}]')
    
    out_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'move_result.txt')
    lines = [f'Moved {added} bookmarks to [{target_folder}]\n']
    write_result(out_path, lines)
    print(f'Result: {out_path}')

# ============================================================
# 命令 4: flatten
# ============================================================
def cmd_flatten(args):
    bp = backup('_before_flatten')
    print(f'Backup: {bp}')
    
    folder_name = args.folder
    keep = args.keep_folder
    
    data = load()
    bar = data['roots']['bookmark_bar']
    
    moved = []
    new_children = []
    for item in bar.get('children', []):
        if item.get('name') == folder_name and item.get('type') == 'folder':
            moved = item.get('children', [])
            if keep:
                item['children'] = []
                new_children.append(item)
        else:
            new_children.append(item)
    
    existing_urls = {c.get('url','') for c in new_children if c.get('type')=='url'}
    for item in deduplicate(moved):
        if item.get('type') == 'url' and item['url'] not in existing_urls:
            new_children.append(copy.deepcopy(item))
        elif item.get('type') == 'folder':
            new_children.append(copy.deepcopy(item))
    
    bar['children'] = new_children
    save(data)
    print(f'Flattened {len(moved)} items from [{folder_name}]')
    
    out_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'flatten_result.txt')
    lines = [f'Flattened {len(moved)} items from [{folder_name}]\n']
    write_result(out_path, lines)
    print(f'Result: {out_path}')

# ============================================================
# 命令 5: dedup - 查找并移除重复书签
# ============================================================
def cmd_dedup(args):
    bp = backup('_before_dedup')
    print(f'Backup: {bp}')
    
    data = load()
    url_map = defaultdict(list)  # url -> [(path, item)]
    
    def collect_urls(items, path=''):
        for item in items:
            if item.get('type') == 'url':
                url_map[item['url']].append((path, copy.deepcopy(item)))
            elif item.get('type') == 'folder':
                collect_urls(item.get('children', []), path + '>' + item.get('name', ''))
    
    for rk, root in data['roots'].items():
        if isinstance(root, dict) and 'children' in root:
            collect_urls(root['children'], rk)
    
    # 找出重复的 URL
    dup_count = 0
    dup_pairs = []
    for url, entries in url_map.items():
        if len(entries) > 1:
            dup_count += len(entries) - 1
            dup_pairs.append((url, entries))
    
    if not dup_pairs:
        print('No duplicate bookmarks found.')
        return
    
    print(f'Found {len(dup_pairs)} URLs with duplicates ({dup_count} extra entries)')
    
    # Show top 20 duplicates
    dup_pairs.sort(key=lambda x: -len(x[1]))
    out_lines = [f'Duplicate bookmarks: {len(dup_pairs)} URLs, {dup_count} extra entries\n']
    for url, entries in dup_pairs[:20]:
        out_lines.append(f'URL: {url[:70]}')
        for path, item in entries:
            out_lines.append(f'  - {item["name"][:50]}  [{path}]')
        out_lines.append('')
    
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'dedup_result.txt')
    write_result(out_path, out_lines)
    print(f'Details: {out_path}')
    
    if args.dry_run:
        print('[DRY RUN] No changes made.')
        return
    
    # Actually remove duplicates (keep first occurrence)
    if not args.auto:
        r = input(f'Remove {dup_count} duplicate entries? (y/N): ')
        if r.lower() != 'y':
            print('Cancelled.')
            return
    
    # Remove duplicates: for each URL, keep the first occurrence
    keep_url = set()
    def dedup_pass(items):
        new_items = []
        removed_count = [0]
        for item in items:
            if item.get('type') == 'url':
                if item['url'] in keep_url:
                    removed_count[0] += 1
                    continue  # skip duplicate
                else:
                    keep_url.add(item['url'])
                    new_items.append(item)
            elif item.get('type') == 'folder':
                ic = copy.deepcopy(item)
                ic['children'] = dedup_pass(item.get('children', []))
                new_items.append(ic)
            else:
                new_items.append(item)
        return new_items, removed_count[0]
    
    total_removed = 0
    for rk in data['roots']:
        nc, cnt = dedup_pass(data['roots'][rk].get('children', []))
        data['roots'][rk]['children'] = nc
        total_removed += cnt
    
    save(data)
    print(f'Removed {total_removed} duplicate entries.')

# ============================================================
# 命令 6: check - 检测失效链接
# ============================================================
def cmd_check(args):
    data = load()
    all_bms = get_all_bookmarks(data)
    
    print(f'Checking {len(all_bms)} bookmarks (timeout={args.timeout}s each)...')
    print('This may take a while...')
    
    results = {'ok': 0, 'redirect': 0, 'client_error': 0, 'server_error': 0, 'timeout': 0, 'error': 0}
    broken = []
    
    for i, bm in enumerate(all_bms):
        url = bm['url']
        name = bm['name']
        
        try:
            req = urllib.request.Request(url, method='HEAD', headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0'
            })
            resp = urllib.request.urlopen(req, timeout=args.timeout)
            code = resp.getcode()
            if code is None or code < 400:
                results['ok'] += 1
            elif code in (301, 302, 303, 307, 308):
                results['redirect'] += 1
            elif 400 <= code < 500:
                results['client_error'] += 1
                broken.append((url, name, code, bm['parent_path']))
            else:
                results['server_error'] += 1
                broken.append((url, name, code, bm['parent_path']))
        except urllib.error.HTTPError as e:
            results['client_error' if 400 <= e.code < 500 else 'server_error'] += 1
            broken.append((url, name, e.code, bm['parent_path']))
        except (urllib.error.URLError, Exception) as e:
            if 'timed out' in str(e).lower() or 'timeout' in str(e).lower():
                results['timeout'] += 1
            else:
                results['error'] += 1
            broken.append((url, name, str(e)[:50], bm['parent_path']))
        
        if (i + 1) % 20 == 0:
            print(f'  Progress: {i+1}/{len(all_bms)} (ok:{results["ok"]} err:{results["client_error"]+results["server_error"]})')
    
    # Write result
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'check_result.txt')
    lines = [f'Link check results: {len(all_bms)} total\n']
    lines.append(f'OK: {results["ok"]}')
    lines.append(f'Redirect: {results["redirect"]}')
    lines.append(f'Client error (4xx): {results["client_error"]}')
    lines.append(f'Server error (5xx): {results["server_error"]}')
    lines.append(f'Timeout: {results["timeout"]}')
    lines.append(f'Other error: {results["error"]}')
    lines.append(f'\nBroken ({len(broken)} total):\n')
    
    for url, name, err, path in broken[:50]:
        lines.append(f'[{err}] {name[:50]}')
        lines.append(f'  URL: {url[:70]}')
        lines.append(f'  Path: {path}')
        lines.append('')
    
    write_result(out_path, lines)
    print(f'\nDone! Result: {out_path}')
    print(f'Broken links: {len(broken)}')

# ============================================================
# 命令 7: search - 搜索书签
# ============================================================
def cmd_search(args):
    data = load()
    keywords = args.keywords
    
    all_bms = get_all_bookmarks(data)
    matched = []
    for bm in all_bms:
        text = bm['name'] + ' ' + bm['url']
        if match_keywords(text, keywords):
            matched.append(bm)
    
    if not matched:
        print(f'No bookmarks matched: {keywords}')
        return
    
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'search_result.txt')
    lines = [f'Search results for [{", ".join(keywords)}]: {len(matched)} bookmarks\n']
    for bm in matched:
        lines.append(f'[{bm["parent_path"]}] {bm["name"]}')
        lines.append(f'  {bm["url"][:80]}')
        lines.append('')
    write_result(out_path, lines)
    print(f'Found {len(matched)} bookmarks -> {out_path}')

# ============================================================
# 命令 8: merge - 合并两个文件夹
# ============================================================
def cmd_merge(args):
    bp = backup('_before_merge')
    print(f'Backup: {bp}')
    
    folder_a = args.folder_a
    folder_b = args.folder_b
    target = args.target or folder_a
    
    data = load()
    bar = data['roots']['bookmark_bar']
    
    # Find folders
    src = None
    src_list = None
    for item in bar.get('children', []):
        if item.get('name') == folder_b and item.get('type') == 'folder':
            src = item
            break
    
    if src is None:
        print(f'Folder [{folder_b}] not found.')
        return
    
    # Find or create target
    tgt = None
    for item in bar.get('children', []):
        if item.get('name') == target and item.get('type') == 'folder':
            tgt = item
            break
    
    if tgt is None:
        # Rename src to target
        src['name'] = target
        print(f'Renamed [{folder_b}] to [{target}] (merged into itself)')
        save(data)
        return
    
    # Merge: add src children to tgt, deduplicate
    existing_urls = {c.get('url','') for c in tgt.get('children',[]) if c.get('type')=='url'}
    added = 0
    for item in src.get('children', []):
        if item.get('type') == 'url' and item['url'] not in existing_urls:
            tgt['children'].append(item)
            added += 1
    
    # Remove src folder if not keeping
    if not args.keep_source:
        new_bar = [item for item in bar.get('children', []) 
                   if not (item.get('name') == folder_b and item.get('type') == 'folder')]
        bar['children'] = new_bar
    
    save(data)
    print(f'Merged {added} bookmarks from [{folder_b}] into [{target}]')
    if not args.keep_source:
        print(f'Removed source folder [{folder_b}]')

# ============================================================
# 命令 9: sort - 排序文件夹内书签
# ============================================================
def cmd_sort(args):
    bp = backup('_before_sort')
    print(f'Backup: {bp}')
    
    folder_name = args.folder
    by = args.by  # name, url, date_added
    reverse = args.reverse
    
    data = load()
    bar = data['roots']['bookmark_bar']
    
    target = None
    for item in bar.get('children', []):
        if item.get('name') == folder_name and item.get('type') == 'folder':
            target = item
            break
    
    if target is None:
        print(f'Folder [{folder_name}] not found.')
        return
    
    children = target.get('children', [])
    
    def sort_key(item):
        if by == 'name':
            return item.get('name', '').lower()
        elif by == 'url':
            return item.get('url', '').lower()
        elif by == 'date_added':
            return item.get('date_added', '0')
        return ''
    
    children.sort(key=sort_key, reverse=reverse)
    target['children'] = children
    
    if not args.dry_run:
        save(data)
        print(f'Sorted [{folder_name}] by {by} (reverse={reverse})')
    else:
        print(f'[DRY RUN] Would sort [{folder_name}] by {by}')
    
    for item in children[:10]:
        if item.get('type') == 'url':
            print(f'  {item["name"][:50]}')

# ============================================================
# 命令 10: clean - 清理空文件夹
# ============================================================
def cmd_clean(args):
    bp = backup('_before_clean')
    print(f'Backup: {bp}')
    
    data = load()
    
    def clean_empty(items):
        new_items = []
        removed = [0]
        for item in items:
            if item.get('type') == 'folder':
                ic = copy.deepcopy(item)
                ic['children'] = clean_empty(item.get('children', []))
                if not ic['children']:
                    removed[0] += 1
                    print(f'  Removing empty folder: {ic["name"]}')
                else:
                    new_items.append(ic)
            else:
                new_items.append(item)
        return new_items, removed[0]
    
    total_removed = 0
    for rk in data['roots']:
        nc, cnt = clean_empty(data['roots'][rk].get('children', []))
        data['roots'][rk]['children'] = nc
        total_removed += cnt
    
    if total_removed == 0:
        print('No empty folders found.')
        return
    
    if args.dry_run:
        print(f'[DRY RUN] Would remove {total_removed} empty folders.')
        return
    
    save(data)
    print(f'Removed {total_removed} empty folders.')

# ============================================================
# 命令 11: stats - 统计信息
# ============================================================
def cmd_stats(args):
    data = load()
    all_bms = get_all_bookmarks(data)
    
    total = len(all_bms)
    by_root = Counter()
    domains = Counter()
    names = [bm['name'] for bm in all_bms]
    
    for bm in all_bms:
        # Parse root
        path = bm['parent_path']
        root = path.split('>')[0] if '>' in path else path
        by_root[root] += 1
        
        # Parse domain
        try:
            parsed = urllib.parse.urlparse(bm['url'])
            if parsed.netloc:
                domains[parsed.netloc] += 1
        except:
            pass
    
    lines = [f'Bookmark Statistics\n{"="*40}']
    lines.append(f'Total bookmarks: {total}')
    lines.append(f'\n--- By root ---')
    for root, cnt in by_root.most_common():
        lines.append(f'  {root}: {cnt}')
    
    lines.append(f'\n--- Top domains ---')
    for domain, cnt in domains.most_common(20):
        lines.append(f'  {domain}: {cnt}')
    
    lines.append(f'\n--- Name length ---')
    lines.append(f'  Shortest: {min((len(n) for n in names), default=0)} chars')
    lines.append(f'  Longest:  {max((len(n) for n in names), default=0)} chars')
    lines.append(f'  Average:  {sum(len(n) for n in names)//max(len(names),1)} chars')
    
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'bookmark_stats.txt')
    write_result(out_path, lines)
    print(f'Stats -> {out_path}')

# ============================================================
# 命令 12: export - 导出为 HTML
# ============================================================
def cmd_export(args):
    data = load()
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'bookmarks_export.html')
    
    def render_html(items, indent=0):
        lines = []
        for item in items:
            sp = '  ' * indent
            if item.get('type') == 'url':
                url = item.get('url', '')
                name = item.get('name', '')
                dt = int(item.get('date_added', '0')) // 1000000 - 11644473600  # WebKit epoch -> Unix
                date_str = datetime.utcfromtimestamp(dt).strftime('%Y-%m-%d') if dt > 0 else ''
                lines.append(f'{sp}<DT><A HREF="{url}" ADD_DATE="{date_str}">{name}</A>')
            elif item.get('type') == 'folder':
                lines.append(f'{sp}<DT><H3>{item.get("name","")}</H3>')
                lines.append(f'{sp}<DL><p>')
                lines.extend(render_html(item.get('children', []), indent+1))
                lines.append(f'{sp}</DL><p>')
        return lines
    
    html_lines = [
        '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        '<TITLE>Bookmarks</TITLE>',
        '<H1>Bookmarks</H1>',
        '<DL><p>',
    ]
    
    for rk in ['bookmark_bar', 'other', 'synced']:
        root = data['roots'].get(rk, {})
        children = root.get('children', [])
        if children:
            html_lines.append(f'  <DT><H3>{rk}</H3>')
            html_lines.append('  <DL><p>')
            html_lines.extend(render_html(children, 2))
            html_lines.append('  </DL><p>')
    
    html_lines.append('</DL><p>')
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_lines))
    
    print(f'Exported {len(get_all_bookmarks(data))} bookmarks -> {out_path}')
    print(f'You can import this file in Chrome: chrome://bookmarks/ -> Import')

# ============================================================
# 命令 13: domain - 按域名分组
# ============================================================
def cmd_domain(args):
    data = load()
    all_bms = get_all_bookmarks(data)
    
    domains = defaultdict(list)
    for bm in all_bms:
        try:
            parsed = urllib.parse.urlparse(bm['url'])
            domain = parsed.netloc or 'unknown'
            domains[domain].append(bm)
        except:
            domains['unknown'].append(bm)
    
    out_path = args.output or os.path.join(os.path.expanduser('~'), 'Desktop', 'bookmark_domains.txt')
    lines = [f'Bookmarks by domain: {len(domains)} domains, {len(all_bms)} total\n']
    
    for domain, bms in sorted(domains.items(), key=lambda x: -len(x[1])):
        lines.append(f'{domain}: {len(bms)}')
        if args.verbose:
            for bm in bms[:5]:
                lines.append(f'  - {bm["name"][:50]}')
            if len(bms) > 5:
                lines.append(f'  ... and {len(bms)-5} more')
        lines.append('')
    
    write_result(out_path, lines)
    print(f'Domain grouping -> {out_path}')

# ============================================================
# CLI 入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Chrome Bookmark Organizer v2.0')
    sub = parser.add_subparsers(dest='cmd')
    
    # scan
    p = sub.add_parser('scan', help='Scan all bookmarks')
    p.add_argument('-o', '--output', default=None)
    p.add_argument('--stats', action='store_true')
    
    # categorize
    p = sub.add_parser('categorize', help='Categorize bookmarks by rules')
    p.add_argument('-r', '--rules', required=True)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('-o', '--output', default=None)
    
    # move
    p = sub.add_parser('move', help='Move matching bookmarks to folder')
    p.add_argument('-f', '--folder', required=True)
    p.add_argument('-k', '--keywords', nargs='+', required=True)
    p.add_argument('--root-only', action='store_true')
    
    # flatten
    p = sub.add_parser('flatten', help='Flatten folder to root')
    p.add_argument('-f', '--folder', required=True)
    p.add_argument('--keep-folder', action='store_true')
    
    # dedup
    p = sub.add_parser('dedup', help='Find and remove duplicate bookmarks')
    p.add_argument('-o', '--output', default=None)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--auto', action='store_true')
    
    # check
    p = sub.add_parser('check', help='Check for broken links')
    p.add_argument('-o', '--output', default=None)
    p.add_argument('--timeout', type=int, default=5)
    
    # search
    p = sub.add_parser('search', help='Search bookmarks by keyword')
    p.add_argument('-k', '--keywords', nargs='+', required=True)
    p.add_argument('-o', '--output', default=None)
    
    # merge
    p = sub.add_parser('merge', help='Merge two folders')
    p.add_argument('-a', '--folder-a', required=True)
    p.add_argument('-b', '--folder-b', required=True)
    p.add_argument('-t', '--target', default=None)
    p.add_argument('--keep-source', action='store_true')
    
    # sort
    p = sub.add_parser('sort', help='Sort bookmarks in a folder')
    p.add_argument('-f', '--folder', required=True)
    p.add_argument('--by', choices=['name','url','date_added'], default='name')
    p.add_argument('--reverse', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    
    # clean
    p = sub.add_parser('clean', help='Remove empty folders')
    p.add_argument('--dry-run', action='store_true')
    
    # stats
    p = sub.add_parser('stats', help='Show bookmark statistics')
    p.add_argument('-o', '--output', default=None)
    
    # export
    p = sub.add_parser('export', help='Export bookmarks to HTML')
    p.add_argument('-o', '--output', default=None)
    
    # domain
    p = sub.add_parser('domain', help='Group bookmarks by domain')
    p.add_argument('-o', '--output', default=None)
    p.add_argument('-v', '--verbose', action='store_true')
    
    args = parser.parse_args()
    
    if not args.cmd:
        parser.print_help()
        sys.exit(1)
    
    # Chrome running check
    if os.name == 'nt':
        import subprocess
        result = subprocess.run('tasklist /FI "IMAGENAME eq chrome.exe" /NH', shell=True, capture_output=True)
        if b'chrome.exe' in result.stdout.lower():
            print('WARNING: Chrome is still running!')
            print('Please close Chrome first: taskkill /F /IM chrome.exe')
            r = input('Continue anyway? (y/N): ')
            if r.lower() != 'y':
                sys.exit(1)
    
    cmds = {
        'scan': cmd_scan, 'categorize': cmd_categorize, 'move': cmd_move,
        'flatten': cmd_flatten, 'dedup': cmd_dedup, 'check': cmd_check,
        'search': cmd_search, 'merge': cmd_merge, 'sort': cmd_sort,
        'clean': cmd_clean, 'stats': cmd_stats, 'export': cmd_export,
        'domain': cmd_domain,
    }
    
    if args.cmd in cmds:
        cmds[args.cmd](args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
