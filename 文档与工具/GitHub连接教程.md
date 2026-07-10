# GitHub 连接教程（Cursor + 你自己的 GitHub）

> **重要：** 下面三件事是 **完全分开** 的，不要混为一谈：
>
> | 是什么 | 作用 | 你该用谁的 |
> |--------|------|------------|
> | **Cursor 账号** | 用 AI、订阅等 | 可以是别人的（你现在的情况） |
> | **GitHub 账号** | 存代码、备份 | **必须是你自己的** |
> | **Windows 登录名**（白木等） | 电脑开机 | 和 GitHub 无关 |

**结论：用别人的 Cursor 完全没问题，代码可以推到你自己名下的 GitHub。**

本文件夹里的 3 个项目已放在一个 Git 仓库里：

- `喝水提醒/`
- `个人账单整理项目/`
- `poem-20260313/`

---

## 特别说明：别人的 Cursor + 自己的 GitHub

Cursor 登录和 GitHub 登录是 **两套系统**：

- 别人借你 Cursor → 只影响谁能用这台电脑上的 AI
- 推代码到 GitHub → 只看 **Git 登录时用的 GitHub 账号**，与 Cursor 账号无关

### 推荐做法（最不容易搞错）

**用终端 + 浏览器登录你自己的 GitHub**，不依赖 Cursor 里已登录的 GitHub：

1. 在本仓库终端设置 **你的** 提交身份：
   ```bash
   git config user.name "你的GitHub用户名"
   git config user.email "你的GitHub邮箱"
   ```
2. 在 https://github.com/new 用 **你的账号** 建私有空仓库
3. 连接并推送（改掉用户名和仓库名）：
   ```bash
   git remote add origin https://github.com/你的用户名/仓库名.git
   git branch -M main
   git push -u origin main
   ```
4. 弹出浏览器时 → 登录 **你的 GitHub** → 授权

这样即使用的是别人的 Cursor，代码也会进 **你的** GitHub 仓库。

### 若 Cursor 里已登录了别人的 GitHub

1. 左下角 **头像** → **Accounts / 账户**
2. 找到 **GitHub** 一行 → 点 **Sign out**（退出别人的）
3. 再点 **Sign in to GitHub** → 浏览器里登录 **你自己的** 账号

或不管 Cursor 里的 GitHub，只用上面「终端 push」方式即可。

### 若推送时仍上了别人的 GitHub

1. Win 搜索 **「凭据管理器」** → **Windows 凭据**
2. 删除所有 `git:https://github.com` 相关条目
3. 重新执行 `git push`，浏览器里登录 **你的** GitHub

---

## 方式一：在 Cursor 里操作（GitHub 已登录你自己的情况下）

### 第 1 步：打开本文件夹

菜单 **文件 → 打开文件夹** → 选择 `cursor暂存待上传到远程仓库`

### 第 2 步：设置 Git 提交身份（填你自己的 GitHub）

Cursor 需要知道「提交者是谁」，这里要填 **GitHub 账号信息**，不是 Windows 用户名，也不是 Cursor 账号。

1. `Ctrl + `` ` 打开终端，执行：

```bash
git config user.name "你的GitHub用户名"
git config user.email "你的GitHub邮箱"
```

示例（请改成你自己的）：

```bash
git config user.name "your-github-id"
git config user.email "your-email@example.com"
```

> 仅设置在本仓库，不会影响别的项目。  
> 邮箱可在 GitHub → Settings → Emails 查看。

### 第 3 步：在 GitHub 网站新建空仓库（用你的账号登录 github.com）

1. 打开 https://github.com/new
2. 用你的 GitHub 账号登录
3. 仓库名例如：`cursor-projects`（可自取）
4. 选择 **Private（私有）**（推荐，里面有个人项目代码）
5. **不要**勾选 “Add a README”
6. 点 **Create repository**

### 第 4 步：推送代码

**若左侧「源代码管理」显示「发布到 GitHub」：**

1. 点击左侧 **分支图标**（源代码管理，`Ctrl+Shift+G`）
2. 点 **发布到 GitHub（Publish to GitHub）**
3. 选择 **私有仓库**
4. 输入仓库名 → 确认

**若已有本地提交、需要连到刚建的仓库：**

1. `Ctrl + `` ` 打开终端
2. 执行（把 `你的用户名` 和 `仓库名` 换成你的）：

```bash
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
git push -u origin main
```

3. 若提示登录，选 **浏览器登录 GitHub**，用你自己的账号授权

### 第 5 步：以后每次改完代码怎么备份

在 Cursor 左侧 **源代码管理**：

1. 看到改动的文件 → 输入说明（如「更新喝水提醒」）
2. 点 **✓ 提交（Commit）**
3. 点 **↑ 同步更改（Sync / Push）**

或双击根目录 **`文档与工具\备份到GitHub.bat`**。

---

## 方式二：用脚本连接（不用 Cursor 界面时）

1. 先在 GitHub 网站建好空私有仓库（同上第 4 步）
2. 双击 **`文档与工具\备份到GitHub.bat`**
3. 输入 **你的 GitHub 用户名**（不是陈白木）
4. 输入仓库名
5. 按提示在浏览器登录 GitHub 并推送

---

## 常见问题

### 1. 推送时让我登录，登录的是谁？

必须是你 **自己的 GitHub 账号**。如果登错了：

- Windows：**设置 → 账户 → 电子邮件和账户** 里不要和 GitHub 混淆
- Git 凭据：搜索「凭据管理器」→ Windows 凭据 → 删除 `git:https://github.com` 相关项 → 重新 push 时再登录正确账号

### 2. Cursor 账号和 GitHub 账号有关系吗？

**没有。** 别人借你 Cursor 用 AI，不影响你把代码推到 **你自己的 GitHub**。  
关键是 `git push` 时浏览器登录的是 **你的 GitHub**。

### 3. Windows 用户名（白木 / 陈白木）和 GitHub 有关系吗？

没有。GitHub 上显示谁，取决于 `git config` 和 push 时登录的 GitHub 账号。

### 4. 哪些文件不会上传？

已在 `.gitignore` 排除，例如：

- 账单备份、`backup/` 目录
- `喝水提醒/data/` 饮水记录
- 大型个人 txt 导出

### 5. 代码里有数据库密码怎么办？

`connector.py` 里仍有本地数据库配置，**务必使用私有仓库**，不要公开分享。

---

## 推荐流程小结（别人的 Cursor + 自己的 GitHub）

```
1. 不用管 Cursor 是谁的账号
2. git config 填你自己的 GitHub 用户名和邮箱
3. 用你的账号在 github.com 建私有空仓库
4. 终端 git push → 浏览器登录你自己的 GitHub
5. 以后改完 → 提交 + push（代码始终进你的仓库）
```

如有报错，把终端或 Cursor 里的**完整错误信息**发出来，便于排查。

---

## 你的账号快捷配置（lllll0912）

本仓库已设置 Git 身份为 `lllll0912`。

**一键备份：** 双击 **`文档与工具\备份到GitHub.bat`**

或手动执行：

```bash
git remote add origin https://github.com/lllll0912/-.git
git branch -M main
git push -u origin main
```

仓库地址：https://github.com/lllll0912/-
