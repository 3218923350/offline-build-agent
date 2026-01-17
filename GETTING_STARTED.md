# 离线构建 Agent - 快速使用指南

## 1分钟快速开始

```bash
cd offline-build-agent
cp env.example .env
# 编辑 .env 填入 API Keys
./deploy.sh
```

## 三种使用方式

### 方式1: CLI 工具（快速测试）

```bash
# 安装
pip install -e .

# 使用
offline-build --input examples/example_tools.json --output ./output

# 查看结果
cat ./output/final_report.txt
```

### 方式2: Python 库（编程集成）

```python
from offline_builder import build_tool_offline, ToolInput
from openai import OpenAI
from pathlib import Path

# 初始化模型
model_a = OpenAI(api_key="...")
model_b = OpenAI(api_key="...")

# 准备工具
tool = ToolInput(
    tool_name="numpy",
    dockerfile="FROM ubuntu:20.04\n...",
    usage_entry_command="python -c 'import numpy'"
)

# 构建
result = build_tool_offline(
    tool_input=tool,
    model_a_client=model_a,
    model_a_name="gpt-4o",
    model_b_client=model_b,
    model_b_name="gemini-2.0-flash-exp",
    output_dir=Path("./output")
)

print(f"成功: {result.success}")
print(f"原因: {result.final_reason}")
```

### 方式3: API 服务（生产部署）

```bash
# Docker Compose 部署
docker-compose up -d

# 提交任务
curl -X POST http://localhost:8000/api/v1/build \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "numpy",
    "dockerfile": "FROM ubuntu:20.04\n...",
    "usage_entry_command": "python -c \"import numpy\""
  }'

# 查询状态
curl http://localhost:8000/api/v1/tasks/{task_id}

# 下载脚本
curl -O http://localhost:8000/api/v1/tasks/{task_id}/scripts
```

## 输入格式

`tools.json`:
```json
[
  {
    "tool_name": "numpy",
    "tool_id": "tool_001",
    "dockerfile": "FROM ubuntu:20.04\nRUN apt-get update...",
    "usage_entry_command": "python3 -c 'import numpy'"
  }
]
```

## 输出结果

```
output/
└── numpy/
    ├── 00_fetch_and_build_online.sh   # 在线下载脚本
    ├── 01_build_offline.sh            # 离线编译脚本
    ├── build.log                      # 完整日志
    └── summary.json                   # 结果摘要
```

## 文档导航

- 📖 [完整文档](README.md) - 详细功能说明
- 🏗️ [架构设计](ARCHITECTURE.md) - 项目结构和模块
- 🚀 [部署指南](DEPLOYMENT.md) - 生产部署方案
- 📡 [API 文档](docs/API.md) - RESTful API 使用
- 💡 [快速开始](docs/QUICK_START.md) - 更多示例
- 📝 [开发总结](docs/OFFLINE_BUILD_SUMMARY.md) - 设计思路

## 常见问题

**Q: 网络命名空间是什么？**
A: 用于创建完全无网环境，确保脚本真正离线可用

**Q: 为什么需要特权模式？**
A: 创建网络命名空间需要 NET_ADMIN 权限

**Q: 支持哪些语言的工具？**
A: Python、C/C++、Go 等，只要能用 Dockerfile 构建

**Q: 失败了怎么办？**
A: 查看 `build.log` 详细日志，检查 `summary.json` 失败类型

**Q: 如何优化提示词？**
A: 编辑 `offline_builder/llm.py` 中的提示词模板

## 下一步

1. ✅ 测试示例工具
2. ✅ 准备实际工具配置
3. ✅ 部署到生产环境
4. ✅ 监控和优化

## 联系支持

- 📧 Email: support@example.com
- 💬 Issues: GitHub Issues
- 📚 Wiki: Project Wiki

