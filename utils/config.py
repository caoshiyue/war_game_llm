##
# Author:  
# Description:  
# LastEditors: Shiyuec
# LastEditTime: 2025-05-29 07:35:34
## 
import yaml
from pathlib import Path

def load_config(config_path: str) -> dict:
    """加载YAML配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 配置验证
        required_keys = [ 'max_workers', 'output_base','data_dir','request_interval']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")
        
        
        # 创建结果目录
        Path(config['output_base']).mkdir(parents=True, exist_ok=True)
        return config
    except Exception as e:
        raise RuntimeError(f"Config loading failed: {str(e)}")