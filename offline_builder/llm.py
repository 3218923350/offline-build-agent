"""
离线构建的大模型交互逻辑（双模型辩论）
"""
from __future__ import annotations

import json
import random
import time
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

from .models import DebateRound, ScriptProposal, SideEffect


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
            if model == "mog-1":
                response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            else:
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
    return """你是「离线构建脚本生成专家（Offline Build Script Proposer）」。

你的任务不是"想办法安装工具"，
而是 **把 Dockerfile 中所有"联网副作用"显式前移到 online 阶段并物化**，
从而保证 offline 阶段在「完全无网络」条件下也能成功运行。

⚠️ 这是一个严格的工程任务，不是概念性讨论。

────────────────────────────────
【全局目标（不可违反）】
────────────────────────────────
你必须生成两个 shell 脚本：

1) 00_fetch_and_build_online.sh
   - 允许联网
   - 允许 apt / pip / curl / wget / git
   - **必须把所有联网副作用"物化"为本地文件**
   - 允许 C/C++ 编译（但必须产出 wheel / 二进制文件）

2) 01_build_offline.sh
   - 运行在完全无网络环境中（ip netns exec offline）
   - 禁止 apt / pip download / curl / wget / git
   - 禁止触发任何编译器（gcc / g++ / cmake / make）
   - 只能使用 online 阶段生成的本地产物

如果你无法保证上述条件，必须返回 can_run=false。

────────────────────────────────
【硬性工程不变量（违反任一条 = can_run=false）】
────────────────────────────────
✓ Python 必须是"确定性产物"（例如源码编译或已下载的发行版）
✓ offline 阶段禁止使用系统 python
✓ offline 阶段 pip install 必须使用 --no-index + --find-links
✓ 所有 Python C 扩展必须在 online 阶段编译成 wheel
✓ offline 阶段不得出现任何 C/C++ 编译行为
✓ 不允许隐式联网（DNS / TLS / metadata / setup.py 下载）
✓ 不允许 CPU 特性自动探测
✓ 每个工具使用独立目录（/root/tools/{tool_name}）

────────────────────────────────
【你必须遵循的"成功参考模式"（SimSIMD Reference）】
────────────────────────────────
下面是一个已经被验证可行的离线构建模式（你必须对齐该模式）：

✔ Online 阶段：
- 构建独立 Python（不依赖系统 Python）
- 冻结 pip / setuptools / wheel 版本
- 对所有 pip install 的包执行：
  - pip wheel → 生成 wheel 文件
- 如果包涉及 SIMD / ISA：
  - 在 online 阶段显式关闭不兼容 target
- offline 阶段不再编译任何 C/C++ 代码

✔ Offline 阶段：
- 只执行 pip install --no-index --find-links
- 只消费 online 阶段生成的 wheel / 二进制文件
- Python 路径必须显式指定

如果你的方案无法与上述模式建立"结构等价关系"，
必须返回 can_run=false。

────────────────────────────────
【必须执行的步骤（不可跳过）】
────────────────────────────────

【Step 1】副作用拆解（必须输出）
请先分析 Dockerfile，并列出一个"联网副作用清单"：
- 来源（apt / pip / git / curl / wget / setup.py / pyproject.toml）
- 对象（包名 / URL / repo）
- 是否涉及 C/C++ 编译
- 是否涉及 CPU 特性探测
- 是否可能隐式联网

如果你无法完整列出这些副作用 → can_run=false。

【Step 2】副作用物化映射
针对 Step 1 中的每一条副作用：
- 明确指出它将在 online 脚本中如何被"物化"
  （例如：wheel 文件 / 源码 tarball / 二进制）
- 明确指出 offline 阶段将如何消费该产物

【Step 3】脚本生成
基于上述分析，生成两个脚本：
- 00_fetch_and_build_online.sh
- 01_build_offline.sh

要求：
- 每一条 offline 命令，都必须能在 online 阶段找到明确来源
- offline 脚本中不得出现 online 脚本未生成的任何文件或依赖

────────────────────────────────
【验证命令改写（强制）】
────────────────────────────────
你必须改写 usage_entry_command：
- 禁止使用 `python` / `python3`
- 必须使用 offline 环境中的"确定性 Python 路径"

示例：
❌ python -c "import xxx"
✅ /root/tools/{tool_name}/miniforge3/bin/python3 -c "import xxx"

────────────────────────────────
【输出格式（严格 JSON，不允许多余文本）】
────────────────────────────────
{
  "side_effects": [
    {
      "source": "...",
      "object": "...",
      "needs_compile": true|false,
      "needs_cpu_detect": true|false,
      "may_access_network": true|false
    }
  ],
  "online_script": "完整 online bash 脚本",
  "offline_script": "完整 offline bash 脚本",
  "rewritten_verify_command": "改写后的验证命令",
  "can_run": true|false,
  "reason": "你的最终判断依据（工程级）"
}"""


