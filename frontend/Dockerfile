# frontend/Dockerfile
FROM node:22-alpine as builder

WORKDIR /app

# 先复制 package.json（利用 Docker 缓存）
COPY package*.json ./

# 安装依赖
RUN npm install --registry=https://registry.npmmirror.com

# 再复制源码（node_modules 已被 .dockerignore 排除）
COPY . .

# 构建
RUN npm run build

# 生产阶段
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]