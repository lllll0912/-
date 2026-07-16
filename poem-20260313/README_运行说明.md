# （已弃用）旧版 Flask + MySQL 运行说明

> **请改用新版静态站**：见同目录 [`README.md`](README.md)。  
> 公开访问请部署到 Render：见 [`部署到Render.md`](部署到Render.md)。  
> 本地预览：双击 `预览本地.bat`。

以下内容仅保留作历史参考（依赖本机 MySQL，无法给外人点链接访问）。

---

## 旧技术栈

- 后端: Python Flask + MySQL
- 端口: 8765
- 入口: `app.py`、`public/`

启动（旧）：

```bash
bash scripts/server_start.sh
# 或
PYTHONPATH=. python app.py
```
