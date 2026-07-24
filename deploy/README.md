# deploy

部署辅助（日常优先 `git push` 自动部署）。

| 路径 | 说明 |
|------|------|
| `fly/重新部署.ps1` | 手动 fly deploy 备用 |
| `fly/同步数据库.ps1` | 应急：本机库盖到云端 |
| `fly/配置GitHub自动部署.bat` | 配置 `FLY_API_TOKEN` |
| `Procfile` | 备用进程声明（Docker 已用 gunicorn） |

根目录的 `Dockerfile` / `fly.toml` 才是 Fly 构建入口。
