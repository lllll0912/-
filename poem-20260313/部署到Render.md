# 每日一诗 — 发布到 Render（约 3 分钟）

别人点开的链接来自 Render，不是 GitHub Pages，国内一般可直接打开。

## 步骤

1. **先把代码推到 GitHub**（若尚未推送）  
   可用 `文档与工具\备份到GitHub.bat`，或在 Cursor 里提交并同步。

2. 打开 Render 控制台：  
   https://dashboard.render.com/select-repo?type=blueprint  
   （没有账号可用 GitHub 登录注册，选免费档即可）

3. 授权 GitHub 后，选择仓库 **`lllll0912/-`**（或你的 monorepo 名）。

4. Render 会读取仓库根目录的 `render.yaml`，创建服务 **`daily-poem`**。  
   确认后点 **Apply**。

5. 等待 Build 变成 Live（约 1～2 分钟）。

6. 在服务页顶部复制网址，形如：  
   `https://daily-poem.onrender.com`  
   把这个链接发给别人即可。

## 手动创建（不用 Blueprint 时）

Dashboard → **New → Static Site** → 选同一仓库：

| 项 | 填什么 |
|----|--------|
| Name | `daily-poem` |
| Root Directory | `poem-20260313` |
| Build Command | `true` |
| Publish Directory | `site` |

## 改诗之后

```text
1. 改 poem.txt（或 stories.json）
2. 双击 预览本地.bat 旁：在项目里运行 python scripts\build_poems_json.py
3. 提交并 push → Render 自动重新部署
```
