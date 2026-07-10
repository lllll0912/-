# 飞猪MCP

通过 [FlyAI](https://flyai.open.fliggy.com/) 调用飞猪 MCP 服务，完成机票、酒店、门票、火车、景点等查询，并自动生成 Markdown 旅行攻略。

**无需 API Key 即可试用**；如需更稳定的结果，可配置 `FLYAI_API_KEY`。

## 快速开始

### 1. 安装 Node.js

本机需先安装 [Node.js LTS](https://nodejs.org/)。安装后在终端执行 `node -v` 确认可用。

### 2. 安装 FlyAI CLI

双击 **`scripts\安装依赖.bat`**，或在项目目录执行：

```bash
npm install
```

也可全局安装：`npm i -g @fly-ai/flyai-cli`

### 3. 探测连接

```bash
python main.py probe
```

### 4. 生成攻略

```bash
python main.py guide 杭州 3 --origin 上海 --budget 2000 --print
```

攻略保存在 `output/` 目录。

## 交互菜单

双击 **`run.bat`**，按提示选择功能。

## 命令一览

| 命令 | 说明 | 示例 |
|------|------|------|
| `probe` | 探测 CLI 是否可用 | `python main.py probe` |
| `ai` | AI 语义搜索（行程规划） | `python main.py ai "五一去杭州玩三天"` |
| `keyword` | 关键词综合搜索 | `python main.py keyword "杭州三日游"` |
| `hotel` | 酒店搜索 | `python main.py hotel 杭州 --poi 西湖` |
| `flight` | 航班搜索 | `python main.py flight 北京 上海 --dep-date 2026-05-01` |
| `train` | 火车搜索 | `python main.py train 北京 上海` |
| `poi` | 景点搜索 | `python main.py poi 杭州 --keyword 西湖` |
| `guide` | 综合攻略生成 | `python main.py guide 三亚 5 --budget 3000` |

## 在 Cursor 里接入 FlyAI Skill

在 Cursor 终端执行（需已安装 Node.js）：

```bash
npx skills add alibaba-flyai/flyai-skill
```

之后可直接在对话里让 Agent 查机票、酒店、做行程规划。

## 可选配置

```bash
flyai config set FLYAI_API_KEY "your-key"
```

## 项目结构

```
飞猪MCP/
├── main.py           # 命令行入口
├── flyai_client.py   # FlyAI CLI 封装
├── guide_builder.py  # 攻略生成
├── package.json      # flyai-cli 依赖
├── run.bat           # 交互菜单
├── scripts/          # 安装脚本
├── examples/         # 示例查询
├── output/           # 生成的攻略（不上传 Git）
└── docs/             # 命令参考
```

## 相关链接

- 开放平台：https://flyai.open.fliggy.com/
- Skill 仓库：https://github.com/alibaba-flyai/flyai-skill
- CLI 包：`@fly-ai/flyai-cli`

## 常见问题

**Windows 下出现 `Assertion failed: UV_HANDLE_CLOSING`**

这是 Node.js 在 Windows 上偶发的退出告警，一般**不影响 JSON 结果**。若命令末尾显示「攻略已保存」或 `[OK] FlyAI 连接正常`，说明查询已成功。
