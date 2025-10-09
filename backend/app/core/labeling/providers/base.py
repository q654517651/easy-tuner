from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
from enum import Enum

from ...exceptions import LabelingError, ValidationError

ImageInput = Union[str, Path, bytes]
TextInput = str


@dataclass
class LabelResult:
    ok: bool
    text: Optional[str] = None
    error_code: Optional[str] = None
    detail: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None


class ConfigFieldType(str, Enum):
    """配置字段类型"""
    TEXT = "text"
    NUMBER = "number"
    SELECT = "select"
    FILE_PATH = "file_path"
    CHECKBOX = "checkbox"


@dataclass
class ConfigField:
    """配置字段定义"""
    key: str  # 配置键名，如 "api_key"
    label: str  # 显示标签，如 "API Key"
    type: ConfigFieldType  # 字段类型
    required: bool = False  # 是否必填
    default: Any = None  # 默认值
    placeholder: str = ""  # 占位提示
    description: str = ""  # 字段说明
    options: List[Dict[str, str]] = field(default_factory=list)  # 下拉选项（type=SELECT时使用）
    min: Optional[float] = None  # 最小值（type=NUMBER时使用）
    max: Optional[float] = None  # 最大值（type=NUMBER时使用）
    step: Optional[float] = None  # 步长（type=NUMBER时使用）


@dataclass
class ProviderMetadata:
    """Provider 元数据"""
    id: str  # provider id，如 "gpt"
    name: str  # 显示名称，如 "OpenAI GPT"
    description: str  # 描述
    config_fields: List[ConfigField]  # 配置字段定义
    supports_video: bool = False  # 是否支持视频
    is_available: bool = False  # 当前是否可用（配置完整且连接正常）


class LabelingProvider(ABC):
    """
    标注 Provider 抽象：
    - 统一 async，避免阻塞事件循环
    - 单多接口统一；单图默认走批量实现的便捷封装
    - 错误请抛 LabelingError/ValidationError，或返回 ok=False 的 LabelResult
    """

    name: str = "base"
    capabilities: Sequence[str] = ("label_image", "translate_text")

    @classmethod
    def get_metadata(cls) -> Optional[ProviderMetadata]:
        """返回 Provider 的元数据和配置字段定义（可选实现）"""
        return None

    @abstractmethod
    async def test_connection(self) -> bool:
        """连通性自检（鉴权、心跳等）。失败返回 False 或抛 LabelingError。"""

    async def generate_label(
        self, image: ImageInput, prompt: Optional[str] = None, **options: Any
    ) -> LabelResult:
        results = await self.generate_labels([image], prompt=prompt, **options)
        return results[0]

    @abstractmethod
    async def generate_labels(
        self, images: Sequence[ImageInput], prompt: Optional[str] = None, **options: Any
    ) -> List[LabelResult]:
        """批量标注，需保证与单图等价的语义。"""

    @abstractmethod
    async def translate(
        self, text: TextInput, *, source_lang: Optional[str] = None, target_lang: str = "zh", **options: Any
    ) -> LabelResult:
        """文本翻译改写。"""

