# 每日一诗

公开网页版：每晚一句诗，任何人点开链接即可浏览。  
推荐托管：**Netlify** 或 **Render**（`*.netlify.app` / `*.onrender.com`），国内多数网络无需 VPN。

## 在线访问

**已发布链接：**

```text
（请用「换方式上线.bat」→ Netlify 拖拽；拿到链接后发我写入此处）
```

源码目录：`site/`（开发） · 独立发布包：`deploy-repo/`（拖拽上线用）

> 不用 GitHub Pages 作主链接。原 monorepo 仓库名是 `-`，Render 里经常选不到——见 [`选不到仓库时.md`](选不到仓库时.md)。

## 本地预览

双击 **`预览本地.bat`**，浏览器打开 http://127.0.0.1:8765

## 第一次上线（推荐）

双击 **`换方式上线.bat`**，选 **1 + 2**：

1. 打开 Netlify Drop  
2. 把 `deploy-repo` 文件夹拖进去  
3. 复制得到的链接分享即可  

详细说明：[`选不到仓库时.md`](选不到仓库时.md)

## 日常更新

1. 改 `poem.txt` 或 `stories.json`  
2. 运行 `python scripts/build_poems_json.py`  
3. 把新的 `site/*` 再复制到 `deploy-repo/`（或再拖一次到 Netlify）  
4. 若已接 Git 仓库：push 后自动重新部署  

## 目录说明

```text
poem-20260313/
├── poem.txt / stories.json
├── scripts/build_poems_json.py
├── site/                 # 开发用静态站
├── deploy-repo/          # 独立发布包（拖拽 / 单独仓库）
├── 换方式上线.bat
├── 预览本地.bat
└── 选不到仓库时.md
```

## 每日如何自动换诗

前端根据当天日期做哈希选诗：同一天所有人看到同一句。

## 后续：诗句背后的故事

在 `stories.json` 用 id 或诗句全文作键填写；有内容时页面显示「缘起」。
