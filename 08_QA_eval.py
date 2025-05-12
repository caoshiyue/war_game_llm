import json
import os
import yaml
import glob

def load_predictions(summary_filepath: str) -> list:
    """
    Loads prediction data from the summary.json file.

    Args:
        summary_filepath: Path to the summary.json file.

    Returns:
        A list of prediction entries if successful, otherwise an empty list.
    """
    try:
        with open(summary_filepath, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)
            if 'label' in summary_data and isinstance(summary_data['label'], list):
                return summary_data['label']
            else:
                print(f"Error: Invalid format in summary file. Expected a 'label' list.")
                return []
    except FileNotFoundError:
        print(f"Error: Summary file not found at {summary_filepath}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {summary_filepath}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while reading {summary_filepath}: {e}")
        return []

def get_ground_truth(ground_truth_folder: str, prediction_item: dict) -> str:
    """
    Retrieves the ground truth answer for a given prediction item.

    Args:
        ground_truth_folder: Path to the folder containing ground truth JSON files.
        prediction_item: A single entry from the predictions list.

    Returns:
        The ground truth answer string if found, otherwise None.
    """
    ground_truth_path_raw = prediction_item.get('path')
    if not ground_truth_path_raw:
        # print(f"Warning: Skipping ground truth lookup due to missing 'path' in item: {prediction_item}") # Optional warning
        return None # Cannot get ground truth if path is missing

    # Extract the actual filename from the potentially repeated path string
    # e.g., "question_000001__...__question_000001.json" -> "question_000001.json"
    # We take the last part after splitting by '__' as it seems to be the filename.
    ground_truth_filename = ground_truth_path_raw.split('__')[-1]
    ground_truth_filepath = os.path.join(ground_truth_folder, ground_truth_filename)

    if not os.path.exists(ground_truth_filepath):
        print(f"Warning: Ground truth file not found for path '{ground_truth_path_raw}' (expected '{ground_truth_filepath}').")
        return None

    try:
        with open(ground_truth_filepath, 'r', encoding='utf-8') as f:
            ground_truth_data = json.load(f)
            # Access the ground truth answer. Based on the example, it's under ['query']['groundtruth']
            ground_truth_answer = ground_truth_data.get('query', {}).get('groundtruth')
            return str(ground_truth_answer) if ground_truth_answer is not None else None # Convert to string
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from ground truth file '{ground_truth_filepath}'.")
        return None
    except Exception as e:
        print(f"Warning: An unexpected error occurred while reading '{ground_truth_filepath}': {e}.")
        return None


def analyze_predictions(predictions: list, ground_truth_folder: str) -> dict:
    """
    Analyzes predictions by comparing them against ground truth data.

    Args:
        predictions: A list of prediction entries.
        ground_truth_folder: Path to the folder containing ground truth JSON files.

    Returns:
        A dictionary containing analysis results (correct, incorrect, total counts).
        Note: 'incorrect_predictions' includes entries where ground truth could not be retrieved.
    """
    correct_predictions = 0
    incorrect_predictions = 0 # This will also count entries where GT loading failed
    total_predictions = len(predictions)

    if not os.path.isdir(ground_truth_folder):
        print(f"Error: Ground truth folder not found or is not a directory: {ground_truth_folder}")
        # If the folder doesn't exist, all predictions are effectively incorrect/unverifiable
        return {
            "total_predictions": total_predictions,
            "correct_predictions": 0,
            "incorrect_predictions": total_predictions # All incorrect if GT folder is bad
        }


    for item in predictions:
        predicted_answer = str(item.get('answer')) if item.get('answer') is not None else None # Convert to string early

        # Attempt to get ground truth. Warnings are printed inside get_ground_truth
        ground_truth_answer = get_ground_truth(ground_truth_folder, item)

        if predicted_answer is None or ground_truth_answer is None:
            # If either prediction answer is missing or ground truth could not be retrieved, count as incorrect
            incorrect_predictions += 1
            # print(f"Warning: Cannot compare due to missing data for item: {item}. Counted as incorrect.") # Optional detailed warning
        elif predicted_answer == ground_truth_answer:
            correct_predictions += 1
        else:
            incorrect_predictions += 1
            # Optional: print details of incorrect prediction
            # print(f"Incorrect prediction for path '{item.get('path', 'N/A')}': Predicted '{predicted_answer}', Ground Truth '{ground_truth_answer}'")


    return {
        "total_predictions": total_predictions,
        "correct_predictions": correct_predictions,
        "incorrect_predictions": incorrect_predictions
    }


def generate_report(model,analysis_results: dict):
    """
    Generates and prints the accuracy report.

    Args:
        analysis_results: Dictionary containing analysis results from analyze_predictions.
    """
    total = analysis_results.get("total_predictions", 0)
    correct = analysis_results.get("correct_predictions", 0)
    incorrect = analysis_results.get("incorrect_predictions", 0) # Includes entries where GT was missing

    print(f"--- {model} Accuracy Report ---")
    print(f"Total Predictions Processed: {total}")
    print(f"Correct Predictions: {correct}")
    print(f"Incorrect Predictions: {incorrect}")

    # Calculate accuracy based on items where ground truth was successfully retrieved AND prediction was available
    # A more nuanced report could distinguish between prediction errors and GT file errors.
    # For a simple accuracy, let's use total processed predictions as the denominator.
    if total > 0:
        accuracy = (correct / total) * 100
        print(f"Overall Accuracy: {accuracy:.2f}%")
        # Optional: Accuracy only among items where GT was successfully retrieved and prediction was available
        # comparable_items = total - (incorrect - correct) # This is tricky, let's stick to overall
    else:
        print("Overall Accuracy: N/A (No predictions processed)")

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
    output_base= config.get('output_base')

    content_files_base_dir = 'extract/'+task_name
    ground_truth_folder_path = os.path.join(data_dir,task_name)
    search_base_dir = os.path.join(output_base, task_name)
    all_summary_files = glob.glob(os.path.join(search_base_dir, '**', 'summary.json'), recursive=True)


    for summary_file_path in all_summary_files:
        model_dir = os.path.dirname(summary_file_path)
        # os.path.basename() 会得到目录的最后一部分，即 '某个目录(model)'
        model_name = os.path.basename(model_dir)
        print(f"\n--------- Processing task: {task_name} ---------")

        # --- Workflow for each individual summary file ---
        # 1. Load predictions from the current summary file
        predictions_list = load_predictions(summary_file_path)

        # Only proceed with analysis and reporting if predictions were loaded successfully from *this* file
        if predictions_list:
            # 2. Analyze predictions against ground truth
            # 注意：这里假设 ground_truth_folder_path 对所有 summary.json 文件都是一样的
            # 如果 ground_truth 路径依赖于 summary.json 的位置，你需要调整 analyze_predictions 或在此之前计算正确的路径
            analysis_results = analyze_predictions(predictions_list, ground_truth_folder_path)

            # 3. Generate and print report for the analysis results of *this* file
            generate_report(model_name,analysis_results)
        else:
            # 如果当前文件加载失败，打印信息并跳过对这个文件的分析和报告
            print(f"Could not load predictions from {summary_file_path}. Skipping analysis for this file.")

# --- Main execution ---
if __name__ == "__main__":

    run('configs/config14.yaml')
    run('configs/config15.yaml')
    run('configs/config16.yaml')