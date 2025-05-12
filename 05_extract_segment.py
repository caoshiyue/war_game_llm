##
# Author:
# Description:
# LastEditors: Shiyuec
# LastEditTime: 2025-05-12 07:08:22
##
import json
import os
import yaml
import re # Import regular expressions module

def parse_interval(step_str):
    """
    Parses a step string like "1-190" or "1743" into a tuple (start, end).
    Returns (None, None) if parsing fails.
    """
    if not isinstance(step_str, str):
        return None, None

    parts = step_str.split('-')
    try:
        if len(parts) == 1:
            time = int(parts[0].strip())
            return time, time
        elif len(parts) == 2:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            # Ensure start <= end
            return min(start, end), max(start, end)
        else:
            return None, None
    except ValueError:
        return None, None

def get_min_max_interval(steps):
    """
    Calculates the overall minimum start time and maximum end time from a list of step strings.
    Returns a string "min_start-max_end" or "" if no valid steps are found.
    """
    min_start = float('inf')
    max_end = float('-inf')

    valid_steps_found = False

    for step_str in steps:
        start, end = parse_interval(step_str)
        if start is not None and end is not None:
            min_start = min(min_start, start)
            max_end = max(max_end, end)
            valid_steps_found = True

    if valid_steps_found and min_start != float('inf') and max_end != float('-inf'):
        # Handle case where min_start and max_end might still be infinity if steps list was empty or invalid
         return f"{min_start}-{max_end}"
    else:
        return ""

def get_nested_value(data, path):
    """
    Retrieves a nested value from a dictionary using a dot-separated path.
    Returns None if any key or index in the path is not found.
    """
    keys = path.split('.')
    current_data = data
    try:
        for key in keys:
            if isinstance(current_data, dict):
                current_data = current_data.get(key)
                if current_data is None:
                    return None
            elif isinstance(current_data, list):
                try:
                    index = int(key)
                    if 0 <= index < len(current_data):
                        current_data = current_data[index]
                    else:
                        return None # Index out of bounds
                except ValueError:
                    return None # Path segment was not a valid integer index for a list
            else:
                return None # Current data is not a dict or list, cannot traverse further
        return current_data
    except Exception:
        return None # Catch any other unexpected errors during traversal


def filter_text_by_time_range(text, time_range_str):
    """
    Filters the input text to include only blocks within the specified time range.
    Blocks are identified by lines starting with "--- 时间步 X/Y ---".
    Extracts text from the header of the first relevant time step up to
    the header of the first time step *after* the range.
    """
    if not isinstance(text, str) or not time_range_str:
        return ""

    start_time, end_time = parse_interval(time_range_str)
    if start_time is None or end_time is None:
        print(f"Warning: Invalid time range format for filtering: {time_range_str}")
        return ""

    lines = text.splitlines()
    filtered_lines = []
    in_range = False
    found_first_block = False

    # Regex to match the time step header line
    time_step_header_re = re.compile(r"--- 时间步 (\d+)/\d+ ---")

    for line in lines:
        match = time_step_header_re.match(line)
        if match:
            try:
                current_time_step = int(match.group(1))

                # If we haven't found the start yet and this is within or after the start
                if not found_first_block and current_time_step >= start_time:
                     in_range = True
                     found_first_block = True

                # If we are in range and this step is past the end, stop
                if in_range and current_time_step > end_time:
                     in_range = False
                     # Do not append the header that is outside the range
                     break # Assume time steps are increasing, so no need to check further lines

            except ValueError:
                # Malformed header, treat as a regular line if currently in range
                pass

        if in_range:
             filtered_lines.append(line)


    return "\n".join(filtered_lines).strip()


