# Media Trip RAG

> 🎬 基于 LangGraph + MCP 的智能多模态 Agent 系统，集成视频字幕生成、出行规划与 RAG 知识库检索于一体。

## ✨ 项目特性

- **智能对话** — 接入大语言模型，支持联网搜索（Tavily）与时间感知的 ReAct 工具调用
- **视频字幕生成** — Whisper 语音识别 → LLM 审校 → 自动修正 → FFmpeg 字幕硬烧，全流程自动化
- **出行规划** — 通过 MCP 协议接入高德地图、12306 等外部服务，智能规划旅行路线
- **RAG 知识库** — 支持上传 PDF / DOCX / TXT / HTML 等文档，自动切分、向量化并存入 ChromaDB，检索时融合 BM25 + 向量 + Reranking 精排
- **意图路由** — 基于 LangGraph 的条件分支工作流，自动识别用户意图并分发到对应 Agent
- **会话记忆** — MySQL 持久化历史 + LLM 摘要压缩的混合记忆管理

## 🏗️ 系统架构

```
┌──────────────┐     SSE     ┌──────────────────────────────────────────┐
│   Vue 3 前端  │ ◄────────► │            FastAPI 后端                    │
│  (Vite)      │            │                                          │
└──────────────┘            │  ┌──────────────────────────────────────┐ │
                            │  │        LangGraph Workflow             │ │
                            │  │                                      │ │
                            │  │  Intent ─┬─► Chat Agent              │ │
                            │  │  Router  ├─► Subtitle Workflow        │ │
                            │  │          ├─► Route Planner Agent      │ │
                            │  │          └─► RAG Pipeline            │ │
                            │  └──────────────────────────────────────┘ │
                            │                                          │
                            │  ┌─────────┐  ┌──────────┐  ┌─────────┐ │
                            │  │  MCP    │  │ ChromaDB │  │  MySQL  │ │
                            │  │ Server  │  │ 向量数据库 │  │ 历史存储 │ │
                            │  └─────────┘  └──────────┘  └─────────┘ │
                            └──────────────────────────────────────────┘
```

## 📁 项目结构

```
.
├── main.py                 # FastAPI 应用入口
├── config/
│   └── settings.py         # 统一配置管理（Pydantic Settings）
├── api/                    # API 路由层
│   ├── auth.py             # 用户认证
│   ├── workflow.py         # 工作流 SSE 推送
│   ├── rag.py              # 知识库文档管理
│   ├── history.py          # 对话历史
│   ├── files.py            # 文件管理
│   └── health.py           # 健康检查
├── agents/                 # 智能体模块
│   ├── base.py             # Agent 基类
│   ├── chat.py             # 对话 Agent（ReAct 工具调用）
│   ├── intent_recognizer.py# 意图识别 Agent
│   ├── route_plan.py       # 出行规划 Agent（高德 + 12306）
│   ├── reviewer.py         # 字幕审核 Agent
│   ├── rewriter.py         # 字幕改写 Agent
│   └── rag_generation.py   # RAG 检索增强生成
├── workflow/               # LangGraph 工作流
│   ├── graph.py            # 工作流图定义与节点实现
│   └── state.py            # 工作流状态定义
├── rag/                    # RAG 模块
│   ├── chroma_connector.py # ChromaDB 向量数据库连接器
│   ├── spliter.py          # 文档解析与切分
│   └── mymodels.py         # Embedding / Reranker 模型管理
├── mcp_server/             # MCP 工具服务器
│   └── server.py           # 字幕处理工具（Whisper、FFmpeg 等）
├── mcp_integration/        # MCP 客户端集成
│   ├── client.py           # MCP 连接管理
│   └── tool_adapter.py     # MCP 工具 → LangChain 工具适配器
├── core/                   # 核心工具
│   ├── llm_client.py       # LLM 客户端工厂
│   ├── logger.py           # 日志管理
│   ├── memory_manager.py   # 混合记忆管理器
│   ├── mysql_history.py    # MySQL 历史记录管理
│   └── whisper.py          # Whisper ASR 封装
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── views/          # 页面视图
│   │   ├── components/     # 组件
│   │   ├── stores/         # Pinia 状态管理
│   │   └── api/            # API 调用封装
│   └── package.json
└── data/                   # 数据目录（已 gitignore）
    ├── original_videos/    # 原始视频
    ├── final_videos/       # 合成后视频
    ├── original_srts/      # Whisper 生成的字幕
    ├── final_srts/         # 修正后的字幕
    ├── chroma_db/          # ChromaDB 持久化
    └── models/             # 本地模型缓存
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 5.7+ / 8.0+
- FFmpeg（需在系统 PATH 中）

### 1. 克隆项目

```bash
git clone https://github.com/<your-username>/media-trip-rag.git
cd media-trip-rag
```

### 2. 后端配置

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key 和数据库配置
```

### 3. 启动 MCP 工具服务器

```bash
python mcp_server/server.py
```

### 4. 启动后端

```bash
python main.py
# 后端运行在 http://localhost:8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:5173
```

## ⚙️ 环境变量

在项目根目录创建 `.env` 文件，参考 `.env.example`：

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | 通义千问 API Key |
| `DASHSCOPE_BASE_URL` | 通义千问 API 地址 |
| `DASHSCOPE_MODEL` | 使用的模型名称 |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | 使用的模型名称 |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |
| `LANGSMITH_API_KEY` | LangSmith 追踪 API Key |
| `LANGCHAIN_PROJECT` | LangSmith 项目名称 |
| `GAODE_URL` | 高德地图 MCP Server SSE 地址 |
| `T12306_URL` | 12306 MCP Server SSE 地址 |
| `MINERU_MODEL_DIR` | MinerU PDF 解析模型本地路径 |

## 🔧 技术栈

**后端**
- FastAPI + Uvicorn — 异步 Web 框架
- LangChain + LangGraph — LLM 编排与工作流引擎
- MCP (FastMCP) — 模型上下文协议工具集成
- ChromaDB — 向量数据库
- Whisper (faster-whisper) — 语音识别
- FFmpeg — 视频处理与字幕硬烧
- MySQL (PyMySQL) — 持久化存储
- Tavily — 联网搜索

**前端**
- Vue 3 + Vite
- Vue Router + Pinia
- Axios + Markdown 渲染 (marked)

**模型**
- 通义千问 (DashScope) — 主力 LLM
- DeepSeek — 辅助 LLM
- BGE-M3 — 文本向量模型
- BGE-Reranker-v2-M3 — 精排模型
- Whisper Large-v3 — 语音识别模型

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。
