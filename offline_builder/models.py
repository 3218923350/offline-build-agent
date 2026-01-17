"""
离线构建的数据模型
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ToolInput:
    """工具输入信息"""
    tool_name: str
    dockerfile: str
    usage_entry_command: str
    tool_id: str = ""


@dataclass
class ScriptProposal:
    """脚本提案"""
    online_script: str
    offline_script: str
    can_run: bool
    reason: str
    model_name: str = ""


@dataclass
class DebateRound:
    """辩论轮次记录"""
    round_index: int
    proposer_name: str
    reviewer_name: str
    proposal: ScriptProposal
    review_can_run: bool
    review_suggestions: str
    reviewer_model: str = ""


@dataclass
class ExecutionResult:
    """执行结果"""
    stage: str  # "online" | "offline" | "verify"
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    error_message: str = ""


@dataclass
class BuildResult:
    """构建结果"""
    tool_name: str
    tool_id: str
    success: bool
    online_script: str
    offline_script: str
    debate_rounds: List[DebateRound]
    execution_history: List[ExecutionResult]
    final_reason: str
    failure_type: str = ""  # "debate_limit" | "execution_limit" | "model_reject" | ""


@dataclass
class OfflineBuildSummary:
    """构建摘要（用于最终统计）"""
    tool_name: str
    tool_id: str
    success: bool
    debate_rounds: int
    execution_attempts: int
    failure_type: str
    failure_reason: str
    final_scripts_ok: bool

