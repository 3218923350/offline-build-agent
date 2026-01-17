import pandas as pd
import json

# 1. 读取 Excel 文件
excel_path = "执行结果5.xlsx"   # 如果不在当前目录，请写完整路径
df = pd.read_excel(excel_path)

# 2. 构造目标 JSON 结构
result = []

for idx, row in df.iterrows():
    item = {
        "tool_name": str(row["name"]),
        "tool_id": str(idx + 1),  # tool_id 从 1 开始
        "dockerfile": str(row["dockerfile"]),
        "usage_entry_command": str(row["usage_entry_command"]),
    }
    result.append(item)

# 3. 写入 JSON 文件（保持 Dockerfile 的换行）
output_path = "tools.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"转换完成，已生成 {output_path}")
