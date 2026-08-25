# 健康档案

## 功能

| 页面 | 说明 |
|------|------|
| `/health/calendar` | 医疗日历（页内上传 / 搜索 / 标注） |

类别：检验单、门诊单、用药（另保留中药方/体检/病史）。

## 数据与 GitHub（真相仓）

- 命名：`YYYY-MM-DD_名称_医院.ext`，路径如 `医疗/数据/01_本人_检验单/...`
- **本机上传**：写入仓库目录 → 你再 `git push`
- **正式站（手机）上传**：写入 GitHub（需 Fly secret `HEALTH_GITHUB_TOKEN`）+ Volume 缓存立刻可看
- 标注保存时也会把 `catalog.json` 同步进 GitHub

### 配置正式站写入 GitHub

1. GitHub → Settings → Developer settings → Personal access tokens  
   建 classic PAT，勾选 **`repo`**（私密仓读写）
2. 本机执行（把 `ghp_xxx` 换成你的 token）：

```bash
fly secrets set HEALTH_GITHUB_TOKEN=ghp_xxx -a bill-private-lllll0912
```

可选（一般不用改，代码里已有默认）：

- `HEALTH_GITHUB_REPO=lllll0912/-`
- `HEALTH_GITHUB_BRANCH=main`
