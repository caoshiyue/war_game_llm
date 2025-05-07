import json
import os
import math
from collections import defaultdict
import yaml
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
        print("输入数据为空。")
        return [], {}

    # 收集所有唯一的文件名
    unique_files = set()
    for entry in comparisons_data:
        if 'path' in entry:
            # 确保 path 格式正确且可以分割
            if '__' not in entry['path'].replace(".json",""):
                 # print(f"警告: 'path' 格式不正确: {entry.get('path', 'N/A')}. 跳过.")
                 continue
            
            try:
                file_a, file_b = entry['path'].replace(".json","").split('__')
                unique_files.add(file_a)
                unique_files.add(file_b)
            except ValueError:
                 # print(f"警告: 'path' 分割失败: {entry.get('path', 'N/A')}. 跳过.")
                 continue # 跳过无法正确分割的条目


    if not unique_files:
        print("没有找到任何文件进行比较。请检查 'path' 字段格式。")
        return [], {}

    # 初始化所有文件的得分
    scores = {filename: initial_score for filename in unique_files}

    # 开始迭代更新得分
    for iteration in range(num_iterations):
        # 随机打乱比较顺序有助于提高收敛性（可选，但推荐）
        # random.shuffle(comparisons_data) 
        
        for entry in comparisons_data:
            if 'path' in entry and 'answer' in entry:
                # 再次检查 path 格式，以防万一
                if '__' not in entry['path'].replace(".json",""):
                     continue
                try:
                    file_a, file_b = entry['path'].replace(".json","").split('__')
                except ValueError:
                     continue # 跳过无法正确分割的条目

                outcome = entry['answer']

                # 确保文件在scores字典中 (尽管前面已经初始化了所有文件，这里做个额外的安全检查)
                if file_a not in scores or file_b not in scores:
                    # print(f"警告: 比较中包含未初始化的文件: {file_a}或{file_b}. 跳过此比较.")
                    continue

                # 获取当前分数
                score_a = scores[file_a]
                score_b = scores[file_b]

                # 计算预期结果（文件A获胜的预期概率）
                try:
                    # 使用logistic函数，类似Elo的转换
                    # math.pow(10, x) 等价于 10**x
                    expected_a = 1 / (1 + math.pow(10, (score_b - score_a) / scale_factor))
                except OverflowError:
                    # 处理分数差异过大导致的溢出
                    # 如果 score_b - score_a 很大 (B分数远高于A)，则 10^很大 -> 无穷，expected_a -> 0
                    # 如果 score_a - score_b 很大 (A分数远高于B)，则 score_b - score_a 很大负数，10^很大负数 -> 0, expected_a -> 1
                    expected_a = 0.0 if score_b > score_a else 1.0
                except Exception as e:
                    print(f"计算预期结果时发生错误: {e}. 跳过此比较.")
                    continue

                # expected_b = 1 - expected_a # 理论上如此，但在更新时只需关注一方的预期和实际结果

                # 实际结果 (Elo系统中，胜得1分，负得0分，平局得0.5分)
                actual_a = 0.0 # 初始化为0
                if outcome == 'A':
                    actual_a = 1.0 # 文件A获胜
                elif outcome == 'B':
                    actual_a = 0.0 # 文件B获胜 (A得0分)
                elif outcome == 'E':
                    actual_a = 0.5 # 平局 (A得0.5分)
                else:
                    # 如果有其他未知的 outcome 值，可以选择跳过或按平局处理
                    # print(f"警告: 未知结果 '{outcome}' 在比较 {file_a} vs {file_b} 中。跳过此比较.")
                    continue # 跳过未知结果的条目
                    # 或者按平局处理: actual_a = 0.5 

                # 更新分数
                # 分数变化 = 学习率 * (实际得分 - 预期得分)
                score_change = learning_rate * (actual_a - expected_a)
                scores[file_a] += score_change
                # 另一方的分数变化是相反的
                # actual_b = 1.0 - actual_a
                # score_change_b = learning_rate * (actual_b - expected_b) 
                # = learning_rate * ((1.0 - actual_a) - (1.0 - expected_a))
                # = learning_rate * (expected_a - actual_a) = -score_change
                scores[file_b] -= score_change


    # 根据最终得分进行排序
    ranked_files_with_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    # 提取排序后的文件名列表
    ranked_filenames = [item[0] for item in ranked_files_with_scores]

    return ranked_filenames, scores # 返回排名和最终得分字典


def single_aggregation(json_filepath):

    print(f"正在从文件读取数据: {json_filepath}")
    comparisons = load_comparisons(json_filepath)  

    if comparisons is not None:
        
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

def run(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    task_name = config['task']
    task_dir = os.path.join(config['output_base'], task_name)

    # 遍历所有模型结果
    for model_name in os.listdir(task_dir):
        summary_path = os.path.join(task_dir, model_name, "summary.json")
        if not os.path.exists(summary_path):
            continue
        try:
            single_aggregation(summary_path)
        except Exception as e:
            print(e)
            continue

# --- 主程序入口 ---
if __name__ == "__main__":
    run("configs/config3.yaml")
    run("configs/config4.yaml")
    run("configs/config5.yaml")
    run("configs/config6.yaml")
    run("configs/config7.yaml")

