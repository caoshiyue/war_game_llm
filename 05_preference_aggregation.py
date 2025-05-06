import json
import os
import math
from collections import defaultdict

def load_comparisons(filepath):
    """
    从指定的JSON文件路径加载比较数据。

    Args:
        filepath (str): JSON文件的路径。

    Returns:
        list: 包含比较条目的列表，每个条目是一个字典。
              如果文件不存在或读取失败，返回 None。
    """
    if not os.path.exists(filepath):
        print(f"错误：文件不存在 - {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'label' in data and isinstance(data['label'], list):
                return data['label']
            else:
                print(f"错误：JSON格式不正确，找不到 'label' 列表 - {filepath}")
                return None
    except json.JSONDecodeError:
        print(f"错误：无法解析JSON文件 - {filepath}")
        return None
    except Exception as e:
        print(f"读取文件时发生未知错误 {filepath}: {e}")
        return None
    
def calculate_win_loss_difference(comparisons_data):
    """
    计算每个文件的胜负次数和胜负差。

    Args:
        comparisons_data (list): 从JSON文件加载的比较条目列表。

    Returns:
        dict: key为文件名，value为字典 {'wins': int, 'losses': int, 'difference': int}
    """
    if not comparisons_data:
        return {}

    file_records = defaultdict(lambda: {'wins': 0, 'losses': 0, 'difference': 0})

    for entry in comparisons_data:
        if 'path' in entry and 'answer' in entry:
            file_a, file_b = entry['path'].split('__')
            outcome = entry['answer']

            # 确保文件在记录中被初始化
            if file_a not in file_records:
                file_records[file_a] # 触发 defaultdict 初始化
            if file_b not in file_records:
                file_records[file_b] # 触发 defaultdict 初始化

            # 根据比较结果更新胜负记录
            if outcome == 'A':
                file_records[file_a]['wins'] += 1
                file_records[file_b]['losses'] += 1
            elif outcome == 'B':
                file_records[file_b]['wins'] += 1
                file_records[file_a]['losses'] += 1
            # 忽略其他 answer 值

    # 计算胜负差
    for file in file_records:
        file_records[file]['difference'] = file_records[file]['wins'] - file_records[file]['losses']

    return dict(file_records) # 返回普通字典

def iterative_ranking(comparisons_data, num_iterations=100, learning_rate=50.0, initial_score=1000.0, scale_factor=400.0):
    """
    使用迭代方法（类似Elo/BT）从两两比较数据生成排名。

    Args:
        comparisons_data (list): 从JSON文件加载的比较条目列表。
        num_iterations (int): 迭代次数。
        learning_rate (float): 学习率或K因子，控制每次更新的步长。
        initial_score (float): 文件的初始分数。
        scale_factor (float): 用于计算预期结果的比例因子，Elo系统中使用400。

    Returns:
        tuple: (按分数降序排列的文件名列表, 最终得分字典)。
              如果输入数据无效，返回 ([], {}).
    """
    if not comparisons_data:
        return [], {}

    # 收集所有唯一的文件名
    unique_files = set()
    for entry in comparisons_data:
        if 'path' in entry:
            file_a, file_b = entry['path'].split('__')
            unique_files.add(file_a)
            unique_files.add(file_b)

    if not unique_files:
        print("没有找到任何文件进行比较。")
        return [], {}

    # 初始化所有文件的得分
    scores = {filename: initial_score for filename in unique_files}

    # 开始迭代更新得分
    for iteration in range(num_iterations):
        for entry in comparisons_data:
            if 'path' in entry and 'answer' in entry:
                file_a, file_b = entry['path'].split('__')
                outcome = entry['answer']

                # 确保文件在scores字典中 (尽管前面已经初始化了所有文件，这里做个额外的安全检查)
                if file_a not in scores or file_b not in scores:
                    # 这不应该发生如果 unique_files 收集正确
                    continue

                # 获取当前分数
                score_a = scores[file_a]
                score_b = scores[file_b]

                # 计算预期结果（文件A获胜的预期概率）
                try:
                    # 使用logistic函数，类似Elo的转换
                    expected_a = 1 / (1 + math.pow(10, (score_b - score_a) / scale_factor))
                except OverflowError:
                    # 处理分数差异过大导致的溢出，score_a远大于score_b时exp很大
                    expected_a = 1 if score_a > score_b else 0
                except Exception as e:
                    print(f"计算预期结果时发生错误: {e}. 跳过此比较.")
                    continue

                expected_b = 1 - expected_a

                # 实际结果
                actual_a = 1 if outcome == 'A' else 0 # 假设 'A' 获胜得 1 分， 'B' 获胜得 0 分
                # actual_b = 1 - actual_a # 虽然可以用，但更新时只需关注一方的diff


                # 更新分数
                #  delta = learning_rate * (actual_a - expected_a)
                # scores[file_a] += delta
                # scores[file_b] -= delta # B 的分数变化是 A 的相反数

                # 更直接的Elo-style更新（确保双方K因子相同且总分不变）
                score_change = learning_rate * (actual_a - expected_a)
                scores[file_a] += score_change
                scores[file_b] -= score_change


    # 根据最终得分进行排序
    ranked_files_with_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    # 提取排序后的文件名列表
    ranked_filenames = [item[0] for item in ranked_files_with_scores]

    return ranked_filenames, scores # 返回排名和最终得分字典

# --- 主程序入口 ---
if __name__ == "__main__":
    # 在这里指定你的JSON文件路径
    # 请确保这个文件存在并且是正确的JSON格式
    json_filepath = "search_psy/results_v3_based_02/search_multi_tank_red/deepseek-r1/summary.json"

    print(f"正在从文件读取数据: {json_filepath}")
    comparisons = load_comparisons(json_filepath)
    
    

    if comparisons is not None:
        
        # 调用 Win/Loss Difference 方法计算胜负并排序输出
        print("\n--- 使用 Win/Loss Difference 方法进行排名 (作为一致性的一种参考) ---")
        win_loss_records = calculate_win_loss_difference(comparisons)
        if win_loss_records:
            # 按胜负差降序排序并输出
            sorted_win_loss = sorted(win_loss_records.items(), key=lambda item: item[1]['difference'], reverse=True)
            print("文件排名 (按胜负差降序):")
            for i, (filename, record) in enumerate(sorted_win_loss):
                 print(f"  {i+1}. {filename}: 胜={record['wins']}, 负={record['losses']}, 胜负差={record['difference']}")
        else:
            print("没有计算出胜负统计和排名，可能数据有问题。")
        print("--- Win/Loss Difference 排名结束 ---\n")
        
        
        
        print("数据读取成功，开始迭代排名计算...")
        # 可以调整迭代次数、学习率等参数以观察效果
        # num_iterations: 迭代次数，通常越多越稳定，但也更耗时
        # learning_rate: 学习率或K因子，控制每次分数调整的幅度
        initial_score = 1500.0
        ranked_files, final_scores = iterative_ranking(
            comparisons,
            num_iterations=200,
            learning_rate=30.0,
            initial_score=initial_score, # 初始分数可以调整
            scale_factor=400.0    # 比例因子，影响分差与预期胜率的关系
        )

        if ranked_files:
            # 构建输出的文件路径
            # ... (此处是构建 output_filepath 的代码) ...
            input_dir = os.path.dirname(json_filepath)
            input_filename_base = os.path.splitext(os.path.basename(json_filepath))[0]
            output_filename = f"{input_filename_base}_ranked_results.json"
            output_filepath = os.path.join(input_dir, output_filename)


            # 准备要输出的JSON数据结构
            output_data = {
                "ranked_files_iterative": ranked_files,
                "ranked_files_winloss": [item[0] for item in sorted_win_loss],
                "file_scores_iterative": final_scores,
                #"win_loss_stats": win_loss_records, # 添加胜负统计数据
            }

            # ... (此处是保存结果到 JSON 文件的代码) ...
            try:
                with open(output_filepath, 'w', encoding='utf-8', newline='') as f:
                     json.dump(output_data, f, indent=4, ensure_ascii=False)
                print(f"迭代排名结果和胜负统计已成功存储到文件: {output_filepath}")
            except Exception as e:
                print(f"\n错误：无法将结果写入文件 {output_filepath}: {e}")
            
            for i, filename in enumerate(ranked_files):
                 score = final_scores.get(filename, initial_score)
                 print(f"{i+1}. {filename} (得分: {score:.2f})")
                 
        else:
            print("\n未能生成排名，可能是数据问题。")

    else:
        print("\n由于数据读取失败，排名计算中止。")