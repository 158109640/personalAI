FROM python:3.12-slim

# 容器内的工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制后端 requirements.txt 到容器内的 /app/backend/
COPY backend/requirements.txt ./backend/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制整个后端代码到容器内的 /app/backend/
COPY backend/ ./backend/

# 设置工作目录为 /app/backend（这样 uvicorn 就能找到 app.main）
WORKDIR /app/backend

# 创建数据目录
RUN mkdir -p ./uploads ./vector_stores ./chroma_db

EXPOSE 8000

# 启动命令（此时在 /app/backend 目录下）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]