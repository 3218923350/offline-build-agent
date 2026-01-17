# 离线构建 Agent - 快速开始

## 1分钟快速启动

```bash
# 1. 设置环境变量
export OPENAI_API_KEY="your-openai-key"
export GEMINI_API_KEY="your-gemini-key"

# 2. 创建网络命名空间
sudo ip netns add offline

# 3. 运行示例
./start_offline_build.sh example_tools.json ./test_output
```

## 输入格式

JSON 文件包含工具列表：

```json
[
  {
    "tool_name": "numpy",
    "tool_id": "tool_001",
    "dockerfile": "FROM ubuntu:20.04\n...",
    "usage_entry_command": "python -c 'import numpy'"
  }
]
```

## 输出结果

```
output/
└── numpy/
    ├── 00_fetch_and_build_online.sh  ✅ 在线下载脚本
    ├── 01_build_offline.sh           ✅ 离线编译脚本
    ├── build.log                     📝 完整日志
    └── summary.json                  📊 结果摘要
```

## 常用命令

```bash
# 处理所有工具
python run_offline.py --input tools.json

# 处理前10个工具
python run_offline.py --input tools.json --start-index 0 --end-index 10

# 使用不同的模型
python run_offline.py --input tools.json --model-a gpt-4o --model-b gpt-4o-mini

# 调整辩论和执行次数
python run_offline.py --input tools.json --max-debate-rounds 5 --max-execution-attempts 5
```

## 查看结果

```bash
# 查看最终报告
cat ./offline_build_output/final_report.txt

# 查看单个工具日志
cat ./offline_build_output/numpy/build.log

# 查看统计
cat ./offline_build_output/numpy/summary.json
```

## 问题排查

### Q: 网络命名空间不存在
```bash
sudo ip netns add offline
sudo ip netns list  # 验证
```

### Q: API Key 错误
```bash
echo $OPENAI_API_KEY
echo $GEMINI_API_KEY
```

### Q: 脚本执行失败
查看详细日志：`build.log`

### Q: 辩论无法收敛
- 增加 `--max-debate-rounds`
- 或检查 Dockerfile 是否过于复杂

## 下一步

📖 阅读完整文档：`OFFLINE_BUILD_README.md`
📝 查看开发总结：`OFFLINE_BUILD_SUMMARY.md`
🧪 运行示例：`./start_offline_build.sh example_tools.json`

## 支持的场景

✅ Python 包（含 C 扩展）
✅ Git 仓库
✅ 系统依赖
✅ SIMD/AVX 特殊处理
✅ 动态库依赖

❌ 需要特定硬件（GPU/FPGA）
❌ 需要外部服务（数据库/Redis）
❌ 过于复杂的编译链

## 技术支持

遇到问题？
1. 检查 `build.log` 详细日志
2. 查看 `summary.json` 失败类型
3. 阅读 `OFFLINE_BUILD_README.md`

