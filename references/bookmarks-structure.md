# Chrome Bookmarks JSON 结构速查

## 文件位置
```
%LOCALAPPDATA%\Google\Chrome\User Data\Default\Bookmarks
```

## JSON 结构
```json
{
  "checksum": "...",
  "roots": {
    "bookmark_bar": {        // 书签栏（主要操作对象）
      "children": [
        { "type": "url", "name": "显示名称", "url": "https://...", "date_added": "...", "guid": "..." },
        { "type": "folder", "name": "文件夹名", "children": [...] }
      ]
    },
    "other": { "children": [] },     // 其他书签
    "synced": { "children": [] }     // 移动设备书签
  },
  "version": 1
}
```

## 注意事项
- `roots` 是 **dict** 不是 list，遍历用 `.values()` 或按 key 访问
- 写入时 `ensure_ascii=False`（中文不转义），`indent=2`
- `guid` 和 `id` 需唯一但 Chrome 不严格校验
- Chrome 时间戳是 WebKit epoch 微秒（1601-01-01 起）

## 书签栏根目录访问
```python
data['roots']['bookmark_bar']['children']  # 书签栏根目录子项列表
```

## 递归遍历所有书签
```python
def scan_all(items, path='', results=None):
    if results is None: results = []
    for item in items:
        if item.get('type') == 'url':
            results.append({'name': item['name'], 'url': item['url'], 'path': path})
        elif item.get('type') == 'folder':
            scan_all(item.get('children', []), path + '>' + item['name'], results)
    return results
```
