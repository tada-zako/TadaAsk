# uv 优化 python 镜像
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HOME=/tmp/tadaask \
    PATH="/app/.venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# 配置非 root 用户
RUN groupadd --system --gid 10001 tadaask \
    && useradd --system --uid 10001 --gid tadaask --home-dir /app tadaask \
    && mkdir -p /app/storages /tmp/tadaask \
    && chown -R tadaask:tadaask /app/storages /tmp/tadaask

USER tadaask

# 容器内部应用运行端口
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
    "--workers", "1", \
    "--no-proxy-headers"]
