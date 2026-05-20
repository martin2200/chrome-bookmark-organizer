# Chrome Bookmark Organizer

Chrome 书签整理 Agent Skill — 让 AI 助手帮你整理 Chrome 书签。

## 功能

| 操作 | 说明 |
|------|------|
| **扫描** | 导出全部书签为 JSON，方便预览和规则设计 |
| **分类** | 按关键词规则将书签自动归类到文件夹 |
| **移动** | 将匹配指定 URL 关键词的书签移入目标文件夹 |
| **展开** | 将文件夹内的书签提升到根目录，删除空文件夹 |
| **去重** | 自动合并 URL 完全相同的重复书签 |

## 安装

将本仓库克隆到你的 skill 目录：

```bash
# WorkBuddy / CodeBuddy
git clone https://github.com/martin2200/chrome-bookmark-organizer.git ~/.workbuddy/skills/chrome-bookmark-organizer/

# OpenClaw
git clone https://github.com/martin2200/chrome-bookmark-organizer.git ~/.qclaw/skills/chrome-bookmark-organizer/
```

## 使用方式

直接在对话中告诉 AI 你想做什么，例如：

- "帮我整理 Chrome 书签，把带 'quantclass' 的都移到『量化学习』文件夹"
- "把『chatgpt』文件夹里的书签全部展开到根目录"
- "按关键词分类书签：AI 相关的放『AI工具』，财经相关的放『财经』"

## 注意事项

- 操作前 AI 会自动关闭 Chrome 进程（防止文件锁）
- 每次操作会自动备份 `Bookmarks` 文件，路径：`Bookmarks.bak_YYYYMMDD_HHMMSS`
- 建议操作前关闭 Chrome 书签云端同步，避免修改被覆盖

## 要求

- Python 3.8+
- Windows（书签路径默认 `~/AppData/Local/Google/Chrome/User Data/Default/Bookmarks`）

## 提交市场

- ClawHub: https://clawhub.ai
- SkillHub: https://lightmake.site
