"""
Wan 系列模型定义
包含 Wan 2.1 和 Wan 2.2 的配置和注册
"""

from dataclasses import dataclass, field
from typing import List

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
class Wan21(BaseTrainingConfig):
    """Wan 2.1 LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "Wan2.1 模型路径",
            "widget": "file_picker",
            "help": "Wan2.1 DiT模型文件路径",
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
    t5_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "T5-XXL 模型路径",
            "widget": "file_picker",
            "help": "T5-XXL文件路径",
            "cli": {"name": "--t5", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )

    task: str = field(
        default="t2i-14B",
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "任务类型",
            "widget": "dropdown",
            "options": ["t2v-1.3B", "t2v-14B", "i2v-14B", "t2i-14B"],
            "help": "wan2.1任务类型选择",
            "target": "cli",
            "cli": {"type": "value", "name": "--task", "formatter": "str", "emit_if_default": False}
        }
    )

    # ================================
    # 视频数据集专用参数（仅视频数据集需要）
    # ================================
    frame_extraction: str = field(
        default="head",
        metadata={
            "group": ParameterGroup.DATASET.key,
            "label": "视频帧提取方式",
            "widget": "dropdown",
            "options": ["head", "chunk", "slide", "uniform", "full"],
            "help": (
                "从视频中提取帧的方式（仅视频数据集需要）：\n"
                "  - head: 从视频开头提取前 N 帧\n"
                "  - chunk: 将视频分割成 N 帧的块\n"
                "  - slide: 滑动采样\n"
                "  - uniform: 均匀采样\n"
                "  - full: 提取全部帧（会被裁剪为 N*4+1 帧）\n"
                "推荐：重复动作用 head/chunk/slide，完整动作用 full"
            ),
            "target": "toml",
            "toml": {
                "section": "datasets",
                "key": "frame_extraction",
                "formatter": "str"
            },
            "dataset_type_filter": ["video"],
            "ui_hidden": False,
            "persist": True
        }
    )

    target_frames: List[int] = field(
        default_factory=lambda: [1, 25, 45],
        metadata={
            "group": ParameterGroup.DATASET.key,
            "label": "目标帧数",
            "widget": "list_int",
            "help": (
                "提取的目标帧数列表，格式: [1, 25, 45]\n"
                "注意：Wan2.1 的帧数必须是 N*4+1 (如 1, 5, 9, 13, 17, 21, 25, 29...)"
            ),
            "target": "toml",
            "toml": {
                "section": "datasets",
                "key": "target_frames",
                "formatter": "list_int"
            },
            "dataset_type_filter": ["video"],
            "ui_hidden": False,
            "persist": True
        }
    )


@dataclass
class Wan22(BaseTrainingConfig):
    """Wan 2.2 LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "wan2.2模型文件路径",
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
    t5_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "T5-XXL 模型路径",
            "widget": "file_picker",
            "help": "T5-XXL文件路径",
            "cli": {"name": "--t5", "type": "value", "formatter": "path"},
            "ui_hidden": False, "persist": True
        }
    )

    task: str = field(
        default="t2v-A14B",
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "任务类型",
            "widget": "dropdown",
            "options": ["t2v-A14B", "i2v-A14B"],
            "help": "wan2.2任务类型选择",
            "target": "cli",
            "cli": {"type": "value", "name": "--task", "formatter": "str", "emit_if_default": False}
        }
    )

    # ================================
    # 视频数据集专用参数（仅视频数据集需要）
    # ================================
    frame_extraction: str = field(
        default="head",
        metadata={
            "group": ParameterGroup.DATASET.key,
            "label": "视频帧提取方式",
            "widget": "dropdown",
            "options": ["head", "chunk", "slide", "uniform", "full"],
            "help": (
                "从视频中提取帧的方式（仅视频数据集需要）：\n"
                "  - head: 从视频开头提取前 N 帧\n"
                "  - chunk: 将视频分割成 N 帧的块\n"
                "  - slide: 滑动采样\n"
                "  - uniform: 均匀采样\n"
                "  - full: 提取全部帧（会被裁剪为 N*4+1 帧）\n"
                "推荐：重复动作用 head/chunk/slide，完整动作用 full"
            ),
            "target": "toml",
            "toml": {
                "section": "datasets",
                "key": "frame_extraction",
                "formatter": "str"
            },
            "dataset_type_filter": ["video"],
            "ui_hidden": False,
            "persist": True
        }
    )

    target_frames: List[int] = field(
        default_factory=lambda: [1, 25, 45],
        metadata={
            "group": ParameterGroup.DATASET.key,
            "label": "目标帧数",
            "widget": "list_int",
            "help": (
                "提取的目标帧数列表，格式: [1, 25, 45]\n"
                "注意：Wan2.2 的帧数必须是 N*4+1 (如 1, 5, 9, 13, 17, 21, 25, 29...)"
            ),
            "target": "toml",
            "toml": {
                "section": "datasets",
                "key": "target_frames",
                "formatter": "list_int"
            },
            "dataset_type_filter": ["video"],
            "ui_hidden": False,
            "persist": True
        }
    )


