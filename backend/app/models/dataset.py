"""
数据集相关模型
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# 导入核心业务模型的DatasetType，避免重复定义
from ..core.dataset.models import DatasetType


class MediaType(str, Enum):
    """媒体类型"""
    IMAGE = "image"
    VIDEO = "video"


class Dataset(BaseModel):
    """数据集模型"""
    dataset_id: str
    name: str
    type: DatasetType = DatasetType.IMAGE
    description: str = ""
    created_at: datetime
    updated_at: datetime
    items: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class DatasetBrief(BaseModel):
    """数据集摘要信息（列表页使用）"""
    id: str
    name: str
    type: DatasetType
    total_count: int = Field(default=0, description="总文件数")
    labeled_count: int = Field(default=0, description="已标注数")
    created_at: datetime
    updated_at: datetime
    thumbnail_url: Optional[str] = None


class ControlImage(BaseModel):
    """控制图信息"""
    url: str = Field(description="控制图访问URL")
    filename: str = Field(description="控制图文件名")


class MediaItem(BaseModel):
    """媒体文件信息"""
    id: str
    filename: str
    file_path: str
    url: str = Field(description="访问URL")
    thumbnail_url: Optional[str] = None
    media_type: MediaType
    caption: str = Field(default="", description="标注文本")
    file_size: int = Field(default=0, description="文件大小(字节)")
    dimensions: Optional[tuple[int, int]] = Field(default=None, description="图片尺寸 [width, height]")
    control_images: Optional[List[ControlImage]] = Field(default=None, description="控制图列表（用于控制图数据集）")
    created_at: datetime
    updated_at: datetime


class DatasetDetail(BaseModel):
    """数据集详细信息"""
    id: str
    name: str
    type: DatasetType
    description: str = ""
    total_count: int = 0
    labeled_count: int = 0
    created_at: datetime
    updated_at: datetime
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # 媒体文件列表（分页）
    media_items: List[MediaItem] = Field(default_factory=list)
    media_total: int = 0
    media_page: int = 1
    media_page_size: int = 50


class CreateDatasetRequest(BaseModel):
    """创建数据集请求"""
    name: str = Field(min_length=1, max_length=100, description="数据集名称")
    type: DatasetType = Field(description="数据集类型")
    description: str = Field(default="", max_length=500, description="数据集描述")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('数据集名称不能为空')
        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'数据集名称不能包含字符: {char}')
        return v.strip()


class UpdateDatasetRequest(BaseModel):
    """更新数据集请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100, description="数据集名称")
    description: Optional[str] = Field(default=None, max_length=500, description="数据集描述")
    tags: Optional[List[str]] = Field(default=None, description="数据集标签")


class ImportMediaRequest(BaseModel):
    """导入媒体文件请求"""
    file_paths: List[str] = Field(description="文件路径列表")
    copy_files: bool = Field(default=True, description="是否复制文件到工作区")
    auto_label: bool = Field(default=False, description="是否自动进行AI打标")


class UpdateCaptionRequest(BaseModel):
    """更新标注请求"""
    caption: str = Field(description="新的标注文本")


class RenameDatasetRequest(BaseModel):
    """重命名数据集请求"""
    new_name: str = Field(min_length=1, max_length=100, description="新的数据集名称")

    @validator('new_name')
    def validate_new_name(cls, v):
        if not v or not v.strip():
            raise ValueError('数据集名称不能为空')
        # 检查非法字符
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f'数据集名称不能包含字符: {char}')
        return v.strip()


class DatasetStats(BaseModel):
    """数据集统计信息"""
    total_datasets: int = 0
    total_media_files: int = 0
    total_labeled_files: int = 0
    storage_usage: int = Field(default=0, description="存储使用量(字节)")
    by_type: Dict[str, int] = Field(default_factory=dict, description="按类型统计")