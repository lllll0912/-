# tools

离线/运维脚本（一般不跑在网页请求里，诗境推荐等会按需 import）。

| 脚本 | 用途 |
|------|------|
| `poetry_fetch.py` | 公开诗库检索 |
| `enrich_poem_stories.py` | 批量补诗境 |
| `poem_intake.py` | 推荐/查诗逻辑 |
| `story_llm.py` | LLM 润色 |
| `restore_from_backup_csv.py` | 从备份 CSV 恢复库 |

在仓库根执行，例如：`python tools/enrich_poem_stories.py --help`
