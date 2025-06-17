'''
Author: Likun Yang
Date: 2025-05-07 09:18:00
LastEditors: caoshiyue caoshiyueKevin@Gmail.com
LastEditTime: 2025-05-30 08:15:09
Copyright (c) 2025 by Likun Yang, All Rights Reserved. 
'''
import os
import asyncio
from utils.config import load_config  # 实现配置文件加载
from processor import DataProcessor
from itertools import product,combinations
from typing import Dict, Tuple, List, Any
import random

def generate_file_pairs_from_list(file_list: list, num_sample: int = 0) -> List[Tuple[str, str]]:

    file_pairs = []
    file_list.sort()
    for item in file_list:
        # Create a tuple with the item repeated 5 times
        # Using tuple([item] * 5) is a concise way to create a tuple of repeated items
        repeated_tuple = tuple([item] )
        file_pairs.append(repeated_tuple)
    # Note: num_sample is ignored based on the described requirement of repeating each item 5 times.
    # If sampling or pair generation was the actual goal, the logic would be different.
    if num_sample!=0:
        file_pairs=file_pairs[:num_sample]
    return file_pairs


def find_data_files(data_dir: str) -> list:
    """获取待处理文件列表"""
    return [os.path.join(data_dir, f) for f in os.listdir(data_dir) 
           if f.endswith('.json')]

async def single_process(model,config_path,**kwargs):
    config = load_config(config_path)
    config['model']=model
    processor = DataProcessor(config)
    data_files = find_data_files(os.path.join(config['data_dir'],config['task']))
    file_pairs = generate_file_pairs_from_list(data_files,kwargs['num_sample'])

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
    semaphore = asyncio.Semaphore(2)  # 同时最多运行4个任务
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    # 并行执行所有任务
    await asyncio.gather(*(sem_task(t) for t in tasks))


# "deepseek-v3", "deepseek-r1", "gpt-4o", "o3-mini", "qwen3-235b-a22b"

if __name__ == "__main__":
    models = ["deepseek-v3", "deepseek-r1",   "qwen3-235b-a22b"]
    configs = [
        "configs/config3_Q2.yaml", # multi_tank_red
        "configs/config4_Q2.yaml", # tank_path_red
        "configs/config5_Q2.yaml", # runaway_red
        "configs/config6_Q2.yaml", # tank_back_red

        "configs/config8_Q2.yaml", # missile_red
        "configs/config9_Q2.yaml",  # drone_red

        "configs/config11_Q2.yaml", # unload_red
        "configs/config12_Q2.yaml", # UGV_red

        "configs/config3_Q1.yaml", # multi_tank_red
        "configs/config4_Q1.yaml", # tank_path_red
        "configs/config5_Q1.yaml", # runaway_red
        "configs/config6_Q1.yaml", # tank_back_red

        "configs/config8_Q1.yaml", # missile_red
        "configs/config9_Q1.yaml",  # drone_red

        "configs/config11_Q1.yaml", # unload_red
        "configs/config12_Q1.yaml", # UGV_red
        
    ]
    asyncio.run(async_runner(models,configs,overwrite=False,num_sample=0))
    #asyncio.run(single_process("gpt-4o","configs/config1.yaml"))

