"""
Z-Image 模型定义
包含 Z-Image LoRA 的配置和注册

Z-Image 是 Tongyi-MAI 开发的文本到图像模型，支持高质量图像生成。
目前仅发布了 Turbo 版本（蒸留模型），推荐使用 ostris 的 De-Turbo 模型或 Training Adapter 进行训练。

参考文档: workspace/runtime/engines/musubi-tuner/docs/zimage.md
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
class ZImageConfig(BaseTrainingConfig):
    """Z-Image LoRA训练配置

    Z-Image 支持文本到图像生成，使用 Qwen3 作为文本编码器。
    推荐参数：
    - timestep_sampling: shift
    - discrete_flow_shift: 2.0
    - blocks_to_swap: 最大28（用于显存优化）
    """

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "Z-Image DiT模型文件路径（推荐使用 ostris De-Turbo 版本）",
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
            "label": "文本编码器路径 (Qwen3)",
            "widget": "file_picker",
            "help": "Qwen3 文本编码器文件路径",
            "cli": {"name": "--text_encoder", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )

    # Z-Image 特有参数
    fp8_llm: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "启用 FP8 LLM",
            "widget": "switch",
            "help": "在 FP8 模式下运行 Text Encoder (Qwen3) 以节省显存",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--fp8_llm", "emit_if_default": False}
        }
    )

    # 覆盖基类的 blocks_to_swap 说明（Z-Image 最大支持 28 块）
    blocks_to_swap: int = field(
        default=0,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "内存交换块(Block Swap)",
            "widget": "number",
            "min": 0, "max": 28,  # Z-Image 最大支持 28 块
            "help": (
                "用于在内存/磁盘间交换激活以降低显存占用；0 表示不启用。\n"
                "Z-Image 最大可交换 28 个块。\n"
                "建议根据显存大小调整：\n"
                "  - 24GB VRAM: blocks_to_swap=10-15\n"
                "  - 16GB VRAM: blocks_to_swap=20-25\n"
                "  - 12GB VRAM: blocks_to_swap=28\n"
                "注意：使用 blocks_to_swap 时建议主机内存 ≥32GB。"
            ),
            "target": "cli",
            "cli": {"type": "value", "name": "--blocks_to_swap", "formatter": "int", "emit_if_default": False}
        }
    )

    # 覆盖基类的 timestep_sampling 和 discrete_flow_shift 默认值
    timestep_sampling: str = field(
        default="shift",
        metadata={
            "group": ParameterGroup.ADVANCED.key,
            "label": "时间步采样",
            "widget": "dropdown",
            "options": ["shift", "uniform"],
            "help": "Z-Image 推荐使用 shift 采样策略",
            "target": "cli",
            "cli": {"type": "value", "name": "--timestep_sampling", "formatter": "str", "emit_if_default": False}
        }
    )

    discrete_flow_shift: float = field(
        default=2.0,
        metadata={
            "group": ParameterGroup.ADVANCED.key,
            "label": "离散流偏移值",
            "widget": "number_float",
            "min": 0.1, "max": 10.0, "step": 0.1,
            "help": "Z-Image 推荐使用 2.0（与 Qwen-Image 的 3.0 不同）",
            "target": "cli",
            "enable_if": {"timestep_sampling": "shift"},
            "cli": {"type": "value", "name": "--discrete_flow_shift", "formatter": "float", "emit_if_default": False}
        }
    )


# ================================
# 注册 Z-Image 模型到全局注册表
# ================================

register_model(ModelSpec(
    type_name="zimage_lora",
    title="Z-Image LoRA",
    config_cls=ZImageConfig,
    script_train="zimage_train_network.py",
    network_module="musubi_tuner.networks.lora_zimage",
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
        "dit_path": "model_paths.zimage.dit_path",
        "vae_path": "model_paths.zimage.vae_path",
        "text_encoder_path": "model_paths.zimage.text_encoder_path"
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="zimage_cache_text_encoder_outputs.py",
            args_template=[
                "--dataset_config", "{dataset_toml}",
                "--text_encoder", "{text_encoder_path}",
                "--batch_size", "16"
            ]
        ),
        CacheStep(
            name="cache_latents",
            script="zimage_cache_latents.py",
            args_template=[
                "--dataset_config", "{dataset_toml}",
                "--vae", "{vae_path}"
            ]
        ),
    ],
    features={
        "experimental": True,  # Z-Image 仍为实验性功能
        "de_turbo_recommended": True,  # 推荐使用 De-Turbo 模型
    },
    supported_dataset_types=[
        DatasetType.IMAGE  # Z-Image 不支持控制图像
    ]
))
