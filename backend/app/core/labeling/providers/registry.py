from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import asdict

from .base import LabelingProvider, ProviderMetadata, ConfigField, ConfigFieldType
from .gpt import GPTProvider
from .lm_studio import LMStudioProvider
from .qwen_vl import QwenVLProvider


_REGISTRY: Dict[str, type[LabelingProvider]] = {
    "gpt": GPTProvider,
    "lm_studio": LMStudioProvider,
    "local_qwen_vl": QwenVLProvider,
}


# Provider 配置 Schema 定义
PROVIDER_METADATA: Dict[str, ProviderMetadata] = {
    "gpt": ProviderMetadata(
        id="gpt",
        name="OpenAI GPT",
        description="OpenAI GPT 视觉模型，支持图像理解和文本生成",
        supports_video=False,
        config_fields=[
            ConfigField(
                key="api_key",
                label="API Key",
                type=ConfigFieldType.TEXT,
                required=True,
                placeholder="sk-...",
                description="OpenAI API Key 或第三方代理 API Key"
            ),
            ConfigField(
                key="base_url",
                label="API Base URL",
                type=ConfigFieldType.TEXT,
                required=True,
                default="https://api.openai.com/v1",
                placeholder="https://api.openai.com/v1",
                description="API 端点地址，使用第三方代理时需修改"
            ),
            ConfigField(
                key="model_name",
                label="模型名称",
                type=ConfigFieldType.SELECT,
                required=True,
                default="gpt-5-mini",
                description="要使用的 GPT 模型",
                options=[
                    {"label": "GPT-5 Mini (快速)", "value": "gpt-5-mini"},
                    {"label": "GPT-5 (标准)", "value": "gpt-5"}
                ]
            ),
            ConfigField(
                key="max_tokens",
                label="最大 Token 数",
                type=ConfigFieldType.NUMBER,
                default=2000,
                min=1,
                max=4096,
                step=1,
                description="生成的最大 token 数量"
            ),
            ConfigField(
                key="temperature",
                label="Temperature",
                type=ConfigFieldType.NUMBER,
                default=0.7,
                min=0.0,
                max=2.0,
                step=0.1,
                description="控制输出的随机性，0-2之间"
            )
        ]
    ),
    "lm_studio": ProviderMetadata(
        id="lm_studio",
        name="LM Studio",
        description="本地部署的视觉语言模型，通过 LM Studio 运行",
        supports_video=True,
        config_fields=[
            ConfigField(
                key="base_url",
                label="服务地址",
                type=ConfigFieldType.TEXT,
                required=True,
                default="http://127.0.0.1:1234/v1",
                placeholder="http://127.0.0.1:1234/v1",
                description="LM Studio 本地服务地址"
            ),
            ConfigField(
                key="model_name",
                label="模型名称",
                type=ConfigFieldType.TEXT,
                default="local-model",
                placeholder="local-model",
                description="LM Studio 中加载的模型名称"
            ),
            ConfigField(
                key="max_tokens",
                label="最大 Token 数",
                type=ConfigFieldType.NUMBER,
                default=2000,
                min=1,
                max=8192,
                step=1,
                description="生成的最大 token 数量"
            ),
            ConfigField(
                key="temperature",
                label="Temperature",
                type=ConfigFieldType.NUMBER,
                default=0.7,
                min=0.0,
                max=2.0,
                step=0.1,
                description="控制输出的随机性，0-2之间"
            )
        ]
    ),
    "local_qwen_vl": ProviderMetadata(
        id="local_qwen_vl",
        name="本地 Qwen-VL",
        description="本地运行的通义千问视觉语言模型（使用 runtime Python 环境）",
        supports_video=True,
        config_fields=[
            ConfigField(
                key="weights_path",
                label="模型权重路径",
                type=ConfigFieldType.FILE_PATH,
                required=True,
                placeholder="请选择 .safetensors 权重文件",
                description="Qwen-VL 模型权重文件路径（.safetensors 格式）"
            )
        ]
    )
}


def get_provider(name: str) -> Optional[LabelingProvider]:
    key = (name or "").lower().strip()
    cls = _REGISTRY.get(key)
    return cls() if cls else None


def has_provider(name: str) -> bool:
    return (name or "").lower().strip() in _REGISTRY


def get_all_provider_metadata() -> List[Dict]:
    """获取所有 provider 的元数据（用于前端显示）"""
    result = []
    for provider_id, metadata in PROVIDER_METADATA.items():
        # 转换为字典，并将 ConfigField 也转换
        meta_dict = {
            "id": metadata.id,
            "name": metadata.name,
            "description": metadata.description,
            "supports_video": metadata.supports_video,
            "is_available": metadata.is_available,
            "config_fields": [
                {
                    "key": field.key,
                    "label": field.label,
                    "type": field.type.value,
                    "required": field.required,
                    "default": field.default,
                    "placeholder": field.placeholder,
                    "description": field.description,
                    "options": field.options,
                    "min": field.min,
                    "max": field.max,
                    "step": field.step
                }
                for field in metadata.config_fields
            ]
        }
        result.append(meta_dict)
    return result


def get_provider_metadata(provider_id: str) -> Optional[ProviderMetadata]:
    """获取指定 provider 的元数据"""
    return PROVIDER_METADATA.get(provider_id)
