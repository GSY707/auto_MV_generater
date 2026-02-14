# Auto MV Generator

基于 **Gemini + Suno + Veo** 的 AI 音乐 MV 自动生成系统。通过自然语言描述，自动完成从音乐创作到 MV 视频生成的全流程。

## ✨ 功能特性

- **AI 音乐生成** — 接入 Suno API，通过灵感模式或自定义模式生成歌曲
- **MV 视频生成** — 基于 Google Veo 自动生成配套 MV 视频
- **AI 封面生成** — 使用 Gemini Image 生成专辑封面
- **智能 Agent** — Gemini Function Calling 驱动的多步编排 Agent，自动协调各工具完成任务
- **Web 管理界面** — React 前端，支持任务管理、曲库浏览、MV 预览和 AI 对话
- **对话式交互** — 支持命令行交互模式和 Web 聊天两种方式

## 🏗️ 技术架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  React 前端  │────▶│  Flask API   │────▶│  Music Agent    │
│  (Vite)     │◀────│  (后端服务)   │◀────│  (Gemini FC)    │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                    ┌──────────────┼──────────────┐
                                    ▼              ▼              ▼
                              ┌──────────┐  ┌──────────┐  ┌──────────┐
                              │ Suno API │  │ Veo API  │  │ Gemini   │
                              │ (音乐)   │  │ (视频)   │  │ (图片)   │
                              └──────────┘  └──────────┘  └──────────┘
```

## 📦 项目结构

```
├── main.py                 # CLI 入口（交互式/单次模式）
├── api/                    # Flask 后端 API
│   ├── app.py              # 应用工厂
│   ├── routes/             # 路由（生成、任务、聊天、MV 等）
│   └── services/           # 业务逻辑（MV 管线、任务存储等）
├── src/                    # 核心逻辑
│   ├── agent/              # Gemini Agent（提示词 & 多步编排）
│   ├── clients/            # 外部 API 客户端（Gemini / Suno / Veo）
│   ├── tools/              # Agent 可调用的工具定义
│   ├── config.py           # 配置管理
│   └── logger.py           # 日志
├── frontend/               # React + Vite 前端
│   └── src/
│       ├── components/     # UI 组件
│       ├── pages/          # 页面（Dashboard / Library / Create / Chat）
│       └── context/        # 全局状态管理
├── output/                 # 生成产物输出目录
└── logs/                   # 运行日志
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm

### 1. 克隆项目

```bash
git clone https://github.com/GSY707/auto_MV_generater.git
cd auto_MV_generater
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：

| 变量 | 说明 |
|------|------|
| `GEMINI_BACKEND` | LLM 后端：`ai_studio` 或 `vertex_ai` |
| `GOOGLE_AI_STUDIO_KEY` | Google AI Studio API Key |
| `SUNO_API_KEY` | Suno 镜像站 API Key |
| `SUNO_BASE_URL` | Suno 镜像站地址 |
| `GEMINI_MODEL` | Gemini 模型（默认 `gemini-2.5-flash`） |
| `SUNO_MODEL` | Suno 模型（默认 `chirp-v5`） |

### 3. 安装依赖

```bash
# 后端
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 4. 启动服务

**方式一：分别启动**

```bash
# 终端 1 - 启动后端 API
python -m api.run

# 终端 2 - 启动前端
cd frontend
npm run dev
```

**方式二：使用脚本**

```bash
# Windows
start.bat
```

访问 http://localhost:5173 打开 Web 界面。

### 5. 命令行模式（可选）

```bash
# 交互式对话
python main.py

# 单次生成
python main.py --once "帮我创作一首关于夏天的流行歌曲"
```

## 📖 API 文档

后端 API 默认运行在 `http://localhost:5000`，主要接口：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/generate` | POST | 提交音乐生成任务 |
| `/api/tasks` | GET | 查询任务列表 |
| `/api/tasks/<id>` | GET | 查询单个任务详情 |
| `/api/chat` | POST | AI 对话 |
| `/api/mv` | POST | 生成 MV |

## 🔧 配置说明

支持通过环境变量或 `.env` 文件配置，完整配置项参见 `.env.example`。

主要配置分类：
- **LLM 配置** — Gemini 后端、模型、温度等
- **Suno 配置** — 镜像站地址和 API Key
- **Veo 配置** — 视频模型、分辨率、时长
- **Agent 配置** — 最大步数、输出 Token 限制

## 📄 许可证

本项目使用 [AGPL-3.0](LICENSE) 许可证。
