# 收藏

私人收藏（作品 / 人物 + 图片）。

## 目录

```text
收藏/
  collection/     # Flask 功能包（git push 推代码）
  数据/
    _meta/catalog.json      # 运行态，.gitignore，正式站 API 写入
    _meta/catalog.empty.json # 空 catalog 模板（进 Git，供新 clone）
    pics/<番号或人名>/       # 运行态，.gitignore
```

## 数据流（稳定后）

| 环境 | 写入 | git push |
|------|------|----------|
| **正式站** | Volume 缓存 → 立刻 `HEALTH_GITHUB_TOKEN` commit 进 GitHub | 只 deploy **代码** |
| **本机** | 写 `收藏/数据/` 做开发测试 | **不推** pics / catalog（已在 `.gitignore`） |

本机要与线上一致：双击 `脚本/工具/收藏-从GitHub同步本地数据.bat`。

已追踪的 pics/catalog 用 **skip-worktree** 屏蔽本地变更（远端文件保留）；换机可再跑 `脚本/工具/收藏-停止Git追踪本地数据.bat`。

**不要**把大量图片打进 Fly 镜像（Dockerfile 不 COPY pics）。

## 相对旧项目的改动

- 去掉 MySQL / FastAPI，改用 JSON catalog
- 仅所有者 / 获分享授权者可见
- 图片按条目分文件夹；正式站与医疗共用 GitHub token

## 访问

- 本机：http://127.0.0.1:8501/collection/
- 正式站：所有者登录后侧栏进入

## 上线

改代码后：`git push origin main` → GitHub Actions 自动 `fly deploy`（运行态数据由正式站写入 GitHub，勿本机推 pics）。
