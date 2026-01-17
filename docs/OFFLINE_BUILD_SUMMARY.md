# 离线构建 Agent 开发总结

## 已完成功能

### 1. 核心模块

- ✅ `offline_models.py`: 数据模型定义
  - ToolInput: 工具输入
  - ScriptProposal: 脚本提案
  - DebateRound: 辩论轮次记录
  - ExecutionResult: 执行结果
  - BuildResult: 构建结果
  - OfflineBuildSummary: 摘要统计

- ✅ `offline_llm.py`: 双模型辩论逻辑
  - 脚本生成者系统提示词（包含硬性约束和最佳实践）
  - 评审者系统提示词（包含6大评审要点）
  - 动态身份交换机制
  - 基于历史和失败日志的上下文管理

- ✅ `offline_builder.py`: 构建执行逻辑
  - 脚本执行（支持网络命名空间）
  - 工具验证
  - 日志记录
  - 自动清理
  - 完整的辩论-执行-反馈循环

- ✅ `offline_cli.py`: 命令行接口
  - JSON 批量输入
  - 进度控制（start-index/end-index）
  - 统计报告生成
  - 异常处理

### 2. 辅助文件

- ✅ `run_offline.py`: 主入口脚本
- ✅ `example_tools.json`: 示例工具配置
- ✅ `start_offline_build.sh`: 快速启动脚本
- ✅ `env.example.sh`: 环境配置模板
- ✅ `OFFLINE_BUILD_README.md`: 完整使用文档

## 核心特性

### 1. 双模型辩论机制

```
模型A提案 → 模型B评审
   ↓              ↓
can_run?      can_run?
   ↓              ↓
两者都同意 → 执行
一方拒绝 → 交换身份继续
两者都拒绝 → 标记为不可行
```

### 2. 智能身份交换

- 提案者同意 + 评审者拒绝 → 交换身份
- 提案者拒绝 + 评审者同意 → 交换身份
- 避免单一模型偏见

### 3. 执行验证循环

```
辩论 → 执行 online → 执行 offline → 验证
         ↓ 失败         ↓ 失败      ↓ 失败
         └─────────────┴───────────┘
                   ↓
            带失败日志回到辩论
```

### 4. 硬性约束检查

1. Python 路径显式化
2. pip install 必须 --no-index
3. C/C++ 扩展预编译
4. 禁止 offline 编译
5. SIMD/ISA 处理
6. 环境隔离

### 5. 详细日志记录

每个工具输出：
- `00_fetch_and_build_online.sh`: 在线脚本
- `01_build_offline.sh`: 离线脚本
- `build.log`: 完整日志（辩论过程+执行历史）
- `summary.json`: 结果摘要

## 系统提示词亮点

### 生成者提示词

- 明确的两阶段目标（online/offline）
- 8条硬性约束
- 8类常见经验和最佳实践
- Bash 脚本模板
- 详细的陷阱说明

### 评审者提示词

- 6大评审维度：
  1. 硬性约束检查
  2. 依赖完整性
  3. 路径和环境
  4. 边界情况
  5. 常见错误
  6. 脚本质量

## 使用流程

```bash
# 1. 初始化环境
source env.example.sh
sudo ip netns add offline

# 2. 准备输入
# 编辑 tools.json

# 3. 运行构建
./start_offline_build.sh tools.json ./output

# 或直接运行
python run_offline.py --input tools.json --output ./output

# 4. 查看结果
cat ./output/final_report.txt
```

## 与原 build_agent 的集成

建议的项目结构：
```
build_agent/
├── build_agent/
│   ├── __init__.py
│   ├── builder.py          # 原有在线构建
│   ├── cli.py              # 原有CLI
│   ├── offline_builder.py  # 新增离线构建
│   ├── offline_cli.py      # 新增离线CLI
│   ├── offline_llm.py      # 新增离线LLM
│   └── offline_models.py   # 新增离线模型
├── run.py                  # 原有在线构建入口
├── run_offline.py          # 新增离线构建入口
├── start_offline_build.sh  # 快速启动
└── OFFLINE_BUILD_README.md # 文档
```

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --input | 必填 | 输入JSON文件 |
| --output | ./offline_build_output | 输出目录 |
| --model-a | gpt-4o | 模型A |
| --model-b | gemini-2.0-flash-exp | 模型B |
| --max-debate-rounds | 10 | 最大辩论轮次 |
| --max-execution-attempts | 10 | 最大执行次数 |
| --start-index | 0 | 起始索引 |
| --end-index | -1 | 结束索引 |

## 失败类型统计

- `debate_limit`: 辩论10轮未达成一致
- `execution_limit`: 执行10次仍失败
- `model_reject`: 双方都认为不可行
- `other`: 其他异常

## 注意事项

1. **网络命名空间**：
   - 必须创建：`sudo ip netns add offline`
   - 需要 root 权限

2. **执行时间**：
   - 单个工具：几分钟到几小时
   - 取决于辩论轮次和执行次数

3. **磁盘空间**：
   - 每个工具可能需要几GB
   - 自动清理构建产物

4. **API 成本**：
   - 每轮辩论：2次 LLM 调用
   - 每次失败：增加上下文长度
   - 建议使用较便宜的模型（如 gemini-2.0-flash）

## 后续优化建议

1. **提示词优化**：
   - 根据实际失败案例补充经验
   - 针对特定语言（Python/C++/Go）定制

2. **缓存机制**：
   - 缓存常见依赖下载结果
   - 缓存成功的脚本模式

3. **并行处理**：
   - 支持多工具并行构建
   - 注意资源限制

4. **增量构建**：
   - 支持从失败点恢复
   - 避免重复辩论

5. **模板库**：
   - 积累成功的脚本模板
   - 按工具类型分类

## 测试建议

```bash
# 1. 测试示例工具
python run_offline.py --input example_tools.json --output ./test

# 2. 测试单个工具
python run_offline.py --input tools.json --start-index 0 --end-index 1 --output ./test

# 3. 批量测试
python run_offline.py --input tools.json --output ./batch_test
```

## 贡献指南

欢迎贡献：
- 成功的脚本案例
- 失败案例分析
- 提示词优化建议
- Bug 修复

## License

与主项目保持一致

