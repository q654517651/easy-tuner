"""
Qwen 系列模型定义
包含 Qwen-Image LoRA 和 Qwen-Image Edit 2095 LoRA 的配置和注册
"""

from dataclasses import dataclass, field
from typing import Optional

# 从父模块导入核心组件
from ..models import (
    BaseTrainingConfig,
    ParameterGroup,
    ModelSpec,
    CacheStep,
    register_model
)
from ...dataset.models import DatasetType


@dataclass
class QwenImageConfig(BaseTrainingConfig):
    """Qwen-Image LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "Qwen-Image DiT模型文件路径",
            "cli": {"name": "--dit", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )
    vae_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "VAE 模型路径",
            "widget": "file_picker",
            "help": "VAE模型文件路径",
            "cli": {"name": "--vae", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )
    text_encoder_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "文本编码器路径",
            "widget": "file_picker",
            "help": "文本编码器模型文件路径",
            "cli": {"name": "--text_encoder", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )


@dataclass
class QwenImageEdit2509Config(BaseTrainingConfig):
    """Qwen-Image Edit 2509 LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "Qwen-Image Edit 2509 DiT模型文件路径",
            "cli": {"name": "--dit", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )
    vae_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "VAE 模型路径",
            "widget": "file_picker",
            "help": "VAE模型文件路径",
            "cli": {"name": "--vae", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )
    text_encoder_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "文本编码器路径",
            "widget": "file_picker",
            "help": "文本编码器模型文件路径",
            "cli": {"name": "--text_encoder", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )

    model_version: str = field(
        default="edit-2509",  # ✅ 写死为 edit-2509
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "模型版本",
            "widget": "text",
            "help": "模型版本标识（自动设置为 edit-2509）",
            "target": "cli",
            "cli": {"type": "value", "name": "--model_version"},
            "ui_hidden": True,  # 不在 UI 显示
            "persist": False
        }
    )


@dataclass
class QwenImageEdit2511Config(BaseTrainingConfig):
    """Qwen-Image Edit 2511 LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "Qwen-Image Edit 2511 DiT模型文件路径",
            "cli": {"name": "--dit", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )
    vae_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "VAE 模型路径",
            "widget": "file_picker",
            "help": "VAE模型文件路径（与 Edit 2509 共享）",
            "cli": {"name": "--vae", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )
    text_encoder_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "文本编码器路径",
            "widget": "file_picker",
            "help": "文本编码器模型文件路径（Qwen2.5-VL）",
            "cli": {"name": "--text_encoder", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )

    model_version: str = field(
        default="edit-2511",  # ✅ 写死为 edit-2511
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "模型版本",
            "widget": "text",
            "help": "模型版本标识（自动设置为 edit-2511）",
            "target": "cli",
            "cli": {"type": "value", "name": "--model_version"},
            "ui_hidden": True,  # 不在 UI 显示
            "persist": False
        }
    )


# ================================
# 注册 Qwen 系列模型到全局注册表
# ================================

register_model(ModelSpec(
    type_name="qwen_image_lora",
    title="Qwen-Image LoRA",
    config_cls=QwenImageConfig,
    script_train="qwen_image_train_network.py",
    network_module="musubi_tuner.networks.lora_qwen_image",
    group_order=[
        ParameterGroup.PATH.key,
        ParameterGroup.BASIC.key,
        ParameterGroup.OPTIMIZER.key,
        ParameterGroup.PRECISION.key,
        ParameterGroup.SAMPLING.key,
        ParameterGroup.SAVING.key,
        ParameterGroup.ADVANCED.key,
    ],
    path_mapping={
        "dit_path": "model_paths.qwen_image.dit_path",
        "vae_path": "model_paths.qwen_image.vae_path",
        "text_encoder_path": "model_paths.qwen_image.text_encoder_path"
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="qwen_image_cache_text_encoder_outputs.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--text_encoder", "{text_encoder_path}",
                           "--batch_size", "1"]
        ),
        CacheStep(
            name="cache_latents",
            script="qwen_image_cache_latents.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--vae", "{vae_path}"]
        ),
    ],
    features={},
    supported_dataset_types=[DatasetType.IMAGE]
))

register_model(ModelSpec(
    type_name="qwen_image_edit_2509_lora",
    title="Qwen-Image Edit 2509 LoRA",
    config_cls=QwenImageEdit2509Config,
    script_train="qwen_image_train_network.py",
    network_module="musubi_tuner.networks.lora_qwen_image",
    group_order=[
        ParameterGroup.PATH.key,
        ParameterGroup.BASIC.key,
        ParameterGroup.OPTIMIZER.key,
        ParameterGroup.PRECISION.key,
        ParameterGroup.SAMPLING.key,
        ParameterGroup.SAVING.key,
        ParameterGroup.ADVANCED.key,
    ],
    path_mapping={
        "dit_path": "model_paths.qwen_image_edit_2509.dit_path",
        "vae_path": "model_paths.qwen_image_edit_2509.vae_path",
        "text_encoder_path": "model_paths.qwen_image_edit_2509.text_encoder_path"
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="qwen_image_cache_text_encoder_outputs.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--text_encoder", "{text_encoder_path}",
                           "--model_version", "edit-2509",
                           "--batch_size", "1"]
        ),
        CacheStep(
            name="cache_latents",
            script="qwen_image_cache_latents.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--model_version", "edit-2509",
                           "--vae", "{vae_path}"]
        ),
    ],
    features={},
    supported_dataset_types=[DatasetType.IMAGE, DatasetType.SINGLE_CONTROL_IMAGE, DatasetType.MULTI_CONTROL_IMAGE]
))

register_model(ModelSpec(
    type_name="qwen_image_edit_2511_lora",
    title="Qwen-Image Edit 2511 LoRA",
    config_cls=QwenImageEdit2511Config,
    script_train="qwen_image_train_network.py",
    network_module="musubi_tuner.networks.lora_qwen_image",
    group_order=[
        ParameterGroup.PATH.key,
        ParameterGroup.BASIC.key,
        ParameterGroup.OPTIMIZER.key,
        ParameterGroup.PRECISION.key,
        ParameterGroup.SAMPLING.key,
        ParameterGroup.SAVING.key,
        ParameterGroup.ADVANCED.key,
    ],
    path_mapping={
        "dit_path": "model_paths.qwen_image_edit_2511.dit_path",
        "vae_path": "model_paths.qwen_image_edit_2511.vae_path",
        "text_encoder_path": "model_paths.qwen_image_edit_2511.text_encoder_path"
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="qwen_image_cache_text_encoder_outputs.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--text_encoder", "{text_encoder_path}",
                           "--model_version", "edit-2511",
                           "--batch_size", "1"]
        ),
        CacheStep(
            name="cache_latents",
            script="qwen_image_cache_latents.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--model_version", "edit-2511",
                           "--vae", "{vae_path}"]
        ),
    ],
    features={},
    supported_dataset_types=[DatasetType.IMAGE, DatasetType.SINGLE_CONTROL_IMAGE, DatasetType.MULTI_CONTROL_IMAGE]
))
