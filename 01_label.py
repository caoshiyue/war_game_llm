##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-04-13 08:16:09
## 
import os
import asyncio
from utils.config import load_config  # 实现配置文件加载
from processor import DataProcessor
from itertools import product

def find_data_files(data_dir: str) -> list:
    """获取待处理文件列表"""
    return [os.path.join(data_dir, f) for f in os.listdir(data_dir) 
           if f.endswith('.json')]

async def single_process(model,config_path,overwrite=True):
    config = load_config(config_path)
    config['model']=model
    processor = DataProcessor(config)
    
    data_files = find_data_files(config['data_dir'])
    await processor.run(data_files,overwrite)
    processor.print_summary()

async def async_runner(models,configs,overwrite):
    """异步任务调度器"""
   
    # 创建所有任务组合
    tasks = [
        single_process(model, config,overwrite)
        for model, config in product(models, configs)
    ]
    
    # 使用信号量控制并发度（根据系统资源调整）
    semaphore = asyncio.Semaphore(10)  # 同时最多运行4个任务
    
    async def sem_task(task):
        async with semaphore:
            return await task
    
    # 并行执行所有任务
    await asyncio.gather(*(sem_task(t) for t in tasks))


# "deepseek-v3", "deepseek-r1", "gpt-4o", "o3-mini", "qwen-max-latest"

if __name__ == "__main__":
    models = ["deepseek-v3", "deepseek-r1", "o1-mini", "qwen-max-latest"]
    configs = [
        "configs/config11.yaml",
        "configs/config12.yaml",
        "configs/config13.yaml",
        "configs/config14.yaml",
        "configs/config15.yaml",
        "configs/config16.yaml"
    ]
    asyncio.run(async_runner(models,configs,overwrite=True))
    #asyncio.run(single_process("gpt-4o","configs/config1.yaml"))

    