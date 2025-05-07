##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-05-06 14:49:10
## 
import json
import os
import yaml

def extract_ranked_steps_by_file(summary_path, ranked_path, n_value):
    """
    从 summary.json 和 summary_ranked_results.json 中提取基于排名的步骤信息，
    按单个文件名聚合结果。

    Args:
        summary_path (str): summary.json 文件的路径。
        ranked_path (str): summary_ranked_results.json 文件的路径。
        n_value (int): 需要提取的前 N 个和后 N 个文件数量。

    Returns:
        None: 生成新的 JSON 文件。
    """
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {summary_path} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {summary_path}.")
        return

    try:
        with open(ranked_path, 'r', encoding='utf-8') as f:
            ranked_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {ranked_path} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {ranked_path}.")
        return

    ranked_files_list = ranked_data.get('ranked_files_iterative', [])
    if not ranked_files_list:
        print("Warning: 'ranked_files_iterative' list is empty or not found.")
        return

    list_length = len(ranked_files_list)

    # 获取前 N 个和后 N 个文件名列表
    top_n_files = ranked_files_list[:n_value]
    # 防止 N 过大导致后 N 个为空或与前 N 个重叠过多
    if n_value >= list_length:
         bottom_n_files = []
    else:
        bottom_n_files = ranked_files_list[-n_value:]

    # 构建一个字典，将 summary.json 中的步骤信息按单个文件名归类
    steps_by_individual_file = {}

    for item in summary_data.get('label', []):
        full_path = item.get('path')
        key_output = item.get('key_output')
        if not full_path or not key_output:
            continue

        parts = full_path.split('__')
        if len(parts) == 2:
            # file1_raw = parts[0] # 第一个文件名本身就和 ranked list 格式一致 (无 .json)
            file1 = parts[0]
            # file2_raw = parts[1] # 第二个文件名带 .json 后缀
            file2 = parts[1].replace('.json', '') # 移除 .json 进行匹配

            step_a = key_output.get('step_A')
            step_b = key_output.get('step_B')

            # 将 step_A 添加到 file1 对应的列表中
            if file1 and step_a:
                if file1 not in steps_by_individual_file:
                    steps_by_individual_file[file1] = []
                steps_by_individual_file[file1].append(step_a)

            # 将 step_B 添加到 file2 对应的列表中
            if file2 and step_b:
                if file2 not in steps_by_individual_file:
                    steps_by_individual_file[file2] = []
                steps_by_individual_file[file2].append(step_b)

    # 构建 first 列表
    first_list = []
    for filename in top_n_files:
        if filename in steps_by_individual_file:
            # 获取该文件名的所有步骤，并去重，保持顺序
            steps = list(dict.fromkeys(steps_by_individual_file[filename]))
            first_list.append({
                "path": f"{filename}.json", # 输出路径为文件名 + .json
                "steps": steps
            })

    # 构建 last 列表
    last_list = []
    for filename in bottom_n_files:
         if filename in steps_by_individual_file:
            # 获取该文件名的所有步骤，并去重，保持顺序
            steps = list(dict.fromkeys(steps_by_individual_file[filename]))
            last_list.append({
                "path": f"{filename}.json", # 输出路径为文件名 + .json
                "steps": steps
            })

    # 构建新的 meta 信息
    original_meta = summary_data.get('meta', {})
    new_meta = {
        "task": original_meta.get("task", "unknown_task"),
        "timestamp": original_meta.get("timestamp", ""),
        "model": original_meta.get("model", "")
    }

    # 构建最终输出结构
    output_data = {
        "meta": new_meta,
        "first": first_list,
        "last": last_list
    }

    # 生成输出文件名
    task_name = new_meta.get("task", "unknown_task")
    output_filename = f"extract/extract_{task_name}.json"

    # 写入新的 JSON 文件
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Successfully generated {output_filename}")
    except IOError:
        print(f"Error: Could not write to file {output_filename}.")


def run(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    task_name = config['task']
    task_dir = os.path.join(config['output_base'], task_name)

    # 遍历所有模型结果
    for model_name in os.listdir(task_dir):
        summary_path = os.path.join(task_dir, model_name, "summary.json")
        ranked_path = os.path.join(task_dir, model_name, "summary_ranked_results.json")
        if not os.path.exists(ranked_path):
            continue
        try:
            
            extract_ranked_steps_by_file(summary_path,ranked_path,N)
        except Exception as e:
            print(e)
            continue


if __name__ == "__main__":
    N = 10  # 您希望提取的前 N 个和后 N 个文件数量

    run("configs/config3.yaml")
