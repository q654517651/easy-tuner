"""
API响应模型
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseResponse):
    """错误响应模型"""
    success: bool = False
    error_type: Optional[str] = None
    detail: Optional[Any] = None


class DataResponse(BaseResponse, Generic[T]):
    """数据响应模型"""
    data: T


class ListResponse(BaseResponse, Generic[T]):
    """列表响应模型"""
    data: List[T]
    total: int = 0
    page: int = 1
    page_size: int = 50


class ProgressResponse(BaseResponse):
    """进度响应模型"""
    progress: float = Field(ge=0, le=100, description="进度百分比 (0-100)")
    current: int = Field(ge=0, description="当前完成数量")
    total: int = Field(ge=0, description="总数量")
    status: str = Field(description="状态描述")
    eta: Optional[float] = Field(default=None, description="预估剩余时间(秒)")


class TaskResponse(BaseResponse):
    """任务响应模型"""
    task_id: str
    status: str
    progress: Optional[ProgressResponse] = None
    result: Optional[Any] = None


class ApiResponse(BaseResponse):
    """通用API响应模型"""
    data: Optional[Any] = None

    def __init__(self, success: bool = True, message: str = "", data: Any = None, **kwargs):
        super().__init__(success=success, message=message, **kwargs)
        self.data = data