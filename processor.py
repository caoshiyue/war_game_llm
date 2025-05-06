##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-04-22 10:06:05
## 
import json
import re
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Tuple
from response import openai_response  # 替换为实际API模块
import logging
from datetime import datetime
import random

class DataProcessor:
    OPTION_PATTERN = re.compile(r'\+\+(A|B|C)\+\+')
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = config['model'] 
        self.summary = {
                        "meta": {
                        'task': config['task'],
                        'timestamp': datetime.now().isoformat(),
                        'model': self.model,      # 统计信息包含模型标识
                        'A': 0,
                        'B': 0,
                        'C': 0,
                        'total': 0
                        },
                        "label": []
                    }
        self.result_dir = os.path.join(
                    self.config['output_base'],
                    self.config['task'],
                    self.model)
        os.makedirs(self.result_dir, exist_ok=True)
        self.field_config = config.get('data_processing', {})
        self.content_field_path_a = self.field_config.get('content_field_a', '').split('.')
        self.content_field_path_b = self.field_config.get('content_field_b', '').split('.')    
        self.extract_rules = [
            {
                'name': rule.get('name', ""),
                'pattern': re.compile(rule.get('pattern',"")),
                'required': rule.get('required', False)
            }
            for rule in config['data_processing'].get('extract_fields', []) or []
        ]
        self.lock = asyncio.Lock()
        

    def _nested_get(self, data: dict, path: list, default=None):
        """安全获取嵌套数据"""
        current = data
        for key in path:
            if isinstance(current, list) and key.isdigit():
                try:
                    current = current[int(key)]
                except (IndexError, ValueError):
                    return default
            elif isinstance(current, dict):
                current = current.get(key, default)
            else:
                return default
        return current


    async def process_file(self, file_path_a: str, file_path_b: str, overwrite=True):
        """处理一对文件"""
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"Start processing pair: {file_path_a}, {file_path_b}")

            # 文件读取
            if not os.path.exists(file_path_a):
                raise FileNotFoundError(f"File not found: {file_path_a}")
            if not os.path.exists(file_path_b):
                raise FileNotFoundError(f"File not found: {file_path_b}")

            base_name_a = os.path.splitext(os.path.basename(file_path_a))[0]
            base_name_b = os.path.splitext(os.path.basename(file_path_b))[0]
            output_filename = f"{base_name_a}__{base_name_b}.json"
            output_path = os.path.join(self.result_dir, output_filename)

            if not overwrite and os.path.exists(output_path):
                logging.info(f"跳过已处理文件对: {file_path_a}, {file_path_b}")
                return

            with open(file_path_a, 'r', encoding='utf-8') as f_a, \
                 open(file_path_b, 'r', encoding='utf-8') as f_b:
                try:
                    data_a = json.load(f_a)
                    data_b = json.load(f_b)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON format in one or both files")

            content_a = self._nested_get(data_a, self.content_field_path_a)
            content_b = self._nested_get(data_b, self.content_field_path_b)

            if not content_a:
                raise KeyError(f"Missing required field in {file_path_a}: {self.content_field_path_a}")
            if not content_b:
                raise KeyError(f"Missing required field in {file_path_b}: {self.content_field_path_b}")

            # API调用
            prompt = self._build_prompt(content_a, content_b)
            n_retry = 0
            response = None
            while n_retry < 5:
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
                await self._save_result(data_a, data_b, prompt, response, answer, extracted, output_filename)

        except Exception as e:
            logger.error(f"Error processing pair {file_path_a}, {file_path_b}: {str(e)}", exc_info=True)
            raise



    def _build_prompt(self, content_a: str, content_b: str) -> list:
        """构建prompt结构，使用两个内容参数"""
        return [
            {"role": "system", "content": self.config['system_prompt']},
            {"role": "user", "content": self.config['user_prompt_template'].format(contentA=content_a, contentB=content_b)}
        ]


    def _extract_answer(self, response: str) -> str:
        """从响应中提取答案"""
        matches = self.OPTION_PATTERN.findall(response)
        if not matches:
            raise ValueError("No valid answer pattern found")
        return matches[-1]
    
    def _extract_fields(self, response: str) -> Dict[str, str]:
        """从响应中提取多个字段"""
        extracted = {}
        for rule in self.extract_rules:
            matches = rule['pattern'].findall(response)
            if not matches:
                if rule['required']:
                    raise ValueError(f"Required field {rule['name']} not found")
                extracted[rule['name']] = None
                continue
            extracted[rule['name']] = matches[-1].strip()
        return extracted
   
    async def _save_result(self, data_a: Dict, data_b: Dict, prompt: str, response: str, answer: str, extras: Dict, filename: str):
        """保存LLM交互结果，记录两个源文件"""
        # 构建结果文件内容
        result_data = {
            "source_file_a": data_a.get('file_path', os.path.basename(data_a.get('filename', ''))),
            "source_file_b": data_b.get('file_path', os.path.basename(data_b.get('filename', ''))),
            "prompt": prompt,
            "llm_response": response,
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
        await loop.run_in_executor(
            None,
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
        summary_path = os.path.join(self.result_dir, 'summary.json')
        if os.path.exists(summary_path):
                os.remove(summary_path)
        # 遍历所有结果文件
        for filename in os.listdir(self.result_dir):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(self.result_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    answer = data.get('answer', 'unknown')
                    key_output = data['extracted']
                    prompt=data['prompt']

                    
                    self.summary['meta'][answer] += 1
                    self.summary['meta']['total'] += 1
                    self.summary['label'].append({
                        "path": filename,
                        #"prompt":prompt,
                        "answer": answer,
                        "key_output":key_output
                    })
            except Exception as e:
                logging.error(f"读取结果文件失败 {filename}: {str(e)}")

        # 保存汇总文件
        
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


    def _atomic_write_summary(self, path: str, summary: dict):
        """原子化写入汇总文件"""
        lock_path = path + ".lock"
        with open(lock_path, 'w') as lock_file:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2, ensure_ascii=False)
            finally:
                os.remove(lock_path)
                
    async def run(self, file_list: list, overwrite=True):
        """处理文件列表中所有可能的无序配对"""
        import itertools

        total_files = len(file_list)
        if total_files < 2:
            print("文件数量少于 2，无法进行配对。")
            return

        pairs = list(itertools.combinations(file_list, 2))
        random.shuffle(pairs) 
        pairs=pairs[:40]
        total_pairs = len(pairs)
        semaphore = asyncio.Semaphore(self.config['max_workers'])
        processed_pairs = 0
        lock = asyncio.Lock()

        async def update_progress():
            nonlocal processed_pairs
            async with lock:
                processed_pairs += 1
                progress = processed_pairs / total_pairs * 100
                print(f"\r {self.config['task']} {self.config['model']}处理进度: {processed_pairs}/{total_pairs} ({progress:.2f}%)", end="", flush=True)

        async def bounded_process(pair):
            file_path_a, file_path_b = pair
            async with semaphore:
                try:
                    await self.process_file(file_path_a, file_path_b, overwrite)
                finally:
                    await update_progress()
                await asyncio.sleep(self.config['request_interval'])

        print(f"开始处理 {total_pairs} 对文件，使用 {self.config['max_workers']} 并发...")

        tasks = [bounded_process(pair) for pair in pairs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        print("\n" + "=" * 40)

        error_count = 0
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
                print(f"任务失败: {str(result)}")

        await self.generate_summary()
