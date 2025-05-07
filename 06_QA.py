'''
Author: Likun Yang
Date: 2025-05-07 09:18:00
LastEditors: Likun Yang
LastEditTime: 2025-05-07 10:07:07
Copyright (c) 2025 by Likun Yang, All Rights Reserved. 
'''
import os
import asyncio
from utils.config import load_config  # 实现配置文件加载
from processor import DataProcessor
from itertools import product,combinations
from typing import Dict, Tuple, List, Any
import random

preference_list_path = "extract/extract_search_multi_tank_red.json"




def generate_file_pairs_from_list(file_list: list, num_sample: int = 0) -> List[Tuple[str, str]]:
    """
    Args:
        file_list: 包含所有文件路径的列表。
        num_sample: 需要抽样的文件对数量。如果为0，则返回所有可能的配对。

    Returns:
        文件对的列表，每个文件对是一个包含两个文件路径的元组。
    """
    
    
    
    
    if len(file_list) < 4:
        print("文件数量少于 4，无法进行配对。")
        return []

    pairs = list(combinations(file_list, 4)) # 需要与config中的路径数量一致
    random.shuffle(pairs)

    if num_sample > 0 and num_sample < len(pairs):
        print(f"从 {len(pairs)} 对中抽样 {num_sample} 对进行处理。")
        return pairs[:num_sample]
    else:
        print(f"将处理所有 {len(pairs)} 对文件。")
        return pairs

def find_data_files(data_dir: str) -> list:
    """获取待处理文件列表"""
    return [os.path.join(data_dir, f) for f in os.listdir(data_dir) 
           if f.endswith('.json')]

async def single_process(model,config_path,**kwargs):
    config = load_config(config_path)
    config['model']=model
    processor = DataProcessor(config)
    data_files = find_data_files(config['data_dir'])
    file_pairs=generate_file_pairs_from_list(data_files,num_sample=kwargs['num_sample'])

    await processor.run(file_pairs,overwrite=kwargs['overwrite'])
    processor.print_summary()

async def async_runner(models,configs,**kwargs):
    """异步任务调度器"""
   
    # 创建所有任务组合
    tasks = [
        single_process(model, config,**kwargs)
        for model, config in product(models, configs)
    ]
    
    # 使用信号量控制并发度（根据系统资源调整）
    semaphore = asyncio.Semaphore(8)  # 同时最多运行4个任务
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    # 并行执行所有任务
    await asyncio.gather(*(sem_task(t) for t in tasks))


# "deepseek-v3", "deepseek-r1", "gpt-4o", "o3-mini", "qwen-max-latest"

if __name__ == "__main__":
    models = ["deepseek-r1",]
    configs = [
        # "configs/config3.yaml",
        # "configs/config4.yaml",
        # "configs/config5.yaml",
        # "configs/config6.yaml",
        # "configs/config7.yaml",
        "configs/config8_多文件.yaml",
        
    ]
    asyncio.run(async_runner(models,configs,overwrite=False,num_sample=16))
    #asyncio.run(single_process("gpt-4o","configs/config1.yaml"))

