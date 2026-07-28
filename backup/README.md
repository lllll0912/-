# backup（隐私 · 不进 Git）

| 场景 | 落点 |
|------|------|
| 本机 `run.bat` | **直接**写到项目根 `backup/`，**保留历史** |
| 正式站（Fly） | 服务器 `/data/backup/`；绑定本机 backup 后自动追加写入 |
| 未绑定 | 侧栏「导出备份」下 zip |

每次备份一套（同一时间戳）大致包括：

| 文件 | 内容 |
|------|------|
| `records_backup_*.csv/.txt` | 账单记录 |
| `*_types.*` / `*_travel.*` | 类型字典、旅游汇总 |
| `*_water.json` | 喝水记录与设置 |
| `*_poems.json` | 诗词原文 / stories / poems.json |
| `*_notes.json` | 全部笔记 Markdown |
| `*_category_rules.json` | 类型字典原文件 |
| `*_notes_md_hints.json` | 笔记 Markdown 速查（若有） |
| `*_fulldata.zip` | **灾难恢复包**：bills.db、notes.db、图片、诗词目录、喝水、字典等原文件 |
| `*_manifest.json` | 本套文件清单 |

**第一次用正式站**：侧栏点「绑定本机 backup」→ 选项目里的 `backup` 文件夹。

按线上字典做本地开发：`tools\sync_rules_from_backup.py` 或 `deploy\fly\拉取线上类型字典.ps1`。
