import os
import json # Assuming load_json and save_json use standard json
import itertools
import random
import datetime
import yaml # For the run function
from tqdm import tqdm # Assuming tqdm is installed

# Helper functions (assuming they exist elsewhere or are defined here)
def load_json(filepath):
    """Loads JSON data from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：文件未找到 {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"错误：解码 JSON 失败 {filepath}")
        return None
    except Exception as e:
        print(f"读取文件时发生错误 {filepath}: {e}")
        return None

def save_json(data, filepath):
    """Saves data as JSON to a file."""
    try:
        # Ensure output directory exists before saving
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"保存文件时发生错误 {filepath}: {e}")


# Modified generate_question_combinations function
def generate_question_combinations(data):
    """Generates combinations of files and tracks the origin of the first item."""
    first_items = data.get('first', [])
    last_items = data.get('last', [])
    combinations = []

    # Rule AA: 2 first
    if len(first_items) >= 2:
        for combo in itertools.combinations(first_items, 1):
            combinations.append({
                'items': list(combo),
                'first_item_source_list': 'first' # The first item in this combo is from 'first'
            })
    else:
        print("警告：'first' 列表中少于2个文件，无法生成 'AA' 类型的组合基础部分。")

    # Rule BB: 2 last
    if len(last_items) >= 2:
        for combo in itertools.combinations(last_items, 1):
            combinations.append({
                'items': list(combo),
                'first_item_source_list': 'last' # The first item in this combo is from 'last'
            })
    else:
        print("警告：'last' 列表中少于2个文件，无法生成 'BB' 类型的组合基础部分。")

    # Rule AB/BA: 1 first, 1 last
    if len(first_items) >= 1 and len(last_items) >= 1:
        ab_pairs = list(itertools.product(first_items, last_items))
        random.shuffle(ab_pairs) # Shuffle pairs to vary AB/BA type if needed for distribution

        for first_item, last_item in ab_pairs:
            # Randomly choose the order for presentation (AB or BA)
            # This affects which item is considered "复盘A"
            if random.choice([True, False]): # True for AB, False for BA
                # Order: first_item, then last_item. "复盘A" is first_item.
                combinations.append({
                    'items': [first_item, last_item],
                    'first_item_source_list': 'first'
                })
            else:
                # Order: last_item, then first_item. "复盘A" is last_item.
                combinations.append({
                    'items': [last_item, first_item],
                    'first_item_source_list': 'last'
                })
    else:
        print("警告：'first' 或 'last' 列表中少于1个文件，无法生成 'AB/BA' 类型的组合基础部分。")

    return combinations

# Modified create_multiple_choice_dataset function
def create_multiple_choice_dataset(input_json_path, content_base_dir, output_dir, descript_high, descript_low):
    """
    Creates the multiple-choice question dataset with 2-file combinations
    and new question/option format.
    """
    main_data = load_json(input_json_path)
    if main_data is None:
        return

    if not descript_high or not descript_low:
        print("错误：descript_high 或 descript_low 未提供。")
        return

    combinations_info = generate_question_combinations(main_data)

    if not combinations_info:
        print("未生成任何有效的题目组合。")
        return

    random.shuffle(combinations_info) # Randomize the order of questions

    question_counter = 0
    for combo_info in tqdm(combinations_info, desc="生成题目"):
        items = combo_info['items']
        first_item_source = combo_info.get('first_item_source_list')

        if len(items) != 2:
            print(f"警告：组合的项数不为2，跳过。组合信息: {items}")
            continue
        if not first_item_source:
            print(f"警告：组合缺少 'first_item_source_list'，跳过。组合信息: {items}")
            continue

        # --- 获取复盘内容 ---
        # items[0] is "复盘A", items[1] is "复盘B"
        replay_data_list = []
        valid_combo = True
        for item_detail in items:
            content = get_content_from_file(item_detail['path'], content_base_dir, 'content')
            all_step = get_content_from_file(item_detail['path'], content_base_dir, 'all_step')
            if content is None: # all_step can be None if not critical, but content is.
                valid_combo = False
                print(f"跳过组合，因为文件 {item_detail['path']} 的内容无法获取。")
                break
            replay_data_list.append({'path': item_detail['path'], 'content': content, 'all_step': all_step})

        if not valid_combo:
            continue

        # --- 生成选项文本 ---
        #复盘A is items[0], its source determines the correct description
        options_texts = []
        correct_option_text = ""

        if first_item_source == 'first': # 复盘A 来自 'first' 列表 (高风险)
            correct_option_text = f"{descript_high}高风险"
            options_texts = [
                correct_option_text,
                f"{descript_high}低风险",
                f"{descript_low}低风险",
                f"{descript_low}高风险"
            ]
        elif first_item_source == 'last': # 复盘A 来自 'last' 列表 (低风险)
            correct_option_text = f"{descript_low}低风险"
            options_texts = [
                correct_option_text,
                f"{descript_low}高风险",
                f"{descript_high}高风险",
                f"{descript_high}低风险"
            ]
        else:
            print(f"警告：未知的 first_item_source_list '{first_item_source}'，跳过组合。")
            continue

        random.shuffle(options_texts) # 随机打乱选项顺序

        # 确定正确答案的标签 (A, B, C, D)
        groundtruth_label = ""
        option_choice_labels = ['A', 'B', 'C', 'D']
        for i, text in enumerate(options_texts):
            if text == correct_option_text:
                groundtruth_label = option_choice_labels[i]
                break
        
        if not groundtruth_label:
            print(f"警告：无法确定正确答案标签，跳过组合。正确选项文本：{correct_option_text}, 随机后选项：{options_texts}")
            continue


        question_json = {
            "meta": {},
            "query": {}
        }

        question_json["meta"]["id"] = question_counter
        now = datetime.datetime.now()
        question_json["meta"]["time"] = now.strftime("%Y%m%d%H%M%S")
        
        # "复盘A" 和 "复盘B" 的内容和元数据
        # replay_data_list[0] is 复盘A, replay_data_list[1] is 复盘B
        presentation_labels_replays = ['A', 'B'] # Labels for the replay content in the query
        question_json["query"][presentation_labels_replays[0]] = replay_data_list[0]['content']
        question_json["meta"][f"{presentation_labels_replays[0]}_file_path"] = replay_data_list[0]['path']
        question_json["meta"][f"{presentation_labels_replays[0]}_all_step"] = replay_data_list[0]['all_step']
        
        question_json["query"][presentation_labels_replays[1]] = replay_data_list[1]['content']
        question_json["meta"][f"{presentation_labels_replays[1]}_file_path"] = replay_data_list[1]['path']
        question_json["meta"][f"{presentation_labels_replays[1]}_all_step"] = replay_data_list[1]['all_step']

        # 问题干和选项      
        question_json["query"]["option_A"] = options_texts[0]
        question_json["query"]["option_B"] = options_texts[1]
        question_json["query"]["option_C"] = options_texts[2]
        question_json["query"]["option_D"] = options_texts[3]
        
        question_json["query"]["groundtruth"] = groundtruth_label

        # 保存题目
        question_filename = f"question_{question_counter:06d}.json"
        output_filepath = os.path.join(output_dir, question_filename)
        save_json(question_json, output_filepath)
        question_counter += 1

    print(f"\n生成完成。共生成 {question_counter} 道题目文件到目录：{output_dir}")


def get_content_from_file(filename, base_dir, content_field):
    """Reads a file from base_dir and returns its 'content_field' field."""
    filepath = os.path.join(base_dir, filename)
    data = load_json(filepath)
    if data and content_field in data:
        return data[content_field]
    else:
        # print(f"警告：文件 {filepath} 不存在或缺少 {content_field} 字段。") # Reduced noise
        return None

def run(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"错误: 配置文件未找到于 {config_path}")
        return
    except yaml.YAMLError as e:
        print(f"错误: 加载配置文件 {config_path} 失败: {e}")
        return
    except Exception as e:
        print(f"错误: 读取配置文件 {config_path} 时发生错误: {e}")
        return

    task_name = config.get('task')
    data_dir = config.get('data_dir')
    
    analysis_config = config.get('analysis')
    if not analysis_config:
        print("错误: 配置文件中未找到 'analysis' 部分。")
        return
        
    descript_high = analysis_config.get('descript_high')
    descript_low = analysis_config.get('descript_low')

    if not task_name or not data_dir:
        print("错误: 配置文件中未找到 'task' 或 'data_dir'。")
        return
    if not descript_high or not descript_low:
        print("错误: 配置文件 'analysis' 部分未找到 'descript_high' 或 'descript_low'。")
        return

    content_files_base_dir = os.path.join('extract', task_name)
    input_main_data_path = os.path.join(content_files_base_dir, 'extract_' + task_name + '.json')
    output_questions_directory = os.path.join(data_dir, task_name)

    print(f"开始生成题目数据集，输入文件：{input_main_data_path}，内容目录：{content_files_base_dir}，输出目录：{output_questions_directory}")
    print(f"使用高风险描述: '{descript_high}'")
    print(f"使用低风险描述: '{descript_low}'")

    create_multiple_choice_dataset(
        input_main_data_path, 
        content_files_base_dir, 
        output_questions_directory,
        descript_high,
        descript_low
    )

if __name__ == "__main__":

    run('configs/config3_Q1.yaml')
    run('configs/config4_Q1.yaml')
    run('configs/config6_Q1.yaml')