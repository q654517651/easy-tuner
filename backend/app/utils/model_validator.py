"""
模型支持校验工具 - 适配FastAPI后端
"""

from typing import List, Dict, Tuple
from ..core.config import get_config
from .logger import get_logger

logger = get_logger(__name__)

def validate_model_for_dataset(model_key: str, filenames: List[str]) -> Tuple[bool, str]:
    """
    检查模型是否支持指定的数据集文件类型
    
    Args:
        model_key: 模型键名 (gpt, lm_studio, local_qwen_vl)
        filenames: 数据集文件名列表
        
    Returns:
        (is_valid, error_message)
    """
    try:
        config = get_config()
        
        # 获取模型配置
        if not hasattr(config.labeling.models, model_key):
            return False, f"未知的模型类型: {model_key}"
        
        model_config = getattr(config.labeling.models, model_key)
        
        # 检查模型是否启用
        if not model_config.enabled:
            return False, f"模型 {model_key} 未启用，请在设置中启用"
        
        # 检查视频支持
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
        has_video = any(
            any(filename.lower().endswith(ext) for ext in video_extensions)
            for filename in filenames
        )
        
        if has_video and not model_config.supports_video:
            return False, f"模型 {model_key} 不支持视频文件打标"
        
        # 检查必要配置
        validation_result = validate_model_config(model_key)
        if not validation_result[0]:
            return validation_result
        
        return True, "模型配置有效"
        
    except Exception as e:
        logger.error(f"模型校验失败: {str(e)}")
        return False, f"模型校验失败: {str(e)}"


def validate_model_config(model_key: str) -> Tuple[bool, str]:
    """
    检查模型配置是否完整
    
    Args:
        model_key: 模型键名
        
    Returns:
        (is_valid, error_message)
    """
    try:
        config = get_config()
        
        if not hasattr(config.labeling.models, model_key):
            return False, f"未知的模型类型: {model_key}"
        
        model_config = getattr(config.labeling.models, model_key)
        
        # 通用检查
        if not model_config.base_url:
            return False, f"模型 {model_key} 缺少服务地址配置"
        
        if not model_config.model_name:
            return False, f"模型 {model_key} 缺少模型名称配置"
        
        # API模型需要API密钥
        if model_key in ['gpt']:
            if not model_config.api_key:
                return False, f"模型 {model_key} 缺少API密钥配置"
        
        return True, "配置完整"
        
    except Exception as e:
        logger.error(f"配置校验失败: {str(e)}")
        return False, f"配置校验失败: {str(e)}"


def get_available_models() -> List[Dict[str, str]]:
    """
    获取所有可用的模型列表
    
    Returns:
        可用模型列表，每个包含 key, name, status
    """
    config = get_config()
    models = []
    
    model_names = {
        'gpt': 'GPT API',
        'lm_studio': 'LM Studio',
        'local_qwen_vl': '本地Qwen-VL'
    }
    
    for model_key, display_name in model_names.items():
        model_config = getattr(config.labeling.models, model_key, None)
        if model_config:
            # 检查配置状态
            is_valid, message = validate_model_config(model_key)
            status = "ready" if (model_config.enabled and is_valid) else "not_ready"
            
            models.append({
                'key': model_key,
                'name': display_name,
                'status': status,
                'message': message if not is_valid else "配置正常",
                'enabled': model_config.enabled,
                'supports_video': model_config.supports_video
            })
    
    return models


def get_recommended_model_for_dataset(filenames: List[str]) -> str:
    """
    为数据集推荐最适合的模型
    
    Args:
        filenames: 数据集文件名列表
        
    Returns:
        推荐的模型键名
    """
    config = get_config()
    available_models = get_available_models()
    
    # 过滤出可用模型
    ready_models = [m for m in available_models if m['status'] == 'ready']
    
    if not ready_models:
        logger.warning("没有可用的打标模型")
        return config.labeling.selected_model
    
    # 检查是否包含视频
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
    has_video = any(
        any(filename.lower().endswith(ext) for ext in video_extensions)
        for filename in filenames
    )
    
    if has_video:
        # 优先选择支持视频的模型
        video_models = [m for m in ready_models if m['supports_video']]
        if video_models:
            # 按优先级排序：本地模型 > LM Studio > API模型
            priority_order = ['local_qwen_vl', 'lm_studio', 'gpt']
            for model_key in priority_order:
                for model in video_models:
                    if model['key'] == model_key:
                        return model_key
            return video_models[0]['key']
        else:
            logger.warning("数据集包含视频文件，但没有支持视频的模型可用")
    
    # 默认优先级：本地 > API
    priority_order = ['lm_studio', 'local_qwen_vl', 'gpt']
    for model_key in priority_order:
        for model in ready_models:
            if model['key'] == model_key:
                return model_key
    
    return ready_models[0]['key']


def check_model_connectivity(model_key: str) -> Tuple[bool, str]:
    """
    检查模型连接状态
    
    Args:
        model_key: 模型键名
        
    Returns:
        (is_connected, status_message)
    """
    try:
        from ..core.labeling.service import LabelingService
        
        labeling_service = LabelingService()
        is_connected = labeling_service.test_ai_connection(model_key)
        
        if is_connected:
            return True, "连接正常"
        else:
            return False, "连接失败"
            
    except Exception as e:
        logger.error(f"连接测试失败: {str(e)}")
        return False, f"连接测试失败: {str(e)}"
