"""
统一的Musubi-Tuner训练器 (FastAPI Backend版本)
支持所有模型类型的LoRA训练（Qwen-Image, Flux, Stable Diffusion等）
从src/easytuner/core/training/trainers/musubi_trainer.py完整迁移
"""

import asyncio
import os
import time
import subprocess
import signal
import uuid
import json
import platform
import re
import psutil
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List

from ....utils.logger import log_info, log_error, log_success, log_progress, log_warning
from ....utils.log_sink import LogSink
from ....core.exceptions import TrainingError
from ....utils.network_retry import NetworkRetryHelper
from ...config import get_config
from ...dataset.models import DatasetType
from ..models import BaseTrainingConfig, TrainingTask, TrainingState, get_model, list_models, build_cli_args, \
    build_toml_dict, dumps_toml


class MusubiTrainer:
    """统一的Musubi-Tuner训练器（支持 workspace-based runtime）"""
    _ACCELERATE_MODULE = "accelerate.commands.launch"

    def __init__(self, task_id: str, event_bus=None):
        from ...environment import get_paths
        import sys

        self.config = get_config()
        self._paths = get_paths()  # 缓存环境路径
        self.task_id = task_id
        self.event_bus = event_bus
        self._proc: Optional[subprocess.Popen] = None
        self._cache_proc: Optional[subprocess.Popen] = None  # 预处理进程
        self._cancelled = False  # 取消标志
        self._id = uuid.uuid4().hex
        self._network_retry = NetworkRetryHelper(max_retries=2, retry_delay=3)
        self._last_logged_line: Optional[str] = None  # 用于过滤重复日志行

        # ✨ 新架构：使用环境管理器统一提供的 Python 路径（避免重复逻辑）
        self._python_exe = self._paths.runtime_python
        if not self._python_exe or not self._python_exe.exists():
            raise TrainingError(
                f"Runtime Python 不存在: {self._python_exe}，"
                "请在设置页面重新安装 Runtime 环境"
            )

        self._musubi_dir = self._paths.musubi_dir  # workspace/runtime/engines/musubi-tuner
        self._musubi_src = self._paths.musubi_src

        if not self._musubi_dir.exists():
            raise TrainingError(
                f"Musubi 训练引擎不存在: {self._musubi_dir}，"
                "请在设置页面重新安装 Runtime 环境"
            )

        # 注册程序退出时的清理函数
        import atexit
        atexit.register(self._emergency_cleanup)

    def _get_task_dir(self, task: TrainingTask) -> Path:
        """获取任务目录（支持新的 task_id--name 格式）"""
        from ..manager import get_training_manager
        
        training_manager = get_training_manager()
        task_dir = training_manager.get_task_dir(task.id)
        
        if not task_dir:
            # 回退到旧格式（兼容性）
            log_error(f"无法找到任务目录，使用回退路径: {task.id}")
            task_dir = Path(self.config.storage.workspace_root) / "tasks" / task.id
        
        return task_dir

    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """发送事件到事件总线"""
        if self.event_bus:
            # 确保包含task_id
            event_data = {"task_id": self.task_id, **data}
            try:
                # 线程安全地投递到主事件循环（不阻塞训练线程）
                self.event_bus.emit_threadsafe(event_type, event_data)
            except Exception as e:
                log_error(f"事件发送失败: {e}")

    def _emit_log(self, message: str, level: str = "info"):
        """发送日志事件"""
        self._emit_event('training.log', {
            'message': message,
            'level': level,
            'timestamp': time.time()
        })

    def _emit_progress(self, **kwargs):
        """发送进度更新事件"""
        self._emit_event('training.progress', kwargs)

    @property
    def _PROJECT_ROOT(self) -> Path:
        """
        获取项目根目录（resources 目录）
        用于解析脚本路径：musubi-tuner 位于 project_root/backend/engines/
        """
        return self._paths.project_root

    @property
    def _WORKING_DIR(self) -> Path:
        """
        获取工作目录（workspace_root）
        用于设置 Popen 的 cwd，使相对路径参数（如 dataset.toml）正确解析
        """
        return self._paths.workspace_root

    # ✨ 直接使用绝对路径的 accelerate 命令（不再相对化）
    def _get_accelerate_cmd(self) -> List[str]:
        """返回 accelerate 命令（使用绝对路径，跨平台稳定）"""
        # 🔧 不使用 .resolve() 以避免在 Linux venv 中解析符号链接
        return [str(self._python_exe), "-m", self._ACCELERATE_MODULE]

    # 从任务配置类的 ClassVar 取 3 个脚本（相对项目根）
    def _scripts_for_task(self, task) -> dict:
        """
        返回：
          - train: 训练脚本的相对 PROJECT_ROOT 路径（必填）
          - cache_steps: [{name, script, args_template, enabled}]（从模型注册表读取）
        仅使用新的 ModelSpec.cache_steps；不再读取旧的 script_cache_te/latents。
        """
        model_spec = get_model(task.training_type)
        # ✨ 使用相对于 PROJECT_ROOT 的路径（最终会用 PROJECT_ROOT / 相对路径来构建绝对路径）
        # musubi-tuner 在新架构中位于 backend/engines/ 下，不再位于 workspace 下
        base = self._musubi_src.relative_to(self._PROJECT_ROOT)

        def resolve(rel: str | None) -> str:
            if not rel:
                raise TrainingError("未声明脚本路径")
            rel = str(rel).replace("\\", "/")
            if rel.startswith("engines/"):
                p = Path(rel)
            elif "/" in rel:
                p = base / rel
            else:
                p = base / "musubi_tuner" / rel
            if p.suffix != ".py":
                p = p.with_suffix(".py")

            full_path = self._PROJECT_ROOT / p
            log_info(f"[脚本解析] 相对路径: {p.as_posix()}")
            log_info(f"[脚本解析] 项目根: {self._PROJECT_ROOT}")
            log_info(f"[脚本解析] 完整路径: {full_path}")
            log_info(f"[脚本解析] 是否存在: {full_path.exists()}")

            if not full_path.exists():
                raise TrainingError(f"脚本不存在: {p.as_posix()}（相对项目根）")
            return p.as_posix()

        # 训练脚本
        train_rel = model_spec.script_train
        if not train_rel:
            raise TrainingError(f"{model_spec.type_name} 未声明训练脚本")

        # 缓存步骤（逐个解析脚本路径，保留模板与 enabled）
        cache_steps = []
        for step in getattr(model_spec, "cache_steps", []) or []:
            cache_steps.append({
                "name": step.name,
                "script": resolve(step.script),
                "args_template": list(getattr(step, "args_template", [])),
                "enabled": getattr(step, "enabled", None),
            })

        return {
            "train": resolve(train_rel),
            "cache_steps": cache_steps,
        }

    # 把任意路径转成"相对 workspace_root"的 POSIX 字符串（失败就抛错，不回退绝对）
    def _rel_to_root_posix(self, p: Path) -> str:
        workspace_root = self._paths.workspace_root
        try:
            rel = os.path.relpath(p, workspace_root)
        except ValueError:
            raise TrainingError(f"路径不在工作区之下，无法使用相对路径: {p}，工作区: {workspace_root}")

        # 检查是否越界（包含 ..）
        if rel.startswith('..'):
            raise TrainingError(f"路径越界，不在工作区之下: {p}，工作区: {workspace_root}")

        return rel.replace("\\", "/")


    def _parse_resolution_freeform(self, reso: str) -> tuple[int, int]:
        """
        宽松解析：从任意字符串里提取整数。
        - 发现 1 个整数 -> 视为正方形 (n, n)
        - 发现 ≥2 个整数 -> 取前两个 (w, h)
        - 未发现整数 -> 报错
        """
        nums = re.findall(r"\d+", str(reso))
        if not nums:
            raise TrainingError(f"无效的分辨率输入（至少需要一个整数或两个整数）: {reso}")
        if len(nums) == 1:
            n = int(nums[0])
            return n, n
        return int(nums[0]), int(nums[1])

    def _to_posix(self, p: Path) -> str:
        return p.as_posix()

    def _bool(self, b: bool) -> str:
        return "true" if b else "false"

    def _create_dataset_config(self, task, preview_mode: bool = False) -> str:
        """
        使用注册表元数据 + Trainer 注入的每数据集覆盖项，生成 dataset.toml
        - image_directory / video_directory / cache_directory / control_directory 在此注入；
        - 其它键（resolution/batch_size/enable_bucket/num_repeats/caption_extension 等）
          由 models.py 的 build_toml_dict 从 config 元数据里自动写入。
        """
        # 1) 计算数据集路径（预览模式可跳过严格校验）
        if preview_mode:
            # 预览模式：返回占位路径（假设是images目录）
            dataset_path = Path(self.config.storage.workspace_root) / "datasets" / (task.dataset_id or "preview") / "images"
            dataset_type = None
        else:
            dataset_path = self._resolve_dataset_path(task.dataset_id)
            # 从数据集目录名提取类型信息
            dataset_type = self._detect_dataset_type(task.dataset_id)
            log_info(f"检测到数据集类型: {dataset_type}")

        if preview_mode:
            # 预览模式：使用虚拟路径，不创建实际目录
            training_dir = Path(self.config.storage.workspace_root) / "tasks" / "preview"
            cache_dir = training_dir / "cache"
        else:
            # 实际训练：使用统一的任务目录（支持新的 task_id--name 格式）
            training_dir = self._get_task_dir(task)
            cache_dir = training_dir / "cache"

            # 确保目录存在（虽然应该已经由TrainingManager创建）
            cache_dir.mkdir(parents=True, exist_ok=True)

        # 3) 设置数据集和缓存路径到配置中 - 使用绝对路径
        # 根据数据集类型设置相应的目录字段
        if dataset_type == DatasetType.VIDEO.value:
            # 视频数据集：使用 video_directory
            task.config.video_directory = str(dataset_path.resolve())
            task.config.image_video_directory = ""  # 清空 image_directory
            log_info(f"视频数据集路径 (video_directory): {task.config.video_directory}")
        else:
            # 图像数据集：使用 image_directory
            task.config.image_video_directory = str(dataset_path.resolve())
            task.config.video_directory = ""  # 清空 video_directory
            log_info(f"图像数据集路径 (image_directory): {task.config.image_video_directory}")
        
        task.config.cache_directory = str(cache_dir.resolve())
        log_info(f"缓存目录路径 (cache_directory): {task.config.cache_directory}")
        
        # 4) 如果是控制图数据集，设置 control_directory
        if dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value]:
            # 控制图目录与原图目录同级
            controls_dir = dataset_path.parent / "controls"
            if controls_dir.exists():
                task.config.control_directory = str(controls_dir.resolve())
                log_info(f"控制图目录路径 (control_directory): {task.config.control_directory}")
            else:
                log_warning(f"控制图目录不存在: {controls_dir}")
                task.config.control_directory = ""
        else:
            # 非控制图数据集，清空 control_directory
            task.config.control_directory = ""

        # 5) 生成 TOML 内容
        toml_dict = build_toml_dict(task.config)
        toml_content = dumps_toml(toml_dict)

        # 6) 落盘并返回相对路径（供训练脚本 --dataset_config 使用）
        toml_path = training_dir / "dataset.toml"
        if not preview_mode:
            # 只有非预览模式才写入文件
            toml_path.write_text(toml_content, encoding="utf-8")
        return self._rel_to_root_posix(toml_path)

    def _resolve_dataset_path(self, dataset_id: str, preview_mode: bool = False) -> Path:
        """解析数据集路径（支持预览模式）"""

        if preview_mode:
            # 预览模式：返回占位路径，避免任何依赖导入（假设是images目录）
            base = Path(self.config.storage.workspace_root) / "datasets" / (dataset_id or "preview")
            return base / "images"

        # 训练模式：按照实际的数据集目录结构查找
        workspace_root = Path(self.config.storage.workspace_root)
        search_dirs = [
            workspace_root / "datasets" / "image_datasets",
            workspace_root / "datasets" / "control_image_datasets",
            workspace_root / "datasets"  # 向后兼容
        ]

        # 查找匹配的数据集目录 (支持新旧两种格式)
        dataset_path = None
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for dir_path in search_dir.iterdir():
                if dir_path.is_dir():
                    # 检查新格式 {dataset_id}--{tag}--{name} 或旧格式 {dataset_id}__{name}
                    if (dir_path.name.startswith(f"{dataset_id}--") or
                        dir_path.name.startswith(f"{dataset_id}__")):
                        dataset_path = dir_path
                        break
            if dataset_path:
                break

        if not dataset_path:
            raise FileNotFoundError(f"数据集目录不存在: 未找到ID为 {dataset_id} 的数据集")

        # 在数据集目录下查找包含图像的子目录
        # 支持：images/（普通图像数据集）、targets/（控制图数据集的原图）、根目录
        candidates = [dataset_path / "images", dataset_path / "targets", dataset_path]
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}

        for p in candidates:
            if p.exists():
                # 检查是否包含图像文件
                if any(f.is_file() and f.suffix.lower() in exts for f in p.glob("*")):
                    return p

        raise ValueError(
            f"在 {dataset_path} 下没有找到图像文件。"
            f"请将图像放入 'images/'（普通数据集）或 'targets/'（控制图数据集）目录中。"
        )

    def _detect_dataset_type(self, dataset_id: str) -> Optional[str]:
        """检测数据集类型（从目录名推断）
        
        Returns:
            数据集类型字符串，如 'single_control_image', 'multi_control_image', 'image', 'video'
            如果无法确定则返回 None
        """
        workspace_root = Path(self.config.storage.workspace_root)
        search_dirs = [
            workspace_root / "datasets" / "image_datasets",
            workspace_root / "datasets" / "control_image_datasets",
            workspace_root / "datasets" / "video_datasets",
            workspace_root / "datasets"
        ]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for dir_path in search_dir.iterdir():
                if dir_path.is_dir():
                    if (dir_path.name.startswith(f"{dataset_id}--") or
                        dir_path.name.startswith(f"{dataset_id}__")):
                        # 从目录名提取类型标签
                        from ...dataset.utils import parse_unified_dataset_dirname
                        _, dtype, _, _ = parse_unified_dataset_dirname(dir_path.name)
                        return dtype
        
        return None

    def _build_dynamic_args(self, config: BaseTrainingConfig, preview_mode: bool = False) -> List[str]:
        """使用新的CLI参数生成系统构建命令行参数"""
        # 直接使用新架构的build_cli_args函数（已处理target过滤）
        # 始终生成完整参数列表，确保预览和实际执行一致
        return build_cli_args(config, force_emit_all=True)

    def _build_args_from_template(self, template: list[str], cfg, paths: dict[str, str]) -> list[str]:
        """
        将 args_template 中的占位符 {key} 用 cfg 或 paths 的值替换。
        - 优先从 paths 取（如 {dataset_toml} / {cache_logs_dir}）
        - 否则从 cfg 取（如 {vae_path} / {text_encoder_path} / {text_encoder_path_2}）
        - 保留普通字面量（如 "--dataset_config"）
        """
        out: list[str] = []
        for item in template:
            if isinstance(item, str) and item.startswith("{") and item.endswith("}"):
                key = item[1:-1]
                if key in paths:
                    out.append(str(paths[key]))
                else:
                    val = getattr(cfg, key, None)
                    if val is None:
                        raise TrainingError(f"缺少必须的配置字段: {key}")
                    out.append(str(val))
            else:
                out.append(str(item))
        return out

    def _build_training_command(self, task: TrainingTask, dataset_config_rel: str, training_dir: Path,
                                preview_mode: bool = False) -> List[str]:
        """
        构建训练命令（避免参数重复，使用元数据系统）
        - dataset_config_rel: 相对项目根的 dataset.toml 路径（上一步返回的值）
        - preview_mode: 是否为预览模式（影响参数显示）
        """
        config = task.config
        model_spec = get_model(task.training_type)

        # 脚本（相对项目根）
        scripts = self._scripts_for_task(task)
        train_py_rel = scripts["train"]

        # 输出目录
        output_dir = (training_dir / "output").resolve()
        output_dir_rel = self._rel_to_root_posix(output_dir)
        if not preview_mode:
            output_dir.mkdir(parents=True, exist_ok=True)

        # ✨ 使用训练脚本的绝对路径（accelerate 支持直接运行脚本文件）
        # 避免 --module 模式下 PYTHONPATH 继承问题
        train_script_absolute = (self._PROJECT_ROOT / train_py_rel).resolve()
        log_info(f"[训练脚本] 绝对路径: {train_script_absolute}")
        log_info(f"[训练脚本] 是否存在: {train_script_absolute.exists()}")

        if not train_script_absolute.exists():
            raise TrainingError(f"训练脚本不存在: {train_script_absolute}")

        # 固定参数（直接运行脚本文件，不使用 --module）
        cmd = [
            str(self._python_exe),  # 🔧 不使用 .resolve() 以避免在 Linux venv 中解析符号链接
            "-m",
            self._ACCELERATE_MODULE,
            ("--num_cpu_threads_per_process", "1"),
            ("--mixed_precision", "bf16"),
            str(train_script_absolute),  # ✅ 直接使用脚本绝对路径
            ("--dataset_config", dataset_config_rel),
            ("--output_dir", output_dir_rel),
            ("--network_module", model_spec.network_module),
        ]

        # 动态参数（来自配置，已过滤target="cli"）
        dynamic_args = self._build_dynamic_args(config, preview_mode=preview_mode)
        cmd.extend(dynamic_args)

        # 采样相关（如果配置了sample_prompt）
        self._add_sampling_args(cmd, config, training_dir, preview_mode=preview_mode)

        # 日志目录
        log_dir = (training_dir / "logs").resolve()
        cmd.append(("--logging_dir", self._rel_to_root_posix(log_dir)))

        # 展平命令用于日志显示
        flat_cmd = self._flatten_command(cmd)
        log_info(f"训练命令: {' '.join(flat_cmd)}")
        return cmd

    def _add_sampling_args(self, cmd: List, config: BaseTrainingConfig, training_dir: Path, preview_mode: bool = False) -> None:
        """方案B：统一的采样参数处理逻辑"""
        # 1. 检查采样开关
        sampling_enabled = getattr(config, "sampling_enabled", False)
        if not sampling_enabled:
            log_info("采样功能未启用，跳过采样设置")
            return

        # 2. 获取采样提示词
        sample_prompt = getattr(config, "sample_prompt", "").strip()
        if not sample_prompt:
            log_info("采样提示词为空，跳过采样设置")
            return

        # 3. 构建采样内容（清理+重组）
        sampling_content = self._build_sampling_content(config, sample_prompt)

        # 4. 处理采样文件路径
        sample_prompts_file = (training_dir / "sample_prompts.txt").resolve()

        if not preview_mode:
            # 实际模式：创建目录并写入文件
            training_dir.mkdir(parents=True, exist_ok=True)
            sample_prompts_file.write_text(sampling_content, encoding="utf-8")

            # 创建采样输出目录
            sample_dir = (training_dir / "sample").resolve()
            sample_dir.mkdir(exist_ok=True)
        else:
            # 预览模式：只构建路径，不实际创建文件
            log_info(f"预览模式：采样文件路径 {sample_prompts_file}")

        # 5. 添加采样CLI参数
        cmd.extend([
            ("--sample_prompts", self._rel_to_root_posix(sample_prompts_file)),
        ])

        # 6. 添加采样频率参数（仅在启用时）
        sample_every_n_epochs = getattr(config, "sample_every_n_epochs", None)
        if sample_every_n_epochs and sample_every_n_epochs > 0:
            cmd.extend([("--sample_every_n_epochs", str(sample_every_n_epochs))])

        sample_at_first = getattr(config, "sample_at_first", False)
        if sample_at_first:
            cmd.append("--sample_at_first")

        log_info(f"采样配置已生成: {sampling_content[:100]}...")

    def _build_sampling_content(self, config: BaseTrainingConfig, prompt: str) -> str:
        """构建完整的采样内容（支持多行，智能清理）"""
        lines = []

        # 处理多行提示词
        for line in prompt.split('\n'):
            line = line.strip()
            if not line:
                continue

            # 清理每行中的旧参数
            clean_line = self._clean_sample_prompt(line)

            # 为每行添加当前配置的参数
            line_with_params = self._append_sampling_params(config, clean_line)
            lines.append(line_with_params)

        return '\n'.join(lines)

    def _clean_sample_prompt(self, prompt: str) -> str:
        """清理单行提示词中的采样参数"""
        import re
        # 移除 --w/--h/--s/--g/--d/--f 等采样参数
        cleaned = re.sub(r'\s*--[whsgdf]\s+[\d.]+(?:\s|$)', ' ', prompt)
        return ' '.join(cleaned.split())

    def _append_sampling_params(self, config: BaseTrainingConfig, prompt: str) -> str:
        """为提示词添加当前配置的采样参数"""
        params = []

        # 参数映射表（确保正确的CLI参数拼接）
        param_mappings = {
            'sample_width': '--w',      # 宽度
            'sample_height': '--h',     # 高度
            'sample_factor': '--f',     # 帧数
            'sample_steps': '--s',      # 步数
            'sample_guidance': '--g',   # 指导系数
            'sample_seed': '--d'        # 种子
        }

        # 构建参数列表
        for field_name, cli_flag in param_mappings.items():
            value = getattr(config, field_name, None)
            if value is not None and str(value).strip() != "":
                params.extend([cli_flag, str(value).strip()])

        # 添加控制图参数（使用相对路径）
        control_image = getattr(config, 'sample_control_image', '').strip()
        if control_image:
            # 此时 control_image 已经是相对路径（如 "control/sample_control.png"）
            params.extend(['--ci', control_image])

        # 组合提示词和参数
        if params:
            return f"{prompt} {' '.join(params)}"
        else:
            return prompt

    def _flatten_command(self, cmd: List) -> List[str]:
        """展平命令用于日志显示"""
        flat_cmd = []
        for item in cmd:
            if isinstance(item, tuple):
                flat_cmd.extend(item)
            elif isinstance(item, list):
                flat_cmd.extend(item)
            else:
                flat_cmd.append(str(item))
        return flat_cmd

    def _create_training_scripts(self, task: TrainingTask, dataset_config_rel: str, training_dir: Path) -> Dict[str, str]:
        """
        生成简洁的 train.bat 脚本
        - 每行一个参数，使用 ^ 连接
        - 切到项目根目录
        - 设置必要环境变量
        """
        # 1) 命令（脚本使用绝对路径，参数使用相对于 workspace_root 的相对路径）
        cmd = self._build_training_command(task, dataset_config_rel, training_dir, preview_mode=False)

        # 2) 从脚本目录跳回工作目录（workspace_root）的相对路径
        # bat 脚本需要 cd 到 workspace_root，这样相对路径参数才能正确解析
        rel_to_root_from_script = os.path.relpath(self._WORKING_DIR, training_dir)
        rel_to_root_win = rel_to_root_from_script.replace("/", "\\")

        # 3) PYTHONPATH 指向 musubi 源码目录（使用绝对路径）
        musubi_src_abs = str(self._musubi_src.resolve())

        # 4) 构建多行命令字符串和一行命令字符串
        flat_cmd = self._flatten_command(cmd)

        # 构建多行格式（Windows批处理风格）- 正确的参数对格式
        cmd_lines = []
        i = 0
        while i < len(flat_cmd):
            if i == 0:
                # 第一行（Python脚本）
                cmd_lines.append(f"{flat_cmd[i]} ^")
                i += 1
            elif i == len(flat_cmd) - 1:
                # 最后一个参数（无续行符）
                cmd_lines.append(f"    {flat_cmd[i]}")
                i += 1
            elif flat_cmd[i].startswith('--'):
                # 参数名开头，检查是否有对应的值
                if i + 1 < len(flat_cmd) and not flat_cmd[i + 1].startswith('--'):
                    # 参数对：--param value
                    cmd_lines.append(f"    {flat_cmd[i]} {flat_cmd[i + 1]} ^")
                    i += 2
                else:
                    # 单独的开关参数：--flag
                    if i == len(flat_cmd) - 1:
                        cmd_lines.append(f"    {flat_cmd[i]}")
                    else:
                        cmd_lines.append(f"    {flat_cmd[i]} ^")
                    i += 1
            else:
                # 其他参数
                if i == len(flat_cmd) - 1:
                    cmd_lines.append(f"    {flat_cmd[i]}")
                else:
                    cmd_lines.append(f"    {flat_cmd[i]} ^")
                i += 1

        # 移除最后一行的续行符
        if cmd_lines and cmd_lines[-1].endswith(' ^'):
            cmd_lines[-1] = cmd_lines[-1][:-2]

        multi_line_cmd = "\n".join(cmd_lines)
        command_line = " ".join(flat_cmd)

        # 5) Windows 批处理（简洁版本）
        bat_content = f"""@echo off
cd /d "%~dp0{rel_to_root_win}"

set "PYTHONPATH={musubi_src_abs};%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"

{multi_line_cmd}
"""

        # 6) 只生成 bat 文件
        bat_path = training_dir / "train.bat"
        bat_path.write_text(bat_content, encoding="utf-8")

        log_info(f"训练脚本已生成: {bat_path}")
        return {
            "bat_script": str(bat_path),
            "command_line": command_line  # 一行命令字符串，便于显示和使用
        }

    def _run_cache_steps(self, task: TrainingTask, dataset_config_rel: str,
                         log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """执行预处理缓存：按 ModelSpec.cache_steps 的顺序执行；不做任何脚本名猜测。"""
        scripts = self._scripts_for_task(task)
        steps: list[dict] = scripts.get("cache_steps", [])

        if not steps:
            log_info("模型未声明缓存步骤，跳过预处理")
            return True

        # 工作路径与上下文 (使用统一目录结构，支持新的 task_id--name 格式)
        training_dir = self._get_task_dir(task)
        cache_logs_dir = (training_dir / "cache").resolve()
        cache_logs_dir.mkdir(parents=True, exist_ok=True)

        paths_ctx = {
            "dataset_toml": dataset_config_rel,
            "cache_logs_dir": self._rel_to_root_posix(cache_logs_dir),
        }

        for step in steps:
            # 条件启用（若注册了 enabled）
            enabled_fn = step.get("enabled")
            if callable(enabled_fn):
                try:
                    if not enabled_fn(task.config):
                        log_info(f"跳过缓存步骤（未启用）: {step.get('name')}")
                        continue
                except Exception as e:
                    log_error(f"评估缓存步骤是否启用失败: {e}")
                    continue

            if self._cancelled:
                log_info("预处理被取消")
                return False

            script_rel = step["script"]
            args_tmpl = step.get("args_template", [])

            # 基于模板构建最终参数
            try:
                step_args = self._build_args_from_template(args_tmpl, task.config, paths_ctx)
            except Exception as e:
                err = f"构建缓存步骤参数失败: {e}"
                log_error(err)
                if log_callback: log_callback(f"[错误] {err}")
                return False

            log_info(f"执行预处理步骤: {step.get('name')} -> {script_rel}")

            # ✨ 使用 python -c 配合 runpy.run_module() 运行，手动注入 sys.path
            # script_rel 格式：runtime/engines/musubi-tuner/src/musubi_tuner/qwen_image_cache_text_encoder_outputs.py
            # 需要转换为模块路径：musubi_tuner.qwen_image_cache_text_encoder_outputs

            # 1. 提取模块路径：从 .../src/ 之后的部分
            script_rel_posix = script_rel.replace("\\", "/")
            if "/src/" in script_rel_posix:
                # 提取 src/ 之后的部分：musubi_tuner/qwen_image_cache_text_encoder_outputs.py
                module_path_part = script_rel_posix.split("/src/", 1)[1]
                # 移除 .py 后缀并转换为模块路径
                module_name = module_path_part.replace("/", ".").replace(".py", "")
                # 结果：musubi_tuner.qwen_image_cache_text_encoder_outputs
            else:
                raise TrainingError(f"无法解析模块路径: {script_rel}")

            # 2. 获取 musubi-tuner/src 的绝对路径（用于 sys.path.insert）
            musubi_src_path = str(self._musubi_src.resolve())

            # 3. 构建 python -c 命令：手动注入 sys.path 并使用 runpy.run_module
            # 格式: python.exe -c "import sys,runpy; sys.path.insert(0,r'路径'); runpy.run_module('模块名', run_name='__main__')" 参数...
            python_oneliner = (
                f"import sys,runpy; "
                f"sys.path.insert(0,r'{musubi_src_path}'); "
                f"runpy.run_module('{module_name}', run_name='__main__')"
            )

            cache_cmd = [
                str(self._python_exe),  # 🔧 不使用 .resolve() 以避免在 Linux venv 中解析符号链接
                "-c",
                python_oneliner,
                *step_args
            ]

            log_info(f"[缓存] 使用 runpy 方式执行: {module_name}")
            log_info(f"[缓存] Python路径注入: {musubi_src_path}")
            log_info(f"[缓存] Python可执行文件: {self._python_exe}")
            log_info(f"[缓存] 完整命令: {' '.join(cache_cmd)}")

            # 4. 环境变量（保留基础设置，不再依赖 PYTHONPATH）
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'

            try:
                # 统一由 LogSink 落盘与广播（此处不直接写文件）
                success = self._network_retry.run_with_retry(
                    command=cache_cmd,
                    cwd=str(self._WORKING_DIR),
                    env=env,
                    log_callback=log_callback,
                    timeout=1800,
                    log_file_path=None
                )
                if not success:
                    err = f"预处理失败: {step.get('name')} ({script_rel})"
                    log_error(err)
                    if log_callback: log_callback(f"[错误] {err}")
                    return False

                ok = f"预处理完成: {step.get('name')}"
                log_success(ok)
                if log_callback: log_callback(f"[完成] {ok}")

            except Exception as e:
                err = f"预处理异常: {e}"
                log_error(err)
                if log_callback: log_callback(f"[异常] {err}")
                return False

        return True

    def build_artifacts(self, task: TrainingTask, force: bool = False) -> Dict[str, Any]:
        """构建训练工件 - 生成所有必要文件并返回scripts_info"""
        try:
            # 验证配置
            self._validate_config(task.config)

            # 训练目录（支持新的 task_id--name 格式）
            training_dir = self._get_task_dir(task)

            # 如果不强制重建，且文件已存在且有效，直接返回现有信息
            if not force and self.validate_artifacts(task):
                log_info(f"训练工件已存在且有效，跳过重建: {task.id}")
                return self._load_existing_scripts_info(task, training_dir)

            log_info(f"生成训练工件: {task.id}")

            # 生成dataset.toml
            dataset_config_rel = self._create_dataset_config(task, preview_mode=False)

            # 生成train.bat和获取command_line
            scripts_info = self._create_training_scripts(task, dataset_config_rel, training_dir)

            # 构建完整的scripts_info
            complete_scripts_info = {
                'command_line': scripts_info['command_line'],
                'bat_script': scripts_info['bat_script'],
                'dataset_config': dataset_config_rel,
                'ready': True,
                'generated_at': time.time()
            }

            log_success(f"训练工件生成完成: {task.id}")
            return complete_scripts_info

        except Exception as e:
            log_error(f"生成训练工件失败: {e}")
            raise TrainingError(f"生成训练工件失败: {e}")

    def validate_artifacts(self, task: TrainingTask) -> bool:
        """验证训练工件是否完整有效"""
        try:
            training_dir = self._get_task_dir(task)

            # 检查必要文件是否存在
            required_files = [
                training_dir / "dataset.toml",
                training_dir / "train.bat"
            ]

            for file_path in required_files:
                if not file_path.exists():
                    log_info(f"工件文件缺失: {file_path}")
                    return False

            # 检查采样文件（如果启用采样）
            if hasattr(task.config, 'sampling_enabled') and task.config.sampling_enabled:
                sample_prompts_file = training_dir / "sample_prompts.txt"
                if not sample_prompts_file.exists():
                    log_info(f"采样文件缺失: {sample_prompts_file}")
                    return False

            return True

        except Exception as e:
            log_error(f"验证工件失败: {e}")
            return False

    def _load_existing_scripts_info(self, task: TrainingTask, training_dir: Path) -> Dict[str, Any]:
        """加载现有的scripts_info"""
        try:
            # 尝试从task.json加载现有的scripts_info
            task_file = training_dir / "task.json"
            if task_file.exists():
                with open(task_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
                    scripts_info = task_data.get('scripts_info')
                    if scripts_info and scripts_info.get('ready'):
                        return scripts_info

            # 如果没有现有信息，重新构建基本信息
            dataset_config_path = training_dir / "dataset.toml"
            bat_script_path = training_dir / "train.bat"

            # 从bat文件推断command_line
            command_line = ""
            if bat_script_path.exists():
                # 简化：读取bat文件内容并提取命令
                bat_content = bat_script_path.read_text(encoding='utf-8')
                # 这里可以加入更复杂的解析逻辑
                command_line = "从现有脚本重建"  # 临时占位

            return {
                'command_line': command_line,
                'bat_script': str(bat_script_path),
                'dataset_config': self._rel_to_root_posix(dataset_config_path),
                'ready': True,
                'loaded_from_existing': True
            }

        except Exception as e:
            log_error(f"加载现有scripts_info失败: {e}")
            raise

    def prepare_training(self, task: TrainingTask) -> Dict[str, Any]:
        """准备训练环境 - 确保工件存在并返回完整信息"""
        try:
            # 验证配置
            self._validate_config(task.config)

            # 使用统一目录结构（支持新的 task_id--name 格式）
            training_dir = self._get_task_dir(task)

            # 确保工件存在（幂等操作）
            if not self.validate_artifacts(task):
                log_info("工件不完整，重新生成...")
                scripts_info = self.build_artifacts(task, force=True)
            else:
                scripts_info = self._load_existing_scripts_info(task, training_dir)

            # 返回完整的训练信息
            return {
                'training_dir': training_dir,
                'dataset_config': scripts_info['dataset_config'],
                'scripts_info': scripts_info,  # 包含command_line！
                'log_file': training_dir / "train.log"
            }

        except Exception as e:
            log_error(f"准备训练失败: {e}")
            raise TrainingError(f"准备训练失败: {e}")

    def _validate_config(self, config: BaseTrainingConfig):
        """验证训练配置"""
        # 对于BaseTrainingConfig，我们验证基本字段即可
        # 模型路径验证移到任务级别验证
        if not hasattr(config, 'resolution') or not config.resolution:
            raise TrainingError("分辨率参数无效")

        if not hasattr(config, 'batch_size') or config.batch_size <= 0:
            raise TrainingError("批大小必须大于0")

        # 验证模型路径 (对于Qwen-Image) - 只在路径非空时验证
        if hasattr(config, 'dit_path') and config.dit_path and config.dit_path.strip():
            if not os.path.exists(config.dit_path):
                raise TrainingError(f"DiT模型路径无效: {config.dit_path}")
        if hasattr(config, 'vae_path') and config.vae_path and config.vae_path.strip():
            if not os.path.exists(config.vae_path):
                raise TrainingError(f"VAE模型路径无效: {config.vae_path}")
        if hasattr(config, 'text_encoder_path') and config.text_encoder_path and config.text_encoder_path.strip():
            if not os.path.exists(config.text_encoder_path):
                raise TrainingError(f"Text Encoder路径无效: {config.text_encoder_path}")

    def run_training(self,
                     task: TrainingTask,
                     progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                     log_callback: Optional[Callable[[str], None]] = None) -> bool:
        """运行训练"""
        sink: Optional[LogSink] = None
        try:
            # 重置取消标志
            self._cancelled = False

            # 统一日志写入/广播
            sink = LogSink(self.task_id, self.event_bus, self.config.storage.workspace_root)

            # 准备训练 - 不直接修改task.state，通过事件通知
            sink.write_line("准备训练环境...", phase='cache')
            # 准备阶段仍然保持RUNNING状态，不再单独设置preparing状态

            training_info = self.prepare_training(task)

            # 执行预处理缓存步骤
            log_info("开始预处理缓存步骤...")
            if log_callback:
                log_callback("开始预处理缓存步骤...")

            # 缓存阶段：通过 LogSink 统一写入与广播
            cache_success = self._run_cache_steps(
                task,
                training_info['dataset_config'],
                log_callback=(lambda line: sink.write_line(line, phase='cache'))
            )
            if not cache_success:
                # 不直接修改task.state，通过回调通知
                error_msg = "预处理缓存失败"
                sink.write_line(error_msg, phase='cache', level='error')
                if progress_callback:
                    progress_callback({"state": "failed", "error": error_msg})
                return False

            # 开始训练 - 先输出欢迎横幅
            banner = """
╔══════════════════════════════════════════════╗
║                                              ║
║     ███████  █████  ███████ ██    ██        ║
║     ██      ██   ██ ██       ██  ██         ║
║     █████   ███████ ███████   ████          ║
║     ██      ██   ██      ██    ██           ║
║     ███████ ██   ██ ███████    ██           ║
║                                              ║
║     ████████ ██   ██ ███    ██ ███████      ║
║        ██    ██   ██ ████   ██ ██           ║
║        ██    ██   ██ ██ ██  ██ █████        ║
║        ██    ██   ██ ██  ██ ██ ██           ║
║        ██     █████  ██   ████ ███████      ║
║                                              ║
║       🚀 AI Model Training Made Easy 🚀      ║
║                                              ║
╚══════════════════════════════════════════════╝
"""
            # 输出横幅到日志和WebSocket
            for line in banner.strip().split('\n'):
                sink.write_line(line, phase='train')
            
            sink.write_line("", phase='train')  # 空行
            sink.write_line("开始正式训练...", phase='train')
            if progress_callback:
                progress_callback({"state": "running"})

            log_info(f"开始训练: {task.name}")
            if log_callback:
                log_callback(f"开始训练: {task.name}")

            # 启动训练进程 - 直接重新构建命令避免字符串分割问题
            training_dir = training_info['training_dir']
            dataset_config = training_info['dataset_config']
            cmd_list = self._build_training_command(task, dataset_config, training_dir, preview_mode=False)
            cmd = self._flatten_command(cmd_list)

            # 设置环境变量，确保能找到musubi_tuner模块
            env = os.environ.copy()
            # ✨ 使用绝对路径（workspace-based runtime）
            env['PYTHONPATH'] = str(self._musubi_src.resolve()) + os.pathsep + env.get('PYTHONPATH', '')
            env['PYTHONIOENCODING'] = 'utf-8'

            # 使用网络重试逻辑启动训练（透传 log_sink）
            return self._run_training_with_retry(task, cmd, env, progress_callback, log_callback, sink)

        except Exception as e:
            # 不直接修改task.state，通过回调通知
            error_msg = str(e)
            if sink is not None:
                sink.write_line(f"训练异常: {error_msg}", phase='train', level='error')
            else:
                self._emit_log(f"训练异常: {error_msg}", "error")
            log_error(f"训练失败: {error_msg}")
            if progress_callback:
                progress_callback({
                    "state": "failed",
                    "error": error_msg
                })
            return False
        finally:
            try:
                if sink is not None:
                    sink.close()
            except Exception:
                pass

    def _run_training_with_retry(self,
                                 task: TrainingTask,
                                 cmd: List[str],
                                 env: Dict[str, str],
                                 progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                                 log_callback: Optional[Callable[[str], None]] = None,
                                 log_sink: Optional[LogSink] = None) -> bool:
        """使用网络重试逻辑运行训练"""
        last_error = None

        for attempt in range(self._network_retry.max_retries + 1):
            # 检查是否已取消
            if self._cancelled:
                if log_sink is not None:
                    log_sink.write_line("训练被取消", phase='train', level='warning')
                else:
                    self._emit_log("训练被取消", "warning")
                log_info("训练被取消")
                return False

            # 设置镜像站
            if attempt < len(self._network_retry.HF_MIRRORS):
                self._network_retry._set_hf_mirror(self._network_retry.HF_MIRRORS[attempt])

            # 记录尝试信息
            mirror_info = f"(尝试 {attempt + 1}/{self._network_retry.max_retries + 1}"
            if attempt < len(self._network_retry.HF_MIRRORS):
                mirror_info += f", 镜像: {self._network_retry.HF_MIRRORS[attempt]}"
            mirror_info += ")"

            start_msg = f"启动训练 {mirror_info}: {task.name}"
            log_info(start_msg)
            if log_sink is not None:
                log_sink.write_line(start_msg, phase='train')
            if log_callback:
                log_callback(start_msg)

            try:
                # 复制环境变量并应用当前镜像设置
                current_env = env.copy()
                if 'HF_ENDPOINT' in os.environ:
                    current_env['HF_ENDPOINT'] = os.environ['HF_ENDPOINT']

                # 🔍 调试：打印 PYTHONPATH 确认是否正确设置
                log_info(f"[环境变量] PYTHONPATH = {current_env.get('PYTHONPATH', '(未设置)')}")
                log_info(f"[工作目录] cwd = {self._WORKING_DIR}")
                log_info(f"[命令] {' '.join(cmd[:5])}...")  # 只打印前5个参数

                # 创建进程
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(self._WORKING_DIR),
                    env=current_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace', bufsize=1
                )

                # 监控训练进度（统一由 LogSink 负责写入/广播）
                training_result = self._monitor_training(task, progress_callback, log_callback, None, log_sink)

                # 检查是否在监控过程中被取消
                if self._cancelled:
                    log_info("训练在监控过程中被取消")
                    if log_sink is not None:
                        log_sink.write_line("训练在监控过程中被取消", phase='train', level='warning')
                    return False

                # 检查训练结果
                if training_result:
                    log_success(f"训练成功完成 {mirror_info}")
                    return True

                # 检查任务状态是否为取消
                if hasattr(task, 'state') and task.state == TrainingState.CANCELLED:
                    log_info("训练任务已被取消，停止重试")
                    if log_sink is not None:
                        log_sink.write_line("训练任务已被取消，停止重试", phase='train', level='warning')
                    return False

                # 训练失败，检查是否为网络错误
                error_output = getattr(task, 'error_message', '')
                if not self._network_retry._is_network_error(error_output):
                    # 非网络错误，不重试
                    log_error(f"非网络错误，停止重试: {error_output}")
                    return False

                last_error = f"训练失败（网络问题）: {error_output}"
                log_error(f"网络错误 {mirror_info}: {last_error}")
                net_msg = f"[网络错误] {mirror_info}: 检测到网络问题"
                if log_sink is not None:
                    log_sink.write_line(net_msg, phase='train', level='error')
                if log_callback:
                    log_callback(net_msg)

            except Exception as e:
                last_error = f"训练异常: {str(e)}"
                log_error(f"异常 {mirror_info}: {last_error}")
                exc_msg = f"[异常] {mirror_info}: {last_error}"
                if log_sink is not None:
                    log_sink.write_line(exc_msg, phase='train', level='error')
                if log_callback:
                    log_callback(exc_msg)

            finally:
                # 🔧 增强进程清理逻辑，确保子进程不阻塞
                if self._proc:
                    try:
                        if self._proc.poll() is None:
                            log_info("终止训练进程...")
                            self._proc.terminate()
                            try:
                                self._proc.wait(timeout=10)
                                log_info("训练进程已正常终止")
                            except subprocess.TimeoutExpired:
                                log_warning("进程未响应terminate，强制kill")
                                self._proc.kill()
                                self._proc.wait(timeout=5)
                                log_info("训练进程已强制终止")

                        # 🔧 关闭输出流，防止管道阻塞
                        if self._proc.stdout and not self._proc.stdout.closed:
                            try:
                                self._proc.stdout.close()
                            except (OSError, ValueError) as e:
                                log_warning(f"关闭 stdout 流失败: {e}")
                                pass
                        if self._proc.stderr and not self._proc.stderr.closed:
                            try:
                                self._proc.stderr.close()
                            except (OSError, ValueError) as e:
                                log_warning(f"关闭 stderr 流失败: {e}")
                                pass
                                
                    except Exception as e:
                        log_error(f"清理进程失败: {e}")
                    finally:
                        self._proc = None

            # 再次检查是否在处理过程中被取消
            if self._cancelled:
                log_info("训练被取消，停止重试")
                if log_sink is not None:
                    log_sink.write_line("训练被取消，停止重试", phase='train', level='warning')
                return False

            # 如果不是最后一次尝试，等待后重试
            if attempt < self._network_retry.max_retries:
                # 在等待重试前再次检查取消状态
                if self._cancelled:
                    log_info("训练被取消，跳过重试")
                    return False

                wait_msg = f"等待 {self._network_retry.retry_delay} 秒后重试..."
                log_info(wait_msg)
                if log_sink is not None:
                    log_sink.write_line(wait_msg, phase='train')
                if log_callback:
                    log_callback(wait_msg)

                # 分段等待，每0.5秒检查一次取消状态
                for i in range(self._network_retry.retry_delay * 2):
                    if self._cancelled:
                        log_info("等待重试期间训练被取消")
                        return False
                    time.sleep(0.5)

        # 所有尝试都失败了
        error_msg = f"所有重试都失败了，最后错误: {last_error}"
        if log_sink is not None:
            log_sink.write_line(error_msg, phase='train', level='error')
        else:
            self._emit_log(error_msg, "error")
        log_error(error_msg)
        if log_callback:
            log_callback(f"[失败] 所有重试都失败了")

        return False

    def _monitor_training(self,
                          task: TrainingTask,
                          progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                          log_callback: Optional[Callable[[str], None]] = None,
                          log_file=None,
                          log_sink: Optional[LogSink] = None) -> bool:
        """监控训练进度（带超时保护，防止子进程阻塞）"""
        try:
            if not self._proc:
                return False

            error_lines = []  # 收集错误输出
            
            # 🔧 添加超时保护机制，防止 readline 永久阻塞
            import time
            last_output_time = time.time()
            no_output_timeout = 60  # 60秒无输出则检查进程状态

            while True:
                # 检查是否被取消
                if self._cancelled:
                    log_info("训练监控过程中收到取消信号")
                    if log_sink is not None:
                        log_sink.write_line("训练被取消", phase='train', level='warning')
                    else:
                        self._emit_log("训练被取消", "warning")
                    return False

                # 🔧 超时保护：定期检查进程状态，避免因子进程持有管道而永久阻塞
                current_time = time.time()
                if current_time - last_output_time > no_output_timeout:
                    return_code = self._proc.poll()
                    if return_code is not None:
                        # 进程已退出但 readline 可能被子进程阻塞
                        log_info(f"检测到进程已退出（超时保护触发），退出码: {return_code}")
                        break  # 强制退出监控循环
                    else:
                        # 进程还在运行，重置计时器继续等待
                        log_info("进程仍在运行但长时间无输出，继续等待...")
                        last_output_time = current_time

                output = self._proc.stdout.readline()
                if output == '' and self._proc.poll() is not None:
                    break

                if output:
                    last_output_time = time.time()  # 🔧 重置超时计时器
                    line = output.strip()

                    # 过滤重复行：与上一行完全相同则跳过
                    if line == self._last_logged_line:
                        continue
                    
                    self._last_logged_line = line

                    # 统一写入与广播
                    if log_sink is not None:
                        # 使用 LogSink 时，所有日志通过其批量推送机制处理（已包含去重）
                        log_sink.write_line(line, phase='train')
                    else:
                        # 不使用 LogSink 时，使用传统的文件写入和事件推送
                        if log_file:
                            log_file.write(output)
                            log_file.flush()
                        self._emit_log(line)
                        # 只在不使用 log_sink 时才调用 callback（避免重复推送）
                        if log_callback:
                            log_callback(line)

                    # 收集可能的错误信息
                    if self._network_retry._is_network_error(line):
                        error_lines.append(line)

                    # 解析训练进度
                    progress_info = self._parse_training_output(line)
                    if progress_info:
                        # 更新任务状态
                        for key, value in progress_info.items():
                            if hasattr(task, key):
                                setattr(task, key, value)

                        # 计算进度百分比
                        if task.total_steps > 0:
                            task.progress = task.current_step / task.total_steps

                        # 发送进度事件和回调
                        progress_data = {
                            "step": task.current_step,
                            "total_steps": task.total_steps,
                            "epoch": task.current_epoch,
                            "loss": task.loss,
                            "lr": task.learning_rate,
                            "speed": task.speed,
                            "eta_seconds": task.eta_seconds,
                            "progress": task.progress
                        }
                        self._emit_progress(**progress_data)

                        if progress_callback:
                            progress_callback(progress_data)

            # 检查训练结果
            return_code = self._proc.poll()
            log_info(f"训练监控结束，进程退出码: {return_code}")
            
            if return_code == 0:
                success_msg = f"训练完成: {task.name}"
                if log_sink is not None:
                    log_sink.write_line(success_msg, phase='train', level='success')
                else:
                    self._emit_log(success_msg, "success")
                log_success(success_msg)
                
                # 确保最终日志能够发送到前端
                time.sleep(0.2)  # 🔧 稍微延长等待时间，确保日志和状态都能推送

                if progress_callback:
                    progress_callback({"state": "completed"})
                return True
            else:
                # 构建错误信息，包括网络错误
                if error_lines:
                    error_msg = f"训练失败，网络错误: {'; '.join(error_lines[-3:])}"  # 最后3行错误
                else:
                    error_msg = f"训练进程退出，代码: {return_code}"

                if log_sink is not None:
                    log_sink.write_line(error_msg, phase='train', level='error')
                else:
                    self._emit_log(error_msg, "error")
                log_error(error_msg)
                
                # 确保最终日志能够发送到前端
                time.sleep(0.2)  # 🔧 稍微延长等待时间
                
                if progress_callback:
                    progress_callback({
                        "state": "failed",
                        "error": error_msg
                    })
                return False

        except Exception as e:
            error_msg = str(e)
            if log_sink is not None:
                log_sink.write_line(f"训练监控失败: {error_msg}", phase='train', level='error')
            else:
                self._emit_log(f"训练监控失败: {error_msg}", "error")
            log_error(f"训练监控失败: {error_msg}")
            if progress_callback:
                progress_callback({
                    "state": "failed",
                    "error": error_msg
                })
            return False

    def _parse_training_output(self, line: str) -> Optional[Dict[str, Any]]:
        """解析训练输出，提取进度信息"""
        try:
            progress_info = {}
            low = line.lower()

            # 仅在明确的训练进度上下文中解析（避免误匹配模型加载进度等）：
            has_steps_marker = ('steps:' in low) or bool(re.search(r'\bstep\s+\d+/\d+', line, re.IGNORECASE))
            has_epoch_marker = bool(re.search(r'\bepoch\s+\d+/\d+', line, re.IGNORECASE))

            # 解析步数和轮次（兼容多种格式）
            # 1) Epoch E/N（独立存在也允许解析）
            epoch_match = re.search(r'Epoch\s+(\d+)/(\d+)', line, re.IGNORECASE)
            if epoch_match:
                progress_info['current_epoch'] = int(epoch_match.group(1))
                progress_info['total_epochs'] = int(epoch_match.group(2))

            # 2) Step X/Y（显示的 Step 前缀）
            step_match = re.search(r'Step\s+(\d+)/(\d+)', line, re.IGNORECASE)
            if step_match:
                progress_info['current_step'] = int(step_match.group(1))
                progress_info['total_steps'] = int(step_match.group(2))

            # 3) tqdm 风格的 "3/640 [...]"（仅在带有 steps: 标记的行兜底）
            if ('current_step' not in progress_info or 'total_steps' not in progress_info) and has_steps_marker:
                generic_step = re.search(r'(\d+)\s*/\s*(\d+)', line)
                if generic_step:
                    cs = int(generic_step.group(1))
                    ts = int(generic_step.group(2))
                    if ts >= cs and ts <= 10_000_000:
                        progress_info['current_step'] = cs
                        progress_info['total_steps'] = ts

            # 解析loss
            # TB 已能提供 loss，这里仅作兜底：兼容 avr_loss 或 loss= / loss:
            loss_match = re.search(r'(?:avr_)?loss\s*[:=]\s*([\d.]+)', line, re.IGNORECASE)
            if loss_match:
                progress_info['loss'] = float(loss_match.group(1))

            # 解析学习率
            lr_match = re.search(r'lr:?\s*([\d.e-]+)', line, re.IGNORECASE)
            if lr_match:
                progress_info['learning_rate'] = float(lr_match.group(1))

            # 解析速度：仅在训练进度行中解析（避免匹配加载行）
            if has_steps_marker or has_epoch_marker:
                speed_its = re.search(r'([\d.]+)\s*it/s', line, re.IGNORECASE)
                if speed_its:
                    progress_info['speed'] = float(speed_its.group(1))
                    progress_info['speed_unit'] = 'it/s'
                else:
                    speed_sit = re.search(r'([\d.]+)\s*s/it', line, re.IGNORECASE)
                    if speed_sit:
                        try:
                            v = float(speed_sit.group(1))
                            if v > 0:
                                progress_info['speed'] = v  # 直接保存原值，不转换
                                progress_info['speed_unit'] = 's/it'
                        except Exception:
                            pass

            # 解析ETA：仅在训练进度行中解析
            if has_steps_marker or has_epoch_marker:
                eta_match = re.search(r'ETA\s*:?\s*(\d{1,2}):(\d{2}):(\d{2})', line, re.IGNORECASE)
                if eta_match:
                    hours, minutes, seconds = map(int, eta_match.groups())
                    progress_info['eta_seconds'] = hours * 3600 + minutes * 60 + seconds
                else:
                    # 支持 <HH:MM:SS 格式
                    eta_angle = re.search(r'<\s*(\d{1,2}):(\d{2}):(\d{2})', line)
                    if eta_angle:
                        hours, minutes, seconds = map(int, eta_angle.groups())
                        progress_info['eta_seconds'] = hours * 3600 + minutes * 60 + seconds
                    else:
                        # 支持 <MM:SS 格式（无小时部分）
                        eta_short = re.search(r'<\s*(\d{1,2}):(\d{2})\b', line)
                        if eta_short:
                            minutes, seconds = map(int, eta_short.groups())
                            progress_info['eta_seconds'] = minutes * 60 + seconds

            # 推导进度
            if 'current_step' in progress_info and 'total_steps' in progress_info and progress_info['total_steps']:
                try:
                    progress_info['progress'] = max(0.0, min(1.0, progress_info['current_step'] / progress_info['total_steps']))
                except Exception:
                    pass

            return progress_info if progress_info else None

        except Exception as e:
            log_error(f"解析训练输出失败: {str(e)}")
            return None

    def cancel_training(self):
        """取消训练 - 强制终止所有相关进程"""
        self._cancelled = True  # 设置取消标志

        # 处理预处理进程
        if self._cache_proc and self._cache_proc.poll() is None:
            try:
                log_info("正在取消预处理进程...")
                self._cache_proc.terminate()
                try:
                    self._cache_proc.wait(timeout=5)
                    log_info("预处理进程已终止")
                except subprocess.TimeoutExpired:
                    log_info("预处理进程未响应，强制终止...")
                    self._cache_proc.kill()
                    self._cache_proc.wait()
                    log_info("预处理进程已强制终止")
                self._cache_proc = None
                return  # 如果只是预处理阶段，直接返回
            except Exception as e:
                log_error(f"终止预处理进程失败: {e}")

        # 处理主训练进程
        if self._proc and self._proc.poll() is None:
            try:
                log_info("正在取消训练...")

                # 获取主进程PID
                main_pid = self._proc.pid
                log_info(f"主训练进程PID: {main_pid}")

                # 方法1: 尝试优雅终止进程树
                try:
                    parent = psutil.Process(main_pid)
                    children = parent.children(recursive=True)

                    log_info(f"发现 {len(children)} 个子进程")

                    # 首先尝试优雅终止所有子进程（从最深的子进程开始）
                    for child in reversed(children):  # 反向遍历，先杀最深的子进程
                        try:
                            log_info(f"终止子进程: PID={child.pid}, 名称={child.name()}")
                            child.terminate()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    # 终止主进程
                    parent.terminate()

                    # 等待进程结束
                    gone, alive = psutil.wait_procs(children + [parent], timeout=5)

                    # 强制杀死仍然存活的进程
                    if alive:
                        log_info(f"强制杀死 {len(alive)} 个未响应的进程")
                        for proc in alive:
                            try:
                                log_info(f"强制杀死进程: PID={proc.pid}, 名称={proc.name()}")
                                proc.kill()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass

                        # 再次等待，缩短超时时间
                        psutil.wait_procs(alive, timeout=2)

                except psutil.NoSuchProcess:
                    log_info("主进程已不存在")
                except Exception as e:
                    log_error(f"使用psutil终止进程失败: {e}")

                    # 方法2: 回退到原始的进程终止方法
                    log_info("回退到基础进程终止方法")
                    try:
                        if os.name == 'nt':  # Windows
                            # Windows上强制终止进程树
                            subprocess.run([
                                "taskkill", "/F", "/T", "/PID", str(main_pid)
                            ], capture_output=True, check=False)
                        else:  # Unix/Linux
                            # 发送SIGTERM到进程组
                            os.killpg(os.getpgid(main_pid), signal.SIGTERM)
                            time.sleep(2)
                            # 如果还未结束，发送SIGKILL
                            try:
                                os.killpg(os.getpgid(main_pid), signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                    except Exception as e2:
                        log_error(f"回退方法也失败: {e2}")

                # 方法3: 额外安全检查 - 查找可能的训练相关进程
                try:
                    self._cleanup_training_processes()
                except Exception as e:
                    log_error(f"清理训练进程时出错: {e}")

                log_info("训练取消完成")

            except Exception as e:
                log_error(f"取消训练时出错: {e}")
            finally:
                self._proc = None

    def _cleanup_training_processes(self):
        """清理可能残留的训练相关进程"""
        try:
            # 查找可能的训练进程（基于进程名称和命令行）
            training_keywords = [
                "qwen_image_train_network.py",
                "musubi_tuner",
                "accelerate",
                "torch.distributed.run"
            ]

            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])

                    # 检查是否为训练相关进程
                    is_training_proc = any(keyword in cmdline.lower() for keyword in training_keywords)

                    if is_training_proc:
                        # 额外检查确保不是当前Python解释器进程
                        if proc.pid != os.getpid():
                            log_info(f"发现可能的残留训练进程: PID={proc.pid}, 命令={cmdline[:100]}...")
                            proc.kill()
                            killed_count += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            if killed_count > 0:
                log_info(f"清理了 {killed_count} 个残留的训练进程")

        except Exception as e:
            log_error(f"清理进程时出错: {e}")

    def _emergency_cleanup(self):
        """程序退出时的紧急清理"""
        try:
            if self._proc and self._proc.poll() is None:
                log_info("程序退出时发现正在运行的训练，执行紧急清理")
                self.cancel_training()

            # 清理网络重试助手
            if self._network_retry:
                self._network_retry.cleanup()
        except Exception as e:
            # 静默处理，避免程序退出时出现错误
            pass

    def is_available(self) -> bool:
        """检查Musubi-Tuner是否可用（workspace-based runtime）"""
        try:
            # ✨ 直接使用缓存的 musubi_dir（workspace/runtime/engines/musubi-tuner）
            if not self._musubi_dir.exists():
                return False

            # 检查关键脚本是否存在
            for model_spec in list_models():
                script_rel_path = f"src/musubi_tuner/{model_spec.script_train}"
                script_path = self._musubi_dir / script_rel_path
                if not script_path.exists():
                    return False

            return True

        except Exception:
            return False

    def _generate_dataset_config(self, toml_path: Path, dataset_id: str, config: BaseTrainingConfig):
        """生成数据集配置文件 (供TrainingManager调用)"""
        try:
            # 计算数据集路径
            dataset_path = self._resolve_dataset_path(dataset_id)

            # 计算缓存目录 (相对于toml文件的位置)
            cache_dir = toml_path.parent / "cache"

            # 设置路径到配置中
            config.image_video_directory = self._rel_to_root_posix(dataset_path)
            config.cache_directory = self._rel_to_root_posix(cache_dir)

            # 生成TOML内容
            toml_dict = build_toml_dict(config)
            toml_content = dumps_toml(toml_dict)

            # 写入文件
            toml_path.write_text(toml_content, encoding="utf-8")

        except Exception as e:
            log_error(f"生成数据集配置文件失败: {e}")
            raise
