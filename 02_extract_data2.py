import os
import json
import yaml
from collections import defaultdict

def analyze_task_results(config_path):
    """
    增强版分析函数（支持key_output汇总）
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    task_name = config['task']
    min_consensus = config['analysis']['min_consensus']
    task_dir = os.path.join(config['output_base'], task_name)

    # 改进数据结构：记录每个答案的模型来源和key_output
    path_records = defaultdict(lambda: {
        'answers': defaultdict(lambda: {'count':0, 'models':dict()}),
        'key_outputs': defaultdict(dict)
    })

    # 遍历所有模型结果
    for model_name in os.listdir(task_dir):
        summary_path = os.path.join(task_dir, model_name, "summary.json")
        if not os.path.exists(summary_path):
            continue

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
                model_id = summary['meta']['model']  # 获取实际模型名称
                
                for item in summary.get('label', []):
                    path = os.path.basename(item['path'])
                    answer = item['answer']
                    key_output = item.get('key_output', {})  # 新增字段获取
                    
                    # 更新计数和模型记录
                    path_records[path]['answers'][answer]['count'] += 1
                    path_records[path]['answers'][answer]['models'][model_id] = key_output
                    
        except Exception as e:
            print(f"跳过 {model_name} 因错误: {str(e)}")
            continue

    # 生成增强版结果
    extract_data = []
    for path, records in path_records.items():
        # 寻找符合共识的答案
        selected_answer = None
        for answer, info in records['answers'].items():
            if info['count'] >= min_consensus:
                selected_answer = answer
                break
        
        if selected_answer:
            # 收集所有模型的key_output
            model_outputs = {
                model: output 
                for model, output in records['answers'][selected_answer]['models'].items()
            }
            
            extract_data.append({
                "path": path,
                "answer": selected_answer,
                "key_outputs": model_outputs  # 新增汇总字段
            })

    # 保存结果（添加版本标识）
    output_path = f"extract/extract_{task_name}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extract_data, f, indent=2, ensure_ascii=False)

    print(f"增强分析完成！结果已保存到 {output_path}")

# 使用方式
if __name__ == "__main__":
    analyze_task_results("configs/config5.yaml")
    analyze_task_results("configs/config6.yaml")
    analyze_task_results("configs/config7.yaml")
    analyze_task_results("configs/config8.yaml")
    analyze_task_results("configs/config9.yaml")
    analyze_task_results("configs/config10.yaml")