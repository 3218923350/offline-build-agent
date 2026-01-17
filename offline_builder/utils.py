"""
工具函数
"""
import re
import unicodedata
from pathlib import Path


def slugify(text: str) -> str:
    """
    将文本转换为合法的文件名/目录名
    """
    text = str(text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-_")
    return text or "unknown"


def ensure_dir(path: Path) -> Path:
    """
    确保目录存在
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def summarize_text(text: str, max_chars: int = 3000) -> str:
    """
    截断文本到指定长度
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... (truncated, total {len(text)} chars)"

