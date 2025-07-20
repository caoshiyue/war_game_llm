import json
import os
import glob
import yaml
from collections import defaultdict

def load_predictions(summary_filepath: str) -> tuple[list, str]:
    """
    Loads prediction data from the summary.json file and extracts the task name from its meta.

    Args:
        summary_filepath: Path to the summary.json file.

    Returns:
        A tuple containing:
        - A list of prediction entries if successful, otherwise an empty list.
        - The task name extracted from meta, or None if not found/invalid.
    """
    try:
        with open(summary_filepath, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)
            task_name = summary_data.get('meta', {}).get('task') # Extract task name from meta
            if 'label' in summary_data and isinstance(summary_data['label'], list):
                return summary_data['label'], task_name
            else:
                print(f"Error: Invalid format in summary file. Expected a 'label' list in {summary_filepath}.")
                return [], None
    except FileNotFoundError:
        print(f"Error: Summary file not found at {summary_filepath}")
        return [], None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {summary_filepath}")
        return [], None
    except Exception as e:
        print(f"An unexpected error occurred while reading {summary_filepath}: {e}")
        return [], None

def get_ground_truth_and_description(ground_truth_filepath: str) -> tuple[str, str]:
    """
    Retrieves the ground truth answer (label) and its description from a ground truth JSON file.

    Args:
        ground_truth_filepath: Full path to the ground truth JSON file.

    Returns:
        A tuple containing (ground truth answer label, ground truth description string) if found,
        otherwise (None, None).
    """
    if not os.path.exists(ground_truth_filepath):
        # This warning might be too noisy if called for every item, consider logging or aggregating
        # print(f"Warning: Ground truth file not found for item's path: '{ground_truth_filepath}'.")
        return None, None

    try:
        with open(ground_truth_filepath, 'r', encoding='utf-8') as f:
            ground_truth_data = json.load(f)
            ground_truth_answer_label = ground_truth_data.get('query', {}).get('groundtruth')
            ground_truth_description = ground_truth_data.get('query', {}).get('groundtruth_description')

            return (str(ground_truth_answer_label) if ground_truth_answer_label is not None else None,
                    str(ground_truth_description) if ground_truth_description is not None else None)
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from ground truth file '{ground_truth_filepath}'.")
        return None, None
    except Exception as e:
        print(f"Warning: An unexpected error occurred while reading '{ground_truth_filepath}': {e}.")
        return None, None

def classify_answer_by_description(description: str) -> str:
    """
    Classifies the question based on predefined keywords in the ground truth description.

    Args:
        description: The ground truth description string.

    Returns:
        The specific category string (e.g., "高风险", "低风险", "长期回报", "短期回报", "其他类型").
    """
    if description is None:
        return "未知分类"
    description_lower = description.lower()

    if "高风险" in description_lower:
        return "高风险"
    elif "低风险" in description_lower:
        return "低风险"
    elif "长期回报" in description_lower:
        return "长期回报"
    elif "短期回报" in description_lower:
        return "短期回报"
    else:
        return "其他类型"

