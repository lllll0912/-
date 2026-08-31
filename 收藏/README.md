# 收藏

私人收藏（作品 / 人物 + 图片）。

## 目录

```text
收藏/
  collection/     # Flask 功能包
  数据/
    _meta/catalog.json
    pics/<番号或人名>/
```

## 图片存放（与医疗日历同一逻辑）

| 环境 | 行为 |
|------|------|
| **本机** | 写入 `收藏/数据/pics/`，你再 `git push` |
| **正式站** | Volume 仅短时缓存 → 立刻用 `HEALTH_GITHUB_TOKEN` commit 进私密 GitHub；读图时缓存未命中再按需从 GitHub 拉取 |

**不要**把大量图片打进 Fly 镜像或长期堆在 Volume（已由 `.dockerignore` 排除 `收藏/数据/pics/`）。

## 相对旧项目的改动

- 去掉 MySQL / FastAPI，改用 JSON catalog
- 仅所有者 / 获分享授权者可见
- 图片按条目分文件夹；正式站与医疗共用 GitHub token

## 访问

- 本机：http://127.0.0.1:8501/collection/
- 正式站：所有者登录后侧栏进入

## 上线

改代码后：`git push origin main` → GitHub Actions 自动 `fly deploy`（不要本机飞大包）。
