"""
离线构建核心逻辑
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config
from .llm import debate_scripts
from .models import (
    BuildResult,
    ExecutionResult,
    OfflineBuildSummary,
    ScriptProposal,
    ToolInput,
)
from .utils import ensure_dir, slugify


def execute_shell_script(
    script_content: str,
    script_name: str,
    work_dir: Path,
    timeout: int = 1800,
    use_netns: bool = False,
) -> ExecutionResult:
    """
    执行 shell 脚本
    
    Args:
        script_content: 脚本内容
        script_name: 脚本文件名
        work_dir: 工作目录
        timeout: 超时时间（秒）
        use_netns: 是否使用网络命名空间（无网环境）
    """
    script_path = work_dir / script_name
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(0o755)
    
    # 确保使用绝对路径
    script_path_abs = script_path.resolve()
    work_dir_abs = work_dir.resolve()
    
    # 验证文件确实存在
    if not script_path_abs.exists():
        return ExecutionResult(
            stage=script_name,
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error_message=f"脚本文件不存在: {script_path_abs}",
        )
    
    # 验证文件可执行
    if not os.access(script_path_abs, os.X_OK):
        return ExecutionResult(
            stage=script_name,
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error_message=f"脚本文件不可执行: {script_path_abs}",
        )
    
    if use_netns:
        # 进入无网环境: ip netns exec offline bash -c "ip link set lo up && bash script.sh"
        cmd = [
            "ip", "netns", "exec", "offline",
            "bash", "-c",
            f"ip link set lo up && cd {work_dir_abs} && bash {script_name}"
        ]
    else:
        # 使用绝对路径执行脚本
        cmd = ["bash", str(script_path_abs)]
    
    # 调试信息：打印实际执行的命令和路径
    print(f"  [调试] 执行命令: {' '.join(cmd)}")
    print(f"  [调试] 工作目录: {work_dir_abs}")
    print(f"  [调试] 脚本路径: {script_path_abs}")
    print(f"  [调试] 脚本存在: {script_path_abs.exists()}")
    print(f"  [调试] 脚本可执行: {os.access(script_path_abs, os.X_OK)}")
    
    try:
        # 确保工作目录是绝对路径
        result = subprocess.run(
            cmd,
            cwd=str(work_dir_abs),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        # 如果执行失败，从 stderr 或 stdout 中提取错误信息
        error_message = ""
        if result.returncode != 0:
            # 优先使用 stderr，如果 stderr 为空则使用 stdout 的最后几行
            if result.stderr and result.stderr.strip():
                # 取 stderr 的最后500字符，避免太长
                error_message = result.stderr.strip()[-3000:] if len(result.stderr) > 3000 else result.stderr.strip()
            elif result.stdout and result.stdout.strip():
                # 如果 stderr 为空，从 stdout 中提取最后几行
                lines = result.stdout.strip().split('\n')
                error_message = '\n'.join(lines[-100:])  # 取最后10行
            else:
                error_message = f"脚本执行失败，退出码: {result.returncode}"
        
        return ExecutionResult(
            stage=script_name,
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            error_message=error_message,
        )
    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            stage=script_name,
            success=False,
            stdout=e.stdout.decode("utf-8", errors="ignore") if e.stdout else "",
            stderr=e.stderr.decode("utf-8", errors="ignore") if e.stderr else "",
            exit_code=-1,
            error_message=f"执行超时（{timeout}秒）",
        )
    except Exception as e:
        return ExecutionResult(
            stage=script_name,
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error_message=f"执行异常: {e}",
        )


def verify_tool(
    usage_entry_command: str,
    tool_dir: Path,
    timeout: int = 300,
) -> ExecutionResult:
    """验证工具是否可用"""
    # 调整验证命令路径（将系统 python 替换为工具的 python）
    adjusted_cmd = usage_entry_command
    
    # 如果命令以 python 开头，替换为工具目录下的 python
    if adjusted_cmd.startswith("python ") or adjusted_cmd == "python":
        python_paths = [
            tool_dir / "bin" / "python",
            tool_dir / "miniforge3" / "bin" / "python",
            tool_dir / "venv" / "bin" / "python",
        ]
        for py_path in python_paths:
            if py_path.exists():
                adjusted_cmd = adjusted_cmd.replace("python", str(py_path), 1)
                break
    
    try:
        result = subprocess.run(
            adjusted_cmd,
            shell=True,
            cwd=tool_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        return ExecutionResult(
            stage="verify",
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )
    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            stage="verify",
            success=False,
            stdout=e.stdout.decode("utf-8", errors="ignore") if e.stdout else "",
            stderr=e.stderr.decode("utf-8", errors="ignore") if e.stderr else "",
            exit_code=-1,
            error_message=f"验证超时（{timeout}秒）",
        )
    except Exception as e:
        return ExecutionResult(
            stage="verify",
            success=False,
            stdout="",
            stderr="",
            exit_code=-1,
            error_message=f"验证异常: {e}",
        )


def write_build_log(log_path: Path, build_result: BuildResult):
    """写入详细的构建日志"""
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"# 离线构建日志: {build_result.tool_name}\n\n")
        f.write(f"工具ID: {build_result.tool_id}\n")
        f.write(f"最终结果: {'✅ 成功' if build_result.success else '❌ 失败'}\n")
        f.write(f"失败类型: {build_result.failure_type}\n\n")
        
        f.write("## 辩论过程\n\n")
        for round in build_result.debate_rounds:
            f.write(f"### 第 {round.round_index} 轮\n\n")
            f.write(f"**提案者**: {round.proposer_name}\n")
            f.write(f"**评审者**: {round.reviewer_name}\n\n")
            f.write(f"**提案者判断**: can_run={round.proposal.can_run}\n")
            f.write(f"**理由**: {round.proposal.reason}\n\n")
            f.write(f"**Online 脚本**:\n```bash\n{round.proposal.online_script}\n```\n\n")
            f.write(f"**Offline 脚本**:\n```bash\n{round.proposal.offline_script}\n```\n\n")
            f.write(f"**评审者判断**: can_run={round.review_can_run}\n")
            f.write(f"**建议**: {round.review_suggestions}\n\n")
            f.write("---\n\n")
        
        f.write("## 执行历史\n\n")
        for exec_result in build_result.execution_history:
            f.write(f"### 阶段: {exec_result.stage}\n\n")
            f.write(f"**结果**: {'✅ 成功' if exec_result.success else '❌ 失败'}\n")
            f.write(f"**退出码**: {exec_result.exit_code}\n\n")
            if exec_result.error_message:
                f.write(f"**错误信息**: {exec_result.error_message}\n\n")
            f.write(f"**STDOUT**:\n```\n{exec_result.stdout}\n```\n\n")
            f.write(f"**STDERR**:\n```\n{exec_result.stderr}\n```\n\n")
            f.write("---\n\n")
        
        f.write(f"## 最终结论\n\n{build_result.final_reason}\n")


def write_summary(summary_path: Path, summary: OfflineBuildSummary):
    """写入简要结论"""
    with summary_path.open("w", encoding="utf-8") as f:
        data = {
            "tool_name": summary.tool_name,
            "tool_id": summary.tool_id,
            "success": summary.success,
            "debate_rounds": summary.debate_rounds,
            "execution_attempts": summary.execution_attempts,
            "failure_type": summary.failure_type,
            "failure_reason": summary.failure_reason,
            "final_scripts_ok": summary.final_scripts_ok,
        }
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_tool_offline(
    tool_input: ToolInput,
    model_a_client,
    model_a_name: str,
    model_b_client,
    model_b_name: str,
    output_dir: Path,
    max_debate_rounds: int = 10,
    max_execution_attempts: int = 10,
) -> BuildResult:
    """
    为单个工具构建离线脚本并验证
    
    Args:
        tool_input: 工具输入信息
        model_a_client: 模型A客户端
        model_a_name: 模型A名称
        model_b_client: 模型B客户端
        model_b_name: 模型B名称
        output_dir: 输出目录
        max_debate_rounds: 最大辩论轮次
        max_execution_attempts: 最大执行尝试次数
    """
    tool_slug = slugify(tool_input.tool_name)
    tool_output_dir = output_dir / tool_slug
    ensure_dir(tool_output_dir)
    
    print(f"\n{'='*80}")
    print(f"开始处理工具: {tool_input.tool_name}")
    print(f"{'='*80}\n")
    
    debate_history = []
    execution_history = []
    execution_failures = []
    
    final_proposal: Optional[ScriptProposal] = None
    success = False
    failure_type = ""
    final_reason = ""
    
    # 主循环：辩论 -> 执行 -> 反馈
    total_attempts = 0
    
    while total_attempts < max_execution_attempts:
        # Phase 1: 辩论生成脚本
        print(f"\n[主循环] 尝试 {total_attempts + 1}/{max_execution_attempts}")
        
        proposal, debate_history, should_execute = debate_scripts(
            tool_name=tool_input.tool_name,
            dockerfile=tool_input.dockerfile,
            usage_entry_command=tool_input.usage_entry_command,
            model_a_client=model_a_client,
            model_a_name=model_a_name,
            model_b_client=model_b_client,
            model_b_name=model_b_name,
            max_debate_rounds=max_debate_rounds,
            execution_failures=execution_failures,
            history=debate_history,
        )
        
        final_proposal = proposal
        
        # 检查辩论结果
        if not should_execute:
            # 双方都拒绝或达到辩论上限
            if len(debate_history) >= max_debate_rounds:
                failure_type = "debate_limit"
                final_reason = f"辩论达到上限（{max_debate_rounds}轮），双方未能达成一致"
            else:
                failure_type = "model_reject"
                final_reason = "双方模型都认为该工具无法在离线环境编译"
            break
        
        # Phase 2: 执行 online 脚本
        print("\n[执行] 开始执行 online 脚本...")
        online_result = execute_shell_script(
            script_content=proposal.online_script,
            script_name="00_fetch_and_build_online.sh",
            work_dir=tool_output_dir,
            timeout=1800,
            use_netns=False,
        )
        execution_history.append(online_result)
        
        if not online_result.success:
            # 构建详细的错误信息
            error_info = online_result.error_message or "未知错误"
            if online_result.exit_code != -1:
                error_info = f"退出码: {online_result.exit_code}, {error_info}"
            
            print(f"  ❌ Online 脚本执行失败: {error_info}")
            # 打印 stderr 的最后几行（如果有）
            if online_result.stderr:
                stderr_lines = online_result.stderr.strip().split('\n')
                if stderr_lines:
                    print(f"  错误输出（最后5行）:")
                    for line in stderr_lines[-5:]:
                        print(f"    {line}")
            
            failure_log = f"Online阶段失败:\n退出码: {online_result.exit_code}\n错误信息: {error_info}\nSTDOUT:\n{online_result.stdout}\nSTDERR:\n{online_result.stderr}"
            execution_failures.append(failure_log)
            total_attempts += 1
            continue
        
        print("  ✅ Online 脚本执行成功")
        
        # Phase 3: 执行 offline 脚本（无网环境）
        print("\n[执行] 开始执行 offline 脚本（无网环境）...")
        offline_result = execute_shell_script(
            script_content=proposal.offline_script,
            script_name="01_build_offline.sh",
            work_dir=tool_output_dir,
            timeout=1800,
            use_netns=True,
        )
        execution_history.append(offline_result)
        
        if not offline_result.success:
            # 构建详细的错误信息
            error_info = offline_result.error_message or "未知错误"
            if offline_result.exit_code != -1:
                error_info = f"退出码: {offline_result.exit_code}, {error_info}"
            
            print(f"  ❌ Offline 脚本执行失败: {error_info}")
            # 打印 stderr 的最后几行（如果有）
            if offline_result.stderr:
                stderr_lines = offline_result.stderr.strip().split('\n')
                if stderr_lines:
                    print(f"  错误输出（最后5行）:")
                    for line in stderr_lines[-5:]:
                        print(f"    {line}")
            
            failure_log = f"Offline阶段失败:\n退出码: {offline_result.exit_code}\n错误信息: {error_info}\nSTDOUT:\n{offline_result.stdout}\nSTDERR:\n{offline_result.stderr}"
            execution_failures.append(failure_log)
            total_attempts += 1
            continue
        
        print("  ✅ Offline 脚本执行成功")
        
        # Phase 4: 验证工具
        print("\n[验证] 开始验证工具...")
        verify_result = verify_tool(
            usage_entry_command=tool_input.usage_entry_command,
            tool_dir=tool_output_dir,
            timeout=300,
        )
        execution_history.append(verify_result)
        
        if not verify_result.success:
            # 构建详细的错误信息
            error_info = verify_result.error_message or "未知错误"
            if verify_result.exit_code != -1:
                error_info = f"退出码: {verify_result.exit_code}, {error_info}"
            
            print(f"  ❌ 工具验证失败: {error_info}")
            # 打印 stderr 的最后几行（如果有）
            if verify_result.stderr:
                stderr_lines = verify_result.stderr.strip().split('\n')
                if stderr_lines:
                    print(f"  错误输出（最后5行）:")
                    for line in stderr_lines[-5:]:
                        print(f"    {line}")
            
            failure_log = f"验证阶段失败:\n退出码: {verify_result.exit_code}\n错误信息: {error_info}\nSTDOUT:\n{verify_result.stdout}\nSTDERR:\n{verify_result.stderr}"
            execution_failures.append(failure_log)
            total_attempts += 1
            continue
        
        print("  ✅ 工具验证成功")
        
        # 成功！
        success = True
        final_reason = f"成功！经过 {len(debate_history)} 轮辩论，{total_attempts + 1} 次执行尝试"
        break
    
    # 检查是否因执行次数耗尽而失败
    if not success and total_attempts >= max_execution_attempts:
        failure_type = "execution_limit"
        final_reason = f"执行次数达到上限（{max_execution_attempts}次），仍未成功"
    
    # 构建结果
    build_result = BuildResult(
        tool_name=tool_input.tool_name,
        tool_id=tool_input.tool_id,
        success=success,
        online_script=final_proposal.online_script if final_proposal else "",
        offline_script=final_proposal.offline_script if final_proposal else "",
        debate_rounds=debate_history,
        execution_history=execution_history,
        final_reason=final_reason,
        failure_type=failure_type,
    )
    
    # 写入日志和总结
    log_path = tool_output_dir / "build.log"
    summary_path = tool_output_dir / "summary.json"
    
    write_build_log(log_path, build_result)
    
    summary = OfflineBuildSummary(
        tool_name=tool_input.tool_name,
        tool_id=tool_input.tool_id,
        success=success,
        debate_rounds=len(debate_history),
        execution_attempts=total_attempts,
        failure_type=failure_type,
        failure_reason=final_reason,
        final_scripts_ok=final_proposal.can_run if final_proposal else False,
    )
    write_summary(summary_path, summary)
    
    # 保留最终脚本
    if final_proposal:
        (tool_output_dir / "00_fetch_and_build_online.sh").write_text(
            final_proposal.online_script, encoding="utf-8"
        )
        (tool_output_dir / "01_build_offline.sh").write_text(
            final_proposal.offline_script, encoding="utf-8"
        )
    
    # 清理中间产物（保留脚本和日志）
    cleanup_build_artifacts(tool_output_dir)
    
    print(f"\n{'='*80}")
    print(f"工具 {tool_input.tool_name} 处理完成: {'✅ 成功' if success else '❌ 失败'}")
    print(f"{'='*80}\n")
    
    return build_result


def cleanup_build_artifacts(tool_dir: Path):
    """清理构建产物，只保留脚本和日志"""
    keep_files = {
        "00_fetch_and_build_online.sh",
        "01_build_offline.sh",
        "build.log",
        "summary.json",
    }
    
    for item in tool_dir.iterdir():
        if item.name not in keep_files:
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                print(f"[清理] 无法删除 {item}: {e}")

