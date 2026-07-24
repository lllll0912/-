# 喝水模块（网站版）

今日打卡、目标进度、设置、近 30 日历史。

**网页小窗**：顶栏或喝水页点「打开网页小窗」→ 浏览器弹出独立小窗（`/water/widget`），倒计时/打卡均走本站会话。

可选：仓库根 `启动喝水小窗.bat` 仍可启动本机 Tk（系统级置顶），与网站共用 `data/water_data.json`。

## 目录

```text
modules/water/
├── README.md
├── blueprint.py
├── store.py
└── schedule_util.py
```

## 数据

- 本地：`data/water_data.json`（含原桌面版迁入的历史）
- Fly：`/data/water_data.json`
