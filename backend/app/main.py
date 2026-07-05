from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, documents, auth # 👈 导入 chat 路由
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
  title="个人 AI 研发助理",
  description="一个集成了 RAG、Agent 和工具调用的 AI 助手",
  version="0.1.0"
)

# 配置 CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173"],  # Vue 默认端口
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# 👇 注册路由
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)

# ✅ 确保 uploads 目录存在
os.makedirs("uploads", exist_ok=True)

# ✅ 正确挂载静态文件
# 注意：目录路径是 "uploads"，访问路径是 "/uploads"
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def root():
  return {"message": "AI 研发助理 API 已启动", "status": "running"}
