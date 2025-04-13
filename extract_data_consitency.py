import os
import json
import yaml
from collections import defaultdict

def analyze_task_results(config_path):
    """
    从config.yaml读取配置进行分析, 并计算各模型与最终共识答案的一致性。
    """
    # 读取配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 获取配置参数
    task_name = config['task']
    min_consensus = config['analysis']['min_consensus']
    output_base = config.get('output_base', '.') # Use current dir if not specified
    task_dir = os.path.join(output_base, task_name)

    # 数据收集
    path_records = defaultdict(lambda: defaultdict(int))
    model_answers = defaultdict(dict) # 新增：存储每个模型的原始答案 {model_name: {path: answer}}

    print(f"开始分析任务: {task_name}")
    print(f"查找目录: {task_dir}")
    model_count = 0
    processed_models = []

    if not os.path.isdir(task_dir):
        print(f"错误：任务目录不存在 {task_dir}")
        return

    for model_name in os.listdir(task_dir):
        model_path = os.path.join(task_dir, model_name)
        if not os.path.isdir(model_path): #确保是目录
            continue

        summary_path = os.path.join(model_path, "summary.json")
        if not os.path.exists(summary_path):
            # print(f"跳过 {model_name}: 未找到 summary.json")
            continue

        model_count += 1
        processed_models.append(model_name)
        # print(f"处理模型: {model_name}")
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
                # 确保 'label' 键存在且是一个列表
                label_data = summary.get('label', [])
                if not isinstance(label_data, list):
                    print(f"警告: {model_name} 的 summary.json 中 'label' 不是列表，跳过此文件。")
                    continue

                for item in label_data:
                    # 确保 item 是字典并且包含 'path' 和 'answer'
                    if isinstance(item, dict) and 'path' in item and 'answer' in item:
                        path = os.path.basename(item['path'])
                        answer = item['answer']
                        path_records[path][answer] += 1
                        model_answers[model_name][path] = answer # 存储模型答案
                    else:
                        print(f"警告: {model_name} 的 summary.json 中发现无效条目: {item}")

        except json.JSONDecodeError as e:
            print(f"跳过 {model_name} 因JSON解析错误: {str(e)} 在文件 {summary_path}")
            processed_models.remove(model_name) # 从已处理列表移除
            continue
        except Exception as e:
            print(f"跳过 {model_name} 因其他错误: {str(e)} 在文件 {summary_path}")
            processed_models.remove(model_name) # 从已处理列表移除
            continue

    if not path_records:
        print("未能从任何模型收集到数据。请检查summary.json文件是否存在且格式正确。")
        return

    print(f"\n共处理了 {len(processed_models)} 个模型的 summary.json 文件: {', '.join(processed_models)}")

    # --- 确定最终共识答案 ---
    consensus_answers = {} # {path: consensus_answer}
    extract_data = []      # 用于存储原始需求的简洁结果

    print(f"\n根据最小共识数 {min_consensus} 生成最终答案...")
    for path, answers in path_records.items():
        # 按计数降序排序，确保选择最常见的答案（如果多个答案达到阈值）
        sorted_answers = sorted(answers.items(), key=lambda item: item[1], reverse=True)

        found_consensus = False
        for answer, count in sorted_answers:
            if count >= min_consensus:
                consensus_answers[path] = answer
                # 仍然添加到 extract_data 以满足原始需求
                extract_data.append({
                    "path": path,
                    "answer": answer
                })
                found_consensus = True
                break # 每个文件只记录第一个（计数最高的）达标答案作为共识

    print(f"共找到 {len(consensus_answers)} 条数据的共识答案。")

    # --- 计算每个模型与共识答案的一致性 ---
    model_consistency = {} # {model_name: consistency_percentage_str}

    print("\n计算各模型与共识答案的一致性...")
    for model_name in processed_models: # 只计算成功处理过的模型
        if model_name not in model_answers: # 安全检查，理论上应该存在
             model_consistency[model_name] = "N/A (无有效数据)"
             continue

        correct_matches = 0
        total_compared = 0
        model_specific_answers = model_answers[model_name]

        for path, model_ans in model_specific_answers.items():
            # 仅当该path存在共识答案时才进行比较
            if path in consensus_answers:
                total_compared += 1
                if model_ans == consensus_answers[path]:
                    correct_matches += 1

        if total_compared > 0:
            consistency_percent = (correct_matches / total_compared) * 100
            model_consistency[model_name] = f"{consistency_percent:.2f}% ({correct_matches}/{total_compared})"
        elif consensus_answers: # 如果有共识答案但该模型没有覆盖这些path
             model_consistency[model_name] = f"0.00% (0/{total_compared}) - 模型未回答任何有共识的条目"
        else: # 如果根本没有共识答案产生
            model_consistency[model_name] = "N/A (无共识答案可比较)"


    # --- 保存结果 ---

    # 1. 保存原始需求的精简结果
    output_path_extract = f"extract_{task_name}.json"
    with open(output_path_extract, 'w', encoding='utf-8') as f:
        json.dump(extract_data, f, indent=2, ensure_ascii=False)
    print(f"\n分析完成！精简结果已保存到 {output_path_extract}")

    # 2. 打印并保存一致性结果
    print("\n--- 模型一致性报告 (与共识答案对比) ---")
    # 按模型名称排序以便查看
    for model_name in sorted(model_consistency.keys()):
        print(f"{model_name}: {model_consistency[model_name]}")

    output_path_consistency = f"consistency_{task_name}.json"
    # 保存排序后的一致性结果，更易读
    sorted_consistency = {k: model_consistency[k] for k in sorted(model_consistency.keys())}
    # with open(output_path_consistency, 'w', encoding='utf-8') as f:
    #     json.dump(sorted_consistency, f, indent=2, ensure_ascii=False)
    # print(f"模型一致性结果已保存到 {output_path_consistency}")


if __name__ == "__main__":
    # 确保配置文件路径正确
    analyze_task_results("configs/config4.yaml")