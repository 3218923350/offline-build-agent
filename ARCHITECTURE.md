# 离线构建 Agent - 项目结构

```
offline-build-agent/
├── offline_builder/          # 核心包
│   ├── __init__.py          # 包初始化
│   ├── __main__.py          # CLI 入口
│   ├── models.py            # 数据模型
│   ├── llm.py               # LLM 交互和辩论逻辑
│   ├── builder.py           # 构建执行逻辑
│   ├── cli.py               # 命令行接口
│   ├── api.py               # FastAPI 服务
│   ├── config.py            # 配置管理
│   └── utils.py             # 工具函数
│
├── examples/                 # 示例
│   └── example_tools.json   # 示例工具配置
│
├── docs/                     # 文档
│   ├── API.md               # API 文档
│   ├── OFFLINE_BUILD_SUMMARY.md  # 开发总结
│   └── QUICK_START.md       # 快速开始
│
├── tests/                    # 测试（待添加）
│   └── test_builder.py
│
├── requirements.txt          # 基础依赖
├── requirements-api.txt      # API 服务依赖
├── setup.py                  # 安装配置
├── README.md                 # 主文档
├── Dockerfile                # Docker 镜像
├── docker-compose.yml        # Docker Compose 配置
├── deploy.sh                 # 快速部署脚本
├── env.example               # 环境变量示例
└── .gitignore                # Git 忽略文件
```

## 模块说明

### offline_builder/models.py
- `ToolInput`: 工具输入
- `ScriptProposal`: 脚本提案
- `DebateRound`: 辩论轮次
- `ExecutionResult`: 执行结果
- `BuildResult`: 构建结果
- `OfflineBuildSummary`: 摘要统计

### offline_builder/llm.py
- `debate_scripts()`: 双模型辩论主函数
- `build_proposer_system_prompt()`: 生成者提示词
- `build_reviewer_system_prompt()`: 评审者提示词
- `call_llm_json_with_retry()`: 带重试的 LLM 调用

### offline_builder/builder.py
- `build_tool_offline()`: 单工具离线构建
- `execute_shell_script()`: 执行脚本
- `verify_tool()`: 验证工具
- `cleanup_build_artifacts()`: 清理产物

### offline_builder/cli.py
- `main()`: CLI 主函数
- `load_tools_from_json()`: 加载工具配置
- `generate_final_report()`: 生成统计报告

### offline_builder/api.py
- FastAPI 服务
- RESTful API 端点
- 后台任务管理

## 使用方式

### 1. 作为库使用

```python
from offline_builder import build_tool_offline, ToolInput
from openai import OpenAI

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

### 2. 命令行工具

```bash
# 安装
pip install -e .

# 使用
offline-build --input tools.json --output ./output

# 或
python -m offline_builder --input tools.json
```

### 3. API 服务

```bash
# 启动服务
uvicorn offline_builder.api:app --host 0.0.0.0 --port 8000

# 或使用入口
offline-build-api

# Docker
docker-compose up -d
```

## 开发

### 安装开发依赖

```bash
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/
```

### 代码格式化

```bash
black offline_builder/
flake8 offline_builder/
mypy offline_builder/
```

## 部署方式

### 1. Docker Compose（生产推荐）

```bash
./deploy.sh
# 选择 1
```

### 2. 直接运行

```bash
./deploy.sh
# 选择 2
```

### 3. Kubernetes（大规模部署）

```yaml
# 待添加 k8s 配置
```

## 扩展

### 添加新的 LLM 提供商

在 `llm.py` 中添加新的客户端初始化逻辑

### 自定义提示词

修改 `build_proposer_system_prompt()` 和 `build_reviewer_system_prompt()`

### 添加新的验证方式

在 `builder.py` 的 `verify_tool()` 中添加逻辑

## License

MIT

