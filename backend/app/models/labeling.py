"""
打标服务相关模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class LabelingModelType(str, Enum):
    """打标模型类型"""
    GPT_4_VISION = "gpt-4-vision"
    LM_STUDIO = "lm-studio"
    QWEN_VL = "qwen-vl"


class LabelingTaskStatus(str, Enum):
    """打标任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchLabelingRequest(BaseModel):
    """批量打标请求"""
    dataset_id: str = Field(description="数据集ID")
    image_ids: Optional[List[str]] = Field(default=None, description="指定图片ID列表，为空则处理所有图片")
    model_type: LabelingModelType = Field(default=LabelingModelType.GPT_4_VISION, description="使用的模型")
    prompt: Optional[str] = Field(default=None, description="自定义提示词")
    overwrite_existing: bool = Field(default=False, description="是否覆盖已有标注")
    batch_size: int = Field(default=5, ge=1, le=20, description="批次大小")


class LabelingProgress(BaseModel):
    """打标进度"""
    task_id: str
    status: LabelingTaskStatus
    total_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    progress_percentage: float = Field(ge=0, le=100, description="完成百分比")
    current_item: Optional[str] = Field(default=None, description="当前处理项目")
    estimated_remaining_seconds: Optional[int] = Field(default=None, description="预估剩余时间(秒)")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime
    updated_at: datetime


class LabelingResult(BaseModel):
    """打标结果"""
    task_id: str
    dataset_id: str
    status: LabelingTaskStatus
    total_processed: int
    successful_count: int
    failed_count: int
    results: List[Dict[str, Any]] = Field(description="详细结果列表")
    execution_time_seconds: float
    created_at: datetime
    completed_at: Optional[datetime] = None


class AvailableModel(BaseModel):
    """可用模型信息"""
    id: str
    name: str
    type: LabelingModelType
    description: str
    supports_batch: bool = True
    max_batch_size: int = 10
    estimated_speed_per_image: float = Field(description="每张图片预估处理时间(秒)")
    is_available: bool = True
    status_message: Optional[str] = None