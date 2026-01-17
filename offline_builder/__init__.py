"""
离线构建 Agent - 将 Docker 工具转换为无网环境可编译的脚本

这是一个独立的工具包，用于将基于 Dockerfile 的工具转换为可在完全离线环境中
编译和运行的 shell 脚本。
"""

__version__ = "1.0.0"
__author__ = "Build Agent Team"

from .models import (
    BuildResult,
    DebateRound,
    ExecutionResult,
    OfflineBuildSummary,
    ScriptProposal,
    SideEffect,
    ToolInput,
)
from .builder import build_tool_offline
from .llm import debate_scripts

__all__ = [
    "BuildResult",
    "DebateRound",
    "ExecutionResult",
    "OfflineBuildSummary",
    "ScriptProposal",
    "SideEffect",
    "ToolInput",
    "build_tool_offline",
    "debate_scripts",
]

