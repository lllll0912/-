# 每日一诗

公开网页版：每晚一句诗，任何人点开链接即可浏览。  
托管在 **Render 静态站**（`*.onrender.com`），国内多数网络无需 VPN。

## 在线访问

部署完成后，链接形如：

```text
https://daily-poem.onrender.com
```

（以你在 Render 后台看到的实际域名为准；部署后会写在下方「已发布链接」。）

**已发布链接：**

```text
（代码已推送到 GitHub；请双击「打开Render部署.bat」或按《部署到Render.md》完成首次创建，把得到的 https://….onrender.com 发回即可写入此处）
```

> 源码：https://github.com/lllll0912/-/tree/main/poem-20260313  
> 不用 GitHub Pages 作为主链接，避免国内访问不稳定。

> 不用 GitHub Pages 作为主链接，避免国内访问不稳定。

## 本地预览

双击 **`预览本地.bat`**，或：

```bash
python scripts/build_poems_json.py
cd site
python -m http.server 8765
```

浏览器打开：http://127.0.0.1:8765

## 日常更新

1. 编辑根目录 `poem.txt` 增加诗句  
2. （可选）在 `stories.json` 里用诗句 `id` 或全文作键，填写创作故事  
3. **必须**运行 `python scripts/build_poems_json.py`（更新 `site/poems.json`）  
4. 提交并 push 到 GitHub → Render 自动重新部署（约 1～2 分钟）

## 部署到 Render（第一次）

完整图文步骤见 **[`部署到Render.md`](部署到Render.md)**。摘要：

1. 打开 [Render Dashboard](https://dashboard.render.com) ，用 GitHub 登录  
2. **New → Blueprint**，选本仓库，应用根目录 `render.yaml`  
3. 等待 `daily-poem` 上线，复制 `https://….onrender.com` 链接分享  

手动创建时：Root Directory = `poem-20260313`，Build = `true`，Publish = `site`

## 目录说明

```text
poem-20260313/
├── poem.txt                 # 诗库原文
├── stories.json             # 可选：创作故事
├── scripts/build_poems_json.py
├── site/                    # 静态站（HTML/CSS/JS + poems.json）
├── render.yaml              # 子项目 Blueprint（备用）
├── 预览本地.bat
├── public/、app.py …        # 旧版 Flask/MySQL，已弃用
└── README_运行说明.md       # 旧版服务说明，仅供参考
```

## 每日如何自动换诗

前端根据当天日期做哈希，在诗库中选出固定一首：同一天、任何人打开都是同一句；换一天即换下一句。无需服务器定时任务。

## 后续：诗句背后的故事

在 `stories.json` 中例如：

```json
{
  "1": "相识那夜临睡发出的第一句。",
  "竹斋眠听雨，梦里长青苔": "也可用诗句全文作键。"
}
```

有内容时，页面会在诗句下显示「缘起」。
