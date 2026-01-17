"""
配置管理
"""
import os
from pathlib import Path


# 工作目录
BASE_WORK_DIR = Path(os.getenv("WORK_DIR", "./offline_build_workspace")).absolute()
LOG_DIR = BASE_WORK_DIR / "logs"

# 确保目录存在
BASE_WORK_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 超时设置
BUILD_TIMEOUT = int(os.getenv("BUILD_TIMEOUT", "1800"))  # 30分钟
RUN_TIMEOUT = int(os.getenv("RUN_TIMEOUT", "300"))  # 5分钟

# LLM 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

# 辩论和执行限制
MAX_DEBATE_ROUNDS = int(os.getenv("MAX_DEBATE_ROUNDS", "10"))
MAX_EXECUTION_ATTEMPTS = int(os.getenv("MAX_EXECUTION_ATTEMPTS", "10"))

