"""
Validation utilities for FastAPI backend
"""

import os
from pathlib import Path
from typing import List
from ..core.config import SUPPORTED_IMAGE_FORMATS, SUPPORTED_VIDEO_FORMATS
from ..core.exceptions import ValidationError

def validate_image_file(file_path: str) -> bool:
    """验证图像文件"""
    if not os.path.exists(file_path):
        raise ValidationError(f"文件不存在: {file_path}")

    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_IMAGE_FORMATS:
        raise ValidationError(f"不支持的图像格式 {ext}，支持的格式: {', '.join(SUPPORTED_IMAGE_FORMATS)}")

    return True

def validate_video_file(file_path: str) -> bool:
    """验证视频文件"""
    if not os.path.exists(file_path):
        raise ValidationError(f"文件不存在: {file_path}")

    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_VIDEO_FORMATS:
        raise ValidationError(f"不支持的视频格式 {ext}，支持的格式: {', '.join(SUPPORTED_VIDEO_FORMATS)}")

    return True

def validate_dataset_name(name: str) -> bool:
    """验证数据集名称"""
    if not name or not name.strip():
        raise ValidationError("数据集名称不能为空")

    if len(name.strip()) < 2:
        raise ValidationError(f"数据集名称至少2个字符: {name}")

    # 检查非法字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        if char in name:
            raise ValidationError(f"数据集名称不能包含字符 '{char}': {name}")

    return True

def validate_resolution(resolution: str) -> bool:
    """验证分辨率格式"""
    try:
        parts = resolution.split(',')
        if len(parts) != 2:
            raise ValidationError(f"分辨率格式应为 'width,height': {resolution}")

        width, height = int(parts[0].strip()), int(parts[1].strip())

        if width <= 0 or height <= 0:
            raise ValidationError(f"分辨率必须大于0: {resolution}")

        if width > 4096 or height > 4096:
            raise ValidationError(f"分辨率不能超过4096: {resolution}")

        return True
    except ValueError:
        raise ValidationError(f"分辨率必须是数字: {resolution}")

def validate_learning_rate(lr: float) -> bool:
    """验证学习率"""
    if lr <= 0:
        raise ValidationError(f"学习率必须大于0: {lr}")

    if lr > 1.0:
        raise ValidationError(f"学习率不建议超过1.0: {lr}")

    return True

def validate_epochs(epochs: int) -> bool:
    """验证训练轮数"""
    if epochs <= 0:
        raise ValidationError(f"训练轮数必须大于0: {epochs}")

    if epochs > 1000:
        raise ValidationError(f"训练轮数过大，请检查设置: {epochs}")

    return True

def validate_batch_size(batch_size: int) -> bool:
    """验证批次大小"""
    if batch_size <= 0:
        raise ValidationError(f"批次大小必须大于0: {batch_size}")

    if batch_size > 32:
        raise ValidationError(f"批次大小过大，可能导致显存不足: {batch_size}")

    return True

def validate_file_paths(paths: List[str], file_type: str = "any") -> List[str]:
    """批量验证文件路径"""
    valid_paths = []

    for path in paths:
        try:
            if file_type == "image":
                validate_image_file(path)
            elif file_type == "video":
                validate_video_file(path)
            elif file_type == "any":
                if not os.path.exists(path):
                    raise ValidationError(f"文件不存在: {path}")

            valid_paths.append(path)
        except ValidationError:
            # 跳过无效文件，继续验证其他文件
            continue

    return valid_paths

def validate_directory(dir_path: str, create_if_missing: bool = False) -> bool:
    """验证目录"""
    if not os.path.exists(dir_path):
        if create_if_missing:
            try:
                os.makedirs(dir_path, exist_ok=True)
                return True
            except Exception as e:
                raise ValidationError(f"无法创建目录 {dir_path}: {str(e)}")
        else:
            raise ValidationError(f"目录不存在: {dir_path}")

    if not os.path.isdir(dir_path):
        raise ValidationError(f"路径不是目录: {dir_path}")

    return True