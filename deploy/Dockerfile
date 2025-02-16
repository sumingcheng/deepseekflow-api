# 构建阶段
FROM python:3.11-slim as builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  gcc \
  python3-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
  && rm -rf ~/.cache/pip/*

# 运行阶段
FROM python:3.11-slim

WORKDIR /app

# 设置 Python 环境
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

# 从构建阶段复制 Python 包
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/

# 复制应用文件
COPY config.py main.py ./

# 暴露端口 - 使用变量
EXPOSE ${PORT:-8080}

# 启动命令 - 使用环境变量
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
