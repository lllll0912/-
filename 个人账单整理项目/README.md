# 个人账单整理

本地全功能账单工具 + 公网**演示站**（假数据）。真实账单不会上传到演示站。

## 怎么用

### 本机完整版（真实数据）

1. 双击 **`run.bat`**
2. 浏览器打开 http://127.0.0.1:8501  
3. 导入 TXT/CSV/XLSX → 清洗分类 → 分析 / 旅游打标 / 类型字典  

数据文件：`data/bills.db`（SQLite，自动创建，**无需 MySQL**）

### 公网演示站

演示页只展示虚构样例，说明产品能力。  

部署后链接写在下方（Netlify / 与「每日一诗」同方式）：

```text
（首次部署后填写）
```

本地预览演示站：

```bash
cd site
python -m http.server 8502
```

打开 http://127.0.0.1:8502

---

## 功能摘要

| 模块 | 说明 |
|------|------|
| 导入清洗 | TXT/CSV/XLSX，自动分类（一级+二级），学习规则 |
| 记录 | 筛选、编辑、批量删除 |
| 分析 | 日历热力、类型-月汇总 |
| 旅游 | 按日期打标、同行人、统计 |
| 类型字典 | `category_rules.json` 可交互维护 |
| 离线报告 | 导航栏下载自包含 zip |

---

## 目录

```text
个人账单整理项目/
├── README.md              ← 本说明（唯一文档）
├── app.py                 ← Flask 主程序
├── run.bat / run.sh
├── requirements.txt
├── category_rules.json
├── parser.py / importers.py / rule_manager.py ...
├── db/                    ← SQLite 连接与仓库
├── templates/             ← 本机 Web UI
├── tests/
├── data/                  ← bills.db（本地，不上传）
├── backup/                ← 入库备份（不上传）
└── site/                  ← 公网演示静态页
```

---

## 隐私说明

- **公网站**：仅演示假数据  
- **本机站**：你的账单只在 `data/bills.db` 与本地备份  
- 仓库已忽略 `data/`、`backup/`、个人 `*.txt` 账单文件  

---

## 变更历史

| 时间 | 内容 |
|------|------|
| 2026-03 | Flask + MySQL 账单工具：导入、记录、分析、旅游、类型字典、离线报告（多轮迭代至 r10） |
| 2026-07-20 | 改为 **SQLite**（去掉本机 MySQL 与明文密码）；文档合并为唯一 README；增加公网演示静态站 `site/` |