# ================================
# 注册 Wan 系列模型到全局注册表
# ================================

register_model(ModelSpec(
    type_name="Wan_2_1",
    title="Wan2.1",
    config_cls=Wan21,
    script_train="wan_train_network.py",
    network_module="musubi_tuner.networks.lora_wan",
    group_order=[
        ParameterGroup.PATH.key,
        ParameterGroup.DATASET.key,
        ParameterGroup.BASIC.key,
        ParameterGroup.OPTIMIZER.key,
        ParameterGroup.PRECISION.key,
        ParameterGroup.SAMPLING.key,
        ParameterGroup.SAVING.key,
        ParameterGroup.ADVANCED.key,
    ],
    path_mapping={
        "dit_path": "model_paths.Wan_2_1.dit_path",
        "vae_path": "model_paths.Wan_2_1.vae_path",
        "t5_path": "model_paths.Wan_2_1.t5_path",
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="wan_cache_text_encoder_outputs.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--t5", "{t5_path}",
                           "--batch_size", "16",
                           "--logging_dir", "{cache_logs_dir}"]
        ),
        CacheStep(
            name="cache_latents",
            script="wan_cache_latents.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--vae", "{vae_path}",
                           "--logging_dir", "{cache_logs_dir}"]
        ),
    ],
    features={},
    supported_dataset_types=[DatasetType.IMAGE, DatasetType.VIDEO]
))

register_model(ModelSpec(
    type_name="Wan_2_2",
    title="Wan2.2",
    config_cls=Wan22,
    script_train="wan_train_network.py",
    network_module="musubi_tuner.networks.lora_wan",
    group_order=[
        ParameterGroup.PATH.key,
        ParameterGroup.DATASET.key,
        ParameterGroup.BASIC.key,
        ParameterGroup.OPTIMIZER.key,
        ParameterGroup.PRECISION.key,
        ParameterGroup.SAMPLING.key,
        ParameterGroup.SAVING.key,
        ParameterGroup.ADVANCED.key,
    ],
    path_mapping={
        "dit_path": "model_paths.Wan_2_2.dit_path",
        "vae_path": "model_paths.Wan_2_2.vae_path",
        "t5_path": "model_paths.Wan_2_2.t5_path",
    },
    cache_steps=[
        CacheStep(
            name="cache_text_encoder_outputs",
            script="wan_cache_text_encoder_outputs.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--t5", "{t5_path}",
                           "--batch_size", "16",
                           "--logging_dir", "{cache_logs_dir}"]
        ),
        CacheStep(
            name="cache_latents",
            script="wan_cache_latents.py",
            args_template=["--dataset_config", "{dataset_toml}",
                           "--vae", "{vae_path}",
                           "--logging_dir", "{cache_logs_dir}"]
        ),
    ],
    features={},
    supported_dataset_types=[DatasetType.IMAGE, DatasetType.VIDEO]
))
