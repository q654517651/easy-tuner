"""
Training models and configurations (FastAPI Backend version)
训练模型和配置定义 - 包含完整的模型注册表系统

从原始 src/easytuner/core/training/models.py 迁移核心功能
"""

from __future__ import annotations
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, Union, Callable

from ..dataset.models import DatasetType


# TrainingState 已移至 core.state.models，避免重复定义
from ..state.models import TrainingState


class ParameterGroup(Enum):
    """训练参数分组枚举 - 定义UI显示顺序和分组信息"""

    # 分组定义格式：(key, title, description)
    PATH = ("path", "模型路径", "模型路径信息")
    DATASET = ("dataset", "数据集参数", "数据集相关配置参数")
    BASIC = ("basic", "基础参数", "基础参数")
    OPTIMIZER = ("optimizer", "优化器与调度", "优化器和学习率调度")
    PRECISION = ("precision", "精度与硬件", "混合精度和硬件配置")
    SAMPLING = ("sampling", "采样配置", "训练过程中的图像采样")
    SAVING = ("saving", "保存配置", "模型检查点保存设置")
    ADVANCED = ("advanced", "高级选项", "高级和实验性参数")

    @property
    def key(self) -> str:
        """分组键值"""
        return self.value[0]

    @property
    def title(self) -> str:
        """分组标题"""
        return self.value[1]

    @property
    def description(self) -> str:
        """分组描述"""
        return self.value[2]

    @classmethod
    def get_ordered_groups(cls) -> List['ParameterGroup']:
        """获取按定义顺序排列的分组列表"""
        return list(cls)


@dataclass
class CacheStep:
    name: str
    script: str
    args_template: List[str]  # 模板形式，不用写函数
    enabled: Optional[Callable[[Any], bool]] = None


