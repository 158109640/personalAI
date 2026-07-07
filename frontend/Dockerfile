# frontend/Dockerfile
FROM node:22-alpine as builder

WORKDIR /app

# 复制 package.json 并安装依赖（使用国内镜像加速）
COPY package*.json ./
RUN npm install -g cnpm --registry=https://registry.npmmirror.com && \
    cnpm install

# 复制源码并构建
COPY . .
RUN npm run build

# 生产阶段：使用 Nginx 托管
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]