"""
Musubi-Tuner 工具函数 - 适配FastAPI后端
使用内嵌的git子模块，无需额外配置
"""

import subprocess
from pathlib import Path
from typing import Dict, Any
from .logger import get_logger

logger = get_logger(__name__)

def get_musubi_path() -> str:
    """获取内嵌的musubi-tuner路径"""
    project_root = Path(__file__).parent.parent.parent.parent
    return str(project_root / "runtime" / "engines" / "musubi-tuner")


def check_musubi_status() -> Dict[str, Any]:
    """检查内嵌musubi-tuner状态"""
    try:
        musubi_dir = Path(get_musubi_path())
        
        if not musubi_dir.exists():
            return {
                "available": False,
                "status": "Musubi训练引擎未找到，请检查runtime/engines/musubi-tuner目录是否存在"
            }
        
        # 检查关键训练脚本
        required_scripts = [
            "src/musubi_tuner/qwen_image_train_network.py",
            "src/musubi_tuner/qwen_image_cache_latents.py",
            "src/musubi_tuner/qwen_image_cache_text_encoder_outputs.py"
        ]
        
        missing_scripts = []
        for script in required_scripts:
            script_path = musubi_dir / script
            if not script_path.exists():
                missing_scripts.append(script)
        
        if missing_scripts:
            return {
                "available": False,
                "status": f"训练脚本缺失: {', '.join(missing_scripts)}"
            }
        
        # 不再检查accelerate命令，因为使用独立环境
        
        # 不再检查模块导入，因为使用独立runtime环境
        # 前端环境不需要也不应该导入musubi_tuner模块
        
        return {
            "available": True,
            "status": "Musubi训练引擎就绪"
        }
        
    except Exception as e:
        logger.error(f"检查Musubi状态失败: {e}")
        return {
            "available": False,
            "status": f"检查失败: {str(e)}"
        }


def get_available_training_backends() -> Dict[str, bool]:
    """获取可用的训练后端"""
    musubi_dir = Path(get_musubi_path())
    
    backends = {
        "qwen_image": False,
        "flux": False,
        "sd": False
    }
    
    if not musubi_dir.exists():
        return backends
    
    # 检查各个模型的训练脚本
    script_mapping = {
        "qwen_image": "src/musubi_tuner/qwen_image_train_network.py",
        "flux": "src/musubi_tuner/flux_train_network.py",
        "sd": "src/musubi_tuner/sd_train_network.py"
    }
    
    for backend, script_path in script_mapping.items():
        if (musubi_dir / script_path).exists():
            backends[backend] = True
    
    return backends


def validate_musubi_installation() -> bool:
    """验证Musubi-Tuner安装完整性"""
    status = check_musubi_status()
    if not status["available"]:
        logger.error(f"Musubi-Tuner不可用: {status['status']}")
        return False
    
    logger.info("Musubi-Tuner验证通过")
    return True


def get_training_script_path(training_type: str) -> str:
    """获取训练脚本路径"""
    musubi_dir = Path(get_musubi_path())
    
    script_mapping = {
        "qwen_image": "src/musubi_tuner/qwen_image_train_network.py",
        "flux": "src/musubi_tuner/flux_train_network.py", 
        "sd": "src/musubi_tuner/sd_train_network.py"
    }
    
    if training_type not in script_mapping:
        raise ValueError(f"不支持的训练类型: {training_type}")
    
    script_path = musubi_dir / script_mapping[training_type]
    if not script_path.exists():
        raise FileNotFoundError(f"训练脚本不存在: {script_path}")
    
    return str(script_path)