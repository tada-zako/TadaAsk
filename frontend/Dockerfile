FROM node:24-alpine AS build

# 前端环境默认变量设置
ARG VITE_API_BASE_URL=/api
ARG VITE_WIDGET_SCRIPT_URL=/widget/tada-ask-widget.js

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WIDGET_SCRIPT_URL=${VITE_WIDGET_SCRIPT_URL}

WORKDIR /app

# 启用 pnpm
RUN corepack enable \
    && corepack prepare pnpm@11.13.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# 打包构建前端
COPY . .
RUN pnpm run build

# 配置 Nginx
FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
