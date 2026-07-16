# Netlify 连接 GitHub 自动部署 — 填写说明

站点：https://warm-tiramisu-0bfbb8.netlify.app/  
代码仓库：https://github.com/lllll0912/daily-poem

在 Netlify → **Project configuration** → **Build & deploy** → **Build settings** 里这样填：

| 项 | 填什么 |
|----|--------|
| **Branch to deploy** | `main` |
| **Base directory** | **留空** |
| **Build command** | **留空**（网站文件已在仓库里，不需要构建） |
| **Publish directory** | **留空** 或填 `.`（表示用仓库根目录） |
| **Functions directory** | 不用管，保持默认即可 |

点 **Save**，然后到 **Deploys** 点 **Trigger deploy → Deploy site** 手动触发一次。

之后：我改完代码并 push 到 `daily-poem` 的 `main` 分支，Netlify 会**自动**重新部署，你不用动手。

---

## 第一次连接 GitHub（若还没连）

1. Netlify → **Project configuration** → **Build & deploy** → **Continuous deployment** → **Link repository**
2. 选 **GitHub** → 仓库 **`lllll0912/daily-poem`**
3. 按上表填 Build settings → Save

若列表里没有 `daily-poem`：  
https://github.com/settings/installations → **Netlify** → Configure → 勾选 **daily-poem** → Save

---

## 和我（Cursor）的分工

- **你**：只在 Netlify 里按上面设置一次  
- **我**：每次改完诗句/诗境/页面后，自动 push 到 GitHub，Netlify 自己更新网站
