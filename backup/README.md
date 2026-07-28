# backup（隐私 · 不进 Git）

| 场景 | 落点 |
|------|------|
| 本机 `run.bat` | **直接**写到项目根 `backup/`，**保留历史**（不删旧的 `records_backup_*`） |
| 正式站（Fly） | 服务器 `/data/backup/`；浏览器侧栏 **绑定本机 backup** 后自动**追加**写入你选的文件夹 |
| 未绑定 / 不支持的浏览器 | 侧栏「导出备份」或提示里的「仍下载 zip」 |

| 内容 | 说明 |
|------|------|
| `records_backup_*` | 账单 + 类型字典 + 旅游打标的一套导出 |
| `原始账单/` | 历年 xlsx/docx 等原始归档 |

**第一次用正式站**：侧栏点「绑定本机 backup」→ 选中本项目里的 `backup` 文件夹。

**按线上字典做本地开发**：正式站导出/同步备份后执行  
`.\.venv\Scripts\python.exe tools\sync_rules_from_backup.py`  
或 `deploy\fly\拉取线上类型字典.ps1`。
