---
name: chrome-bookmark-organizer
description: Chrome 书签整理与管理工具（完整版）。涵盖扫描、分类、移动、展开、去重、失效检测、搜索、合并、排序、清理、统计、导出等常用功能。触发词：整理书签、书签分类、书签管理、移动书签、合并书签、Chrome bookmarks、去重、失效链接检测、导出书签、搜索书签。
---

# Chrome 书签整理 Skill（完整版 v2.0）

## ⚠️ 铁律（每次操作前必须遵守）

1. **先杀 Chrome 再改文件** — `taskkill /F /IM chrome.exe`，确认无残留进程后再写入
2. **云端同步会覆盖本地修改** — 操作前提醒用户关闭 Chrome 书签同步
3. **结果写文件不要 print** — PowerShell GBK 编码会导致中文崩溃
4. **每次操作前必须备份** — 用带时间戳的文件名，不覆盖旧备份
5. **操作后给用户确认** — 展示分类结果，让用户检查是否有误匹配
6. **检查 Chrome 是否在运行** — 脚本内置检查，但 AI 仍应先确认

## 工具说明

统一工具 `scripts/bookmark_tool.py`，支持 **12 个子命令**：

| 命令 | 功能 | 常用参数 |
|------|------|----------|
| `scan` | 扫描所有书签 | `-o` 输出路径，支持按文件夹统计 |
| `categorize` | 按规则分类根目录书签 | `-r rules.json`，支持 `--dry-run` |
| `move` | 移动匹配书签到指定文件夹 | `-f 文件夹 -k 关键词`，支持 `--root-only` |
| `flatten` | 展开文件夹到根目录 | `-f 文件夹`，支持 `--keep-folder` |
| `dedup` | 查找并移除重复书签 | `--auto` 自动确认，`--dry-run` 预览 |
| `check` | 检测失效链接（HTTP 状态码） | `--timeout` 超时秒数 |
| `search` | 按关键词搜索书签 | `-k 关键词1 关键词2` |
| `merge` | 合并两个文件夹 | `-a 源文件夹 -b 目标文件夹`，支持 `--keep-source` |
| `sort` | 对文件夹内书签排序 | `-f 文件夹 --by name/url/date_added` |
| `clean` | 清理空文件夹 | `--dry-run` 预览 |
| `stats` | 显示书签统计信息 | 无额外参数 |
| `export` | 导出为 HTML（Netscape 格式） | `-o 输出路径` |
| `domain` | 按域名分组统计 | `-v` 显示详情 |

## 标准工作流

### Phase 0: 杀 Chrome
```powershell
taskkill /F /IM chrome.exe
Start-Sleep -Seconds 2
Get-Process chrome -ErrorAction SilentlyContinue
```

### Phase 1: 扫描现状
```bash
python scripts/bookmark_tool.py scan -o ~/Desktop/bm_scan.txt
python scripts/bookmark_tool.py stats -o ~/Desktop/bm_stats.txt
python scripts/bookmark_tool.py domain -v -o ~/Desktop/bm_domain.txt
```
读取结果文件，展示给用户，确认整理方向。

### Phase 2: 去重 + 清理（推荐先做）
```bash
# 查看重复书签
python scripts/bookmark_tool.py dedup --dry-run -o ~/Desktop/bm_dedup.txt

# 确认后执行
python scripts/bookmark_tool.py dedup --auto

# 清理空文件夹
python scripts/bookmark_tool.py clean --dry-run
python scripts/bookmark_tool.py clean
```

### Phase 3: 失效链接检测（可选）
```bash
python scripts/bookmark_tool.py check --timeout 5 -o ~/Desktop/bm_check.txt
```
读取结果，让用户决定是否删除失效书签。

### Phase 4: 分类整理
```bash
# 使用默认规则
python scripts/bookmark_tool.py categorize -r rules_default.json --dry-run
python scripts/bookmark_tool.py categorize -r rules_default.json

# 移动特定书签到文件夹
python scripts/bookmark_tool.py move -f "邢不行" -k "bbs.quantclass.cn"
```

### Phase 5: 验证 + 导出备份
```bash
python scripts/bookmark_tool.py scan -o ~/Desktop/bm_after.txt
python scripts/bookmark_tool.py export -o ~/Desktop/bookmarks_backup.html
```

## 各命令详解

### scan — 扫描书签
```bash
python scripts/bookmark_tool.py scan [-o output] [--stats]
```
- 递归扫描所有书签（含子文件夹）
- `--stats` 附加按文件夹统计
- 输出到文件，避免控制台编码问题

### categorize — 按规则分类
```bash
python scripts/bookmark_tool.py categorize -r rules.json [--dry-run] [-o output]
```
- 按 JSON 规则将根目录散落书签分类
- `--dry-run` 预览不写入
- 规则文件格式见 `rules_default.json`

### dedup — 去重
```bash
python scripts/bookmark_tool.py dedup [--dry-run] [--auto] [-o output]
```
- 全层级扫描，找出 URL 重复的书签
- 默认保留第一次出现的位置，移除后续重复项
- `--auto` 跳过确认直接执行

### check — 失效链接检测
```bash
python scripts/bookmark_tool.py check [--timeout 5] [-o output]
```
- 对每个书签发 HTTP HEAD 请求
- 标记 4xx/5xx/timeout 的书签
- 结果文件含完整错误信息，方便用户决定如何处理

### search — 搜索书签
```bash
python scripts/bookmark_tool.py search -k keyword1 keyword2 [-o output]
```
- 在书签名称和 URL 中搜索关键词
- 支持多关键词（OR 逻辑）

### merge — 合并文件夹
```bash
python scripts/bookmark_tool.py merge -a 源文件夹 -b 目标文件夹 [-t 重命名] [--keep-source]
```
- 将源文件夹内容合并到目标文件夹
- 自动去重（相同 URL 不重复添加）
- `--keep-source` 保留空源文件夹

### sort — 排序
```bash
python scripts/bookmark_tool.py sort -f 文件夹 --by name [--reverse]
```
- `by` 可选：`name`（名称）、`url`、`date_added`
- `--reverse` 倒序排列

### clean — 清理空文件夹
```bash
python scripts/bookmark_tool.py clean [--dry-run]
```
- 递归清理所有空文件夹
- `--dry-run` 预览要删除的文件夹

### stats — 统计
```bash
python scripts/bookmark_tool.py stats [-o output]
```
输出：总数、按 root 分布、Top 20 域名、名称长度统计。

### export — 导出 HTML
```bash
python scripts/bookmark_tool.py export [-o output.html]
```
- 导出为 Netscape Bookmark HTML 格式
- 可被 Chrome/Edge/Firefox 导入

### domain — 按域名分组
```bash
python scripts/bookmark_tool.py domain [-v] [-o output]
```
- 统计每个域名的书签数量
- `-v` 显示每个域名下的书签名称

## 分类规则设计原则

1. **精准词在前**（域名、专有名词），**宽泛词在后**（通用词汇）
2. **first match wins** — 一条书签只归一个文件夹
3. 最后一个 rule 应为兜底的 `{"folder":"其他","keywords":[]}`
4. 分类结果必须让用户确认后再写入

### rules.json 格式
```json
[
  {"folder": "文件夹名", "keywords": ["关键词1", "关键词2"]},
  {"folder": "其他", "keywords": []}
]
```

## 参考

- [Bookmarks JSON 结构速查](references/bookmarks-structure.md)
- [默认分类规则](rules_default.json)
