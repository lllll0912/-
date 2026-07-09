# 本地项目合集

本仓库包含多个个人项目，通过 Git 同步到 GitHub 进行备份。

## 项目列表

| 目录 | 说明 |
|------|------|
| `喝水提醒/` | 定点喝水提醒桌面小工具 |
| `个人账单整理项目/` | 个人账单导入、分类与统计 |
| `poem-20260313/` | 诗词相关 Web 项目 |

## 首次连接 GitHub

1. 在 [GitHub 新建仓库](https://github.com/new)（建议 **Private 私有仓库**）
   - 不要勾选「Add a README」（本地已有代码）
2. 双击运行 **`connect_github.bat`**
3. 按提示输入 GitHub 用户名和仓库名
4. 浏览器登录授权后，代码会自动推送

## 日常备份（改完代码后）

在项目根目录执行：

```bash
git add .
git commit -m "描述你做了什么修改"
git push
```

或双击 **`sync_github.bat`** 一键提交并推送。

## 注意事项

- `backup/`、`账单备份/`、`喝水提醒/data/` 等个人数据已加入 `.gitignore`，**不会上传**
- 数据库密码请使用环境变量 `DB_PASSWORD`，建议使用 **私有仓库**
- 喝水提醒自动启动：见 `喝水提醒/install_autostart.bat`
