"""
Flux 系列模型定义
包含 Flux Kontext LoRA 的配置和注册
"""

from dataclasses import dataclass, field

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
class FluxKontext(BaseTrainingConfig):
    """Flux Kontext LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "Flux-Kontext DiT模型文件路径",
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
    text_encoder1_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "文本编码器路径(T5-XXL)",
            "widget": "file_picker",
            "help": "T5-XXL文件路径",
            "cli": {"name": "--text_encoder1", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )

    text_encoder2_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "文本编码器路径 (CLIP-L)",
            "widget": "file_picker",
            "help": "CLIP-L文件路径",
            "cli": {"name": "--text_encoder2", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )


# ================================
# 注册 Flux 系列模型到全局注册表
# ================================

register_model(ModelSpec(
    type_name="flux_kontext_lora",
    title="Flux Kontext LoRA",
    config_cls=FluxKontext,
    script_train="flux_kontext_train_network.py",  # ✅ 修正为正确的脚本名
    network_module="musubi_tuner.networks.lora_flux",
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
        "dit_path": "model_paths.flux_kontext.dit_path",
        "vae_path": "model_paths.flux_kontext.vae_path",
        "text_encoder1_path": "model_paths.flux_kontext.text_encoder1_path",
        "text_encoder2_path": "model_paths.flux_kontext.text_encoder2_path"
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="flux_kontext_cache_text_encoder_outputs.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--text_encoder1", "{text_encoder1_path}",
                           "--text_encoder2", "{text_encoder2_path}",
                           "--batch_size", "16",
                           "--logging_dir", "{cache_logs_dir}"]
        ),
        CacheStep(
            name="cache_latents",
            script="flux_kontext_cache_latents.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--vae", "{vae_path}",
                           "--logging_dir", "{cache_logs_dir}"]
        ),
    ],
    features={},
    supported_dataset_types=[DatasetType.IMAGE, DatasetType.SINGLE_CONTROL_IMAGE]
))
