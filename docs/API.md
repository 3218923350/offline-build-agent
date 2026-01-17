# 离线构建 Agent API 使用文档

## API 端点

### 1. 健康检查

```bash
GET /health
```

响应：
```json
{
  "status": "healthy"
}
```

### 2. 提交构建任务

```bash
POST /api/v1/build
Content-Type: application/json

{
  "tool_name": "numpy",
  "dockerfile": "FROM ubuntu:20.04\nRUN apt-get update...",
  "usage_entry_command": "python -c 'import numpy'",
  "tool_id": "optional-id",
  "model_a": "gpt-4o",
  "model_b": "gemini-2.0-flash-exp",
  "max_debate_rounds": 10,
  "max_execution_attempts": 10
}
```

响应：
```json
{
  "task_id": "uuid-here",
  "status": "pending",
  "tool_name": "numpy",
  "progress": null,
  "result": null,
  "error": null
}
```

### 3. 批量提交任务

```bash
POST /api/v1/build/batch
Content-Type: application/json

{
  "tools": [
    {
      "tool_name": "numpy",
      "dockerfile": "...",
      "usage_entry_command": "..."
    },
    ...
  ]
}
```

### 4. 查询任务状态

```bash
GET /api/v1/tasks/{task_id}
```

响应：
```json
{
  "task_id": "uuid",
  "status": "completed",
  "tool_name": "numpy",
  "progress": "构建完成",
  "result": {
    "success": true,
    "debate_rounds": 3,
    "execution_attempts": 1,
    "failure_type": "",
    "final_reason": "成功！"
  },
  "error": null
}
```

### 5. 下载日志

```bash
GET /api/v1/tasks/{task_id}/logs
```

返回文本文件

### 6. 下载脚本

```bash
GET /api/v1/tasks/{task_id}/scripts
```

返回 tar.gz 压缩包，包含：
- `00_fetch_and_build_online.sh`
- `01_build_offline.sh`
- `build.log`
- `summary.json`

### 7. 列出所有任务

```bash
GET /api/v1/tasks
```

## 使用示例

### Python 客户端

```python
import requests

# 提交任务
response = requests.post(
    "http://localhost:8000/api/v1/build",
    json={
        "tool_name": "numpy",
        "dockerfile": "FROM ubuntu:20.04...",
        "usage_entry_command": "python -c 'import numpy'"
    }
)
task_id = response.json()["task_id"]

# 轮询状态
import time
while True:
    status_resp = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}")
    status = status_resp.json()
    print(f"Status: {status['status']}")
    
    if status["status"] in ["completed", "failed"]:
        break
    
    time.sleep(10)

# 下载脚本
if status["status"] == "completed":
    scripts = requests.get(f"http://localhost:8000/api/v1/tasks/{task_id}/scripts")
    with open(f"{task_id}_scripts.tar.gz", "wb") as f:
        f.write(scripts.content)
```

### curl 示例

```bash
# 提交任务
TASK_ID=$(curl -X POST http://localhost:8000/api/v1/build \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "numpy",
    "dockerfile": "FROM ubuntu:20.04\nRUN apt-get update && apt-get install -y python3-pip\nRUN pip3 install numpy",
    "usage_entry_command": "python3 -c \"import numpy; print(numpy.__version__)\""
  }' | jq -r '.task_id')

# 查询状态
curl http://localhost:8000/api/v1/tasks/$TASK_ID

# 下载脚本
curl -O http://localhost:8000/api/v1/tasks/$TASK_ID/scripts
```

## 部署

### Docker Compose（推荐）

```bash
# 1. 配置环境变量
cp env.example .env
# 编辑 .env 填入 API Keys

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止服务
docker-compose down
```

### 直接运行

```bash
# 1. 安装依赖
pip install -r requirements.txt -r requirements-api.txt
pip install -e .

# 2. 配置环境变量
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...

# 3. 创建网络命名空间
sudo ip netns add offline

# 4. 启动服务
uvicorn offline_builder.api:app --host 0.0.0.0 --port 8000
```

## 注意事项

1. **网络命名空间**：需要 root 权限创建
2. **Docker 特权模式**：容器需要 `--privileged` 或 `--cap-add=NET_ADMIN`
3. **磁盘空间**：每个任务可能需要几GB空间
4. **执行时间**：任务可能需要数小时
5. **并发**：默认使用后台任务，支持多任务并发

