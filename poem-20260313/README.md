# 每日一诗

公开网页：每晚一句诗，可点「诗境」看出处、全诗、背景与解读。

## 怎么用网站

| 方式 | 地址 / 操作 |
|------|-------------|
| **线上** | https://warm-tiramisu-0bfbb8.netlify.app/ |
| **本地预览** | 双击 `预览本地.bat`，浏览器打开 http://127.0.0.1:8765 |
| **源码仓库** | https://github.com/lllll0912/daily-poem |

日常：

1. 在 `poem.txt` 按日期加诗句  
2. （可选）在 `stories.json` 人工改某条故事；不改也行，发布时会自动补缺失故事  
3. 告诉我更新，或运行：  
   `powershell -ExecutionPolicy Bypass -File scripts\publish_to_github.ps1`  
   → 自动补故事 → 构建 → 推送到 GitHub → Netlify 自动上线  

Netlify 需已连接仓库 `daily-poem`，Build settings：**Branch=`main`，其余留空**。

## 目录（只保留在用的）

```text
poem-20260313/
├── README.md                 ← 本说明（唯一文档）
├── poem.txt                  ← 诗库原文
├── stories.json              ← 诗境故事（可自动生成）
├── requirements.txt
├── .env.example              ← 可选大模型 Key 模板
├── 预览本地.bat
├── site/                     ← 静态站（本地与构建产物）
├── scripts/
│   ├── build_poems_json.py   ← poem.txt + stories → site/poems.json
│   ├── generate_stories.py   ← 自动补故事
│   ├── poetry_fetch.py       ← 诗词检索 API
│   ├── story_llm.py          ← 大模型解读（可选）
│   └── publish_to_github.ps1 ← 一键发布
└── deploy-repo/              ← 推送到 daily-poem 的发布副本（勿手改）
```

可选：复制 `.env.example` 为 `.env`，填 DeepSeek 等 API Key，故事解读会更细。

## 变更历史

| 时间 | 内容 |
|------|------|
| 2026-03 | 初版：Flask + MySQL，本地每日推诗（已废弃） |
| 2026-07-15 | 改为**纯静态站**；从 `poem.txt` 生成 `poems.json`；按日期算法每日一诗 |
| 2026-07-16 | 上线 **Netlify**（`warm-tiramisu-0bfbb8.netlify.app`）；独立仓库 `daily-poem`；Render 因绑卡放弃 |
| 2026-07-16 | 增加「诗境」：出处 / 全诗 / 背景 / 解读 / 意在何处 |
| 2026-07-16 | 故事自动生成：诗词 API + 可选大模型；批量补全约 220+ 条 |
| 2026-07-20 | 清理目录：删除 Flask/MySQL/Node 遗留与多余文档，只保留本 README |
