# 每日一诗

公开网页版：每晚一句诗，任何人点开链接即可浏览。  
推荐托管：**Netlify** 或 **Render**（`*.netlify.app` / `*.onrender.com`），国内多数网络无需 VPN。

## 在线访问

**公网链接：** https://warm-tiramisu-0bfbb8.netlify.app/

**GitHub 仓库：** https://github.com/lllll0912/daily-poem

## 诗境功能

诗句下方有 **「诗境」** 按钮，可进入：

- 出处
- 全诗
- 创作背景
- 解读
- 意在何处

故事数据在 `stories.json`，构建时写入 `poems.json`。目前已为前 3 句写好示例，其余逐步补充。

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

在 `stories.json` 按诗句 `id` 填写：

```json
{
  "1": {
    "source": "宋 · 蒋捷《视夜》",
    "full_poem": "全诗正文",
    "background": "时代与创作环境",
    "interpretation": "解读",
    "meaning": "要表达什么"
  }
}
```

保存 → `python scripts/build_poems_json.py` → `同步并推送daily-poem.bat`（或 Netlify 重新部署）。