def process_model_run(summary_path, ranked_path, n_value, config, data_dir):
    """
    Processes summary and ranked data for a single model run.
    Extracts steps, calculates all_step, extracts content, and structures data
    for both the task summary file and individual content files.

    Args:
        summary_path (str): summary.json 文件的路径。
        ranked_path (str): summary_ranked_results.json 文件的路径。
        n_value (int): 需要提取的前 N 个和后 N 个文件数量。
        config (dict): 加载的配置字典。
        data_dir (str): 原始数据文件所在的基目录。

    Returns:
        dict: Contains processed data:
              {"meta": {}, "first_summary_items": [], "last_summary_items": [], "individual_files_to_save": []}
              Returns None if critical files are not found or cannot be parsed.
    """
    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {summary_path} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {summary_path}.")
        return None
    except Exception as e:
        print(f"Error reading {summary_path}: {e}")
        return None

    try:
        with open(ranked_path, 'r', encoding='utf-8') as f:
            ranked_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {ranked_path} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {ranked_path}.")
        return None
    except Exception as e:
        print(f"Error reading {ranked_path}: {e}")
        return None

    ranked_files_list = ranked_data.get('ranked_files_iterative', [])
    if not ranked_files_list:
        print("Warning: 'ranked_files_iterative' list is empty or not found in ranked data.")
        # Return structure with empty lists, but valid meta
        return {
            "meta": summary_data.get('meta', {}),
            "first_summary_items": [],
            "last_summary_items": [],
            "individual_files_to_save": []
        }

    list_length = len(ranked_files_list)

    # Get top N and bottom N filenames
    top_n_files = ranked_files_list[:n_value]
    # Prevent N too large causing bottom_n to be empty or overlap too much (though overlap is fine for summary lists)
    bottom_n_files = ranked_files_list[-n_value:] if n_value < list_length else []

    # Build a dictionary mapping individual filenames to their steps and original full_path
    steps_by_individual_file = {}
    file_to_original_full_path = {}

    for item in summary_data.get('label', []):
        full_path = item.get('path')
        key_output = item.get('key_output')
        if not full_path or not key_output:
            continue

        parts = full_path.split('__')
        if len(parts) == 2:
            file1 = parts[0]
            file2 = parts[1].replace('.json', '')

            step_a = key_output.get('step_A')
            step_b = key_output.get('step_B')

            if file1:
                if file1 not in steps_by_individual_file:
                    steps_by_individual_file[file1] = []
                if step_a:
                    steps_by_individual_file[file1].append(step_a)
                file_to_original_full_path[file1] = full_path

            if file2:
                if file2 not in steps_by_individual_file:
                    steps_by_individual_file[file2] = []
                if step_b:
                    steps_by_individual_file[file2].append(step_b)
                file_to_original_full_path[file2] = full_path
        else:
             # Handle cases where full_path might not have '__'
             filename = full_path.replace('.json', '')
             step = key_output.get('step') # Assume a single 'step' key
             if filename:
                 if filename not in steps_by_individual_file:
                      steps_by_individual_file[filename] = []
                 if step:
                     steps_by_individual_file[filename].append(step)
                 file_to_original_full_path[filename] = full_path

    first_summary_items = []
    last_summary_items = []
    individual_files_to_save = [] # Contains {path: ..., content: ...}

    config_file_configs = config.get('data_processing', {}).get('file_configs', [])

    # Process files for the 'first' list in summary
    for filename in top_n_files:
        if filename in steps_by_individual_file:
            original_steps = list(dict.fromkeys(steps_by_individual_file[filename])) # Get unique steps
            all_step = get_min_max_interval(original_steps)
            original_full_path = file_to_original_full_path.get(filename)

            # Data for summary file
            summary_item = {
                 "path": filename + ".json",
                 "steps": original_steps,
                 "all_step": all_step
            }
            first_summary_items.append(summary_item)

            # Data and content for individual file
            extracted_content = "" # Default empty

            if original_full_path:
                 original_parts = original_full_path.split('__')
                 is_file1 = (len(original_parts) == 2 and original_parts[0] == filename)
                 is_file2 = (len(original_parts) == 2 and original_parts[1].replace('.json', '') == filename)
                 is_single_file = (len(original_parts) == 1 and original_parts[0].replace('.json', '') == filename)

                 field_path = None
                 if is_file1 and len(config_file_configs) > 0:
                     field_path = config_file_configs[0].get('path')
                 elif is_file2 and len(config_file_configs) > 1:
                     field_path = config_file_configs[1].get('path')
                 elif is_single_file and len(config_file_configs) > 0:
                      field_path = config_file_configs[0].get('path')


                 if field_path:
                     data_file_path = os.path.join(data_dir, filename + '.json')
                     if os.path.exists(data_file_path):
                         try:
                             with open(data_file_path, 'r', encoding='utf-8') as df:
                                 data_file_data = json.load(df)

                             raw_content = get_nested_value(data_file_data, field_path)

                             if raw_content and all_step:
                                 filtered_content = filter_text_by_time_range(raw_content, all_step)
                                 extracted_content = filtered_content
                             elif raw_content:
                                 # If no valid all_step, include all raw content found (or decide to exclude)
                                 # Based on requirement 2, individual file only needs content,
                                 # and filtering is based on all_step. If all_step is empty, no content.
                                 extracted_content = "" if not all_step else raw_content # Only include content if all_step is valid
                                 if not all_step and raw_content:
                                     print(f"Warning: No valid 'all_step' found for {filename}. Content not extracted for individual file.")


                         except FileNotFoundError:
                             print(f"Warning: Data file not found: {data_file_path}")
                         except json.JSONDecodeError:
                             print(f"Warning: Could not decode JSON from data file: {data_file_path}")
                         except Exception as e:
                             print(f"Warning: Error processing data file {data_file_path}: {e}")
                     else:
                         print(f"Warning: Data file not found: {data_file_path}")
                 else:
                     print(f"Warning: No field path configured for file: {filename} (Original path: {original_full_path})")
            else:
                 print(f"Warning: Original full path not found for ranked file: {filename}")

            # Add data for saving individual content file
            individual_files_to_save.append({
                 "path": filename + ".json", # Use filename.json as the identifier
                 "content": extracted_content, # Only the content
                 "all_step": all_step
            })
        else:
             print(f"Warning: Ranked file '{filename}' from top N not found in summary steps.")


    # Process files for the 'last' list in summary
    # Need to avoid processing the same file twice if it appears in both top and bottom N
    # This uses the set of processed files from the top N loop
    processed_in_top_n = {item['path'].replace('.json','') for item in first_summary_items}

    for filename in bottom_n_files:
        # Only process if not already processed in the top N list
        if filename not in processed_in_top_n and filename in steps_by_individual_file:
            original_steps = list(dict.fromkeys(steps_by_individual_file[filename])) # Get unique steps
            all_step = get_min_max_interval(original_steps)
            original_full_path = file_to_original_full_path.get(filename)

            # Data for summary file
            summary_item = {
                 "path": filename + ".json",
                 "steps": original_steps,
                 "all_step": all_step
            }
            last_summary_items.append(summary_item)

            # Data and content for individual file
            extracted_content = "" # Default empty

            if original_full_path:
                 original_parts = original_full_path.split('__')
                 is_file1 = (len(original_parts) == 2 and original_parts[0] == filename)
                 is_file2 = (len(original_parts) == 2 and original_parts[1].replace('.json', '') == filename)
                 is_single_file = (len(original_parts) == 1 and original_parts[0].replace('.json', '') == filename)

                 field_path = None
                 if is_file1 and len(config_file_configs) > 0:
                     field_path = config_file_configs[0].get('path')
                 elif is_file2 and len(config_file_configs) > 1:
                     field_path = config_file_configs[1].get('path')
                 elif is_single_file and len(config_file_configs) > 0:
                      field_path = config_file_configs[0].get('path')

                 if field_path:
                     data_file_path = os.path.join(data_dir, filename + '.json')
                     if os.path.exists(data_file_path):
                         try:
                             with open(data_file_path, 'r', encoding='utf-8') as df:
                                 data_file_data = json.load(df)

                             raw_content = get_nested_value(data_file_data, field_path)

                             if raw_content and all_step:
                                 filtered_content = filter_text_by_time_range(raw_content, all_step)
                                 extracted_content = filtered_content
                             elif raw_content:
                                 # Only include content if all_step is valid
                                 extracted_content = "" if not all_step else raw_content
                                 if not all_step and raw_content:
                                     print(f"Warning: No valid 'all_step' found for {filename}. Content not extracted for individual file.")


                         except FileNotFoundError:
                             print(f"Warning: Data file not found: {data_file_path}")
                         except json.JSONDecodeError:
                             print(f"Warning: Could not decode JSON from data file: {data_file_path}")
                         except Exception as e:
                             print(f"Warning: Error processing data file {data_file_path}: {e}")
                     else:
                         print(f"Warning: Data file not found: {data_file_path}")
                 else:
                     print(f"Warning: No field path configured for file: {filename} (Original path: {original_full_path})")
            else:
                 print(f"Warning: Original full path not found for ranked file: {filename}")

            # Add data for saving individual content file
            individual_files_to_save.append({
                 "path": filename + ".json",
                 "content": extracted_content,
                 "all_step": all_step
            })
        # else: Warning already printed for top N if not found in summary steps


    return {
        "meta": summary_data.get('meta', {}),
        "first_summary_items": first_summary_items,
        "last_summary_items": last_summary_items,
        "individual_files_to_save": individual_files_to_save
    }


