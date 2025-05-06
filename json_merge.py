##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-04-21 07:44:26
## 
import json
import os

def merge_chunks_results(json_file_path):
    # 读取JSON文件
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 检查并合并chunks_results中的content
    if "analyze_1" in data and "chunks_results" in data["analyze_1"]:
        chunks_results = data["analyze_1"]["chunks_results"]
        
        if len(chunks_results) > 1:
            # 合并多个content
            merged_content = ''.join(item["content"] for item in chunks_results)
            data["analyze_1"]["chunks_results"] = [{"content": merged_content}]
        elif len(chunks_results) == 1:
            # 只有一个元素，保持不变
            pass

    # 将修改后的数据写回文件
    with open(json_file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# 指定文件夹路径
folder_path = 'data/results_overall_deepseek_v3'

# 遍历文件夹中的JSON文件
for filename in os.listdir(folder_path):
    if filename.endswith('.json'):
        json_file_path = os.path.join(folder_path, filename)
        merge_chunks_results(json_file_path)
