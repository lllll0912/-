## 项目运行与服务说明（poem-20260313）

### 1. 技术栈与入口

- **后端**: Python 3.7 + Flask
- **数据库**: MySQL (`teacher_db`)
- **主要入口文件**: `app.py`
- **静态页面**: `public/index.html` + `public/main.js`

### 2. 服务端口与进程

- 默认端口：**8765**
  - 在 `app.py` 里固定为：
    - `PORT` 环境变量未设置：端口为 `8765`
    - 如需改端口，可在启动前导出 `PORT`，例如 `PORT=9000`
- 进程类型：`python3` / `python3.7` 运行 `app.py`

你可以通过下面任一方式确认服务：

```bash
# 查看本项目服务当前状态（推荐）
bash scripts/server_status.sh

# 或根据端口查询（不依赖脚本）
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

### 3. 标准启动 / 停止 / 状态查看

在项目根目录 `poem-20260313` 下：

- **启动服务**

```bash
bash scripts/server_start.sh
```

浏览器访问：

```text
http://127.0.0.1:8765
```

- **停止服务**

```bash
bash scripts/server_stop.sh
```

- **查看服务是否在运行以及对应端口 / PID**

```bash
bash scripts/server_status.sh
```

### 4. 不通过脚本手动操作（标准方式）

- 前台启动（调试用）：

```bash
PYTHONPATH=. python3 app.py
```

在该终端按 `Ctrl + C` 即可停止服务。

- 后台 / 端口 + PID 方式：

```bash
# 查询 8765 端口对应的进程
lsof -nP -iTCP:8765 -sTCP:LISTEN

# 根据输出中的 PID 杀进程，例如 PID=12038
kill 12038        # 正常结束
kill -9 12038     # 如未结束则强制结束
```

