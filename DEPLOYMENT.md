# 离线构建 Agent - 部署指南

## 快速部署（推荐）

```bash
# 1. 配置环境变量
cp env.example .env
# 编辑 .env，填入 API Keys

# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
# 选择部署方式
```

## 部署方式对比

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| Docker Compose | 易部署、隔离性好、可扩展 | 需要 Docker | 生产环境 |
| 直接运行 | 简单、调试方便 | 依赖系统环境 | 开发测试 |
| Kubernetes | 高可用、自动扩展 | 复杂 | 大规模部署 |

## 方式1: Docker Compose（生产推荐）

### 前置要求
- Docker >= 20.10
- Docker Compose >= 2.0

### 部署步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd offline-build-agent

# 2. 配置环境变量
cp env.example .env
vi .env  # 填入 API Keys

# 3. 构建并启动
docker-compose up --build -d

# 4. 查看日志
docker-compose logs -f

# 5. 测试服务
curl http://localhost:8000/health

# 6. 停止服务
docker-compose down
```

### 配置说明

`docker-compose.yml` 关键配置：

```yaml
services:
  offline-build-api:
    privileged: true  # 必须：创建网络命名空间
    ports:
      - "8000:8000"   # API 端口
    volumes:
      - ./output:/app/output      # 输出目录持久化
      - ./workspace:/app/workspace  # 工作目录持久化
```

### 生产优化

```yaml
services:
  offline-build-api:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 16G
        reservations:
          cpus: '2'
          memory: 8G
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 方式2: 直接运行

### 前置要求
- Python >= 3.8
- pip
- sudo 权限（创建网络命名空间）

### 部署步骤

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt -r requirements-api.txt
pip install -e .

# 3. 配置环境变量
export OPENAI_API_KEY="your-key"
export GEMINI_API_KEY="your-key"

# 4. 创建网络命名空间
sudo ip netns add offline

# 5. 启动服务
python -m uvicorn offline_builder.api:app --host 0.0.0.0 --port 8000

# 或作为后台服务
nohup python -m uvicorn offline_builder.api:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
```

### 使用 systemd 管理

创建 `/etc/systemd/system/offline-build-agent.service`:

```ini
[Unit]
Description=Offline Build Agent API
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/offline-build-agent
Environment="PATH=/path/to/venv/bin"
EnvironmentFile=/path/to/offline-build-agent/.env
ExecStartPre=/usr/bin/sudo /usr/sbin/ip netns add offline
ExecStart=/path/to/venv/bin/python -m uvicorn offline_builder.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable offline-build-agent
sudo systemctl start offline-build-agent
sudo systemctl status offline-build-agent
```

## 方式3: Kubernetes（大规模）

### ConfigMap: 配置

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: offline-build-config
data:
  MAX_DEBATE_ROUNDS: "10"
  MAX_EXECUTION_ATTEMPTS: "10"
  WORK_DIR: "/app/workspace"
  OUTPUT_DIR: "/app/output"
```

### Secret: 敏感信息

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: offline-build-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  GEMINI_API_KEY: "..."
```

### Deployment: 部署

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: offline-build-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: offline-build-agent
  template:
    metadata:
      labels:
        app: offline-build-agent
    spec:
      containers:
      - name: api
        image: offline-build-agent:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: offline-build-config
        - secretRef:
            name: offline-build-secrets
        resources:
          limits:
            cpu: "4"
            memory: "16Gi"
          requests:
            cpu: "2"
            memory: "8Gi"
        volumeMounts:
        - name: output
          mountPath: /app/output
        - name: workspace
          mountPath: /app/workspace
        securityContext:
          privileged: true  # 必须：创建网络命名空间
      volumes:
      - name: output
        persistentVolumeClaim:
          claimName: offline-build-output
      - name: workspace
        emptyDir: {}
```

### Service: 服务

```yaml
apiVersion: v1
kind: Service
metadata:
  name: offline-build-agent
spec:
  selector:
    app: offline-build-agent
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### PVC: 持久化存储

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: offline-build-output
spec:
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: 1Ti
  storageClassName: standard
```

## 监控和日志

### Prometheus 监控

```yaml
# 添加到 Deployment
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### 日志收集

使用 Fluentd/Fluent Bit 收集日志：

```yaml
# DaemonSet 配置
```

## 故障排查

### 1. 网络命名空间创建失败

```bash
# 检查权限
sudo ip netns list

# 重新创建
sudo ip netns del offline
sudo ip netns add offline
```

### 2. Docker 容器无法创建网络命名空间

```bash
# 确保使用特权模式
docker run --privileged ...

# 或添加能力
docker run --cap-add=NET_ADMIN --cap-add=SYS_ADMIN ...
```

### 3. API 调用失败

```bash
# 检查环境变量
docker exec offline-build-agent env | grep API_KEY

# 检查日志
docker logs offline-build-agent
```

### 4. 磁盘空间不足

```bash
# 清理旧的构建产物
docker exec offline-build-agent find /app/output -type d -mtime +7 -exec rm -rf {} +

# 或手动清理
rm -rf ./output/old-tool-*
```

## 性能优化

### 1. 并发处理

修改 API 服务配置：

```bash
uvicorn offline_builder.api:app --workers 4 --host 0.0.0.0 --port 8000
```

### 2. 缓存策略

- 缓存常见依赖包
- 复用网络命名空间
- 共享基础镜像

### 3. 资源限制

```yaml
resources:
  limits:
    cpu: "4"
    memory: "16Gi"
  requests:
    cpu: "2"
    memory: "8Gi"
```

## 安全建议

1. **API 密钥安全**：使用 Secret 管理，不要硬编码
2. **网络隔离**：使用防火墙限制访问
3. **权限最小化**：只授予必要的权限
4. **定期更新**：及时更新依赖包
5. **审计日志**：记录所有 API 调用

## 扩展阅读

- [API 文档](docs/API.md)
- [架构说明](ARCHITECTURE.md)
- [快速开始](docs/QUICK_START.md)

