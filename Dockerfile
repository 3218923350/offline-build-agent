FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    sudo \
    curl \
    wget \
    git \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt requirements-api.txt ./
COPY offline_builder ./offline_builder/
COPY setup.py ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-api.txt \
    && pip install --no-cache-dir -e .

# 创建网络命名空间（需要特权模式）
# 注意：容器需要使用 --privileged 或 --cap-add=NET_ADMIN 运行

# 暴露 API 端口
EXPOSE 8000

# 默认命令：启动 API 服务
CMD ["python", "-m", "uvicorn", "offline_builder.api:app", "--host", "0.0.0.0", "--port", "8000"]

