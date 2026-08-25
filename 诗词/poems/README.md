# 诗词模块

职责：每日诗词展示、诗库维护、按风格推荐入库、手动查诗入库。

## 目录

```text
modules/poems/
├── README.md
└── poem_admin.py       ← 读写 poems_data、增删改

（站点根）
poems_data/             ← poem.txt / stories.json / poems.json
tools/                  ← poetry_fetch、enrich、poem_intake、story_llm…
```

## 页面

- `/poems` 展示
- `/poems/admin` 维护（二次密码）
- `/poems/new` 推荐 / 查诗 / 传统表单

## 数据

- 本地：`poems_data/`
- Fly：优先 `/data/poems/`（若设置了 `BILL_DATA_DIR`）
