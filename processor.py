##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-05-07 08:31:47
## 
import json
import re
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple, List, Any
from response import openai_response  # 替换为实际API模块
import logging
from datetime import datetime
import random
import itertools

# Setup basic logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class DataProcessor:
    # 拓展答案选项到 A, B, C, D, E
    OPTION_PATTERN = re.compile(r'\+\+(A|B|C|D|E)\+\+')

    def __init__(self, config: Dict):
        self.config = config
        self.model = config['model']

        # 初始化统计信息，包含 A-E 选项
        self.summary = {
            "meta": {
                'task': config['task'],
                'timestamp': datetime.now().isoformat(),
                'model': self.model,
                'A': 0,
                'B': 0,
                'C': 0,
                'D': 0,  # 新增 D 选项
                'E': 0,  # 新增 E 选项
                'total': 0
            },
            "label": []
        }

        self.result_dir = os.path.join(
            self.config['output_base'],
            self.config['task'],
            self.model
        )
        os.makedirs(self.result_dir, exist_ok=True)

        self.field_config = config.get('data_processing', {})
        self.file_configs: List[Dict[str, Any]] = self.field_config.get('file_configs', [])
        if not self.file_configs:
             raise ValueError("Configuration missing 'data_processing.file_configs'")

        self.extract_rules = [
            {
                'name': rule.get('name', ""),
                'pattern': re.compile(rule.get('pattern', ""), re.DOTALL), # Added re.DOTALL for multiline match
                'required': rule.get('required', False)
            }
            for rule in config['data_processing'].get('extract_fields', []) or []
        ]
        self.lock = asyncio.Lock()


    def _nested_get(self, data: dict, path: list, default=None):
        """安全获取嵌套数据"""
        current = data
        for key in path:
            if isinstance(current, list) and isinstance(key, str) and key.isdigit():
                try:
                    current = current[int(key)]
                except (IndexError, ValueError):
                    return default
            elif isinstance(current, dict):
                current = current.get(key, default)
            else:
                return default
        return current

    async def _read_files_and_extract_contents(self, file_paths: Tuple[str, ...]) -> Tuple[List[Dict], Dict[str, str]]:
        """根据 file_configs 读取多个文件并提取指定内容"""
        if len(file_paths) != len(self.file_configs):
             raise ValueError(f"Number of input files ({len(file_paths)}) does not match number of file_configs ({len(self.file_configs)})")

        source_data = []
        extracted_contents = {}

        loop = asyncio.get_running_loop()

        async def read_single_file(f_path, config):
            try:
                with open(f_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    content_path = [] if config['path'] == '' else config['path'].split('.')
                    content = self._nested_get(data, content_path)
                    if content is None:
                        raise KeyError(f"Missing required field in {f_path}: {config['path']}")
                    return data, config['name'], content
            except FileNotFoundError:
                raise FileNotFoundError(f"File not found: {f_path}")
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON format in {f_path}")
            except KeyError as e:
                 raise KeyError(f"Error extracting content from {f_path}: {e}")
            except Exception as e:
                 raise RuntimeError(f"Error reading or processing {f_path}: {str(e)}")

        tasks = [read_single_file(file_paths[i], self.file_configs[i]) for i in range(len(file_paths))]
        results = await asyncio.gather(*tasks)

        for data, name, content in results:
             source_data.append(data)
             extracted_contents[name] = content

        return source_data, extracted_contents


    async def process_unit(self, file_paths: Tuple[str, ...], overwrite=True):
        """处理一个文件单元 (包含多个文件)"""
        logger = logging.getLogger(__name__)
        try:

            # 生成输出文件名
            base_names = [os.path.splitext(os.path.basename(f))[0] for f in file_paths]
            output_filename = "__".join(base_names) + ".json"
            output_path = os.path.join(self.result_dir, output_filename)

            if not overwrite and os.path.exists(output_path):
                logger.info(f"跳过已处理文件单元: {file_paths}")
                return

            # 文件读取和内容提取
            source_data, extracted_contents = await self._read_files_and_extract_contents(file_paths)

            # API调用
            prompt = self._build_prompt(extracted_contents)
            n_retry = 0
            response = None

            while n_retry < 5: # Retry up to 5 times
                try:
                    response = await openai_response(
                        model=self.config['model'],
                        messages=prompt,
                        **self.config['api_params']
                    )
                    answer = self._extract_answer(response)
                    extracted = self._extract_fields(response)
                    n_retry = 10
                except Exception as api_error:
                    print(api_error)
                    n_retry += 1
            # 结果处理
            if response:
                await self._save_result(source_data, prompt, response, answer, extracted, output_filename)
            else:
                 logger.error(f"Failed to get a valid response after {n_retry} retries for {file_paths}")


        except Exception as e:
            logger.error(f"Error processing unit {file_paths}: {str(e)}", exc_info=True)
            # Depending on requirements, you might want to raise the exception or just log

    def _build_prompt(self, contents: Dict[str, str]) -> list:
        """构建prompt结构，使用字典中的内容参数"""
        # The user_prompt_template in config should use keys corresponding to names in file_configs
        # e.g., user_prompt_template: |
        #           File A Content: {contentA}
        #           File B Content: {contentB}
        try:
            user_content = self.config['user_prompt_template'].format(prompt=contents)
        except KeyError as e:
            logger.error(f"Prompt template missing key: {e}. Available keys: {list(contents.keys())}")
            raise

        return [
            {"role": "system", "content": self.config['system_prompt']},
            {"role": "user", "content": user_content}
        ]

    def _extract_answer(self, response: str) -> str:
        """从响应中提取答案 (A, B, C, D, E)"""
        matches = self.OPTION_PATTERN.findall(response)
        if not matches:
            # Log a warning if no answer is found, maybe return a default or raise
            logger.warning(f"No valid answer pattern found in response: {response[:200]}...") # Log beginning of response
            # Decide how to handle this: raise error, return 'unknown', etc.
            # Let's return 'unknown' and log it.
            return 'unknown' # Or raise ValueError("No valid answer pattern found")
        return matches[-1]

    def _extract_fields(self, response: str) -> Dict[str, str]:
        """从响应中提取多个字段"""
        extracted = {}
        for rule in self.extract_rules:
            matches = rule['pattern'].findall(response)
            if not matches:
                if rule['required']:
                    logger.error(f"Required field '{rule['name']}' not found in response.")
                    # Decide how to handle required field missing: raise or return None
                    raise ValueError(f"Required field '{rule['name']}' not found")
                extracted[rule['name']] = None
                continue
            extracted[rule['name']] = matches[-1].strip() # Use the last match
        return extracted

    async def _save_result(self, source_data: List[Dict], prompt: list, response: str, answer: str, extras: Dict, filename: str):
        """保存LLM交互结果，记录所有源文件"""

        # Record source file identifiers based on file_configs order
        source_files_info = []
        for i, data in enumerate(source_data):
             config_name = self.file_configs[i].get('name', f'file_{i}')
             source_files_info.append({
                 "name": config_name,
                 # Attempt to get original file path/name from data, or use a placeholder
                 "identifier": data.get('file_path', data.get('filename', f'unknown_file_{i}'))
             })

        # 构建结果文件内容
        result_data = {
            "source_files": source_files_info, # List of source file info
            "prompt": prompt,
            "llm_response": response, # Save the extracted text content
            "answer": answer,
            "extracted": extras,  # 包含所有提取字段
            "metadata": {
                "model": self.model,
                "processed_at": datetime.now().isoformat()
            }
        }

        # 保存结果文件
        output_path = os.path.join(self.result_dir, filename)
        loop = asyncio.get_running_loop()
        # Use ThreadPoolExecutor for file I/O
        await loop.run_in_executor(
            None, # Use default executor
            lambda: json.dump(
                result_data,
                open(output_path, 'w', encoding='utf-8'),
                indent=2,
                ensure_ascii=False
            )
        )
        
    def _percentage(self, key: str) -> float:
        """计算百分比"""
        if self.summary['total'] == 0:
            return 0.0
        return round(self.summary[key] / self.summary['total'] * 100, 1)
    
    def print_summary(self):
        """打印美观的统计摘要"""
        meta = self.summary['meta']
        labels = [k for k in meta.keys() if k not in ('task', 'timestamp', 'model', 'total')]
        
        # 构建表格内容
        table_header = f"{meta['model']} 模型处理报告".center(50)
        time_str = datetime.fromisoformat(meta['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
        
        # 计算百分比
        def get_percent(key):
            if meta['total'] == 0:
                return 0.0
            return round((meta[key] / meta['total']) * 100, 1)
        
        # 构建表格行
        rows = [
            ("▏" + "▔"*48 + "▕"),
            (f"▏{table_header:^48}▕"),
            ("▏" + "-"*48 + "▕"),
            (f"▏{'任务名称:':<15}{meta['task']:<33}▕"),
            (f"▏{'处理时间:':<15}{time_str:<33}▕"),
            (f"▏{'总处理量:':<15}{meta['total']:<33,}▕"),
            ("▏" + "-"*48 + "▕")
        ]
        
        # 添加分类统计
        max_label_len = max(len(l) for l in labels)
        for label in sorted(labels):
            row = (f"▏{f'{label} 数量:':<{15+max_label_len}}"
                f"{meta[label]:<6,} ({get_percent(label)}%){' ':>10}▕")
            rows.append(row)
        
        rows.append("▏" + "▔"*48 + "▕")
        
        # 打印表格
        print("\n" + "\n".join(rows))


    async def generate_summary(self):
        """根据输出目录生成最终统计"""
        logger.info("Generating summary...")
        summary_path = os.path.join(self.result_dir, 'summary.json')

        # Reset summary counts before recalculating
        self.summary['meta'] = {
            'task': self.config['task'],
            'timestamp': datetime.now().isoformat(),
            'model': self.model,
            'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0, # Reset counts
            'total': 0
        }
        self.summary['label'] = [] # Reset label list

        # 遍历所有结果文件
        processed_files = 0
        for filename in os.listdir(self.result_dir):
            if not filename.endswith('.json') or filename == 'summary.json': # Skip summary file itself
                continue

            file_path = os.path.join(self.result_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Use .get for robustness
                    answer = data.get('answer', 'unknown')
                    key_output = data.get('extracted', {})
                    # prompt = data.get('prompt', 'N/A') # Only uncomment if you want prompt in summary label

                    # Update counts based on answer (A, B, C, D, E, or unknown)
                    if answer in self.summary['meta']:
                         self.summary['meta'][answer] += 1
                    else:
                         # Handle unexpected answers by adding them or counting under 'unknown'
                         if 'unknown' not in self.summary['meta']:
                              self.summary['meta']['unknown'] = 0
                         self.summary['meta']['unknown'] += 1
                         logger.warning(f"Unexpected answer '{answer}' found in file {filename}")

                    self.summary['meta']['total'] += 1

                    self.summary['label'].append({
                        "path": filename,
                        #"prompt": prompt, # Uncomment if needed
                        "answer": answer,
                        "key_output": key_output
                    })
                    processed_files += 1
            except json.JSONDecodeError:
                 logger.error(f"Invalid JSON format in result file {filename}")
            except Exception as e:
                logger.error(f"读取结果文件失败 {filename}: {str(e)}")

        # Sort labels alphabetically by filename for consistent output
        self.summary['label'].sort(key=lambda x: x['path'])

        # Save summary file
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: json.dump(
                self.summary,
                open(summary_path, 'w', encoding='utf-8'),
                indent=2,
                ensure_ascii=False
            )
        )
        logger.info(f"Summary generated and saved to {summary_path} based on {processed_files} result files.")


    async def run(self, file_pairs: List[Tuple[str, ...]], overwrite: bool = True):
        """
        处理输入的文件对列表。

        Args:
            file_pairs: 文件对的列表，每个元素是一个包含多个文件路径的元组。
                        元组的长度必须与配置文件中的 file_configs 数量一致。
            overwrite: 是否覆盖已存在的输出文件。
        """
        total_pairs = len(file_pairs)
        if total_pairs == 0:
            logger.warning("没有文件对需要处理。")
            return

        # Check if the number of files in pairs matches config
        # if file_pairs and len(file_pairs[0]) != len(self.file_configs):
        #     raise ValueError(f"Mismatch: Input file tuples have {len(file_pairs[0])} files, but config requires {len(self.file_configs)}")

        semaphore = asyncio.Semaphore(self.config.get('max_workers', 5)) # Default to 5 workers
        processed_pairs = 0
        lock = asyncio.Lock() # For updating the progress counter safely

        async def update_progress():
            nonlocal processed_pairs
            async with lock:
                processed_pairs += 1
                progress = processed_pairs / total_pairs * 100
                # Avoid division by zero if total_pairs is somehow 0
                if total_pairs > 0:
                     print(f"\r {self.config['task']} {self.config['model']} 处理进度: {processed_pairs}/{total_pairs} ({progress:.2f}%)", end="", flush=True)
                else:
                     print(f"\r {self.config['task']} {self.config['model']} 处理进度: {processed_pairs}/?", end="", flush=True)


        async def bounded_process(pair):
            async with semaphore:
                try:
                    await asyncio.sleep(random.uniform(1, self.config['request_interval']))
                    await self.process_unit(pair, overwrite)
                finally:
                    await update_progress()


        logger.info(f"开始处理 {total_pairs} 个文件单元，使用 {self.config.get('max_workers', 5)} 并发...")

        tasks = [bounded_process(pair) for pair in file_pairs]
        # Use asyncio.as_completed if you want to process results as they finish,
        # but gather is fine if you just need to wait for all.
        results = await asyncio.gather(*tasks)

        print("\n" + "=" * 40) # Newline and separator

        error_count = 0
        for i, result in enumerate(results):
             if isinstance(result, Exception):
                 error_count += 1
                 # Log the error along with the pair that failed
                 logger.error(f"任务失败 (Pair {i+1}/{total_pairs} - {file_pairs[i]}): {str(result)}", exc_info=True)

        logger.info(f"处理完成。总计 {total_pairs} 个单元, {error_count} 个失败。")

        # Generate the final summary after all processing attempts are done
        await self.generate_summary()