def build_reviewer_system_prompt() -> str:
    """构建评审者的系统提示词"""
    return """你是「离线构建脚本评审专家（Offline Build Script Reviewer）」。

你的任务是：**判断这两个脚本是否真的能在"完全无网络环境"下成功运行**。

────────────────────────────────
【你的唯一判断标准】
────────────────────────────────
offline 阶段是否 **完全不依赖任何 online 阶段未显式生成的副作用**。

────────────────────────────────
【评审步骤（必须逐条检查）】
────────────────────────────────

【Step 1】副作用覆盖检查
- 对照 proposer 给出的 side_effects 清单
- 检查 online_script 是否为每一项生成了明确的本地产物
- 检查 offline_script 是否只使用这些产物

如果存在任何遗漏 → can_run=false。

【Step 2】offline 纯度检查
offline_script 中 **禁止出现**：
- apt / apt-get / yum / apk
- pip install（未带 --no-index）
- pip download / pip wheel
- curl / wget / git
- gcc / g++ / make / cmake
- setup.py / pyproject.toml 触发构建

出现任意一项 → can_run=false。

【Step 3】Python 确定性检查
- offline_script 中 python 路径是否显式
- 是否误用了系统 python
- rewritten_verify_command 是否使用了正确的 python

【Step 4】隐式风险检查
- setup.py 是否可能在 install 阶段联网
- SIMD / ISA 是否在 online 阶段显式关闭
- 是否存在动态库缺失风险

────────────────────────────────
【输出格式（严格 JSON，不允许多余文本）】
────────────────────────────────
{
  "can_run": true|false,
  "key_issues": [
    "具体问题 1",
    "具体问题 2"
  ],
  "suggestions": "如果 can_run=false，说明需要如何修改；如果 can_run=true，说明为什么可信"
}

注意：Reviewer 的角色不是"挑毛病"，
而是 检查"副作用是否 100% 被覆盖和冻结"。"""


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
        f"\n原始验证命令: {usage_entry_command}",
    ]
    
    # 添加历史辩论记录
    if history:
        prompt_parts.append("\n\n【历史辩论记录】")
        for round in history[-3:]:  # 只保留最近3轮
            prompt_parts.append(f"\n第 {round.round_index} 轮:")
            prompt_parts.append(f"- 提案者({round.proposer_name})认为 can_run={round.proposal.can_run}")
            prompt_parts.append(f"  理由: {round.proposal.reason}")
            
            # 显示副作用分析
            if round.proposal.side_effects:
                prompt_parts.append(f"  识别到的副作用:")
                for effect in round.proposal.side_effects[:5]:  # 最多显示5个
                    prompt_parts.append(f"    - {effect.source}: {effect.object}")
            
            prompt_parts.append(f"  改写后的验证命令: {round.proposal.rewritten_verify_command}")
            prompt_parts.append(f"- 评审者({round.reviewer_name})认为 can_run={round.review_can_run}")
            prompt_parts.append(f"  建议: {round.review_suggestions}")
    
    # 添加执行失败记录
    if execution_failures:
        prompt_parts.append("\n\n【执行失败记录】（最后1000行）")
        for i, failure in enumerate(execution_failures[-2:], 1):
            truncated = failure[-1000:] if len(failure) > 1000 else failure
            prompt_parts.append(f"\n失败 {i}:\n```\n{truncated}\n```")
    
    prompt_parts.append("\n\n请基于以上信息，按照 Step 1 → Step 2 → Step 3 的顺序分析并生成两个 shell 脚本。")
    
    return "".join(prompt_parts)


def build_reviewer_user_prompt(
    tool_name: str,
    dockerfile: str,
    proposal: ScriptProposal,
) -> str:
    """构建评审者的用户提示词"""
    side_effects_text = ""
    if proposal.side_effects:
        side_effects_text = "\n\n【提案者识别的副作用清单】\n"
        for i, effect in enumerate(proposal.side_effects, 1):
            side_effects_text += f"{i}. 来源: {effect.source}, 对象: {effect.object}\n"
            side_effects_text += f"   - 需要编译: {effect.needs_compile}\n"
            side_effects_text += f"   - CPU探测: {effect.needs_cpu_detect}\n"
            side_effects_text += f"   - 可能联网: {effect.may_access_network}\n"
    
    return f"""工具名称: {tool_name}

原始 Dockerfile:
```dockerfile
{dockerfile}
```
{side_effects_text}

【提案者生成的脚本】

online 脚本:
```bash
{proposal.online_script}
```

offline 脚本:
```bash
{proposal.offline_script}
```

改写后的验证命令: {proposal.rewritten_verify_command}

提案者的判断: can_run={proposal.can_run}
理由: {proposal.reason}

请按照评审步骤（Step 1 → Step 2 → Step 3 → Step 4）逐条检查，判断是否真的能在无网环境成功运行。"""


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
                side_effects=[],
                online_script="",
                offline_script="",
                rewritten_verify_command=usage_entry_command,
                can_run=False,
                reason=f"LLM调用失败: {e}",
                model_name=proposer_name,
            )
            return proposal, history, False
        
        # 解析副作用列表
        side_effects = []
        raw_effects = proposer_response.get("side_effects", [])
        if isinstance(raw_effects, list):
            for effect_dict in raw_effects:
                if isinstance(effect_dict, dict):
                    side_effects.append(SideEffect(
                        source=effect_dict.get("source", ""),
                        object=effect_dict.get("object", ""),
                        needs_compile=bool(effect_dict.get("needs_compile", False)),
                        needs_cpu_detect=bool(effect_dict.get("needs_cpu_detect", False)),
                        may_access_network=bool(effect_dict.get("may_access_network", False)),
                    ))
        
        proposal = ScriptProposal(
            side_effects=side_effects,
            online_script=proposer_response.get("online_script", ""),
            offline_script=proposer_response.get("offline_script", ""),
            rewritten_verify_command=proposer_response.get("rewritten_verify_command", usage_entry_command),
            can_run=bool(proposer_response.get("can_run", False)),
            reason=proposer_response.get("reason", ""),
            model_name=proposer_name,
        )
        
        print(f"  提案者认为: can_run={proposal.can_run}")
        print(f"  识别到 {len(proposal.side_effects)} 个副作用")
        print(f"  改写后的验证命令: {proposal.rewritten_verify_command}")
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

