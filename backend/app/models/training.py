"""
训练相关模型
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TrainingState(str, Enum):
    """训练状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingTaskBrief(BaseModel):
    """训练任务摘要信息"""
    id: str
    name: str
    dataset_id: str
    training_type: str
    state: TrainingState
    progress: float = Field(ge=0.0, le=100.0, description="训练进度 (0-1 或 0-100)")
    current_step: int = 0
    total_steps: int = 0
    current_epoch: int = 0
    total_epochs: int = 0
    speed: Optional[float] = None
    eta_seconds: Optional[int] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TrainingTaskDetail(BaseModel):
    """训练任务详细信息"""
    id: str
    name: str
    dataset_id: str
    training_type: str
    state: TrainingState
    progress: float = Field(ge=0.0, le=100.0, description="训练进度 (0-100)")
    current_step: int = 0
    total_steps: int = 0
    current_epoch: int = 0
    loss: float = 0.0
    learning_rate: float = 0.0
    eta_seconds: Optional[int] = None
    speed: Optional[float] = None  # it/s
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[str] = Field(default_factory=list)
    error_message: str = ""
    output_dir: str = ""
    checkpoint_files: List[str] = Field(default_factory=list)
    sample_images: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict, description="训练配置")
    task_dir_name: Optional[str] = Field(None, description="任务目录名（格式: {id}--{name}）")


class CreateTrainingTaskRequest(BaseModel):
    """创建训练任务请求"""
    name: str = Field(min_length=1, max_length=100, description="训练任务名称")
    dataset_id: str = Field(min_length=1, description="数据集ID")
    training_type: str = Field(default="qwen_image_lora", description="训练类型")
    config: Dict[str, Any] = Field(default_factory=dict, description="训练配置参数")

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('任务名称不能为空')
        return v.strip()


class TrainingModelSpec(BaseModel):
    """训练模型规范"""
    type_name: str = Field(description="模型类型标识")
    title: str = Field(description="模型显示名称")
    script_train: str = Field(description="训练脚本路径")
    script_cache_te: Optional[str] = Field(description="文本编码器缓存脚本")
    script_cache_latents: Optional[str] = Field(description="潜在变量缓存脚本")
    network_module: Optional[str] = Field(description="网络模块")
    group_order: List[str] = Field(default_factory=list, description="参数分组顺序")
    path_mapping: Dict[str, str] = Field(default_factory=dict, description="路径映射")
    supported_dataset_types: List[str] = Field(default_factory=list, description="支持的数据集类型列表")


class ParameterGroup(BaseModel):
    """参数分组"""
    key: str
    title: str
    description: str


class ParameterField(BaseModel):
    """参数字段定义"""
    name: str
    label: str
    widget: str
    help: str
    group: str
    value: Any
    default_value: Any
    options: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    enable_if: Optional[Dict[str, Any]] = None


class TrainingConfigSchema(BaseModel):
    """训练配置模式"""
    groups: List[ParameterGroup]
    fields: List[ParameterField]
    model_spec: TrainingModelSpec


class CLIPreviewRequest(BaseModel):
    """CLI命令预览请求"""
    training_type: str = Field(description="训练类型")
    config: Dict[str, Any] = Field(description="训练配置参数")
    dataset_id: str = Field(description="数据集ID")
    output_dir: str = Field(description="输出目录")


class CLIPreviewResponse(BaseModel):
    """CLI命令预览响应"""
    command: str = Field(description="完整的CLI命令")
    script_path: str = Field(description="训练脚本路径")
    args: List[str] = Field(description="命令行参数列表")
    working_directory: str = Field(description="工作目录")
    toml_content: str = Field(description="dataset.toml文件内容")
    toml_path: str = Field(description="dataset.toml文件路径")
    bat_script: Optional[str] = Field(None, description="Windows批处理脚本内容")


class TrainingStats(BaseModel):
    """训练统计信息"""
    total_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
