# 离线构建代理改造日志

## 2026-01-17 - 严格工程化改造

### 改造目标

将离线构建代理从"概念性方案"改造为"严格的工程化工具"，确保：
1. **副作用分析**：明确识别并列出所有联网副作用
2. **物化映射**：确保每个副作用在 online 阶段都被"物化"为本地文件
3. **验证命令改写**：强制改写 python 等系统命令为确定性路径
4. **100% 覆盖检查**：Reviewer 检查副作用是否完全被覆盖

### 核心变更

#### 1. 数据模型变更 (`models.py`)

**新增 `SideEffect` 类**：
```python
@dataclass
class SideEffect:
    source: str              # "apt" | "pip" | "git" | "curl" | "wget" | "setup.py"
    object: str              # 包名 / URL / repo
    needs_compile: bool      # 是否涉及 C/C++ 编译
    needs_cpu_detect: bool   # 是否涉及 CPU 特性探测
    may_access_network: bool # 是否可能隐式联网
```

**更新 `ScriptProposal` 类**：
- 新增字段：`side_effects: List[SideEffect]` - 副作用清单
- 新增字段：`rewritten_verify_command: str` - 改写后的验证命令

#### 2. Proposer 系统提示词重写 (`llm.py`)

完全重写 `build_proposer_system_prompt()`，新提示词强调：

**三个强制步骤**：
1. **Step 1 - 副作用拆解**：必须列出所有联网副作用
   - 来源（apt/pip/git/curl/wget/setup.py）
   - 对象（包名/URL/repo）
   - 编译需求、CPU探测、隐式联网风险
   
2. **Step 2 - 副作用物化映射**：
   - 明确每个副作用如何在 online 阶段被"物化"
   - 明确 offline 阶段如何消费该产物
   
3. **Step 3 - 脚本生成**：
   - 确保每个 offline 命令都能追溯到 online 产物

**验证命令改写**（强制）：
- ❌ 禁止: `python -c "import xxx"`
- ✅ 必须: `/root/tools/{tool_name}/miniforge3/bin/python3 -c "import xxx"`

**输出格式**（严格 JSON）：
```json
{
  "side_effects": [...],
  "online_script": "...",
  "offline_script": "...",
  "rewritten_verify_command": "...",
  "can_run": true|false,
  "reason": "..."
}
```

#### 3. Reviewer 系统提示词重写 (`llm.py`)

完全重写 `build_reviewer_system_prompt()`，新提示词强调：

**唯一判断标准**：
> offline 阶段是否完全不依赖任何 online 阶段未显式生成的副作用

**四个检查步骤**：
1. **Step 1 - 副作用覆盖检查**：
   - 对照 proposer 的 side_effects 清单
   - 检查 online_script 是否为每一项生成了产物
   - 检查 offline_script 是否只使用这些产物

2. **Step 2 - offline 纯度检查**：
   - 禁止出现：apt, pip install（未带 --no-index）, curl, wget, git
   - 禁止出现：gcc, g++, make, cmake
   - 禁止出现：setup.py 触发构建

3. **Step 3 - Python 确定性检查**：
   - offline_script 中 python 路径是否显式
   - rewritten_verify_command 是否使用正确的 python

4. **Step 4 - 隐式风险检查**：
   - setup.py 是否可能在 install 阶段联网
   - SIMD/ISA 是否在 online 阶段显式关闭

**角色定位**：
> Reviewer 不是"挑毛病"，而是检查"副作用是否 100% 被覆盖和冻结"

#### 4. 用户提示词更新

**Proposer 用户提示词** (`build_proposer_user_prompt`)：
- 显示历史辩论中的副作用分析（前5个）
- 显示改写后的验证命令
- 引导按 Step 1 → Step 2 → Step 3 顺序分析

**Reviewer 用户提示词** (`build_reviewer_user_prompt`)：
- 显示完整的副作用清单
- 显示改写后的验证命令
- 引导按 Step 1 → Step 2 → Step 3 → Step 4 顺序检查

