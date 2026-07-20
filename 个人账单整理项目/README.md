# 个人账单整理

云端维护真实账单（密码保护）+ 本地改代码推 GitHub → Fly 自动部署。

| | 地址 / 做法 |
|--|--|
| **正式网站（数据在这）** | https://bill-private-lllll0912.fly.dev |
| **改代码上线** | 本地改完 → `git push origin main` → GitHub Action 自动 `fly deploy` |
| **本机调试（可选）** | 双击 `run.bat` → http://127.0.0.1:8501（一般不必同步云端数据） |

---

## 本地 / GitHub / Fly 各自职责（务必按这个理解）

| 角色 | 负责什么 | 不负责什么 |
|------|----------|------------|
| **本地电脑** | 改代码、跑测试、`git push`；可选本机调试 UI | **不是**正式账单库；日常不必更新 `data/bills.db` |
| **GitHub** | **代码唯一来源**（版本历史）；触发自动部署 | **不存**真实账单、`.env`、密码 |
| **Fly 云端** | **正式程序 + 正式数据库**（`/data/bills.db`）；你日常导入/编辑都在这 | 不自动把账单写回 GitHub |

```text
你改代码（本地）──push──► GitHub ──Action──► Fly 更新界面/程序
你改账单（浏览器）──────────────────────────► Fly /data/bills.db
你点「导出备份」──下载 zip──► 你的电脑（建议解压到本仓库 backup/）
```

---

## 目录大纲（随改动维护）

```text
个人账单整理项目/
├── README.md
├── requirements.txt / .env.example
├── run.bat / run.sh              ← 本机可选调试
├── Dockerfile / fly.toml         ← Fly 构建（根目录）
├── app.py / auth.py / …          ← 核心程序
├── db/                           ← SQLite 与备份逻辑
├── templates/
├── tests/
├── data/                         ← 本机调试库（可空，不进 Git）
├── backup/                       ← 本地备份落点（不进 Git）；导出 zip 解压到此
├── 账单备份/                     ← 原始账单归档（不进 Git）
├── deploy/fly/                   ← 应急脚本（一般用 git push 即可）
│   ├── 重新部署.ps1              ← 手动 fly deploy 备用
│   └── 同步数据库.ps1            ← 仅应急：本机库盖到云端
└── tools/                        ← 恢复脚本等
```

仓库根目录另有：`.github/workflows/deploy-bill-fly.yml`（push 后自动部署）。

---

## 日常怎么用

### 维护账单（主路径）

1. 打开 https://bill-private-lllll0912.fly.dev 登录  
2. 导入 / 改记录 / 旅游 / 类型字典  
3. 定期点导航 **「导出备份」** → 浏览器下载 `records_backup_时间戳.zip`  
4. 把 zip **解压到本仓库 `个人账单整理项目/backup/`**（命名已与旧备份一致：csv/txt/types/travel）

云端还会在 Volume 的 `/data/backup/` 留一份同名文件（机器重建也不丢程序卷上的备份；你电脑上的 `backup/` 才是带回家的副本）。

### 改网站代码

1. 本地修改  
2. `git add` / `commit` / `push origin main`  
3. GitHub → Actions 里看 `Deploy bill app to Fly` 是否绿  
4. 刷新网站（冷启动可能多等几秒）

首次启用自动部署：双击 `deploy\fly\配置GitHub自动部署.bat`，把 `FLY_API_TOKEN` 填进 GitHub Secrets（做一次即可）。

### 本机调试（可选）

`run.bat`。数据用本机空库或自己导入即可，**不必**每次从云端拉库。

---

## 自动部署：配置 `FLY_API_TOKEN`（做一次）

1. 本机执行（已登录 flyctl 时）：

```powershell
flyctl tokens create deploy -a bill-private-lllll0912 -x 8760h
```

2. 打开 GitHub 仓库 `lllll0912/-` → **Settings → Secrets and variables → Actions → New repository secret**  
   - Name: `FLY_API_TOKEN`  
   - Value: 上一步输出的 token  

3. 之后每次 push 到 `main` 且改动了 `个人账单整理项目/**`，会自动部署。

也可在 Actions 页手动 **Run workflow**。

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `BILL_ACCESS_PASSWORD` | 访问密码（Fly secrets + 本机 `.env`） |
| `BILL_SECRET_KEY` | 会话密钥 |
| `BILL_COOKIE_SECURE` | HTTPS 用 `1` |
| `BILL_DATA_DIR` | Fly 上为 `/data`（库在 `/data/bills.db`，备份在 `/data/backup`） |

---

## 隐私

- 真实账单只在 Fly Volume + 你导出的本地 `backup/`  
- 勿把 `data/`、`backup/`、`.env`、个人账单文件提交 GitHub  
- 仓库建议保持 **Private**  

---

## 变更历史

| 时间 | 内容 |
|------|------|
| 2026-03 | Flask 账单工具至 r10（原 MySQL） |
| 2026-07-20 | SQLite；密码登录 r11；Fly 上线；从 CSV 恢复 5712 条；修旅游页 SQL |
| 2026-07-20 | 目录整理；**去掉隧道与演示站**；**GitHub Action → Fly 自动部署**；导航 **导出备份**；版本 **r12** |
| 2026-07-20 | **界面 r13**：深色侧边栏、毛玻璃顶栏、统一组件样式与登录页 |
