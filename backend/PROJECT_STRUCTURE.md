# 个人 AI 研发助理 - 项目结构说明

本项目是一个基于 FastAPI 和 LangChain 的 AI Agent 应用，采用分层架构设计。

## 项目目录树
backend/
├── app/
│ ├── api/ # 接口层：接收 HTTP 请求
│ │ ├── init.py
│ │ ├── chat.py # 对话接口
│ │ └── documents.py # 文档上传/查询接口
│ ├── core/ # 核心配置层
│ │ ├── init.py
│ │ ├── config.py # 全局配置（从 .env 读取）
│ │ └── database.py # 数据库连接与会话管理
│ ├── models/ # 数据模型层：定义数据库表结构
│ │ ├── init.py
│ │ ├── user.py # 用户表
│ │ ├── document.py # 文档表
│ │ └── conversation.py # 对话与消息表
│ ├── services/ # 业务逻辑层：核心功能实现
│ │ ├── init.py
│ │ ├── ai_service.py # AI 对话服务（调用 LLM）
│ │ ├── agent_service.py # Agent 服务（工具调用编排）
│ │ ├── rag_service.py # RAG 服务（文档检索与问答）
│ │ ├── weather_service.py # 天气查询服务
│ │ └── search_service.py # 联网搜索服务
│ ├── tools/ # 工具层：可复用的功能模块
│ │ ├── init.py
│ │ ├── weather.py # 天气工具（同步包装）
│ │ └── search.py # 搜索工具（同步包装）
│ ├── utils/ # 通用工具函数
│ │ ├── init.py
│ │ └── helpers.py # 辅助函数
│ └── main.py # FastAPI 应用入口
├── tests/ # 单元测试
├── uploads/ # 用户上传的原始文件
├── vector_stores/ # FAISS 向量存储（RAG 数据）
├── venv/ # Python 虚拟环境
├── .env # 环境变量（不提交到 Git）
├── app.db # SQLite 数据库文件
├── requirements.txt # 项目依赖
└── run.py # 项目启动脚本

## 核心目录详解

### 1. API 层 (`app/api/`)

**作用**：接收 HTTP 请求，是项目的入口。

**调用关系**：
- 收到请求 → 解析参数 → 调用对应的 Service → 返回 JSON 响应

**示例：`chat.py`**
```python
@router.post("")
async def chat(request: ChatRequest):
    # 1. 管理会话
    # 2. 调用 agent_service.chat()
    # 3. 返回响应

## 调用流程图
┌─────────────┐
│   用户请求   │
└──────┬──────┘
       ↓
┌─────────────┐
│  API 层      │ ← 接收请求，解析参数
│ (chat.py)    │
└──────┬──────┘
       ↓
┌─────────────┐
│ Service 层   │ ← 编排业务逻辑
│(agent_service)│
└──────┬──────┘
       ↓
┌─────────────┐
│  Tools 层    │ ← 执行具体功能
│(weather/search)│
└──────┬──────┘
       ↓
┌─────────────┐
│  外部服务    │ ← 调用 API
│(高德/Tavily) │
└─────────────┘

## 如何添加新功能？
添加新路由：在 app/api/ 下新建文件，定义路由。
添加业务逻辑：在 app/services/ 下新建 Service。
添加工具：在 app/tools/ 下新建 Tool。
在 main.py 中注册路由。