#### 5. 验证逻辑更新 (`builder.py`)

**`verify_tool()` 函数简化**：
- 移除了自动路径替换逻辑（因为 Proposer 已经改写了命令）
- 直接使用 `proposal.rewritten_verify_command`
- 减少隐式行为，增加透明度

**构建日志增强**：
- 输出副作用分析（包括编译需求、CPU探测、联网风险）
- 输出改写后的验证命令
- 更清晰的调试信息

### 工程化改进

#### 改进前的问题

1. **缺乏副作用分析**：Proposer 直接生成脚本，没有明确分析依赖来源
2. **验证命令不确定**：依赖运行时的路径猜测，不可靠
3. **Reviewer 角色模糊**：既检查脚本质量，又挑毛病，标准不清
4. **隐式行为太多**：自动替换路径等行为增加了不确定性

#### 改进后的特点

1. **显式副作用管理**：
   - Proposer 必须先分析所有副作用
   - 每个副作用都有明确的来源和目标
   - 可追溯性强

2. **验证命令确定性**：
   - Proposer 负责改写验证命令
   - 使用显式的绝对路径
   - 消除运行时猜测

3. **Reviewer 角色清晰**：
   - 唯一目标：检查副作用覆盖率
   - 不是挑毛病，而是验证工程完整性
   - 明确的检查步骤

4. **减少隐式行为**：
   - 验证逻辑不再自动替换路径
   - 所有转换都在 LLM 层面完成
   - 提高透明度和可调试性

### 参考模式

改造基于已验证的 **SimSIMD 成功模式**：

**Online 阶段**：
- 构建独立 Python（Miniforge3）
- 冻结 pip/setuptools/wheel 版本
- pip wheel 生成所有 wheel 文件
- 显式关闭 SIMD/ISA 不兼容 target

**Offline 阶段**：
- 只执行 `pip install --no-index --find-links`
- 只消费 wheel 文件
- Python 路径显式指定

### 使用示例

改造后，LLM 的输出会包含更多结构化信息：

```json
{
  "side_effects": [
    {
      "source": "pip",
      "object": "numpy",
      "needs_compile": true,
      "needs_cpu_detect": false,
      "may_access_network": false
    },
    {
      "source": "apt",
      "object": "gcc, g++, make",
      "needs_compile": false,
      "needs_cpu_detect": false,
      "may_access_network": true
    }
  ],
  "online_script": "...",
  "offline_script": "...",
  "rewritten_verify_command": "/root/tools/numpy-tool/miniforge3/bin/python3 -c 'import numpy; print(numpy.__version__)'",
  "can_run": true,
  "reason": "所有 C 扩展已在 online 阶段编译为 wheel，offline 阶段使用 --no-index 安装"
}
```

### 向后兼容性

**不兼容变更**：
- `ScriptProposal` 模型增加了必需字段
- `verify_tool()` 函数签名变更（参数从 `usage_entry_command` 改为 `verify_command`）
- LLM 响应格式变更（必须包含 `side_effects` 和 `rewritten_verify_command`）

**迁移建议**：
- 重新训练或更新 LLM 提示词
- 更新所有调用 `verify_tool()` 的代码
- 检查所有依赖 `ScriptProposal` 的代码

### 测试建议

1. **副作用识别测试**：验证 Proposer 能否完整识别所有副作用
2. **验证命令改写测试**：验证路径改写是否正确
3. **Reviewer 检查测试**：验证 Reviewer 能否发现遗漏的副作用
4. **端到端测试**：使用已知工具（如 SimSIMD）验证完整流程

### 下一步改进方向

1. **副作用模板库**：建立常见工具的副作用模式库
2. **自动化测试**：增加单元测试和集成测试
3. **错误诊断增强**：提供更详细的失败原因分析
4. **性能优化**：减少 LLM 调用次数，优化辩论策略

