# deploy

部署辅助（日常优先 `git push` 自动部署）。

## 铁律：推上线 ≠ 覆盖线上数据

| 动作 | 影响 |
|------|------|
| `git push` → GitHub Actions → `fly deploy` | **只换应用代码**（镜像）；`/data` Volume **原样保留** |
| 正式站导入账单 / 改字典 / 改旅游 / 写笔记 | 写在 Volume，开发期间照常用，上线后还在 |
| 本机 `data/` | 仅本地调试用，**不会**随 git 上云 |

Volume 上持久数据：`bills.db`、`category_rules.json`、`notes.db`(+assets)、`poems/`、`water_data.json`、`backup/`。

种子文件（`modules/bills/category_rules.json`、`poems_data/` 等）**仅在 Volume 对应文件不存在时拷贝一次**，已有数据绝不覆盖。

## 脚本

| 路径 | 说明 |
|------|------|
| `fly/重新部署.ps1` | 手动 fly deploy 备用 |
| `fly/拉取线上数据到本机.ps1` | **推荐**：线上 → 本机（对齐开发，不改云端） |
| `fly/拉取线上类型字典.ps1` | 只拉类型字典 |
| `fly/同步数据库.ps1` | ⚠ 应急：本机库**盖掉**线上账单（需输入 YES） |
| `fly/同步喝水数据.ps1` | ⚠ 应急：本机喝水**盖掉**线上（需输入 YES） |
| `fly/配置GitHub自动部署.bat` | 配置 `FLY_API_TOKEN` |
| `Procfile` | 备用进程声明（Docker 已用 gunicorn） |

根目录的 `Dockerfile` / `fly.toml` 才是 Fly 构建入口（`[mounts]` → `/data`）。