@dataclass
class BaseTrainingConfig:
    """训练配置基类（按用户指定分组与顺序）"""

    # ================================
    # 隐藏设置 不参与展示
    # ================================

    caption_extension: str = field(
        default=".txt",
        metadata={
            "target": "toml",  # 只写入 dataset.toml
            "toml": {
                "section": "general",
                "key": "caption_extension",
                "formatter": "str"
            },
            "ui_hidden": False, "persist": True
        }
    )

    image_video_directory: str = field(
        default="",
        metadata={
            "target": "toml",
            "toml": {
                "section": "datasets",
                "key": "image_directory",
                "formatter": "str"
            },
            "ui_hidden": False, "persist": True
        }
    )

    cache_directory: str = field(
        default="",
        metadata={
            "target": "toml",
            "toml": {
                "section": "datasets",
                "key": "cache_directory",
                "formatter": "str"
            },
            "ui_hidden": False, "persist": True
        }
    )

    # ================================
    # 2. 基础设置（Training Core）
    # ================================
    resolution: str = field(
        default="1024,1024",
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "训练分辨率",
            "widget": "resolution_selector",
            "help": "训练图像分辨率（宽,高）",
            "target": "toml",
            "toml": {
                "section": "general",  # 写入 [general]
                "key": "resolution",
                "formatter": "res_array"  # 自定义格式器，把 "1024,1024" -> [1024, 1024]
            }
        }
    )

    max_train_epochs: int = field(
        default=16,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "训练轮数",
            "widget": "number",
            "min": 1, "max": 100,
            "help": "完整数据集遍历次数",
            "target": "cli",  # ← 显式声明这是 CLI 参数
            "cli": {"type": "value", "name": "--max_train_epochs", "formatter": "int", "emit_if_default": False}
        }
    )

    batch_size: int = field(
        default=1,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "批大小",
            "widget": "number",
            "min": 1,
            "max": 64,
            "help": "每步样本数，越大越耗显存",
            "target": "toml",
            "toml": {
                "section": "general",
                "key": "batch_size",
                "formatter": "int"
            }
        }
    )

    gradient_accumulation_steps: int = field(
        default=1,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "梯度累计",
            "widget": "number",
            "min": 1, "max": 1024,
            "help": "反向传播前累计的步数（等效更大批量）",
            "target": "cli",
            "cli": {"type": "value", "name": "--gradient_accumulation_steps", "formatter": "int",
                    "emit_if_default": False}
        }
    )

    repeats: int = field(
        default=10,
        metadata={
            "group": ParameterGroup.DATASET.key,  # 使用新的DATASET组
            "label": "数据集重复次数",
            "widget": "number",
            "min": 1, "max": 100,
            "help": "每个 epoch 内的数据集重复遍历；可用于平衡不同规模的数据集",
            "target": "toml",
            "toml": {
                "section": "datasets",  # ← 由你的 TOML 生成器把该键下沉到每个 [[datasets]] 条目
                "key": "num_repeats",  # ← TOML 正确键名
                "formatter": "int"
            }
        }
    )

    enable_bucket: bool = field(
        default=True,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "启用分桶",
            "widget": "switch",
            "help": "自动分辨率分桶以提高训练效率",
            "target": "toml",
            "toml": {
                "section": "general",
                "key": "enable_bucket",
                "formatter": "bool"
            }
        }
    )

    bucket_no_upscale: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "禁用放大",
            "widget": "switch",
            "help": "启用后分桶不会对小图放大，只对大图缩小",
            "target": "toml",
            "toml": {
                "section": "general",
                "key": "bucket_no_upscale",
                "formatter": "bool"
            }
        }
    )

    network_dim: int = field(
        default=32,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "LoRA 维度",
            "widget": "number",
            "min": 4, "max": 512, "step": 4,
            "help": "LoRA 矩阵秩（容量/效果）",
            "target": "cli",
            "cli": {"type": "value", "name": "--network_dim", "formatter": "int", "emit_if_default": False}
        }
    )

    network_alpha: int = field(
        default=16,
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "LoRA Alpha",
            "widget": "number",
            "min": 1, "max": 512,
            "help": "一般不大于维度；建议 ≤ network_dim",
            "target": "cli",
            "cli": {"type": "value", "name": "--network_alpha", "formatter": "int", "emit_if_default": False}
        }
    )

    blocks_to_swap: Optional[int] = field(
        default=30,
        metadata={
            "group": ParameterGroup.BASIC.key,  # 可按你的分组改：BASIC/ADVANCED等
            "label": "Block Swap（交换块数）",
            "widget": "number",
            "min": 0, "max": 64,
            "help": (
                "用于在内存/磁盘间交换激活以降低显存占用；0 或留空表示不启用。\n"
                "在 1024×1024、batch=1、--mixed_precision bf16、--gradient_checkpointing、--xformers 下的参考：\n"
                "  - 不启用：≈42GB VRAM\n"
                "  - 启用 --fp8_base --fp8_scaled：≈30GB VRAM\n"
                "  - 在上面基础上 blocks_to_swap=16：≈24GB VRAM\n"
                "  - 在上面基础上 blocks_to_swap=45：≈12GB VRAM\n"
                "注意：使用 blocks_to_swap 时建议主机内存 ≥64GB。"
            ),
            "target": "cli",
            "cli": {"type": "value", "name": "--blocks_to_swap", "formatter": "int", "emit_if_default": False}
        }
    )

    output_name: str = field(
        default="",
        metadata={
            "group": ParameterGroup.BASIC.key,
            "label": "输出名称",
            "widget": "text",
            "help": "产物命名（权重/样例图前缀）",
            "target": "cli",
            "cli": {"type": "value", "name": "--output_name", "formatter": "str", "emit_if_default": False}
        }
    )

    # ================================
    # 3. 优化器与调度器（Optimizer & Scheduler）
    # ================================
    optimizer: str = field(
        default="adamw8bit",
        metadata={
            "group": ParameterGroup.OPTIMIZER.key,
            "label": "优化器",
            "widget": "dropdown",
            "options": ["adamw", "adamw8bit", "adafactor", "lion"],
            "help": "常用：adamw / adamw8bit",
            "target": "cli",
            "cli": {"type": "value", "name": "--optimizer_type", "formatter": "str", "emit_if_default": False}
        }
    )

    learning_rate: float = field(
        default=1e-4,
        metadata={
            "group": ParameterGroup.OPTIMIZER.key,
            "label": "学习率",
            "widget": "number_float",
            "help": "过大会不稳，过小收敛慢",
            "target": "cli",
            "cli": {"type": "value", "name": "--learning_rate", "formatter": "float", "emit_if_default": False}
        }
    )

    scheduler: str = field(
        default="cosine",
        metadata={
            "group": ParameterGroup.OPTIMIZER.key,
            "label": "学习率调度器",
            "widget": "dropdown",
            "options": ["cosine", "linear", "constant", "constant_with_warmup", "cosine_with_restarts"],
            "help": "余弦适合大多数场景；重启适合长训波动",
            "target": "cli",
            "cli": {"type": "value", "name": "--lr_scheduler", "formatter": "str", "emit_if_default": False}
        }
    )

    # TODO 这里有个问题 选择constant时不应该展示预热相关的，因为constant不支持预热，以及当选择比例的时候并没有比例可选，但这个之后再解决
    warmup_mode: str = field(
        default="steps",
        metadata={
            "group": ParameterGroup.OPTIMIZER.key,
            "label": "Warmup 模式",
            "widget": "dropdown",
            "options": ["steps", "ratio"],
            "help": "选择 warmup 方式：步数 或 比例",
            "target": "cli",
            "enable_if": {"scheduler__in": ["cosine", "linear", "constant_with_warmup", "cosine_with_restarts"]}
        }
    )

    warmup_steps: int = field(
        default=0,
        metadata={
            "group": ParameterGroup.OPTIMIZER.key,
            "label": "Warmup 步数",
            "widget": "number",
            "min": 0,
            "help": "学习率预热步数，0 表示不启用",
            "target": "cli",
            "cli": {"type": "value", "name": "--lr_warmup_steps", "formatter": "int", "emit_if_default": False},
            "enable_if": {
                "scheduler__in": ["cosine", "linear", "constant_with_warmup", "cosine_with_restarts"],
                "warmup_mode": "steps"
            }
        }
    )

    # ================================
    # 4. 过程中采样（Sampling）
    # ================================

    sampling_enabled: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "启用训练中采样",
            "widget": "switch",
            "help": "打开后训练中会按设定频率生成样例图像",
            "target": "sample",  # 改为sample，由_add_sampling_args统一处理
            "ui_hidden": False,
            "persist": True,
        }
    )

    sample_prompt: str = field(
        default="",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "采样提示词",
            "widget": "textarea",
            "help": "训练中用于生成预览的提示词（可空）",
            "target": "sample",
            "ui_hidden": False, "persist": True
        }
    )

    # 采样宽度 (--w)
    sample_width: str = field(
        default="1024",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "采样宽度",
            "widget": "number",
            "help": "采样宽度 (--w)",
            "target": "sample",
            "formatter": "int",
            "enable_if": {"sampling_enabled": True},
            "ui_hidden": True,
            "persist": True,
        },
    )

    # 采样高度 (--h)
    sample_height: str = field(
        default="1024",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "采样高度",
            "widget": "number",
            "help": "采样高度 (--h)",
            "target": "sample",
            "formatter": "int",
            "enable_if": {"sampling_enabled": True},
            "ui_hidden": True,
            "persist": True,
        },
    )

    # 采样 F 参数 (--f)
    sample_factor: str = field(
        default="1",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "生成帧数",
            "widget": "number",
            "help": "生成帧数，图片模型为1帧",
            "target": "sample",
            "formatter": "int",
            "enable_if": {"sampling_enabled": True},
            "ui_hidden": True,
            "persist": True,
        },
    )

    # 采样步数 (--s)
    sample_steps: str = field(
        default="20",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "采样步数",
            "widget": "number",
            "help": "采样步数 (--s)",
            "target": "sample",
            "formatter": "int",
            "enable_if": {"sampling_enabled": True},
            "ui_hidden": True,
            "persist": True,
        },
    )

    # 采样指导系数 (--g)
    sample_guidance: str = field(
        default="2.5",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "采样指导系数",
            "widget": "number",
            "help": "采样 guidance scale (--g)",
            "target": "sample",
            "formatter": "float",  # 修复：应该是float
            "enable_if": {"sampling_enabled": True},  # 添加条件依赖
            "ui_hidden": True,
            "persist": True,
        },
    )

    # 采样种子 (--d)
    sample_seed: str = field(
        default="42",
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "采样种子",
            "widget": "number",
            "help": "采样随机种子 (--d)",
            "target": "sample",
            "formatter": "int",
            "enable_if": {"sampling_enabled": True},
            "ui_hidden": True,
            "persist": True,
        },
    )

    sample_every_n_epochs: int = field(
        default=2,
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "每 N 轮采样",
            "widget": "number",
            "min": 1, "max": 100,
            "help": "每隔多少个 epoch 生成一次预览",
            "target": "cli",
            "cli": {"type": "value", "name": "--sample_every_n_epochs", "formatter": "int", "emit_if_default": False}
        }
    )

    sample_at_first: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.SAMPLING.key,
            "label": "首轮即采样",
            "widget": "switch",
            "help": "在第 1 个 epoch 结束时也生成一次预览",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--sample_at_first", "emit_if_default": False}
        }
    )

    # ================================
    # 5. 硬件与精度（Hardware & Precision）
    # ================================
    mixed_precision: str = field(
        default="bf16",
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "混合精度",
            "widget": "dropdown",
            "options": ["bf16", "fp16"],
            "help": "推荐 bf16；若不支持再考虑 fp16",
            "target": "cli",
            "cli": {"type": "value", "name": "--mixed_precision", "formatter": "str", "emit_if_default": False}
        }
    )

    attention_type: str = field(
        default="sdpa",
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "注意力机制",
            "widget": "dropdown",
            "options": ["sdpa", "xformers", "flash_attn"],
            "help": "PyTorch SDPA / xformers / flash_attn",
            "target": "cli",
            "cli": {
                "type": "choice_flag",
                "choices_map": {
                    "sdpa": "--sdpa",
                    "xformers": "--xformers",
                    "flash_attn": "--flash_attn",
                },
                "emit_if_default": True
            }
        }
    )

    gradient_checkpointing: bool = field(
        default=True,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "梯度检查点",
            "widget": "switch",
            "help": "降低显存占用，略增计算开销",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--gradient_checkpointing", "emit_if_default": True}
        }
    )

    fp8_base: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "启用 FP8 Base",
            "widget": "switch",
            "help": "启用 FP8 base 算法以减少显存占用。",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--fp8_base", "emit_if_default": False}
        }
    )

    fp8_scaled: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "启用 FP8 Scaled",
            "widget": "switch",
            "help": "启用 FP8 scaled 算法以进一步降低显存占用。",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--fp8_scaled", "emit_if_default": False}
        }
    )

    fp8_vl: bool = field(
        default=False,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "启用 FP8 VL",
            "widget": "switch",
            "help": "启用 FP8 VL 算法（适用于 Vision-Language 模型部分）。",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--fp8_vl", "emit_if_default": False}
        }
    )

    # ================================
    # 6. 保存（Saving）
    # ================================
    save_every_n_epochs: int = field(
        default=4,
        metadata={
            "group": ParameterGroup.SAVING.key,
            "label": "每 N 轮保存",
            "widget": "number",
            "min": 1, "max": 100,
            "help": "检查点保存频率（按 epoch）",
            "target": "cli",
            "cli": {"type": "value", "name": "--save_every_n_epochs", "formatter": "int", "emit_if_default": False}
        }
    )

    # ================================
    # 7. 高级设置（Advanced）
    # ================================
    timestep_sampling: str = field(
        default="shift",
        metadata={
            "group": ParameterGroup.ADVANCED.key,
            "label": "时间步采样",
            "widget": "dropdown",
            "options": ["shift", "qwen_shift"],
            "help": "选择训练用的时间步采样策略",
            "target": "cli",
            "cli": {"type": "value", "name": "--timestep_sampling", "formatter": "str", "emit_if_default": False}
        }
    )

    discrete_flow_shift: float = field(
        default=3.0,
        metadata={
            "group": ParameterGroup.ADVANCED.key,
            "label": "离散流偏移值",
            "widget": "number_float",
            "min": 0.1, "max": 10.0, "step": 0.1,
            "help": "配合 shift 使用的偏移强度",
            "target": "cli",
            "enable_if": {"timestep_sampling": "shift"},
            "cli": {"type": "value", "name": "--discrete_flow_shift", "formatter": "float", "emit_if_default": False}
        }
    )

    seed: int = field(
        default=42,
        metadata={
            "group": ParameterGroup.ADVANCED.key,
            "label": "随机种子",
            "widget": "number",
            "min": 0, "max": 2147483647,
            "help": "固定可复现性；-1/空表示随机",
            "target": "cli",
            "cli": {"type": "value", "name": "--seed", "formatter": "int", "emit_if_default": False}
        }
    )


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
class QwenImageEditConfig(BaseTrainingConfig):
    """Qwen-Image LoRA训练配置"""

    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "DiT 模型路径",
            "widget": "file_picker",
            "help": "Qwen-Image Edit模型文件路径",
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

    edit: bool = field(
        default=True,
        metadata={
            "group": ParameterGroup.PRECISION.key,
            "label": "启用 FP8 Base",
            "widget": "switch",
            "help": "启用 FP8 base 算法以减少显存占用。",
            "target": "cli",
            "cli": {"type": "toggle_true", "name": "--edit", "emit_if_default": False}
        }
    )


