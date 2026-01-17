"""
离线构建的大模型交互逻辑（双模型辩论）
"""
from __future__ import annotations

import json
import random
import time
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from .models import DebateRound, ScriptProposal


def call_llm_json_with_retry(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 3,
) -> dict:
    """带重试的 LLM JSON 调用"""
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except json.JSONDecodeError as e:
            last_error = f"JSON解析失败: {e}"
            print(f"[LLM] 尝试 {attempt + 1}/{max_retries}: {last_error}")
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            last_error = f"LLM调用失败: {e}"
            print(f"[LLM] 尝试 {attempt + 1}/{max_retries}: {last_error}")
            time.sleep(random.uniform(1, 3))
    
    raise RuntimeError(f"LLM调用失败（已重试{max_retries}次）: {last_error}")


def build_proposer_system_prompt() -> str:
    """构建脚本生成者的系统提示词"""
    return """你是"离线构建脚本生成专家"。

目标：
给定一个 Dockerfile，请将其**等价转换**为两个 shell 脚本：

1) 00_fetch_and_build_online.sh
   - 允许联网
   - 允许 apt / pip / curl / git
   - 必须完成：
     • Python 环境安装（如 Dockerfile 中需要）
     • 所有依赖包下载（包括 C/C++ 扩展）
     • C/C++ 扩展必须编译成 wheel
     • 所有资源文件下载
   - 禁止在 offline 阶段再编译 C 代码

2) 01_build_offline.sh
   - 完全无网络（ip netns exec offline 环境）
   - 只能使用 online 阶段产物
   - 禁止 apt / pip download / curl / git / wget
   - 禁止 CPU 特性自动探测
   - 禁止触发编译器

【硬性工程约束（违反任意一条必须 can_run=false）】
✓ Python 必须显式路径，不允许使用系统 python（建议用 Miniforge3）
✓ pip install 必须使用 --no-index + --find-links
✓ C/C++ 扩展必须在 online 阶段编译成 wheel
✓ offline 阶段不得触发编译器（gcc/g++/clang）
✓ 如果工具涉及 SIMD / ISA（如 simsimd）：
  - 必须在 online 阶段显式禁用不兼容 target
✓ 环境隔离：每个工具使用独立目录（/root/tools/{tool_name}）
✓ Python 环境隔离：使用 venv 或独立的 Miniforge3

【常见经验和最佳实践】
1. **Python 环境管理**：
   - 推荐使用 Miniforge3（自带 conda + pip）
   - 安装路径：/root/tools/{tool_name}/miniforge3
   - 创建独立 venv：/root/tools/{tool_name}/venv
   - Python 路径示例：/root/tools/{tool_name}/miniforge3/bin/python

2. **依赖下载和安装**：
   - Online: pip download --dest ./packages {package_name}
   - Online: pip wheel --wheel-dir ./wheels --no-deps {package_name}
   - Offline: pip install --no-index --find-links ./packages {package_name}
   - 注意：必须下载所有传递依赖

3. **C/C++ 扩展处理**：
   - 必须在 online 阶段编译：pip wheel --no-deps numpy
   - 禁用 SIMD：SIMSIMD_TARGET_X86=0 pip wheel simsimd
   - 禁用 AVX：CFLAGS="-march=x86-64" pip wheel package_name
   - 静态链接优先：避免动态库依赖问题

4. **Git 仓库处理**：
   - Online: git clone {repo_url} ./repo
   - Offline: cd ./repo && pip install --no-index --no-build-isolation -e .
   - 或者 Online 阶段直接 pip wheel ./repo

5. **系统依赖**：
   - Online 阶段：apt-get install 所有需要的系统包
   - Offline 阶段：不要用 apt，假设所有依赖已安装

6. **环境变量**：
   - 设置 PATH: export PATH=/root/tools/{tool_name}/miniforge3/bin:$PATH
   - 设置 LD_LIBRARY_PATH（如果有动态库）
   - 禁用网络检测：NO_PROXY=* HTTP_PROXY= HTTPS_PROXY=

7. **验证命令调整**：
   - 原始：python -c 'import numpy'
   - 调整：/root/tools/{tool_name}/miniforge3/bin/python -c 'import numpy'
   - 或使用激活脚本：source {venv}/bin/activate && python -c 'import numpy'

8. **常见陷阱**：
   - ❌ 不要在 offline 阶段使用 pip install {package} (会尝试联网)
   - ❌ 不要在 offline 阶段使用 curl/wget/git
   - ❌ 不要依赖 CPU 特性自动检测（会编译多个版本）
   - ❌ 不要使用 pip install -e . 在 offline（可能触发编译）
   - ✅ 使用 pip install --no-build-isolation 避免隔离环境下载
   - ✅ 使用 --no-deps 避免自动解析依赖
   - ✅ 明确指定所有依赖的版本

【脚本模板建议】

Online 脚本模板：
```bash
#!/bin/bash
set -e  # 遇错即停

TOOL_DIR="/root/tools/{tool_name}"
mkdir -p $TOOL_DIR
cd $TOOL_DIR

echo "[1/5] 安装 Miniforge3..."
wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh -b -p $TOOL_DIR/miniforge3
export PATH="$TOOL_DIR/miniforge3/bin:$PATH"

echo "[2/5] 安装系统依赖..."
apt-get update && apt-get install -y gcc g++ make

echo "[3/5] 下载 Python 包..."
mkdir -p packages wheels
pip download --dest packages numpy
pip wheel --wheel-dir wheels --no-deps numpy

echo "[4/5] 编译 C 扩展..."
# 如果有 SIMD/AVX 需要禁用
# SIMSIMD_TARGET_X86=0 pip wheel --wheel-dir wheels simsimd

echo "[5/5] 验证产物..."
ls -lh packages/ wheels/
echo "Online 阶段完成"
```

Offline 脚本模板：
```bash
#!/bin/bash
set -e

TOOL_DIR="/root/tools/{tool_name}"
cd $TOOL_DIR
export PATH="$TOOL_DIR/miniforge3/bin:$PATH"

echo "[1/3] 安装包（无网）..."
pip install --no-index --find-links ./packages --find-links ./wheels numpy

echo "[2/3] 验证安装..."
python -c "import numpy; print(numpy.__version__)"

echo "[3/3] 清理临时文件..."
rm -rf packages/ wheels/
echo "Offline 阶段完成"
```

输出 JSON 格式：
{
  "online_script": "完整的 bash 脚本内容（基于模板调整）",
  "offline_script": "完整的 bash 脚本内容（基于模板调整）",
  "can_run": true|false,
  "reason": "详细说明你的判断依据，如果是 false 必须指出具体问题"
}"""


