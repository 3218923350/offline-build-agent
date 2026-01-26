"""
离线构建 Agent 命令行入口
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from .builder import build_tool_offline
from .models import ToolInput
from dotenv import load_dotenv


def load_tools_from_json(json_path: Path) -> List[ToolInput]:
    """从 JSON 文件加载工具列表"""
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    tools = []
    if isinstance(data, list):
        for item in data:
            tools.append(ToolInput(
                tool_name=item.get("tool_name", item.get("name", "unknown")),
                dockerfile=item.get("dockerfile", ""),
                usage_entry_command=item.get("usage_entry_command", ""),
                tool_id=item.get("id", item.get("tool_id", "")),
            ))
    elif isinstance(data, dict):
        # 如果是单个工具
        tools.append(ToolInput(
            tool_name=data.get("tool_name", data.get("name", "unknown")),
            dockerfile=data.get("dockerfile", ""),
            usage_entry_command=data.get("usage_entry_command", ""),
            tool_id=data.get("id", data.get("tool_id", "")),
        ))
    
    return tools


def generate_final_report(output_dir: Path):
    """生成最终统计报告"""
    total = 0
    success = 0
    failure_by_type = {
        "debate_limit": 0,
        "execution_limit": 0,
        "model_reject": 0,
        "other": 0,
    }
    
    report_path = output_dir / "final_report.txt"
    
    with report_path.open("w", encoding="utf-8") as f:
        f.write("# 离线构建最终报告\n\n")
        
        for tool_dir in sorted(output_dir.iterdir()):
            if not tool_dir.is_dir():
                continue
            
            summary_file = tool_dir / "summary.json"
            if not summary_file.exists():
                continue
            
            total += 1
            with summary_file.open("r", encoding="utf-8") as sf:
                summary = json.load(sf)
            
            tool_name = summary.get("tool_name", "unknown")
            tool_success = summary.get("success", False)
            
            if tool_success:
                success += 1
                f.write(f"✅ {tool_name}\n")
            else:
                failure_type = summary.get("failure_type", "other")
                failure_reason = summary.get("failure_reason", "未知")
                failure_by_type[failure_type] = failure_by_type.get(failure_type, 0) + 1
                f.write(f"❌ {tool_name}\n")
                f.write(f"   失败类型: {failure_type}\n")
                f.write(f"   原因: {failure_reason}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("## 统计摘要\n\n")
        f.write(f"总工具数: {total}\n")
        if total > 0:
            f.write(f"成功: {success} ({success/total*100:.1f}%)\n")
            f.write(f"失败: {total - success} ({(total-success)/total*100:.1f}%)\n\n")
        else:
            f.write("成功: 0\n")
            f.write("失败: 0\n")
            f.write("注意: 没有找到任何工具结果\n\n")
        f.write("失败原因分布:\n")
        for ftype, count in failure_by_type.items():
            if count > 0:
                f.write(f"  - {ftype}: {count}\n")
    
    print(f"\n最终报告已生成: {report_path}")
    print(f"总工具数: {total}")
    if total > 0:
        print(f"成功: {success} ({success/total*100:.1f}%)")
        print(f"失败: {total - success} ({(total-success)/total*100:.1f}%)")
    else:
        print("成功: 0")
        print("失败: 0")
        print("注意: 没有找到任何工具结果，可能所有任务都被中断或未完成")


def main(argv: Optional[List[str]] = None):
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="离线构建 Agent - 将 Docker 工具转换为无网环境可编译的脚本"
    )
    
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="输入 JSON 文件路径（包含工具列表）",
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="./offline_build_output",
        help="输出目录（默认: ./offline_build_output）",
    )
    
    parser.add_argument(
        "--model-a",
        type=str,
        default=os.getenv("OPENAI_MODEL", "gpt-4o"),
        help="模型A名称（默认: gpt-4o）",
    )
    
    parser.add_argument(
        "--model-b",
        type=str,
        default=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
        help="模型B名称（默认: gemini-2.0-flash-exp）",
    )
    
    parser.add_argument(
        "--max-debate-rounds",
        type=int,
        default=10,
        help="最大辩论轮次（默认: 10）",
    )
    
    parser.add_argument(
        "--max-execution-attempts",
        type=int,
        default=10,
        help="最大执行尝试次数（默认: 10）",
    )
    
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="从第几个工具开始处理（默认: 0）",
    )
    
    parser.add_argument(
        "--end-index",
        type=int,
        default=-1,
        help="处理到第几个工具（默认: -1，处理全部）",
    )
    
    args = parser.parse_args(argv)
    
    # 检查输入文件
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}")
        sys.exit(1)
    
    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 初始化模型客户端
    print("初始化模型客户端...")
    
    # 模型A (OpenAI/GPT)
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not openai_api_key:
        print("警告: OPENAI_API_KEY 未设置")
    
    model_a_client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
    model_a_name = args.model_a
    
    # 模型B (Gemini)
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    gemini_base_url = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    if not gemini_api_key:
        print("警告: GEMINI_API_KEY 未设置")
    
    model_b_client = OpenAI(api_key=gemini_api_key, base_url=gemini_base_url)
    model_b_name = args.model_b
    
    print(f"模型A: {model_a_name}")
    print(f"模型B: {model_b_name}")
    
    # 加载工具列表
    print(f"\n加载工具列表: {input_path}")
    tools = load_tools_from_json(input_path)
    print(f"共加载 {len(tools)} 个工具")
    
    # 切片处理
    start_idx = args.start_index
    end_idx = args.end_index if args.end_index > 0 else len(tools)
    tools_to_process = tools[start_idx:end_idx]
    print(f"将处理: {len(tools_to_process)} 个工具 (索引 {start_idx} 到 {end_idx-1})")
    
    # 处理每个工具
    results = []
    for idx, tool in enumerate(tools_to_process, start=start_idx):
        print(f"\n{'#'*80}")
        print(f"处理进度: {idx + 1 - start_idx}/{len(tools_to_process)}")
        print(f"{'#'*80}")
        
        try:
            result = build_tool_offline(
                tool_input=tool,
                model_a_client=model_a_client,
                model_a_name=model_a_name,
                model_b_client=model_b_client,
                model_b_name=model_b_name,
                output_dir=output_dir,
                max_debate_rounds=args.max_debate_rounds,
                max_execution_attempts=args.max_execution_attempts,
            )
            results.append(result)
        except KeyboardInterrupt:
            print("\n\n用户中断，生成当前报告...")
            break
        except Exception as e:
            print(f"\n处理工具 {tool.tool_name} 时发生异常: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 生成最终报告
    print("\n" + "="*80)
    print("所有工具处理完成，生成最终报告...")
    print("="*80)
    generate_final_report(output_dir)
    
    print(f"\n所有结果已保存到: {output_dir}")


if __name__ == "__main__":
    main()