def analyze_predictions_for_model(predictions: list, task_name: str, ground_truth_base_dir: str) -> dict:
    """
    Analyzes predictions for a single model and a specific task,
    categorizing results based on ground truth description content.
    Includes totals for '风险类总计' and '回报类总计'.

    Args:
        predictions: A list of prediction entries for a specific model and task.
        task_name: The task name associated with these predictions (from summary.json meta).
        ground_truth_base_dir: The base directory where all ground truth task folders are located.

    Returns:
        A dictionary containing analysis results, categorized by the specific answer type
        derived from the description, plus '风险类总计' and '回报类总计'.
    """
    category_results = defaultdict(lambda: {"total": 0, "correct": 0, "incorrect": 0})
    
    if not os.path.isdir(ground_truth_base_dir):
        print(f"Error: Ground truth base directory not found or is not a directory: {ground_truth_base_dir}")
        return {}
    
    current_task_ground_truth_folder = os.path.join(ground_truth_base_dir, task_name)
    if not os.path.isdir(current_task_ground_truth_folder):
        print(f"Error: Ground truth folder for task '{task_name}' not found: {current_task_ground_truth_folder}")
        return {}

    for item in predictions:
        predicted_answer_label = str(item.get('answer')) if item.get('answer') is not None else None

        ground_truth_filename = item.get('path')
        if not ground_truth_filename:
            continue
        
        full_ground_truth_filepath = os.path.join(current_task_ground_truth_folder, ground_truth_filename)

        ground_truth_answer_label, ground_truth_description = get_ground_truth_and_description(full_ground_truth_filepath)

        category = classify_answer_by_description(ground_truth_description)

        # Update specific category stats
        category_results[category]["total"] += 1

        is_correct = False
        if predicted_answer_label is None or ground_truth_answer_label is None:
            category_results[category]["incorrect"] += 1
        elif predicted_answer_label == ground_truth_answer_label:
            category_results[category]["correct"] += 1
            is_correct = True
        else:
            category_results[category]["incorrect"] += 1
        
        # Update risk/reward totals
        if category in ["高风险", "低风险"]:
            category_results["风险类总计"]["total"] += 1
            if is_correct:
                category_results["风险类总计"]["correct"] += 1
            else:
                category_results["风险类总计"]["incorrect"] += 1
        elif category in ["长期回报", "短期回报"]:
            category_results["回报类总计"]["total"] += 1
            if is_correct:
                category_results["回报类总计"]["correct"] += 1
            else:
                category_results["回报类总计"]["incorrect"] += 1

    return dict(category_results)

def generate_report(model: str, analysis_results: dict):
    """
    Generates and prints the accuracy report, categorized by ground truth description content,
    including risk/reward class totals and overall total.

    Args:
        model: The name of the model being reported on.
        analysis_results: Dictionary containing analysis results from analyze_predictions.
    """
    print(f"--- {model} Accuracy Report (Categorized by Ground Truth Description) ---")

    # Define custom order for categories for better readability
    custom_order = ["高风险", "低风险", "风险类总计", "长期回报", "短期回报", "回报类总计", "其他类型", "总计"]
    
    # Filter and sort categories based on custom_order, keeping only present ones
    sorted_categories = [cat for cat in custom_order if cat in analysis_results]
    
    # Add any unlisted categories at the end, before "总计", if they somehow appeared
    for cat in analysis_results:
        if cat not in sorted_categories:
            if "总计" in sorted_categories: # Insert before total if total is present
                sorted_categories.insert(sorted_categories.index("总计"), cat)
            else: # Otherwise append
                sorted_categories.append(cat)

    for category in sorted_categories:
        stats = analysis_results[category]
        total = stats.get("total", 0)
        correct = stats.get("correct", 0)
        incorrect = stats.get("incorrect", 0)

        # Use bold for total categories
        if category in ["风险类总计", "回报类总计", "总计"]:
            print(f"\n**Category: {category}**")
        else:
            print(f"\nCategory: {category}")
            
        print(f"  Total Questions: {total}")
        print(f"  Correct Answers: {correct}")
        print(f"  Incorrect Answers: {incorrect}")

        if total > 0:
            accuracy = (correct / total) * 100
            print(f"  Accuracy: {accuracy:.2f}%")
        else:
            print("  Accuracy: N/A (No questions in this category)")
    print("-" * 40)