def run(config_path):
    """
    Loads configuration and processes files for each model.
    Generates individual content JSON files per ranked file and a consolidated task summary file.
    """
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
    output_base = config.get('output_base')
    data_dir = config.get('data_dir')
    n_value = config.get('N', 10)

    if not task_name or not output_base or not data_dir:
        print("Error: Config file must contain 'task', 'output_base', and 'data_dir' keys.")
        return

    task_dir = os.path.join(output_base, task_name)

    if not os.path.exists(task_dir):
         print(f"Error: Task directory not found: {task_dir}")
         return

    # Define the task-specific output directory for extracted files
    task_output_dir = os.path.join("extract", task_name)
    os.makedirs(task_output_dir, exist_ok=True)
    print(f"Ensuring output directory exists: {task_output_dir}")

    # Lists to accumulate data for the final task summary file
    all_first_summary_data = []
    all_last_summary_data = []
    task_summary_meta = None # To store meta from the first successfully processed model

    # Iterate through all model results within the task directory
    model_dirs = [d for d in os.listdir(task_dir) if os.path.isdir(os.path.join(task_dir, d))]
    if not model_dirs:
         print(f"No model directories found in {task_dir}")
         return

    for i, model_name in enumerate(model_dirs):
        model_dir = os.path.join(task_dir, model_name)
        summary_path = os.path.join(model_dir, "summary.json")
        ranked_path = os.path.join(model_dir, "summary_ranked_results.json")

        if not os.path.exists(summary_path):
            print(f"Warning: summary.json not found for model {model_name}. Skipping.")
            continue
        if not os.path.exists(ranked_path):
            print(f"Warning: summary_ranked_results.json not found for model {model_name}. Skipping.")
            continue

        print(f"\nProcessing model: {model_name}")

        # Process data for this specific model run
        model_results = process_model_run(
            summary_path, ranked_path, n_value, config, data_dir
        )

        if model_results is None:
             print(f"Skipping model {model_name} due to processing errors.")
             continue # Skip this model if processing failed

        # Store meta from the first processed model for the task summary
        if task_summary_meta is None:
            task_summary_meta = model_results.get('meta', {})
            # Optionally add task name to meta if not already there
            if 'task' not in task_summary_meta:
                 task_summary_meta['task'] = task_name

        # Save individual content JSON files for each relevant file from this model run
        print(f"Saving individual content files for model {model_name}...")
        for file_data in model_results.get('individual_files_to_save', []):
             if 'path' in file_data and 'content' in file_data:
                 output_filename = os.path.join(task_output_dir, file_data['path'])
                 try:
                     # Write only the content value
                     with open(output_filename, 'w', encoding='utf-8') as f:
                          # json.dump(file_data['content'], f, indent=2, ensure_ascii=False)
                          # If content is string, just write it. If it needs to be a JSON string inside, dump it.
                          # Based on example, it looks like raw text might be inside a JSON string field.
                          # Let's assume the individual file should contain JUST the string content.
                          json.dump({'content':file_data['content'],'all_step':file_data['all_step']} , f, ensure_ascii=False, indent=2)

                     # print(f"Generated content file: {output_filename}") # Too verbose?
                 except IOError:
                     print(f"Error: Could not write individual file {output_filename}.")
                 except Exception as e:
                      print(f"Error writing individual file {output_filename}: {e}")
             else:
                  print(f"Warning: Invalid data structure for individual file save from model {model_name}.")


        # Accumulate data for the final task summary file
        all_first_summary_data.extend(model_results.get('first_summary_items', []))
        all_last_summary_data.extend(model_results.get('last_summary_items', []))


    # --- After processing all models ---

    # Remove duplicates from first and last lists based on 'path' for the summary
    # This assumes if a file appears in top/bottom N for multiple models, we only list it once in the final summary
    # If you need to list it multiple times (once per model it appeared in top/bottom), remove this deduplication step
    def deduplicate_summary_items(items):
        seen_paths = set()
        deduplicated = []
        for item in items:
            if 'path' in item and item['path'] not in seen_paths:
                deduplicated.append(item)
                seen_paths.add(item['path'])
        return deduplicated

    final_first_summary = deduplicate_summary_items(all_first_summary_data)
    final_last_summary = deduplicate_summary_items(all_last_summary_data)


    # Construct the final task summary data structure
    task_summary_data = {
        "meta": task_summary_meta if task_summary_meta is not None else {"task": task_name, "timestamp": "", "model": ""},
        "first": final_first_summary,
        "last": final_last_summary
    }

    # Construct the path for the task summary file
    task_summary_filename = f"extract_{task_name}.json"
    task_summary_path = os.path.join(task_output_dir, task_summary_filename)

    # Write the final task summary file
    try:
        with open(task_summary_path, 'w', encoding='utf-8') as f:
            json.dump(task_summary_data, f, indent=2, ensure_ascii=False)
        print(f"\nSuccessfully generated task summary file: {task_summary_path}")
    except IOError:
        print(f"\nError: Could not write task summary file {task_summary_path}.")
    except Exception as e:
         print(f"\nError writing task summary file {task_summary_path}: {e}")


if __name__ == "__main__":
    # N and data_dir are now read from config
    run("configs/config3.yaml")
    run("configs/config4.yaml")
    run("configs/config5.yaml")
    # run("configs/config6.yaml")
    # run("configs/config7.yaml")
