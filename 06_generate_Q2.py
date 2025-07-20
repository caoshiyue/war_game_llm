##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-06-03 06:30:00
## 
'''
Author: Likun Yang
Date: 2025-05-07 14:26:06
LastEditors: caoshiyue caoshiyueKevin@Gmail.com
LastEditTime: 2025-05-30 08:14:12
Copyright (c) 2025 by Likun Yang, All Rights Reserved. 
'''
import json
import os
import random
import itertools
import datetime
from tqdm import tqdm
import yaml
def load_json(filepath):
    """Loads a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"错误：解码JSON文件失败 {filepath}")
        return None

def save_json(data, filepath):
    """Saves data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"错误：保存文件失败 {filepath}: {e}")

def get_content_from_file(filename, base_dir, content):
    """Reads a file from base_dir and returns its 'content' field."""
    filepath = os.path.join(base_dir, filename)
    data = load_json(filepath)
    if data and content in data:
        return data[content]
    else:
        print(f"警告：文件 {filepath} 不存在或缺少 {content} 字段。")
        return None

def generate_question_combinations(data):
    """Generates combinations of files based on the rules."""
    first_items = data.get('first', [])
    last_items = data.get('last', [])
    combinations = []

    # Rule 1: 1 first, 3 last
    if len(last_items) >= 3:
        for first_item in first_items:
            for last_combo in itertools.combinations(last_items, 2):
                combo_items = [first_item] + list(last_combo)
                combinations.append({
                    'items': combo_items,
                    'ground_truth_path': first_item['path'],
                    'question_type': 'first_single' # Indicates the single item was from 'first'
                })
    else:
        print("警告：'last' 列表中少于3个文件，无法生成 '1 first, 3 last' 组合。")

    # Rule 2: 3 first, 1 last
    if len(first_items) >= 3:
        for last_item in last_items:
            for first_combo in itertools.combinations(first_items, 2):
                combo_items = list(first_combo) + [last_item]
                combinations.append({
                    'items': combo_items,
                    'ground_truth_path': last_item['path'],
                    'question_type': 'last_single' # Indicates the single item was from 'last'
                })
    else:
         print("警告：'first' 列表中少于3个文件，无法生成 '3 first, 1 last' 组合。")


    return combinations

def create_multiple_choice_dataset(input_json_path, content_base_dir, output_dir, character_phrases):
    """
    Creates the multiple-choice question dataset.

    Args:
        input_json_path (str): Path to the main JSON file containing 'first' and 'last' lists.
        content_base_dir (str): Base directory containing content JSON files (e.g., 'extract/search/').
        output_dir (str): Directory to save the generated question JSON files.
    """
    main_data = load_json(input_json_path)
    if main_data is None:
        return

    combinations = generate_question_combinations(main_data)

    if not combinations:
        print("未生成任何有效的题目组合。")
        return
    
    # Randomize the order of questions
    random.shuffle(combinations)

    question_counter = 0
    for combo_info in tqdm(combinations, desc="生成题目"):
        items = combo_info['items']
        ground_truth_path = combo_info['ground_truth_path']
        question_type = combo_info['question_type']

        # --- 要求2：根据文件组合名，获取选项信息 ---
        options_data = []
        valid_combo = True
        for item in items:
            content = get_content_from_file(item['path'], content_base_dir,'content')
            all_step = get_content_from_file(item['path'], content_base_dir,'all_step')
            if content is None:
                # If content is missing for any file, skip this combination
                valid_combo = False
                print(f"跳过组合，因为文件 {item['path']} 的内容无法获取。")
                break
            options_data.append({'path': item['path'], 'content': content,'all_step': all_step})

        if not valid_combo:
            continue # Skip to the next combination if content retrieval failed

        # Randomize the order of options
        random.shuffle(options_data)

        # Assign option labels and find the ground truth label
        option_labels = ['A', 'B', 'C']
        question_json = {
                        "meta":{},
                        "query":{}
                        }
        ground_truth_label = None
        
        question_json["meta"]["id"] = question_counter
        now = datetime.datetime.now()
        question_json["meta"]["time"] = now.strftime("%Y%m%d%H%M%S")

        for i, option_item in enumerate(options_data):
            label = option_labels[i]
            question_json["query"][f"{label}"] = option_item['content']
            question_json["meta"][f"{label}_file_path"] = option_item['path']
            question_json["meta"][f"{label}_all_step"] = option_item['all_step']
            # Find the label corresponding to the ground truth path
            if option_item['path'] == ground_truth_path:
                ground_truth_label = label

        # Formulate the question stem based on the type of single item
        correct_option_text=""
        if question_type == 'first_single':
            stem = f"首先，分别分析复盘中玩家对哪些单位采取了哪些行动。其次，回答哪一个对局中玩家的采取的策略是{character_phrases[0]}，在回答的最后以++A++,++B++,++C++的形式作为答案，若无法判断则回答++E++。"
            correct_option_text= character_phrases[0]
        else: # 'last_single'
            stem = f"首先，分别分析复盘中玩家对哪些单位采取了哪些行动。其次，回答哪一个对局中玩家的采取的策略是{character_phrases[1]}，在回答的最后以++A++,++B++,++C++的形式作为答案，若无法判断则回答++E++。"
            correct_option_text= character_phrases[1]

        question_json["query"]["base_question"] = stem
        question_json["query"]["groundtruth"] = ground_truth_label
        question_json["query"]["groundtruth_description"] = correct_option_text
        
        # Save the generated question
        question_filename = f"question_{question_counter:06d}.json"
        output_filepath = os.path.join(output_dir, question_filename)
        save_json(question_json, output_filepath)
        question_counter += 1

    print(f"\n生成完成。共生成 {question_counter} 道题目文件到目录：{output_dir}")

def run(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        return
    except yaml.YAMLError as e:
        print(f"Error loading config file {config_path}: {e}")
        return
    except Exception as e:
        print(f"Error reading config file {config_path}: {e}")
        return

    task_name = config.get('task')
    data_dir = config.get('data_dir')
    character_phrases = config.get('analysis', {}).get('character')
    
    content_files_base_dir = 'extract/'+task_name
    input_main_data_path = os.path.join(content_files_base_dir,'extract_'+task_name+'.json')

    output_questions_directory = os.path.join(data_dir,task_name)

    # 确保 output 目录存在
    os.makedirs(output_questions_directory, exist_ok=True)

    print(f"开始生成题目数据集，输入文件：{input_main_data_path}，内容目录：{content_files_base_dir}，输出目录：{output_questions_directory}")

    # 调用函数生成数据集
    create_multiple_choice_dataset(input_main_data_path, content_files_base_dir, output_questions_directory,character_phrases)


# --- 示例使用 ---
if __name__ == "__main__":
    configs = [
        "configs/config3_Q2.yaml", # multi_tank_red
        "configs/config4_Q2.yaml", # tank_path_red
         "configs/config5_Q2.yaml", # runaway_red
        "configs/config6_Q2.yaml", # tank_back_red
         "configs/config7_Q2.yaml", # fast_observe_red
         "configs/config8_Q2.yaml", # missile_red
        "configs/config9_Q2.yaml",  # drone_red
         "configs/config11_Q2.yaml", # unload_red
        "configs/config12_Q2.yaml", # UGV_red
    ]
    for c in  configs:
        run(c)