def build_reviewer_system_prompt() -> str:
    """构建评审者的系统提示词"""
    return """你是"离线构建脚本评审专家"。

任务：评审另一个 AI 生成的两个 shell 脚本（online + offline），判断是否能在无网环境成功运行。

评审要点：
1. **检查硬性约束**（违反任何一条必须 can_run=false）：
   ✓ Python 路径是否显式指定（不能用 python/python3，要用完整路径）
   ✓ pip install 是否使用 --no-index + --find-links（offline阶段）
   ✓ C/C++ 扩展是否在 online 阶段编译成 wheel
   ✓ offline 阶段是否有联网操作（curl/wget/git/pip download）
   ✓ offline 阶段是否触发编译器（gcc/g++/clang/cmake）

2. **检查依赖完整性**：
   ✓ online 阶段是否下载了所有依赖（包括传递依赖）
   ✓ 是否遗漏了系统依赖（libssl/libffi等）
   ✓ Python 包的版本是否指定
   ✓ 是否有隐式的网络依赖（如 setup.py 中的下载）

3. **检查路径和环境**：
   ✓ online 和 offline 阶段的路径是否一致
   ✓ 环境变量是否正确设置（PATH/LD_LIBRARY_PATH）
   ✓ 工作目录是否正确（cd 到正确位置）
   ✓ 验证命令的 Python 路径是否正确

4. **检查边界情况**：
   ✓ SIMD/ISA/AVX 特性是否在 online 阶段禁用
   ✓ 动态链接库是否在 online 阶段安装
   ✓ 权限问题（是否需要 sudo）
   ✓ 磁盘空间（是否清理临时文件）

5. **检查常见错误**：
   ✓ 是否使用了 pip install package（应该用 --no-index）
   ✓ 是否使用了 pip install -e .（可能触发编译）
   ✓ 是否遗漏了 --no-build-isolation
   ✓ 是否假设了网络可用（DNS查询/证书验证）
   ✓ 是否使用了系统 python（/usr/bin/python）

6. **脚本质量检查**：
   ✓ 是否有 set -e（遇错即停）
   ✓ 是否有清晰的日志输出（echo 关键步骤）
   ✓ 是否检查了关键文件是否存在
   ✓ 是否有适当的错误处理

输出 JSON 格式：
{
  "can_run": true|false,
  "suggestions": "详细的评审意见，如果 can_run=false 必须说明原因和改进建议",
  "key_issues": ["问题1", "问题2"]  // 可选，列出关键问题
}"""


