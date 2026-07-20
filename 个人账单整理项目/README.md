# 个人账单整理

本地全功能账单工具 + 公网**演示站**（假数据）+ **本机隧道外网访问**（真实账单，密码保护）。

## 怎么用

### 本机使用（真实数据，免密）

1. 双击 **`run.bat`**
2. 打开 http://127.0.0.1:8501  

数据在 `data/bills.db`（SQLite，无需 MySQL）。

---

### 外网访问真实账单（当前推荐 · 不用绑信用卡）

原理：电脑开着跑账单程序 + Cloudflare 免费隧道生成公网链接 + 密码登录。

**条件：** 电脑开机联网；可锁屏/熄屏；不要睡眠/关机。关掉启动窗口 = 外网失效。

#### 第一次

1. 双击 **`install_cloudflared.bat`**（装隧道工具；若已装可跳过）
2. 双击 **`start_public.bat`**
   - 会生成 `.env` 并打开记事本：把 **密码** 改成你自己的，保存关闭
   - **再双击一次** `start_public.bat`
3. 窗口里会出现类似：`https://xxxx.trycloudflare.com`
4. 手机用**流量**打开该链接 → 输入密码 → 即可维护真实账单

（`启动外网访问.bat` / `安装隧道工具.bat` 与上面英文名是同一套，任选其一即可。）

#### 以后每次要外网用

双击 **`start_public.bat`**，把窗口里新的 https 链接发到手机即可。

> 临时隧道每次启动链接可能变化。以后有信用卡换 Fly 后，可以固定一个网址、电脑关机也能开。

---

### 公网演示站（假数据，Netlify）

仓库：https://github.com/lllll0912/bill-demo  
仅展示效果，**不是**你的真实账单。

本地预览演示：`预览演示站.bat` → http://127.0.0.1:8502  

---

### 以后：换到 Fly.io（需信用卡）

有卡后再做。配置已留在 `Dockerfile` / `fly.toml`。概要：

```powershell
fly auth login
# 改 fly.toml 的 app 名后：
fly apps create …
fly volumes create bill_data --region nrt --size 1
fly secrets set BILL_ACCESS_PASSWORD="…" BILL_SECRET_KEY="…" BILL_COOKIE_SECURE=1
fly deploy
```

并把本机 `data/bills.db` 迁到云上 `/data/bills.db`。换 Fly 后可不再开本机隧道。

---

## 环境变量（`.env`）

| 变量 | 说明 |
|------|------|
| `BILL_ACCESS_PASSWORD` | 访问密码（外网必填） |
| `BILL_SECRET_KEY` | 会话密钥 |
| `BILL_COOKIE_SECURE` | HTTPS 时设 `1`（隧道/Fly 都用 1） |

---

## 功能摘要

导入清洗、记录、分析、旅游打标、类型字典、离线报告；设密码后全站需登录。

---

## 隐私

- 演示站：假数据  
- 隧道方案：数据仍在你电脑的 `data/bills.db`，经 Cloudflare 中转加密访问  
- 勿把 `data/`、`.env`、个人账单文件提交到 Git  

---

## 变更历史

| 时间 | 内容 |
|------|------|
| 2026-03 | Flask 账单工具（多轮至 r10） |
| 2026-07-20 | SQLite；演示站；密码登录；**本机 Cloudflare 隧道外网**；预留 Fly 配置 |