def run_unified_analysis(config_paths: list):
    """
    Runs a unified analysis across specified config files, aggregating results by model name.
    Only processes summary files that match the task specified in the config.
    """
    all_model_aggregated_results = defaultdict(lambda: defaultdict(lambda: {"total": 0, "correct": 0, "incorrect": 0}))
    
    ground_truth_base_data_dir = None 
    summary_files_to_process = [] 

    for config_path in config_paths:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except (FileNotFoundError, yaml.YAMLError, Exception) as e:
            print(f"Error loading config file {config_path}: {e}")
            continue

        task_name_from_config = config.get('task')
        current_output_base = config.get('output_base')
        current_data_dir = config.get('data_dir')

        if not task_name_from_config or not current_output_base or not current_data_dir:
            print(f"Warning: Skipping config {config_path} due to missing 'task', 'output_base', or 'data_dir'.")
            continue
        
        if ground_truth_base_data_dir is None:
            ground_truth_base_data_dir = current_data_dir
        elif ground_truth_base_data_dir != current_data_dir:
            print(f"Warning: Inconsistent 'data_dir' found. Using '{ground_truth_base_data_dir}' as base for all ground truths. Config '{config_path}' specified '{current_data_dir}'.")

        task_output_dir = os.path.join(current_output_base, task_name_from_config)
        
        current_task_summary_files = glob.glob(os.path.join(task_output_dir, '**', 'summary.json'), recursive=True)
        
        for summary_file_path in current_task_summary_files:
            model_dir = os.path.dirname(summary_file_path)
            model_name = os.path.basename(model_dir)

            predictions_list, task_name_from_summary_file = load_predictions(summary_file_path)
            
            if predictions_list and task_name_from_summary_file == task_name_from_config:
                summary_files_to_process.append((model_name, predictions_list, task_name_from_summary_file))
            else:
                if not predictions_list:
                    print(f"Could not load predictions from {summary_file_path}. Skipping analysis for this file.")
                elif task_name_from_summary_file != task_name_from_config:
                    print(f"Skipping {summary_file_path}: Task '{task_name_from_summary_file}' from summary.json does not match config task '{task_name_from_config}'.")


    if not ground_truth_base_data_dir:
        print("Error: No valid 'data_dir' found in any config to determine ground truth base directory. Exiting.")
        return

    if not summary_files_to_process:
        print("No relevant summary files found based on the provided configs and tasks. No reports will be generated.")
        return

    for model_name, predictions_list, task_name_from_summary in summary_files_to_process:
        print(f"\n--- Analyzing predictions for model: {model_name}, task: {task_name_from_summary} ---")
        
        current_file_analysis_results = analyze_predictions_for_model(
            predictions_list, task_name_from_summary, ground_truth_base_data_dir
        )

        # Aggregate results for this model across all its tasks
        for category, stats in current_file_analysis_results.items():
            all_model_aggregated_results[model_name][category]["total"] += stats["total"]
            all_model_aggregated_results[model_name][category]["correct"] += stats["correct"]
            all_model_aggregated_results[model_name][category]["incorrect"] += stats["incorrect"]
            
    print("\n\n--- Generating Final Reports by Model ---")
    if not all_model_aggregated_results:
        print("No predictions were successfully processed after analysis. No reports will be generated.")
        return

    for model_name, aggregated_results in all_model_aggregated_results.items():
        # Ensure '总计' category is properly aggregated
        total_total = sum(v["total"] for k, v in aggregated_results.items() if k not in ["总计", "风险类总计", "回报类总计"])
        total_correct = sum(v["correct"] for k, v in aggregated_results.items() if k not in ["总计", "风险类总计", "回报类总计"])
        total_incorrect = sum(v["incorrect"] for k, v in aggregated_results.items() if k not in ["总计", "风险类总计", "回报类总计"])
        
        aggregated_results["总计"]["total"] = total_total
        aggregated_results["总计"]["correct"] = total_correct
        aggregated_results["总计"]["incorrect"] = total_incorrect

        generate_report(model_name, aggregated_results)

# --- Main execution ---
if __name__ == "__main__":
    configs = [
        # "configs/config3_Q1.yaml", # multi_tank_red
        # "configs/config4_Q1.yaml", # tank_path_red
        # "configs/config5_Q1.yaml", # runaway_red
        # "configs/config6_Q1.yaml", # tank_back_red

         "configs/config8_Q1.yaml", # missile_red
        # "configs/config9_Q1.yaml",  # drone_red

        #"configs/config11_Q1.yaml", # unload_red
        #"configs/config12_Q1.yaml", # UGV_red

    ]
    run_unified_analysis(configs)