@dataclass
class FluxKontext(BaseTrainingConfig):
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


@dataclass
class Wan21(BaseTrainingConfig):
    dit_path: str = field(
        default="",
        metadata={
            "group": ParameterGroup.PATH.key,
            "label": "Wan2.1 模型路径",
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
            "label": "优化器",
            "widget": "dropdown",
            "options": ["t2v-1.3B", "t2v-14B", "i2v-14B", "t2i-14B"],
            "help": "wan2.1任务类型选择",
            "target": "cli",
            "cli": {"type": "value", "name": "--task", "formatter": "str", "emit_if_default": False}
        }
    )



@dataclass
class Wan22(BaseTrainingConfig):
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


@dataclass
class TrainingTask:
    """训练任务"""
    id: str  # 使用id而不是task_id，保持与TrainingManager一致
    name: str
    config: BaseTrainingConfig
    dataset_id: str = ""
    training_type: str = "qwen_image_lora"
    state: TrainingState = TrainingState.PENDING
    progress: float = 0.0
    current_step: int = 0
    total_steps: int = 0
    current_epoch: int = 0
    loss: float = 0.0
    learning_rate: float = 0.0
    eta_seconds: Optional[int] = None
    speed: Optional[float] = None  # it/s
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    logs: List[str] = field(default_factory=list)
    error_message: str = ""
    output_dir: str = ""
    checkpoint_files: List[str] = field(default_factory=list)
    sample_images: List[str] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.state, str):
            self.state = TrainingState(self.state)
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def created_time(self) -> str:
        """向后兼容的created_time属性"""
        if self.created_at:
            return self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        return ""

    @property
    def task_id(self) -> str:
        """向后兼容的task_id属性"""
        return self.id


