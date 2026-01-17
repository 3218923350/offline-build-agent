"""
API 服务 - 提供 HTTP 接口

使用 FastAPI 提供 RESTful API 服务
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from openai import OpenAI

from .builder import build_tool_offline
from .models import ToolInput

# 初始化 FastAPI
app = FastAPI(
    title="离线构建 Agent API",
    description="将 Dockerfile 转换为离线可执行脚本",
    version="1.0.0",
)

# 任务状态存储
tasks: Dict[str, Dict] = {}

# 输出目录
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./api_output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class BuildRequest(BaseModel):
    """构建请求"""
    tool_name: str
    dockerfile: str
    usage_entry_command: str
    tool_id: Optional[str] = None
    model_a: Optional[str] = "gpt-4o"
    model_b: Optional[str] = "gemini-2.0-flash-exp"
    max_debate_rounds: Optional[int] = 10
    max_execution_attempts: Optional[int] = 10


class BatchBuildRequest(BaseModel):
    """批量构建请求"""
    tools: List[BuildRequest]


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # "pending" | "running" | "completed" | "failed"
    tool_name: str
    progress: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None


def run_build_task(task_id: str, request: BuildRequest):
    """后台运行构建任务"""
    try:
        # 更新状态为运行中
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = "初始化模型客户端..."
        
        # 初始化模型客户端
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        gemini_base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
        
        model_a_client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
        model_b_client = OpenAI(api_key=gemini_api_key, base_url=gemini_base_url)
        
        # 准备工具输入
        tool_input = ToolInput(
            tool_name=request.tool_name,
            dockerfile=request.dockerfile,
            usage_entry_command=request.usage_entry_command,
            tool_id=request.tool_id or task_id,
        )
        
        tasks[task_id]["progress"] = "开始构建..."
        
        # 执行构建
        result = build_tool_offline(
            tool_input=tool_input,
            model_a_client=model_a_client,
            model_a_name=request.model_a,
            model_b_client=model_b_client,
            model_b_name=request.model_b,
            output_dir=OUTPUT_DIR,
            max_debate_rounds=request.max_debate_rounds,
            max_execution_attempts=request.max_execution_attempts,
        )
        
        # 更新状态为完成
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = {
            "success": result.success,
            "tool_name": result.tool_name,
            "tool_id": result.tool_id,
            "debate_rounds": len(result.debate_rounds),
            "execution_attempts": len(result.execution_history),
            "failure_type": result.failure_type,
            "final_reason": result.final_reason,
        }
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "离线构建 Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/v1/build": "提交构建任务",
            "POST /api/v1/build/batch": "批量提交构建任务",
            "GET /api/v1/tasks/{task_id}": "查询任务状态",
            "GET /api/v1/tasks/{task_id}/logs": "下载任务日志",
            "GET /api/v1/tasks/{task_id}/scripts": "下载生成的脚本",
        }
    }


@app.post("/api/v1/build", response_model=TaskStatus)
async def create_build_task(request: BuildRequest, background_tasks: BackgroundTasks):
    """
    提交构建任务
    """
    task_id = str(uuid.uuid4())
    
    # 初始化任务状态
    tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "tool_name": request.tool_name,
        "progress": None,
        "result": None,
        "error": None,
    }
    
    # 添加后台任务
    background_tasks.add_task(run_build_task, task_id, request)
    
    return TaskStatus(**tasks[task_id])


@app.post("/api/v1/build/batch")
async def create_batch_build_tasks(request: BatchBuildRequest, background_tasks: BackgroundTasks):
    """
    批量提交构建任务
    """
    task_ids = []
    
    for tool_request in request.tools:
        task_id = str(uuid.uuid4())
        
        tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "tool_name": tool_request.tool_name,
            "progress": None,
            "result": None,
            "error": None,
        }
        
        background_tasks.add_task(run_build_task, task_id, tool_request)
        task_ids.append(task_id)
    
    return {"task_ids": task_ids, "count": len(task_ids)}


@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    查询任务状态
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskStatus(**tasks[task_id])


@app.get("/api/v1/tasks/{task_id}/logs")
async def get_task_logs(task_id: str):
    """
    下载任务日志
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    tool_name = task["tool_name"]
    
    # 查找日志文件
    from .utils import slugify
    tool_slug = slugify(tool_name)
    log_file = OUTPUT_DIR / tool_slug / "build.log"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")
    
    return FileResponse(
        path=log_file,
        filename=f"{tool_slug}_build.log",
        media_type="text/plain",
    )


@app.get("/api/v1/tasks/{task_id}/scripts")
async def get_task_scripts(task_id: str):
    """
    下载生成的脚本（压缩包）
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    tool_name = task["tool_name"]
    
    from .utils import slugify
    tool_slug = slugify(tool_name)
    tool_dir = OUTPUT_DIR / tool_slug
    
    # 创建压缩包
    import shutil
    import tempfile
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
        archive_path = tmp.name
    
    shutil.make_archive(
        archive_path.replace(".tar.gz", ""),
        "gztar",
        tool_dir,
    )
    
    return FileResponse(
        path=archive_path,
        filename=f"{tool_slug}_scripts.tar.gz",
        media_type="application/gzip",
    )


@app.get("/api/v1/tasks")
async def list_tasks():
    """
    列出所有任务
    """
    return {
        "tasks": [TaskStatus(**task) for task in tasks.values()],
        "count": len(tasks),
    }


@app.get("/health")
async def health_check():
    """
    健康检查
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)

