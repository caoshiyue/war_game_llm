import os
import json
import yaml
from collections import defaultdict

def analyze_task_results(config_path):
    """
    从config.yaml读取配置进行分析
    """
    # 读取配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 获取配置参数
    task_name = config['task']
    min_consensus = config['analysis']['min_consensus']  # 新增配置项
    task_dir = os.path.join(config['output_base'], task_name)

    # 数据收集
    path_records = defaultdict(lambda: defaultdict(int))
    for model_name in os.listdir(task_dir):
        summary_path = os.path.join(task_dir, model_name, "summary.json")
        if not os.path.exists(summary_path):
            continue

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
                for item in summary.get('label', []):
                    path = os.path.basename(item['path'])
                    answer = item['answer']
                    path_records[path][answer] += 1
        except Exception as e:
            print(f"跳过 {model_name} 因错误: {str(e)}")
            continue

    # 生成简洁结果
    extract_data = []
    for path, answers in path_records.items():
        for answer, count in answers.items():
            if count >= min_consensus:
                extract_data.append({
                    "path": path,
                    "answer": answer
                })
                break  # 每个文件只记录第一个达标的答案

    # 保存结果
    output_path = f"extract_{task_name}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extract_data, f, indent=2, ensure_ascii=False)

    print(f"分析完成！精简结果已保存到 {output_path}")

# 使用方式
if __name__ == "__main__":
    analyze_task_results("configs/config3.yaml")
    analyze_task_results("configs/config4.yaml")