# ================================
# 模型注册表系统
# ================================

@dataclass
class ModelSpec:
    """模型规范定义"""
    type_name: str  # 模型唯一标识
    title: str  # UI 展示名
    config_cls: Type[Any]  # dataclass 配置类
    script_train: str  # 训练脚本路径
    script_cache_te: Optional[str] = None  # 缓存文本编码脚本
    script_cache_latents: Optional[str] = None  # 缓存潜变量脚本
    network_module: Optional[str] = None  # 网络模块路径
    group_order: Optional[List[str]] = None  # 字段分组顺序
    features: Dict[str, Any] = field(default_factory=dict)  # 额外功能开关
    path_mapping: Optional[Dict[str, str]] = None  # 路径映射
    cache_steps: List[CacheStep] = field(default_factory=list)
    supported_dataset_types: List[DatasetType] = field(default_factory=list)  # 支持的数据集类型


# 全局注册表
_REGISTRY: Dict[str, ModelSpec] = {}


def register_model(spec: ModelSpec) -> None:
    """注册模型到全局注册表"""
    if spec.type_name in _REGISTRY:
        raise ValueError(f"重复注册的模型: {spec.type_name}")
    _REGISTRY[spec.type_name] = spec


def list_models() -> List[ModelSpec]:
    """返回所有已注册模型列表"""
    return list(_REGISTRY.values())


