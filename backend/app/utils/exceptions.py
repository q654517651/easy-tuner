"""
自定义异常类 - 适配FastAPI后端
"""

class EasyTunerError(Exception):
    """EasyTuner基础异常类"""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}

class DatasetError(EasyTunerError):
    """数据集相关错误"""
    pass

class DatasetNotFoundError(DatasetError):
    """数据集不存在"""
    
    def __init__(self, dataset_id: str):
        super().__init__(
            f"数据集不存在: {dataset_id}",
            error_code="DATASET_NOT_FOUND",
            details={"dataset_id": dataset_id}
        )

class DatasetCreateError(DatasetError):
    """数据集创建失败"""
    pass

class ImageProcessingError(EasyTunerError):
    """图像处理错误"""
    pass

class ImageNotFoundError(ImageProcessingError):
    """图像文件不存在"""
    
    def __init__(self, image_path: str):
        super().__init__(
            f"图像文件不存在: {image_path}",
            error_code="IMAGE_NOT_FOUND",
            details={"image_path": image_path}
        )

class ImageFormatError(ImageProcessingError):
    """不支持的图像格式"""
    
    def __init__(self, format_type: str):
        super().__init__(
            f"不支持的图像格式: {format_type}",
            error_code="UNSUPPORTED_IMAGE_FORMAT",
            details={"format": format_type}
        )

class LabelingError(EasyTunerError):
    """打标相关错误"""
    pass

class AIServiceError(LabelingError):
    """AI服务调用错误"""
    
    def __init__(self, service_name: str, original_error: str):
        super().__init__(
            f"AI服务调用失败 ({service_name}): {original_error}",
            error_code="AI_SERVICE_ERROR",
            details={"service": service_name, "original_error": original_error}
        )

class TrainingError(EasyTunerError):
    """训练相关错误"""
    pass

class TrainingConfigError(TrainingError):
    """训练配置错误"""
    pass

class TrainingNotFoundError(TrainingError):
    """训练任务不存在"""
    
    def __init__(self, task_id: str):
        super().__init__(
            f"训练任务不存在: {task_id}",
            error_code="TRAINING_NOT_FOUND",
            details={"task_id": task_id}
        )

class StorageError(EasyTunerError):
    """存储相关错误"""
    pass

class ConfigError(EasyTunerError):
    """配置相关错误"""
    pass

class ValidationError(EasyTunerError):
    """验证错误"""
    
    def __init__(self, field: str, value: str, reason: str):
        super().__init__(
            f"验证失败 {field}='{value}': {reason}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "value": value, "reason": reason}
        )