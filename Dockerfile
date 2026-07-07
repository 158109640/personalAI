FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（包括编译工具和常用库）
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制后端依赖文件
COPY backend/requirements.txt ./backend/

# 安装 Python 依赖（使用清华镜像加速）
RUN pip install --no-cache-dir -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 验证关键依赖是否安装成功
RUN python -c "import rank_bm25; print('rank_bm25 installed successfully')" || \
    (echo "rank_bm25 not installed, retrying..." && \
     pip install rank_bm25 -i https://pypi.tuna.tsinghua.edu.cn/simple)

# 复制整个后端代码
COPY backend/ ./backend/

# 创建工作目录
WORKDIR /app/backend

# 创建必要的数据目录
RUN mkdir -p ./uploads ./vector_stores ./chroma_db

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]