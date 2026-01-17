# 🚀 离线构建 Agent (Offline Build Agent)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

将基于 Dockerfile 的工具智能转换为可在**完全离线环境**中编译和运行的 shell 脚本。

## ✨ 核心特性

- 🤖 **双模型辩论**：两个 AI 模型相互提案和评审，确保脚本质量
- 🔄 **智能身份交换**：意见不一致时自动交换角色，避免单一模型偏见
- ✅ **执行验证循环**：自动执行脚本并根据失败日志持续优化
- 🔒 **无网环境测试**：使用 Linux 网络命名空间确保真正离线
- 📊 **详细日志记录**：完整记录辩论过程和执行历史
- 🎯 **硬性约束检查**：确保生成的脚本满足离线环境要求

## 🎯 使用场景

适用于需要在**无网络环境**部署工具的场景：

- ✅ 气隙环境（Air-gapped）部署
- ✅ 内网隔离环境
- ✅ 高安全要求场景
- ✅ 边缘计算节点
- ✅ 科学计算集群

## 📦 快速开始

### 方式1: 快速部署（推荐）

```bash
# 1. 克隆项目
git clone <repo-url>
cd offline-build-agent

# 2. 配置环境
cp env.example .env
# 编辑 .env 填入 API Keys

# 3. 一键部署
chmod +x deploy.sh
./deploy.sh
```

### 方式2: Docker Compose

```bash
docker-compose up -d
curl http://localhost:8000/health
```

### 方式3: 命令行工具

```bash
pip install -e .
offline-build --input tools.json --output ./output
```

## 📝 输入输出

### 输入格式

```json
[
  {
    "tool_name": "numpy",
    "tool_id": "tool_001",
    "dockerfile": "FROM ubuntu:20.04\nRUN apt-get update && apt-get install -y python3 python3-pip\nRUN pip3 install numpy",
    "usage_entry_command": "python3 -c 'import numpy; print(numpy.__version__)'"
  }
]
```

### 输出结果

```
output/
└── numpy/
    ├── 00_fetch_and_build_online.sh   # ✅ 在线下载脚本（可联网执行）
    ├── 01_build_offline.sh            # ✅ 离线编译脚本（无网执行）
    ├── build.log                      # 📝 完整日志（辩论+执行历史）
    └── summary.json                   # 📊 结果摘要
```

## 🏗️ 工作流程

```
输入 Dockerfile + 验证命令
         ↓
┌──────────────────────────────┐
│   双模型辩论（最多10轮）      │
│   ┌────────┐    ┌────────┐  │
│   │ 模型 A │ ⇄  │ 模型 B │  │
│   │ 提案者 │    │ 评审者 │  │
│   └────────┘    └────────┘  │
│   · 提案生成脚本             │
│   · 评审检查约束             │
│   · 意见不一致 → 交换身份    │
└──────────────────────────────┘
         ↓ 双方同意
┌──────────────────────────────┐
│   执行验证（最多10次）        │
│   1. 执行 online 脚本（有网） │
│   2. 执行 offline 脚本（无网）│
│   3. 验证工具可用性           │
│   失败 → 回到辩论阶段         │
└──────────────────────────────┘
         ↓ 成功
    生成脚本 + 日志 + 摘要
```

## 🔧 核心约束

生成的脚本必须满足：

1. ✅ Python 路径显式化（不使用系统 python）
2. ✅ 离线安装（`pip install --no-index --find-links`）
3. ✅ C/C++ 扩展预编译（online 阶段编译成 wheel）
4. ✅ 禁止 offline 编译（不触发 gcc/g++）
5. ✅ SIMD/ISA 处理（禁用不兼容特性）
6. ✅ 环境隔离（独立目录和虚拟环境）

## 📖 文档导航

| 文档 | 说明 |
|------|------|
| [GETTING_STARTED.md](GETTING_STARTED.md) | 快速使用指南 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 项目架构和模块 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 生产部署方案 |
| [docs/API.md](docs/API.md) | RESTful API 文档 |
| [docs/QUICK_START.md](docs/QUICK_START.md) | 更多示例 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 项目完成状态 |

## 🎮 使用方式

### CLI 工具

```bash
# 处理所有工具
offline-build --input tools.json --output ./output

# 处理部分工具
offline-build --input tools.json --start-index 0 --end-index 100

# 自定义模型
offline-build --input tools.json --model-a gpt-4o --model-b gemini-2.0-flash-exp
```

### Python 库

```python
from offline_builder import build_tool_offline, ToolInput
from openai import OpenAI
from pathlib import Path

tool = ToolInput(
    tool_name="numpy",
    dockerfile="...",
    usage_entry_command="python -c 'import numpy'"
)

model_a = OpenAI(api_key="...")
model_b = OpenAI(api_key="...")

result = build_tool_offline(
    tool_input=tool,
    model_a_client=model_a,
    model_a_name="gpt-4o",
    model_b_client=model_b,
    model_b_name="gemini-2.0-flash-exp",
    output_dir=Path("./output")
)
```

### API 服务

```bash
# 提交任务
curl -X POST http://localhost:8000/api/v1/build \
  -H "Content-Type: application/json" \
  -d @task.json

# 查询状态
curl http://localhost:8000/api/v1/tasks/{task_id}

# 下载脚本
curl -O http://localhost:8000/api/v1/tasks/{task_id}/scripts
```

## 🛠️ 系统要求

- Python 3.8+
- Linux 操作系统（需要 `ip netns` 支持）
- sudo 权限（创建网络命名空间）
- Docker（可选，用于容器化部署）

## 📊 性能指标

- 平均辩论轮次：3-5轮
- 平均执行次数：1-3次
- 单工具处理时间：10分钟 - 2小时
- 成功率：取决于工具复杂度

## 🤝 贡献

欢迎贡献：

- 🐛 Bug 报告
- ✨ 新功能建议
- 📝 文档改进
- 💡 成功案例分享

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 🙏 致谢

基于原 [build_agent](../build_agent) 项目开发，感谢所有贡献者。

---

**快速链接**：
[快速开始](GETTING_STARTED.md) | 
[部署指南](DEPLOYMENT.md) | 
[API 文档](docs/API.md) | 
[架构说明](ARCHITECTURE.md)