def get_model(type_name: str) -> ModelSpec:
    """通过 type_name 获取模型规范"""
    try:
        return _REGISTRY[type_name]
    except KeyError as e:
        raise KeyError(f"未知模型类型: {type_name}") from e


# ================================
# 工具函数
# ================================

def get_fields_by_group(config_cls: Type[Any], group_key: str) -> List[Tuple[str, Any]]:
    """获取指定分组的字段列表"""
    result = []
    if is_dataclass(config_cls):
        for f in fields(config_cls):
            metadata = f.metadata or {}
            if metadata.get("group") == group_key:
                result.append((f.name, f))
    return result


def field_enabled(config: Any, metadata: Dict[str, Any]) -> bool:
    """检查字段是否应该启用（条件渲染）"""
    enable_if = metadata.get("enable_if")
    if not enable_if:
        return True

    for key, expected in enable_if.items():
        if key.endswith("__in"):
            attr = key[:-4]
            val = getattr(config, attr, None)
            if val not in (expected or []):
                return False
        else:
            val = getattr(config, key, None)
            if val != expected:
                return False
    return True


def build_cli_args(config: Any, force_emit_all: bool = False) -> List[str]:
    """从配置对象生成CLI命令行参数（尊重 target 目标）

    Args:
        config: 配置对象
        force_emit_all: 是否强制输出所有参数（预览模式使用）
    """
    args: List[str] = []
    cls = type(config)

    if not is_dataclass(cls):
        return args

    for f in fields(cls):
        metadata = f.metadata or {}
        cli = metadata.get("cli")
        target = metadata.get("target")
        # 兼容旧写法：有 cli 但未声明 target，则默认 target=cli
        if target is None and cli:
            target = "cli"

        # 只收集 CLI 目标
        if target not in ("cli", "both") or not cli:
            continue

        if not field_enabled(config, metadata):
            continue

        value = getattr(config, f.name)
        emit_if_default = bool(cli.get("emit_if_default", False))
        is_default = (hasattr(f, "default") and value == f.default)

        # 预览模式下强制显示重要参数，即使是默认值
        if not force_emit_all and not emit_if_default and is_default:
            continue

        cli_type = cli.get("type")
        if cli_type == "toggle_true":
            if bool(value):
                args.append(cli["name"])
        elif cli_type == "choice_flag":
            choices_map = cli.get("choices_map", {})
            flag = choices_map.get(str(value))
            if flag:
                args.append(flag)
        else:
            flag = cli.get("name")
            if flag:
                formatter = cli.get("formatter")
                if formatter == "int":
                    args.extend([flag, str(int(value))])
                elif formatter == "float":
                    args.extend([flag, str(float(value))])
                else:
                    args.extend([flag, str(value)])
    return args