def build_proposer_user_prompt(
    tool_name: str,
    dockerfile: str,
    usage_entry_command: str,
    history: List[DebateRound],
    execution_failures: List[str],
) -> str:
    """构建生成者的用户提示词"""
    prompt_parts = [
        f"工具名称: {tool_name}",
        f"\nDockerfile 内容:\n```dockerfile\n{dockerfile}\n```",
        f"\n验证命令: {usage_entry_command}",
    ]
    
    # 添加历史辩论记录
    if history:
        prompt_parts.append("\n\n【历史辩论记录】")
        for round in history[-3:]:  # 只保留最近3轮
            prompt_parts.append(f"\n第 {round.round_index} 轮:")
            prompt_parts.append(f"- 提案者({round.proposer_name})认为 can_run={round.proposal.can_run}")
            prompt_parts.append(f"  理由: {round.proposal.reason}")
            prompt_parts.append(f"- 评审者({round.reviewer_name})认为 can_run={round.review_can_run}")
            prompt_parts.append(f"  建议: {round.review_suggestions}")
    
    # 添加执行失败记录
    if execution_failures:
        prompt_parts.append("\n\n【执行失败记录】（最后1000行）")
        for i, failure in enumerate(execution_failures[-2:], 1):
            truncated = failure[-1000:] if len(failure) > 1000 else failure
            prompt_parts.append(f"\n失败 {i}:\n```\n{truncated}\n```")
    
    prompt_parts.append("\n\n请基于以上信息生成或改进两个 shell 脚本。")
    
    return "".join(prompt_parts)


def build_reviewer_user_prompt(
    tool_name: str,
    dockerfile: str,
    proposal: ScriptProposal,
) -> str:
    """构建评审者的用户提示词"""
    return f"""工具名称: {tool_name}

原始 Dockerfile:
```dockerfile
{dockerfile}
```

提案者生成的脚本:

【online 脚本】
```bash
{proposal.online_script}
```

【offline 脚本】
```bash
{proposal.offline_script}
```

提案者的判断: can_run={proposal.can_run}
理由: {proposal.reason}

请仔细评审这两个脚本，判断是否真的能在无网环境成功运行。"""


