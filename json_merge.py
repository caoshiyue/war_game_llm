##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-05-23 13:44:27
## 
import json
import os

def merge_chunk_analysis_results(json_file_path):
    # 读取JSON文件
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 检查并合并chunk_analysis_results中的content
    if "sides_data" in data :
        for i,content_i in enumerate(data["sides_data"]) :
            if  "chunk_analysis_results" in content_i:
                chunk_analysis_results = content_i["chunk_analysis_results"]
                if chunk_analysis_results==[] and content_i["color"]=="Red":
                    os.remove(json_file_path)
                    return
            if len(chunk_analysis_results) > 1:
                # 合并多个content
                merged_content = ''.join(item["llm_analysis"] for item in chunk_analysis_results)
                data["sides_data"][i]["chunk_analysis_results"] = [{"llm_analysis": merged_content}]
            elif len(chunk_analysis_results) == 1:
                # 只有一个元素，保持不变
                pass

    # 将修改后的数据写回文件
    with open(json_file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def delete_files_with_error(folder_path):
    """
    遍历指定文件夹中的所有文件，如果文件内容包含 "error" 字符串，则删除该文件。

    Args:
        folder_path (str): 要检测的文件夹路径。
    """
    if not os.path.isdir(folder_path):
        print(f"错误：文件夹 '{folder_path}' 不存在或不是一个有效的文件夹。")
        return

    print(f"开始检测文件夹：'{folder_path}' 中的文件...")
    deleted_files_count = 0

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if "API 调用失败" in content:
                        print(f"  发现文件 '{filename}' 包含 'error'，正在删除...")
                        os.remove(file_path)
                        deleted_files_count += 1
                    else:
                        print(f"  文件 '{filename}' 未包含 'error'，跳过。")
            except Exception as e:
                print(f"  读取文件 '{filename}' 时发生错误：{e}")
        else:
            print(f"  跳过非文件项：'{filename}'")

    print(f"\n检测完成。共删除 {deleted_files_count} 个包含 'error' 的文件。")

# 指定文件夹路径
folder_path = 'data/section1'

delete_files_with_error(folder_path)
# 遍历文件夹中的JSON文件
for filename in os.listdir(folder_path):
    if filename.endswith('.json'):
        json_file_path = os.path.join(folder_path, filename)
        merge_chunk_analysis_results(json_file_path)
