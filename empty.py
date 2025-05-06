'''
Author: caoshiyue caoshiyueKevin@Gmail.com
Date: 2025-05-04 03:36:54
LastEditors: caoshiyue caoshiyueKevin@Gmail.com
LastEditTime: 2025-05-04 04:34:55
FilePath: /strategy4/empty.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
import json

# 读取JSON文件

file_path="search_psy/results_v3_based/search_multi_tank_red/deepseek-r1/summary.json"
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 过滤label列表
filtered_labels = [
    item for item in data["label"]
    if item.get("key_output", {}).get("action_A") != "对局A片段描述"
]

# 更新数据
data["label"] = filtered_labels

# 保存修改后的JSON（可以选择覆盖原文件或保存为新文件）
with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
