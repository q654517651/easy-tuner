"""
系统信息相关的数据模型
"""
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class GPUMetrics(BaseModel):
    """GPU指标数据模型"""
    id: int
    name: str
    memory_total: int           # 总显存 MB
    memory_used: int            # 已用显存 MB
    memory_free: int            # 空闲显存 MB
    memory_utilization: float   # 显存利用率 0-100%
    gpu_utilization: float      # GPU利用率 0-100%
    temperature: int            # 温度 摄氏度
    power_draw: float          # 当前功耗 瓦特
    power_limit: float         # 功耗上限 瓦特
    fan_speed: Optional[int] = None    # 风扇转速 % (可选)


class SystemGPUResponse(BaseModel):
    """GPU系统信息响应模型"""
    gpus: List[GPUMetrics]
    timestamp: str
    total_gpus: int


class GPUError(BaseModel):
    """GPU错误信息模型"""
    error_type: str
    message: str
    gpu_id: Optional[int] = None