# data（隐私 · 不进 Git）

本机运行时数据目录：

| 路径 | 说明 |
|------|------|
| `bills.db` | 账单 SQLite |
| `notes.db` / `notes_assets/` | 笔记与配图 |
| `water_data.json` | 喝水记录与设置 |
| `category_rules.json` | 类型字典（本地副本） |
| `health/` | 健康档案：检验单/中药方等原件 + `_meta/catalog.json` |
| `health/_meta/purposes.json` | 看病目的标签字典 |
| `health/_meta/watchlist.json` | 关注指标清单（OCR 前） |

Fly 上对应 Volume：`BILL_DATA_DIR=/data`。

健康档案源目录在桌面 `医疗/档案/`；网站读的是 `data/health/` 副本。改目的标签会写回本机 catalog。