def _parse_resolution_to_list(v: Any) -> List[int]:
    """
    支持：
      - "1024,1024" / "960, 544"
      - [1024, 1024] / (1024, 1024)
    """
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v]
    if isinstance(v, str):
        parts = [p.strip() for p in v.split(",") if p.strip()]
        if len(parts) == 2:
            return [int(parts[0]), int(parts[1])]
    # 兜底：返回空或抛错都行，这里返回空，避免训练时直接崩
    return []


_FORMATTERS = {
    "int": lambda x: None if x in (None, "") else int(x),
    "float": lambda x: None if x in (None, "") else float(x),
    "bool": lambda x: bool(x) if not isinstance(x, str) else x.lower() in ("1", "true", "yes"),
    "str": lambda x: None if x is None else str(x),
    "res_array": _parse_resolution_to_list,  # e.g. "1024,1024" -> [1024, 1024]
    # 可按需扩展更多 formatter
}


def _apply_formatter(val: Any, fmt: str | None):
    if fmt is None:
        return val
    fn = _FORMATTERS.get(fmt)
    if not fn:
        return val
    try:
        return fn(val)
    except Exception:
        # 避免 formatter 异常导致整体失败
        return val


def build_toml_dict(config: Any, datasets: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    仅支持嵌套写法：
        metadata = {
            "target": "toml" | "both",
            "toml": {"section": "general"|"datasets", "key": "xxx", "formatter": "..."}
        }
    注意：不再接收 datasets 覆盖项；多数据集请在 config 中自行表示（若你当前只支持单数据集，这里就生成1条 [[datasets]]）
    """
    if not is_dataclass(config):
        raise ValueError("build_toml_dict: config 必须是 dataclass 实例")

    toml: Dict[str, Any] = {"general": {}, "datasets": []}

    # 1) general
    for f in fields(config):
        md = f.metadata or {}
        if md.get("target") not in ("toml", "both"):
            continue
        tinfo = md.get("toml") or {}
        if tinfo.get("section") != "general":
            continue

        key = tinfo.get("key") or f.name
        fmt = tinfo.get("formatter")
        val = getattr(config, f.name, None)
        val = _apply_formatter(val, fmt)
        if val is None:
            continue
        toml["general"][key] = val

    # 2) datasets（模板默认值）
    dataset_item: Dict[str, Any] = {}
    for f in fields(config):
        md = f.metadata or {}
        if md.get("target") not in ("toml", "both"):
            continue
        tinfo = md.get("toml") or {}
        if tinfo.get("section") != "datasets":
            continue

        key = tinfo.get("key") or f.name
        fmt = tinfo.get("formatter")
        val = getattr(config, f.name, None)
        val = _apply_formatter(val, fmt)
        if val is None:
            continue
        dataset_item[key] = val

    # 没有 datasets 字段也至少生成一个空项，保持脚本兼容
    toml["datasets"].append(dict(dataset_item))

    return toml


def dumps_toml(t: Dict[str, Any]) -> str:
    """
    将 build_toml_dict 的结构序列化成 TOML 文本：
      [general]
      key = value
      ...
      [[datasets]]
      key = value
      ...
    """
    lines: List[str] = []

    # general
    lines.append("[general]")
    for k, v in (t.get("general") or {}).items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        elif isinstance(v, (list, tuple)):
            # 简单数组序列化（适用 resolution 等）
            arr = ", ".join(str(x) for x in v)
            lines.append(f"{k} = [{arr}]")
        elif v is None:
            continue
        else:
            # 字符串：用双引号
            s = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{s}"')

    # datasets
    for ds in (t.get("datasets") or []):
        lines.append("")
        lines.append("[[datasets]]")
        for k, v in (ds or {}).items():
            if isinstance(v, bool):
                lines.append(f"{k} = {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{k} = {v}")
            elif isinstance(v, (list, tuple)):
                arr = ", ".join(str(x) for x in v)
                lines.append(f"{k} = [{arr}]")
            elif v is None:
                continue
            else:
                s = str(v).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{k} = "{s}"')

    return "\n".join(lines) + "\n"


# ================================
# 自动注册已知模型
# ================================


# 注册 Qwen-Image LoRA 模型
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
    type_name="qwen_image_edit_lora",
    title="Qwen-Image Edit LoRA",
    config_cls=QwenImageEditConfig,
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
        "dit_path": "model_paths.qwen_image_edit.dit_path",
        "vae_path": "model_paths.qwen_image_edit.vae_path",
        "text_encoder_path": "model_paths.qwen_image_edit.text_encoder_path"
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
    supported_dataset_types=[DatasetType.IMAGE, DatasetType.SINGLE_CONTROL_IMAGE]
))

register_model(ModelSpec(
    type_name="flux_kontext_lora",
    title="Flux Kontext LoRA",
    config_cls=FluxKontext,
    script_train="qwen_image_train_network.py",
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

register_model(ModelSpec(
    type_name="Wan_2_1",
    title="Wan2.1",
    config_cls=Wan21,
    script_train="wan_train_network.py",
    network_module="musubi_tuner.networks.lora_wan",
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
