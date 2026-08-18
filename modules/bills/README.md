# 账单财务模块

职责：账单导入清洗、SQLite 存储、分析看板、类型规则、旅游标签相关数据。

## 目录

```text
modules/bills/
├── README.md
├── db/                 ← SQLite connector / schema / repository / backup
├── importers.py
├── parser.py
├── rule_manager.py
├── category_rules.json
└── preview_store.py
```

页面路由仍在根目录 `app.py`（导入、记录、分析、类型、旅游、备份下载）。

## 数据

- 本地：`data/bills.db`（gitignore）
- Fly：`/data/bills.db`
- 规则：`category_rules.json`
- 备份：导航「导出备份」→ 解压到仓库根 `backup/`

## 启动

在仓库根执行 `run.bat`，侧边栏「账单财务」下进入各页。
