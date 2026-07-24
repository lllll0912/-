# 个人网站

综合个人站：账单、生活日志、喝水、诗词。  
文档规范见 [`docs/开发说明.txt`](docs/开发说明.txt)：**README（本文件）** + **[`VERSION.md`](VERSION.md)**（需求/版本记录）。

| | |
|--|--|
| **正式站** | https://bill-private-lllll0912.fly.dev |
| **本机** | 双击 `run.bat` → http://127.0.0.1:8501 |
| **上线** | `git push origin main` → Actions 自动 Fly 部署 |
| **访问密码** | 环境变量 `BILL_ACCESS_PASSWORD`（本机见 `.env`，勿提交） |

---

## 根目录里有什么（只保留这些）

```text
README.md / VERSION.md     ← 双文档（用法 + 版本）
app.py / auth.py           ← 网站入口与登录
run.bat / run.sh           ← 本机启动网站
启动喝水小窗.bat             ← 桌面悬浮窗（与网站共用喝水数据）
requirements.txt / .env.example
Dockerfile / fly.toml      ← Fly 构建（必须在根）
modules/                   ← 业务模块（账单/诗词/喝水…）
templates/ / static/       ← 页面与样式
tools/                     ← 离线脚本（诗境补全等）
tests/                     ← 单元测试
deploy/                    ← 部署辅助脚本
docs/                      ← 开发说明与归档文档
legacy/                    ← 旧独立项目（不进侧边栏）
poems_data/                ← 诗库文本数据
data/ / backup/            ← 隐私运行数据（不进 Git）
.github/                   ← CI
```

其它文件不该长期堆在根目录；新增请按功能放进上表文件夹（见开发说明第 3 条）。

---

## 各目录干什么

| 目录 | 干什么 | 说明文档 |
|------|--------|----------|
| `modules/bills` | 账单库、导入、规则、报表 | [README](modules/bills/README.md) |
| `modules/poems` | 诗词增删改与数据读写 | [README](modules/poems/README.md) |
| `modules/water` | 网站喝水打卡 | [README](modules/water/README.md) |
| `modules/travel` | 旅游说明（页在账单下） | [README](modules/travel/README.md) |
| `templates` | Jinja 页面 | [README](templates/README.md) |
| `static` | CSS 等静态资源 | [README](static/README.md) |
| `tools` | 命令行维护脚本 | [README](tools/README.md) |
| `tests` | 测试 | [README](tests/README.md) |
| `deploy` | 手动部署/同步库 | [README](deploy/README.md) |
| `docs` | 开发说明、归档 MD | [README](docs/README.md) |
| `legacy` | 桌面喝水、飞猪、旧诗站等 | [README](legacy/README.md) |
| `data` | 本机 SQLite / 喝水 JSON | [README](data/README.md) |
| `backup` | 导出备份与原始账单归档 | [README](backup/README.md) |
| `poems_data` | 诗句与诗境 JSON | [README](poems_data/README.md) |

侧边栏：账单财务 · 生活日常 · 诗意 · 数据与账户。

---

## 配置参数（最新）

| 变量 | 用途 | 备注 |
|------|------|------|
| `BILL_ACCESS_PASSWORD` | 整站访问密码 | Fly secrets + 本地 `.env` |
| `BILL_SECRET_KEY` | Session 密钥 | 生产务必自定义 |
| `BILL_COOKIE_SECURE` | HTTPS Cookie | Fly=`1`；本机 HTTP=`0` |
| `BILL_DATA_DIR` | 数据根目录 | Fly=`/data` |
| `BILL_DB_PATH` | 可选，直接指定库文件 | 一般不用 |
| `POEM_ADMIN_PASSWORD` | 诗库维护密码 | 可回退到访问密码 |
| `POEM_LLM_*` | 诗境 LLM（可选） | 见 `.env.example`，勿提交密钥 |

复制 `.env.example` → `.env` 后改密码即可本机调试。

---

## 本地 / GitHub / Fly

| 角色 | 做什么 |
|------|--------|
| 本地 | 改代码、`run.bat`、push |
| GitHub | 代码版本；触发部署；**不存**真实账单 |
| Fly | 正式程序 + Volume（`bills.db`、`water_data.json` 等） |

版本与历次需求：[VERSION.md](VERSION.md)。