def debate_scripts(
    tool_name: str,
    dockerfile: str,
    usage_entry_command: str,
    model_a_client: OpenAI,
    model_a_name: str,
    model_b_client: OpenAI,
    model_b_name: str,
    max_debate_rounds: int = 10,
    execution_failures: Optional[List[str]] = None,
    history: Optional[List[DebateRound]] = None,
) -> Tuple[ScriptProposal, List[DebateRound], bool]:
    """
    双模型辩论生成脚本
    
    Returns:
        (final_proposal, debate_history, should_execute)
        should_execute: True 表示双方都同意 can_run=True，可以执行
    """
    if execution_failures is None:
        execution_failures = []
    if history is None:
        history = []
    
    proposer_client = model_a_client
    proposer_name = model_a_name
    reviewer_client = model_b_client
    reviewer_name = model_b_name
    
    proposer_sys_prompt = build_proposer_system_prompt()
    reviewer_sys_prompt = build_reviewer_system_prompt()
    
    start_round = len(history)
    
    for round_idx in range(start_round, start_round + max_debate_rounds):
        print(f"\n[辩论] 第 {round_idx + 1} 轮")
        print(f"  提案者: {proposer_name}")
        print(f"  评审者: {reviewer_name}")
        
        # Step 1: 提案者生成脚本
        proposer_user_prompt = build_proposer_user_prompt(
            tool_name, dockerfile, usage_entry_command, history, execution_failures
        )
        
        try:
            proposer_response = call_llm_json_with_retry(
                proposer_client,
                proposer_name,
                proposer_sys_prompt,
                proposer_user_prompt,
            )
        except Exception as e:
            print(f"[辩论] 提案者调用失败: {e}")
            # 返回失败提案
            proposal = ScriptProposal(
                online_script="",
                offline_script="",
                can_run=False,
                reason=f"LLM调用失败: {e}",
                model_name=proposer_name,
            )
            return proposal, history, False
        
        proposal = ScriptProposal(
            online_script=proposer_response.get("online_script", ""),
            offline_script=proposer_response.get("offline_script", ""),
            can_run=bool(proposer_response.get("can_run", False)),
            reason=proposer_response.get("reason", ""),
            model_name=proposer_name,
        )
        
        print(f"  提案者认为: can_run={proposal.can_run}")
        print(f"  理由: {proposal.reason[:100]}...")
        
        # Step 2: 评审者评审
        reviewer_user_prompt = build_reviewer_user_prompt(tool_name, dockerfile, proposal)
        
        try:
            reviewer_response = call_llm_json_with_retry(
                reviewer_client,
                reviewer_name,
                reviewer_sys_prompt,
                reviewer_user_prompt,
            )
        except Exception as e:
            print(f"[辩论] 评审者调用失败: {e}")
            # 评审失败，但保留提案
            review_can_run = False
            review_suggestions = f"评审失败: {e}"
        else:
            review_can_run = bool(reviewer_response.get("can_run", False))
            review_suggestions = reviewer_response.get("suggestions", "")
        
        print(f"  评审者认为: can_run={review_can_run}")
        print(f"  建议: {review_suggestions[:100]}...")
        
        # 记录本轮辩论
        debate_round = DebateRound(
            round_index=round_idx + 1,
            proposer_name=proposer_name,
            reviewer_name=reviewer_name,
            proposal=proposal,
            review_can_run=review_can_run,
            review_suggestions=review_suggestions,
            reviewer_model=reviewer_name,
        )
        history.append(debate_round)
        
        # Step 3: 判断辩论结果
        if proposal.can_run and review_can_run:
            # 双方都同意，可以执行
            print("  ✅ 双方都同意 can_run=True，进入执行阶段")
            return proposal, history, True
        
        if not proposal.can_run and not review_can_run:
            # 双方都拒绝，工具不可行
            print("  ❌ 双方都认为 can_run=False，工具不可行")
            return proposal, history, False
        
        if proposal.can_run and not review_can_run:
            # 提案者同意，评审者拒绝 -> 交换身份
            print("  🔄 提案者同意但评审者拒绝，交换身份继续辩论")
            proposer_client, reviewer_client = reviewer_client, proposer_client
            proposer_name, reviewer_name = reviewer_name, proposer_name
        
        # 如果提案者拒绝，评审者同意：也交换身份，让评审者来生成
        if not proposal.can_run and review_can_run:
            print("  🔄 提案者拒绝但评审者同意，交换身份继续辩论")
            proposer_client, reviewer_client = reviewer_client, proposer_client
            proposer_name, reviewer_name = reviewer_name, proposer_name
    
    # 达到最大辩论轮次
    print(f"  ⏱️ 达到最大辩论轮次 {max_debate_rounds}，结束辩论")
    last_proposal = history[-1].proposal if history else proposal
    return last_proposal, history, False

