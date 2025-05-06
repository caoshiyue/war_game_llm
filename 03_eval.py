##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-04-12 14:30:25
## 
import os
import json
import yaml
from collections import defaultdict

def calculate_accuracy(config_path):
    """基于extract文件校验各模型准确率"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 获取配置参数
    task_name = config['task'] #! 这里的方案不好
    if task_name.endswith("_eval"):
        task_name_base=task_name[:-5]
    else:
        task_name_base=task_name
    output_base = config['output_base']
    extract_path = f"extract/extract_{task_name_base}.json"
    report_path = config['analysis'].get('accuracy_report', f"accuracy_{task_name}.json")

    # 加载标准答案
    try:
        with open(extract_path, 'r', encoding='utf-8') as f:
            extract_data = json.load(f)
        correct_answers = {os.path.basename(item['path']): item['answer'] for item in extract_data}
    except FileNotFoundError:
        raise Exception(f"Extract文件不存在: {extract_path}")

    # 初始化统计
    accuracy_report = []
    task_dir = os.path.join(output_base, task_name)

    # 遍历所有模型结果
    for model_dir in os.listdir(task_dir):
        model_path = os.path.join(task_dir, model_dir)
        if not os.path.isdir(model_path):
            continue

        summary_path = os.path.join(model_path, "summary.json")
        if not os.path.exists(summary_path):
            continue

        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            
            stats = {
                "model": summary['meta']['model'],
                "total_samples": 0,
                "correct": 0,
                "accuracy": 0.0
            }

            for item in summary.get('label', []):
                file_path = os.path.basename(item['path'])
                if file_path not in correct_answers:
                    continue
                
                stats['total_samples'] += 1
                if item['answer'] == correct_answers[file_path]:
                    stats['correct'] += 1

            if stats['total_samples'] > 0:
                stats['accuracy'] = round(stats['correct'] / stats['total_samples'], 4)
            
            accuracy_report.append(stats)

        except Exception as e:
            print(f"跳过 {model_dir} 因错误: {str(e)}")
            continue

    # 生成最终报告
    final_report = {
        "task": task_name,
        "extract_source": extract_path,
        "total_files": len(correct_answers),
        "models": sorted(accuracy_report, key=lambda x: x['accuracy'], reverse=True)
    }

  # 新增控制台输出
    print(f"\n{' 准确率分析报告 ':=^60}")
    print(f"任务名称: {final_report['task']}")
    print(f"基准文件: {final_report['extract_source']}")
    print(f"总样本量: {final_report['total_files']} 条\n")
    
    # 打印表格头
    print(f"{'模型名称':<20} | {'测试样本':>8} | {'正确数':>8} | {'准确率':>10}")
    print("-" * 60)
    
    # 打印每个模型的数据
    for model in final_report['models']:
        # 格式化为百分比显示
        accuracy_pct = f"{model['accuracy']:.2%}"
        
        print(
            f"{model['model']:<20} | "
            f"{model['total_samples']:>8} | "
            f"{model['correct']:>8} | "
            f"{accuracy_pct:>10}"
        )
    
    print("=" * 60 + "\n")
    # 保存报告
    # with open(report_path, 'w', encoding='utf-8') as f:
    #     json.dump(final_report, f, indent=2, ensure_ascii=False)
    
    print(f"准确率分析完成！{report_path}")

if __name__ == "__main__":
    
    calculate_accuracy("configs/config3_eval.yaml")
    calculate_accuracy("configs/config4_eval.yaml")
    calculate_accuracy("configs/config5_eval.yaml")
    calculate_accuracy("configs/config6_eval.yaml")
    calculate_accuracy("configs/config7_eval.yaml")
    

