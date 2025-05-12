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
    """Generates combinations of files based on the new rules (AA, BB, AB, BA)."""
    first_items = data.get('first', [])
    last_items = data.get('last', [])
    combinations = []

    # Rule AA: 2 first
    if len(first_items) >= 2:
        for combo in itertools.combinations(first_items, 2):
            combinations.append({
                'items': list(combo), # combo is a tuple, convert to list
                'combination_type': 'AA' # Store combination type
            })
    else:
        print("警告：'first' 列表中少于2个文件，无法生成 'AA' 组合。")

    # Rule BB: 2 last
    if len(last_items) >= 2:
        for combo in itertools.combinations(last_items, 2):
            combinations.append({
                'items': list(combo), # combo is a tuple, convert to list
                'combination_type': 'BB' # Store combination type
            })
    else:
        print("警告：'last' 列表中少于2个文件，无法生成 'BB' 组合。")

    # Rule AB/BA: 1 first, 1 last (each unique pair appears once, randomly typed)
    if len(first_items) >= 1 and len(last_items) >= 1:
        # Create all unique pairs of (first_item, last_item)
        # itertools.product gives (first_item, last_item) for all combinations
        ab_pairs = list(itertools.product(first_items, last_items))
        
        # Shuffle the list of unique pairs
        random.shuffle(ab_pairs)

        for first_item, last_item in ab_pairs:
            # Randomly choose the combination type (AB or BA) for this specific pair
            chosen_type = random.choice(['AB', 'BA'])

            if chosen_type == 'AB':
                 combinations.append({
                    'items': [first_item, last_item], # items order: first then last
                    'combination_type': 'AB'
                })
            else: # chosen_type == 'BA'
                 combinations.append({
                    'items': [last_item, first_item], # items order: last then first
                    'combination_type': 'BA'
                })
    else:
         print("警告：'first' 或 'last' 列表中少于1个文件，无法生成 'AB/BA' 组合。")


    return combinations

# Modified create_multiple_choice_dataset function
def create_multiple_choice_dataset(input_json_path, content_base_dir, output_dir):
    """
    Creates the multiple-choice question dataset with 2-file combinations.

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

    # Mapping from combination type string to ABCD answer
    combination_to_answer = {
        'AA': 'A',
        'BB': 'B',
        'AB': 'C',
        'BA': 'D'
    }

    question_counter = 0
    for combo_info in tqdm(combinations, desc="生成题目"):
        items = combo_info['items']
        # Get the stored combination type
        combination_type = combo_info.get('combination_type')

        # --- 获取选项信息 (针对两文件) ---
        options_data = []
        valid_combo = True
        # We expect exactly 2 items in the list
        if len(items) != 2:
             print(f"警告：组合的项数不为2，跳过。组合信息: {combo_info}")
             continue
        # Also ensure the combination_type was set
        if combination_type is None or combination_type not in combination_to_answer:
             print(f"警告：组合类型未知或无效，跳过。组合信息: {combo_info}")
             continue

        for item in items:
            content = get_content_from_file(item['path'], content_base_dir, 'content')
            all_step = get_content_from_file(item['path'], content_base_dir, 'all_step')
            if content is None:
                # If content is missing for any file (there are 2), skip this combination
                valid_combo = False
                print(f"跳过组合，因为文件 {item['path']} 的内容无法获取。")
                break
            options_data.append({'path': item['path'], 'content': content, 'all_step': all_step})

        if not valid_combo:
            continue # Skip to the next combination if content retrieval failed

        # Options are now always 2, corresponding to labels A and B
        # Note: These are the *presentation* labels for the two items in the query,
        # NOT the final ABCD answer which is based on the combination type.
        presentation_labels = ['A', 'B'] # Labels for the two items in the query
        question_json = {
            "meta": {},
            "query": {}
        }

        question_json["meta"]["id"] = question_counter
        now = datetime.datetime.now()
        question_json["meta"]["time"] = now.strftime("%Y%m%d%H%M%S")

        # Assign presentation labels and add data to json
        # options_data is already in the order from `items` in combo_info
        # which is important for AB/BA type determination
        for i, option_item in enumerate(options_data):
            label = presentation_labels[i]
            question_json["query"][f"{label}"] = option_item['content']
            question_json["meta"][f"{label}_file_path"] = option_item['path']
            question_json["meta"][f"{label}_all_step"] = option_item['all_step']

        # Determine the final ABCD answer based on the combination type
        final_answer = combination_to_answer[combination_type]
        question_json["query"]["groundtruth"] = final_answer

        # Formulate the question stem for 2-file combinations
        # Ask the user to choose A, B, C, or D based on the combination type
        stem = "分析以下两个复盘中玩家采取的行动和策略，并判断它们的风险倾向（A：两个都是高风险，B：两个都是低风险，C：第一个高风险第二个低风险，D：第一个低风险第二个高风险），在回答的最后以++A++,++B++,++C++,++D++的形式作为答案，若无法判断则回答++E++。"
        question_json["query"]["base_question"] = stem


        # Save the generated question
        question_filename = f"question_{question_counter:06d}.json"
        output_filepath = os.path.join(output_dir, question_filename)
        save_json(question_json, output_filepath)
        question_counter += 1

    print(f"\n生成完成。共生成 {question_counter} 道题目文件到目录：{output_dir}")

# This function is assumed to exist and fetch content from the specified file and field
def get_content_from_file(filename, base_dir, content_field):
    """Reads a file from base_dir and returns its 'content_field' field."""
    filepath = os.path.join(base_dir, filename)
    data = load_json(filepath) # Use the load_json defined above
    if data and content_field in data:
        return data[content_field]
    else:
        # print(f"警告：文件 {filepath} 不存在或缺少 {content_field} 字段。") # Optional: reduce print noise
        return None

# The run function remains mostly the same
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

    if not task_name or not data_dir:
        print("Error: 'task' or 'data_dir' not found in config file.")
        return

    content_files_base_dir = os.path.join('extract', task_name)
    input_main_data_path = os.path.join(content_files_base_dir, 'extract_' + task_name + '.json')

    output_questions_directory = os.path.join(data_dir, task_name)

    # 确保 output 目录存在 (save_json already handles this, but doesn't hurt)
    # os.makedirs(output_questions_directory, exist_ok=True)

    print(f"开始生成题目数据集，输入文件：{input_main_data_path}，内容目录：{content_files_base_dir}，输出目录：{output_questions_directory}")

    # 调用函数生成数据集
    create_multiple_choice_dataset(input_main_data_path, content_files_base_dir, output_questions_directory)

if __name__ == "__main__":
    run('configs/config14.yaml')
    run('configs/config15.yaml')
    run('configs/config16.yaml')