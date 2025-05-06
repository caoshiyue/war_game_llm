##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-04-22 06:13:44
## 
import json

with open("search_psy/results_v3_based/search_Return_red/deepseek-r1/summary.json", 'r', encoding='utf-8') as file:
    data = json.load(file)

output_lines = []
for item in data["label"]:
    if item["answer"] == "A":
        output_lines.append(item["key_output"]["action_A"])
    elif item["answer"] == "B":
        output_lines.append(item["key_output"]["action_B"])

with open("output.txt", "w", encoding="utf-8") as f:
    for line in output_lines:
        f.write(line + "\n")

print("提取结果已写入到 output.txt 文件中。")