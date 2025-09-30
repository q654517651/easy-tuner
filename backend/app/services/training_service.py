"""
训练服务
"""

import threading
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from ..models.training import (
    TrainingTaskBrief, TrainingTaskDetail, CreateTrainingTaskRequest,
    TrainingModelSpec, ParameterGroup, ParameterField, TrainingConfigSchema,
    CLIPreviewRequest, CLIPreviewResponse, TrainingStats
)
from ..core.training.manager_new import get_training_manager
from ..core.training.models import (
    list_models, get_model, get_fields_by_group, build_cli_args,
    ParameterGroup as CoreParameterGroup, QwenImageConfig, field_enabled,
    build_toml_dict, dumps_toml
)
from ..core.dataset.manager import get_dataset_manager
from ..utils.exceptions import TrainingNotFoundError, DatasetNotFoundError
from ..utils.logger import log_info, log_error
from .tb_event_service import get_tb_event_service


class TrainingService:
    """训练服务"""

    def __init__(self):
        self._training_manager = get_training_manager()
        self._dataset_manager = get_dataset_manager()
        self._lock = threading.Lock()
        # 添加配置引用
        from ..core.config import get_config
        self.config = get_config()

    def get_available_models(self) -> List[TrainingModelSpec]:
        """获取可用的训练模型列表"""
        model_specs = list_models()
        return [
            TrainingModelSpec(
                type_name=spec.type_name,
                title=spec.title,
                script_train=spec.script_train,
                script_cache_te=spec.script_cache_te,
                script_cache_latents=spec.script_cache_latents,
                network_module=spec.network_module,
                group_order=spec.group_order or [],
                path_mapping=spec.path_mapping or {},
                supported_dataset_types=spec.supported_dataset_types or []
            )
            for spec in model_specs
        ]

    def get_training_config_schema(self, training_type: str) -> TrainingConfigSchema:
        """获取训练配置模式"""
        try:
            spec = get_model(training_type)
            config_cls = spec.config_cls

            # 获取参数分组
            groups = []
            for group_enum in CoreParameterGroup.get_ordered_groups():
                groups.append(ParameterGroup(
                    key=group_enum.key,
                    title=group_enum.title,
                    description=group_enum.description
                ))

            # 获取所有字段
            fields = []
            config_instance = config_cls()  # 创建默认实例

            # ★ 从设置中注入模型路径到配置实例
            if spec.path_mapping:
                from ..core.config import get_config
                config = get_config()
                for field_name, config_path in spec.path_mapping.items():
                    try:
                        # 解析配置路径，如 "model_paths.qwen_image.dit_path"
                        path_parts = config_path.split('.')
                        value = config
                        for part in path_parts:
                            value = getattr(value, part, None) if hasattr(value, part) else None
                            if value is None:
                                break

                        # 如果获取到有效值，设置到配置实例中
                        if value and hasattr(config_instance, field_name):
                            setattr(config_instance, field_name, str(value))
                    except (AttributeError, KeyError, TypeError):
                        # 路径不存在或访问失败，跳过
                        continue

            for group in groups:
                group_fields = get_fields_by_group(config_cls, group.key)
                for field_name, field_obj in group_fields:
                    metadata = field_obj.metadata or {}

                    # 获取当前值和默认值（当前值可能已经从设置中注入）
                    current_value = getattr(config_instance, field_name)
                    default_value = getattr(field_obj, 'default', None)

                    fields.append(ParameterField(
                        name=field_name,
                        label=metadata.get('label', field_name),
                        widget=metadata.get('widget', 'text'),
                        help=metadata.get('help', ''),
                        group=group.key,
                        value=current_value,
                        default_value=default_value,
                        options=metadata.get('options'),
                        min_value=metadata.get('min'),
                        max_value=metadata.get('max'),
                        step=metadata.get('step'),
                        enable_if=metadata.get('enable_if')
                    ))

            model_spec = TrainingModelSpec(
                type_name=spec.type_name,
                title=spec.title,
                script_train=spec.script_train,
                script_cache_te=spec.script_cache_te,
                script_cache_latents=spec.script_cache_latents,
                network_module=spec.network_module,
                group_order=spec.group_order or [],
                path_mapping=spec.path_mapping or {},
                supported_dataset_types=spec.supported_dataset_types or []
            )

            return TrainingConfigSchema(
                groups=groups,
                fields=fields,
                model_spec=model_spec
            )

        except KeyError:
            raise ValueError(f"未知的训练类型: {training_type}")

    def preview_cli_command(self, request: CLIPreviewRequest) -> CLIPreviewResponse:
        """预览CLI命令（使用实际训练器逻辑）"""
        try:
            from ..core.training.trainers.musubi_trainer import MusubiTrainer
            from ..core.training.models import TrainingTask, TrainingState
            from datetime import datetime
            import uuid

            # 获取模型规范
            spec = get_model(request.training_type)
            config_cls = spec.config_cls

            # 创建配置实例
            config = config_cls()
            for key, value in request.config.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            from ..core.training.models import build_cli_args
            cli_args = build_cli_args(config)

            # 创建临时任务用于预览
            task = TrainingTask(
                id=str(uuid.uuid4())[:8] + "_preview",
                name="Preview Task",
                config=config,
                dataset_id=request.dataset_id,
                training_type=request.training_type,
                state=TrainingState.PENDING,
                created_at=datetime.now()
            )

            # 使用训练器生成预览命令和配置（预览模式）
            trainer = MusubiTrainer("preview", None)  # 预览模式使用临时task_id

            # 预览模式：生成TOML配置和CLI命令
            toml_path = trainer._create_dataset_config(task, preview_mode=True)

            # 使用预览模式的路径 (统一目录结构)
            training_dir = Path("workspace/tasks/preview")

            # 生成CLI命令（预览模式）
            cmd = trainer._build_training_command(task, toml_path, training_dir, preview_mode=True)
            flat_cmd = trainer._flatten_command(cmd)

            # 获取TOML内容（重新生成以获取内容）
            dataset_path = trainer._resolve_dataset_path(request.dataset_id, preview_mode=True)
            cache_dir = training_dir / "cache"
            datasets = [{
                "image_directory": trainer._rel_to_root_posix(dataset_path),
                "cache_directory": trainer._rel_to_root_posix(cache_dir)
            }]
            toml_dict = build_toml_dict(config, datasets)
            toml_content = dumps_toml(toml_dict)

            # 生成批处理脚本
            rel_to_root_from_script = "../../.."  # 假设在训练目录下
            musubi_src_rel = "runtime/engines/musubi-tuner/src"

            # 构建多行格式
            cmd_lines = []
            for i, arg in enumerate(flat_cmd):
                if i == 0:
                    cmd_lines.append(f"{arg} ^")
                elif i == len(flat_cmd) - 1:
                    cmd_lines.append(f"    {arg}")
                else:
                    cmd_lines.append(f"    {arg} ^")

            multi_line_cmd = "\n".join(cmd_lines)

            bat_content = f"""@echo off
cd /d "%~dp0{rel_to_root_from_script}"

set "PYTHONPATH={musubi_src_rel};%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"

{multi_line_cmd}

pause
"""

            return CLIPreviewResponse(
                command=" ".join(flat_cmd),
                script_path=f"runtime/engines/musubi-tuner/src/{spec.script_train}",
                args=flat_cmd[1:],  # 去掉脚本路径
                working_directory=str(trainer._PROJECT_ROOT),
                toml_content=toml_content,
                toml_path=toml_path,
                bat_script=bat_content
            )

        except KeyError as e:
            log_error(f"未知的训练类型: {request.training_type}")
            raise ValueError(f"未知的训练类型: {request.training_type}")
        except Exception as e:
            import traceback
            log_error(f"预览CLI命令失败: {e}")
            log_error(f"错误详情: {traceback.format_exc()}")
            raise ValueError(f"预览CLI命令失败: {e}")

    async def create_task(self, request: CreateTrainingTaskRequest) -> str:
        """创建训练任务"""
        with self._lock:
            try:
                # 验证数据集是否存在
                dataset = self._dataset_manager.get_dataset(request.dataset_id)
                if not dataset:
                    raise DatasetNotFoundError(request.dataset_id)

                # 获取训练模型配置类
                spec = get_model(request.training_type)
                config_cls = spec.config_cls

                # 创建配置实例
                config = config_cls()

                # 设置配置参数
                for key, value in request.config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

                # 创建训练任务
                task_id = await self._training_manager.create_task(
                    name=request.name,
                    dataset_id=request.dataset_id,
                    training_type=request.training_type,
                    config=config
                )

                # 注释：sample_prompts.txt 文件由 Trainer.build_artifacts() 统一生成，包含完整的采样参数
                # 不再在此处重复创建，避免覆盖 Trainer 生成的正确文件

                log_info(f"创建训练任务成功: {request.name} ({task_id})")
                return task_id

            except Exception as e:
                log_error(f"创建训练任务失败: {request.name}", e)
                raise

    def list_tasks(self) -> List[TrainingTaskBrief]:
        """获取训练任务列表"""
        tasks = self._training_manager.list_tasks()
        return [
            TrainingTaskBrief(
                id=task.id,
                name=task.name,
                dataset_id=task.dataset_id,
                training_type=task.training_type,
                state=task.state,
                progress=task.progress,
                current_step=task.current_step,
                total_steps=task.total_steps,
                current_epoch=task.current_epoch,
                total_epochs=getattr(task.config, 'max_train_epochs', 0) if hasattr(task, 'config') else 0,
                speed=task.speed,
                eta_seconds=task.eta_seconds,
                created_at=task.created_at or task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at
            )
            for task in tasks
        ]

    def get_task(self, task_id: str) -> Optional[TrainingTaskDetail]:
        """获取训练任务详情"""
        task = self._training_manager.get_task(task_id)
        if not task:
            return None

        # 尝试从TensorBoard获取最新进度（不管任务状态）
        try:
            tb_service = get_tb_event_service()
            tb_progress = tb_service.get_training_progress(task_id)

            # 用TensorBoard数据更新进度信息（如果有的话）
            if tb_progress:
                # 只有TensorBoard有数据时才更新，避免覆盖现有数据
                if tb_progress["current_epoch"] > 0:
                    task.current_epoch = tb_progress["current_epoch"]
                if tb_progress["total_epochs"] > 0:
                    task.total_epochs = tb_progress["total_epochs"]
                if tb_progress["current_step"] > 0:
                    task.current_step = tb_progress["current_step"]
                if tb_progress["total_steps"] > 0:
                    task.total_steps = tb_progress["total_steps"]
                if tb_progress["progress"] > 0:
                    task.progress = tb_progress["progress"]
                if tb_progress["loss"] is not None:
                    task.loss = tb_progress["loss"]
                if tb_progress["learning_rate"] is not None:
                    task.learning_rate = tb_progress["learning_rate"]

                log_info(f"从TensorBoard更新任务 {task_id} 进度: epoch {task.current_epoch}, step {task.current_step}, progress {task.progress:.2%}")
        except Exception as e:
            log_error(f"从TensorBoard获取任务 {task_id} 进度失败: {e}")
            # 失败时不影响原有逻辑，继续返回原始数据

        return TrainingTaskDetail(
            id=task.id,
            name=task.name,
            dataset_id=task.dataset_id,
            training_type=task.training_type,
            state=task.state,
            progress=task.progress,
            current_step=task.current_step,
            total_steps=task.total_steps,
            current_epoch=task.current_epoch,
            loss=task.loss,
            learning_rate=task.learning_rate,
            eta_seconds=task.eta_seconds,
            speed=task.speed,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            logs=task.logs,
            error_message=task.error_message,
            output_dir=task.output_dir,
            checkpoint_files=task.checkpoint_files,
            sample_images=task.sample_images,
            config=self._convert_config_to_dict(task.config)
        )

    async def start_task(self, task_id: str) -> Tuple[bool, str]:
        """开始训练任务"""
        try:
            success = await self._training_manager.start_task(task_id)
            if success:
                return True, "任务启动成功"
            else:
                return False, "任务启动失败"
        except Exception as e:
            log_error(f"启动训练任务异常: {e}")
            return False, f"任务启动失败: {str(e)}"

    async def stop_task(self, task_id: str) -> Tuple[bool, str]:
        """停止训练任务"""
        try:
            success = await self._training_manager.cancel_task(task_id)
            if success:
                return True, "任务停止成功"
            else:
                return False, "任务停止失败"
        except Exception as e:
            log_error(f"停止训练任务异常: {e}")
            return False, f"任务停止失败: {str(e)}"

    async def delete_task(self, task_id: str) -> Tuple[bool, str]:
        """删除训练任务"""
        try:
            success = await self._training_manager.delete_task(task_id)
            if success:
                return True, "删除训练任务成功"
            else:
                return False, "删除训练任务失败"
        except Exception as e:
            log_error(f"删除训练任务异常: {e}")
            return False, f"删除训练任务失败: {str(e)}"

    def get_training_stats(self) -> TrainingStats:
        """获取训练统计信息"""
        tasks = self._training_manager.list_tasks()

        total_tasks = len(tasks)
        running_tasks = len([t for t in tasks if t.state.value in ['running']])
        completed_tasks = len([t for t in tasks if t.state.value == 'completed'])
        failed_tasks = len([t for t in tasks if t.state.value == 'failed'])

        return TrainingStats(
            total_tasks=total_tasks,
            running_tasks=running_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks
        )

    def refresh_task_files(self, task_id: str) -> None:
        """刷新训练任务文件列表"""
        self._training_manager.refresh_task_files(task_id)

    def _create_sample_prompt_file(self, task_id: str, sample_prompt: str):
        """创建sample_prompt文件"""
        if not sample_prompt or not sample_prompt.strip():
            return None

        try:
            from pathlib import Path

            # 创建任务目录
            task_dir = Path(self.config.storage.workspace_root) / "tasks" / task_id
            task_dir.mkdir(parents=True, exist_ok=True)

            # 创建sample_prompts.txt文件
            prompt_file = task_dir / "sample_prompts.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(sample_prompt.strip())

            log_info(f"创建sample prompt文件: {prompt_file}")
            return prompt_file

        except Exception as e:
            log_error(f"创建sample prompt文件失败: {e}")
            return None

    def _convert_config_to_dict(self, config: Any) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        if hasattr(config, '__dict__'):
            return {k: v for k, v in config.__dict__.items() if not k.startswith('_')}
        return {}

    def list_sample_images(self, task_id: str) -> List[Dict[str, str]]:
        """获取训练任务的采样图片列表"""
        try:
            task_dir = Path(f"workspace/tasks/{task_id}")
            sample_dir = task_dir / "output" / "sample"

            if not sample_dir.exists():
                return []

            # 扫描采样图片
            sample_images = []
            for img_file in sample_dir.glob("*"):
                if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                    sample_images.append({
                        "filename": img_file.name,
                        "url": f"/api/v1/training/tasks/{task_id}/files/sample/{img_file.name}"
                    })

            # 按文件名排序
            sample_images.sort(key=lambda x: x["filename"])
            return sample_images

        except Exception as e:
            log_error(f"获取采样图片失败: {e}")
            return []

    def list_artifacts(self, task_id: str) -> List[Dict[str, str]]:
        """获取训练任务的模型文件列表"""
        try:
            task_dir = Path(f"workspace/tasks/{task_id}")
            output_dir = task_dir / "output"

            if not output_dir.exists():
                return []

            # 扫描模型文件
            artifacts = []
            for model_file in output_dir.glob("*.safetensors"):
                if model_file.is_file():
                    artifacts.append({
                        "filename": model_file.name,
                        "url": f"/api/v1/training/tasks/{task_id}/files/output/{model_file.name}"
                    })

            # 按文件名排序
            artifacts.sort(key=lambda x: x["filename"])
            return artifacts

        except Exception as e:
            log_error(f"获取模型文件失败: {e}")
            return []


# 全局服务实例
_training_service_instance = None
_lock = threading.Lock()

def get_training_service() -> TrainingService:
    """获取训练服务实例"""
    global _training_service_instance
    if _training_service_instance is None:
        with _lock:
            if _training_service_instance is None:
                _training_service_instance = TrainingService()
    return _training_service_instance
