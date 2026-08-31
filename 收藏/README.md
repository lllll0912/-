# 收藏

从桌面 `teachersql-20260312` 迁入的私人收藏（作品 / 人物 + 图片）。

## 目录

```text
收藏/
  collection/     # Flask 功能包
  数据/
    _meta/catalog.json
    pics/<番号或人名>/
```

## 相对旧项目的改动

- 去掉 MySQL / FastAPI，改用 JSON catalog（与医疗模块同一套路）
- 仅所有者可见；挂在个人站侧栏「收藏」
- 图片仍按条目分文件夹；改番号/人名会自动迁移目录
- 本机无 MySQL 时，已从原 `pics/` 目录重建作品列表（人物需自行补录）

## 访问

- 本机：http://127.0.0.1:8501/collection/
- 正式站：所有者登录后侧栏进入
