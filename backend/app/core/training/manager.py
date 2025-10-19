"""
新的训练管理器 - 基于事件驱动和状态管理器的重构版本
"""

import asyncio
import json
import threading
import time
import uuid
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import BaseTrainingConfig, TrainingTask
from ..state.models import TrainingState
from ..state.manager import TrainingStateManager
from ..state.events import EventBus
from ...utils.logger import log_info, log_error, log_success
from ...core.exceptions import TrainingError, TrainingNotFoundError
from ..config import get_config
from ..dataset.utils import gen_short_id, safeify_name


class TrainingManager:
    """新的训练管理器 - 专注任务生命周期管理，使用统一状态管理"""

    def __init__(self, state_manager: TrainingStateManager, event_bus: EventBus, main_loop: asyncio.AbstractEventLoop):
        logger = logging.getLogger(__name__)
        self.config = get_config()
        self._state_manager = state_manager
        self._event_bus = event_bus
        self._main_loop = main_loop
        self._tasks: Dict[str, TrainingTask] = {}
        self._trainers: Dict[str, Any] = {}  # task_id -> trainer instance
        self._lock = threading.Lock()

        # ——工作区解析与就绪检查（不落到 CWD，不自动创建）——
        self._workspace_ready: bool = False
        raw = getattr(self.config.storage, "workspace_root", "") or ""
        ws = Path(raw).expanduser()
        try:
            ws = ws.resolve(strict=False)  # 允许不存在
        except Exception:
            logger.exception("解析 workspace_root 失败：%r", raw)
            self.workspace_root = ws
            self.tasks_dir = ws / "tasks"
            self._workspace_ready = False
        else:
            self.workspace_root = ws
            self.tasks_dir = ws / "tasks"
            if ws.exists():
                try:
                    self.tasks_dir.mkdir(parents=True, exist_ok=True)
                    self._workspace_ready = True
                except Exception:
                    logger.exception("创建 tasks 目录失败：%s", self.tasks_dir)
                    self._workspace_ready = False

        # 订阅状态事件以同步任务对象
        self._event_bus.subscribe('state.transitioned', self._sync_task_state)

        # 加载现有任务
        self.load_tasks()

    async def _await_on_main_loop(self, coro_factory):
        """安全地在主事件循环上执行协程：
        - 若当前就在主事件循环，直接 await；
        - 否则使用 run_coroutine_threadsafe 并等待结果。
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop and current_loop is self._main_loop:
            return await coro_factory()
        fut = asyncio.run_coroutine_threadsafe(coro_factory(), self._main_loop)
        return fut.result()

    async def create_task(self, name: str, dataset_id: str, training_type: str, config: BaseTrainingConfig) -> str:
        """创建训练任务"""
        try:
            # 在锁内检查就绪状态并快照目录，避免并发切换
            with self._lock:
                if not self._workspace_ready:
                    raise TrainingError("工作区未就绪，请先在系统设置中选择工作区")
                tasks_dir = self.tasks_dir

            # 生成短ID（固定8位）
            task_id = gen_short_id(k=8)

            # 生成安全任务名称
            safe_task_name = safeify_name(name)

            # 生成目录名（带去重）
            base_dirname = f"{task_id}--{safe_task_name}"
            final_dirname = base_dirname
            counter = 2
            while (tasks_dir / final_dirname).exists():
                safe_name_with_counter = safeify_name(f"{name} {counter}")
                final_dirname = f"{task_id}--{safe_name_with_counter}"
                counter += 1

            # 使用最终目录名创建路径
            task_dir = tasks_dir / final_dirname

            # 创建任务对象（task_id 保持为短ID）
            task = TrainingTask(
                id=task_id,
                name=name,
                config=config,
                state=TrainingState.PENDING,
                created_at=datetime.now(),
                progress=0.0,
                logs=[]
            )

            # 设置额外属性
            task.dataset_id = dataset_id
            task.training_type = training_type

            # 预估总步数，避免创建后显示 0/0 导致进度条异常
            try:
                total_steps = self._estimate_total_steps(dataset_id, config)
                if total_steps > 0:
                    task.total_steps = total_steps
                    task.current_step = 0
                    task.progress = 0.0
            except Exception as e:
                log_error(f"预估总步数失败（不影响创建）: {e}")

            # 创建任务目录结构
            self._create_task_directory_structure(task_dir)

            # 生成训练工件
            await self._generate_training_artifacts(task)

            # 保存任务
            with self._lock:
                self._tasks[task_id] = task
            self._save_task_to_file(task)

            # 初始化状态管理器中的状态
            await self._state_manager.transition_state(
                task_id, TrainingState.PENDING, f"create_{task_id}"
            )

            log_info(f"创建训练任务成功: {name} (ID: {task_id})")
            return task_id

        except Exception as e:
            log_error(f"创建训练任务失败: {e}")
            raise TrainingError(f"创建训练任务失败: {e}")

    def _estimate_total_steps(self, dataset_id: str, config: BaseTrainingConfig) -> int:
        """根据数据集规模与配置预估总步数。
        公式：
          steps_per_epoch = ceil( (num_items * repeats) / (batch_size * grad_acc) )
          total_steps     = steps_per_epoch * max_train_epochs
        任一参数缺失或无效则返回 0。
        """
        try:
            # 动态导入以避免启动阶段循环依赖
            from ..dataset.manager import DatasetManager
            dm = DatasetManager()
            ds = dm.get_dataset(dataset_id)
            if not ds:
                return 0
            num_items = int(getattr(ds, 'get_item_count', lambda: 0)() or 0)

            epochs = int(getattr(config, 'max_train_epochs', 0) or 0)
            batch_size = int(getattr(config, 'batch_size', 0) or 0)
            grad_acc = int(getattr(config, 'gradient_accumulation_steps', 1) or 1)
            repeats = int(getattr(config, 'repeats', 1) or 1)

            if num_items <= 0 or epochs <= 0 or batch_size <= 0 or grad_acc <= 0 or repeats <= 0:
                return 0

            import math
            eff_batch = batch_size * grad_acc
            steps_per_epoch = math.ceil((num_items * repeats) / eff_batch)
            total_steps = steps_per_epoch * epochs
            return int(total_steps)
        except Exception as e:
            log_error(f"估算总步数异常: {e}")
            return 0

    async def start_task(self, task_id: str) -> bool:
        """启动训练任务"""
        try:
            # 运行前检查就绪
            with self._lock:
                if not self._workspace_ready:
                    log_error("工作区未就绪，无法启动训练")
                    return False
                if not self._is_runtime_ready():
                    log_error("运行时未就绪（缺少 runtime/python），无法启动训练")
                    return False
            task = self.get_task(task_id)
            if not task:
                raise TrainingNotFoundError(f"任务不存在: {task_id}")

            # 检查当前状态
            snapshot = await self._state_manager.get_state(task_id)
            if not snapshot:
                log_error(f"任务状态不存在: {task_id}")
                return False

            log_info(f"准备启动任务 {task_id}，当前状态: {snapshot.state}")

            # 只有特定状态才能启动
            if snapshot.state not in [TrainingState.PENDING, TrainingState.FAILED, TrainingState.CANCELLED]:
                log_error(f"任务状态不允许启动: {snapshot.state}")
                return False

            log_info(f"任务状态检查通过，允许启动: {snapshot.state}")

            # 直接转换到运行状态
            cause_id = f"start_{task_id}_{time.time()}"
            success = await self._state_manager.transition_state(
                task_id, TrainingState.RUNNING, cause_id,
                metadata={'initiated_by': 'user'}
            )

            if not success:
                return False

            # RUNNING 切换成功后：清空内存日志与文件日志，通知前端清屏
            try:
                # 1) 清空内存日志（WS 历史回放的来源）
                with self._lock:
                    if hasattr(task, 'logs') and isinstance(task.logs, list):
                        task.logs.clear()
                        # 同步保存到文件（保持任务文件一致）
                        self._save_task_to_file(task)
                # 2) 截断 train.log（保持与 tail 兼容，截断而非删除）
                try:
                    task_dir = self._find_task_dir(task_id)
                    if task_dir:
                        log_file = task_dir / "train.log"
                        with open(log_file, 'w', encoding='utf-8') as f:
                            f.write("")
                except Exception as e:
                    log_error(f"清空 train.log 失败: {e}")
                # 2.5) 通知前端清屏（兼容前端监听的 training_task_restart 事件）
                try:
                    self._event_bus.emit_threadsafe('training_task_restart', {
                        'task_id': task_id,
                        'reason': 'user_restart'
                    })
                except Exception as e:
                    log_error(f"发送清屏事件失败: {e}")
            except Exception as e:
                log_error(f"启动前清理失败: {e}")

            # 使用独立线程启动训练（避免阻塞事件循环）
            def run_training_in_thread():
                # 创建新的事件循环用于异步调用
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._run_training_async(task_id))
                except Exception as e:
                    # 回滚状态 + 写一行错误日志，避免“假活”
                    try:
                        loop.run_until_complete(
                            self._state_manager.transition_state(
                                task_id, TrainingState.FAILED, f"trainer_start_failed_{task_id}",
                                metadata={'error': str(e)}
                            )
                        )
                    except Exception:
                        pass
                    try:
                        with self._lock:
                            task_local = self._tasks.get(task_id)
                            if task_local and hasattr(task_local, 'logs') and isinstance(task_local.logs, list):
                                task_local.logs.append(f"[ERROR] start failed: {e}")
                                self._save_task_to_file(task_local)
                    except Exception:
                        pass
                    log_error(f"训练线程异常: {e}")
                finally:
                    try:
                        loop.close()
                    except Exception:
                        pass

            training_thread = threading.Thread(target=run_training_in_thread, daemon=True)
            training_thread.start()

            log_info(f"启动训练任务: {task.name}")
            return True

        except Exception as e:
            log_error(f"启动训练任务失败: {e}")
            return False

    def update_workspace(self, new_root: str | Path) -> bool:
        """切换工作区路径（线程安全）。返回是否就绪。
        策略：锁内切换路径与清空索引，并标记未就绪；锁外加载任务；成功后再置为就绪。
        """
        logger = logging.getLogger(__name__)
        with self._lock:
            try:
                root = Path(new_root).expanduser().resolve(strict=False)
                self.workspace_root = root
                self.tasks_dir = root / "tasks"
                # 切换期间标记未就绪并清空索引，避免半状态
                self._workspace_ready = False
                self._tasks.clear()
                if not root.exists():
                    logger.info("工作区不存在，标记未就绪：%s", root)
                    return False
                try:
                    self.tasks_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    logger.exception("创建 tasks 目录失败：%s", self.tasks_dir)
                    return False
            except Exception:
                logger.exception("更新训练管理器工作区失败")
                return False

        # 在锁外执行潜在的耗时扫描
        try:
            self.load_tasks()
            with self._lock:
                self._workspace_ready = True
            logger.info("工作区已更新：%s（ready=True，tasks=%d）", self.workspace_root, len(self._tasks))
            return True
        except Exception:
            logger.exception("切换工作区后加载任务失败")
            # 保持未就绪
            return False

    def _is_runtime_ready(self) -> bool:
        """检查运行时环境是否就绪（使用环境管理器的统一检测）"""
        try:
            from ..environment import get_paths
            paths = get_paths()
            return paths.runtime_python_exists
        except Exception as e:
            log_error(f"检查运行时就绪状态失败: {e}")
            return False

    async def cancel_task(self, task_id: str) -> bool:
        """取消训练任务"""
        try:
            # 检查当前状态
            snapshot = await self._state_manager.get_state(task_id)
            if not snapshot:
                return False

            # 幂等：若任务已非活跃，则视为已取消成功
            if not snapshot.state.is_active():
                log_info(f"取消幂等：任务 {task_id} 已处于非活跃状态 {snapshot.state}")
                return True

            # 异步取消：立即返回，取消完成后通过回调更新状态
            if task_id in self._trainers:
                trainer = self._trainers[task_id]
                if hasattr(trainer, 'cancel_training'):
                    def cancel_in_background():
                        try:
                            log_info(f"开始取消训练任务: {task_id}")
                            trainer.cancel_training()
                            log_info(f"训练任务取消完成: {task_id}")

                            # 取消完成后，原子性条件转换 —— 投递到主事件循环
                            async def _finalize():
                                ok, prev = await self._state_manager.transition_if_current_in(
                                    task_id,
                                    {TrainingState.RUNNING, TrainingState.PENDING},
                                    TrainingState.CANCELLED,
                                    f"cancel_completed_{task_id}",
                                    {'initiated_by': 'user', 'completed': True}
                                )
                                if not ok:
                                    log_info(f"跳过取消：当前状态 {prev}")

                            # 投递到主事件循环
                            fut = asyncio.run_coroutine_threadsafe(_finalize(), self._main_loop)
                            try:
                                fut.result()  # 等待完成，便于发现异常
                            except Exception as e:
                                log_error(f"finalize cancel failed: {e}")

                        except Exception as e:
                            log_error(f"取消训练器失败: {e}")

                            # 取消失败，原子性条件转换为失败状态
                            async def _finalize_failed():
                                ok, prev = await self._state_manager.transition_if_current_in(
                                    task_id,
                                    {TrainingState.RUNNING, TrainingState.PENDING},
                                    TrainingState.FAILED,
                                    f"cancel_failed_{task_id}",
                                    {'initiated_by': 'user', 'error': str(e)}
                                )
                                if not ok:
                                    log_info(f"跳过取消失败转换：当前状态 {prev}")

                            # 投递到主事件循环
                            fut = asyncio.run_coroutine_threadsafe(_finalize_failed(), self._main_loop)
                            try:
                                fut.result()
                            except Exception as e2:
                                log_error(f"finalize cancel failed transition failed: {e2}")

                    threading.Thread(target=cancel_in_background, daemon=True).start()

            else:
                # 无训练器实例：可能是进程已不受管（如服务重启）。为避免卡住，直接将状态置为 CANCELLED。
                async def _finalize_no_trainer():
                    return await self._state_manager.transition_if_current_in(
                        task_id,
                        {TrainingState.RUNNING, TrainingState.PENDING},
                        TrainingState.CANCELLED,
                        f"cancel_no_trainer_{task_id}",
                        {'initiated_by': 'user', 'reason': 'no_trainer_instance'}
                    )

                # 同环 await，异环 thread-safe（统一封装）
                ok, prev = await self._await_on_main_loop(_finalize_no_trainer)

                if ok:
                    log_info(f"取消(无训练器)成功：任务 {task_id}，从 {prev} -> cancelled")
                else:
                    log_info(f"取消(无训练器)幂等：任务 {task_id}，当前状态 {prev} 无需变更")

            # 立即返回，不等待取消完成（已处理状态转换）
            log_info(f"取消训练任务: {task_id}")
            return True

        except Exception as e:
            log_error(f"取消训练任务失败: {e}")
            return False

    async def delete_task(self, task_id: str) -> bool:
        """删除训练任务"""
        try:
            # 检查状态，不能删除活跃任务（但对僵尸任务做兜底）
            snapshot = await self._state_manager.get_state(task_id)
            if snapshot and snapshot.state.is_active():
                # 若无训练器实例，视为僵尸任务：先置为 CANCELLED，再继续删除
                if task_id not in self._trainers:
                    log_info(f"删除任务 {task_id}：活跃但无训练器，判定僵尸任务，先取消再删除")

                    async def _finalize_cancel_before_delete():
                        return await self._state_manager.transition_if_current_in(
                            task_id,
                            {TrainingState.RUNNING, TrainingState.PENDING},
                            TrainingState.CANCELLED,
                            f"force_cancel_before_delete_{task_id}",
                            {'reason': 'zombie_active_state_no_trainer'}
                        )

                    try:
                        ok, prev = await self._await_on_main_loop(_finalize_cancel_before_delete)
                        if ok:
                            log_info(f"删除前取消成功：任务 {task_id}，从 {prev} -> cancelled")
                        else:
                            log_info(f"删除前取消幂等：任务 {task_id}，当前状态 {prev} 无需变更")
                    except Exception as e:
                        log_error(f"删除前取消失败: {e}")
                else:
                    log_error("不能删除正在运行的任务")
                    return False

            # 删除任务目录
            task_dir = self._find_task_dir(task_id)
            if task_dir and task_dir.exists():
                import shutil
                shutil.rmtree(task_dir)

            # 从内存中删除
            with self._lock:
                self._tasks.pop(task_id, None)

            # 清理状态管理器
            await self._state_manager.cleanup_task(task_id)

            log_info(f"删除训练任务: {task_id}")
            return True

        except Exception as e:
            log_error(f"删除训练任务失败: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[TrainingTask]:
        """获取训练任务"""
        # 首先从内存中查找
        task = self._tasks.get(task_id)
        if task:
            # 对于非训练状态的任务，从train.log文件刷新历史日志
            if task.state != TrainingState.RUNNING:
                self._load_historical_logs(task)
            return task

        # 如果内存中没有，尝试从文件系统加载
        log_info(f"任务 {task_id} 不在内存中，尝试从文件系统加载")

        # 使用 _find_task_dir 查找任务目录
        task_dir = self._find_task_dir(task_id)
        if not task_dir:
            log_error(f"任务目录不存在: {task_id}")
            return None

        task_file = task_dir / "task.json"
        if not task_file.exists():
            log_error(f"任务文件不存在: {task_file}")
            return None

        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)

            # 重建任务对象
            task = self._rebuild_task_from_data(task_data)
            if task:
                # 若文件标记为运行中，但内存中无训练器实例，视为异常恢复：立即标记为失败
                if task.state == TrainingState.RUNNING and task_id not in self._trainers:
                    with self._lock:
                        task.state = TrainingState.FAILED
                        task.completed_at = datetime.now()
                    self._save_task_to_file(task)
                    async def _to_failed():
                        await self._state_manager.transition_state(
                            task_id, TrainingState.FAILED, f"recover_no_trainer_{task_id}",
                            metadata={'reason': 'recovered_on_demand', 'prev_state': 'running'}
                        )
                    try:
                        fut = asyncio.run_coroutine_threadsafe(_to_failed(), self._main_loop)
                        fut.result()
                    except Exception as e:
                        log_error(f"恢复时转换失败: {e}")

                # 从train.log文件读取历史日志（如果存在）
                self._load_historical_logs(task)

                # 缓存到内存中
                self._tasks[task.id] = task
                # 异步确保状态存在
                import asyncio
                try:
                    asyncio.create_task(self._ensure_state_exists(task))
                except RuntimeError:
                    pass
                log_info(f"成功从文件系统加载任务: {task_id}")
                return task
            else:
                log_error(f"重建任务对象失败: {task_id}")
                return None

        except Exception as e:
            log_error(f"从文件系统加载任务失败 {task_id}: {e}")
            return None

    def list_tasks(self) -> List[TrainingTask]:
        """列出所有训练任务"""
        return list(self._tasks.values())

    def save_task(self, task: TrainingTask) -> None:
        """保存训练任务"""
        try:
            self._save_task_to_file(task)
        except Exception as e:
            log_error(f"保存训练任务失败: {e}")

    async def _reconcile_task_process(self, task_id: str) -> None:
        """对齐历史任务的进程状态：运行中但无训练器 -> 失败。
        仅用于应用启动后的历史任务清理，避免 WS/状态误判。
        """
        try:
            task = self._tasks.get(task_id)
            if not task:
                return
            if task.state != TrainingState.RUNNING:
                return
            if task_id not in self._trainers:
                with self._lock:
                    task.state = TrainingState.FAILED
                    task.completed_at = datetime.now()
                self._save_task_to_file(task)
                await self._state_manager.transition_state(
                    task_id, TrainingState.FAILED, f"recover_on_start_{task_id}",
                    metadata={'reason': 'recovered_on_startup', 'prev_state': 'running'}
                )
                log_info(f"历史运行中任务已标记为失败并对齐: {task_id}")
        except Exception as e:
            log_error(f"启动对齐历史任务失败 {task_id}: {e}")

    def load_task_for_editing(self, task_id: str) -> Dict[str, Any]:
        """载入任务配置到UI界面进行编辑"""
        try:
            task_dir = self._find_task_dir(task_id)
            if not task_dir:
                raise TrainingNotFoundError(f"任务不存在: {task_id}")

            task_file = task_dir / "task.json"
            if not task_file.exists():
                raise TrainingNotFoundError(f"任务不存在: {task_id}")

            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)

            # 检查是否可编辑
            if not task_data.get('editable', True):
                raise TrainingError(f"任务正在运行中，无法编辑: {task_id}")

            return task_data

        except Exception as e:
            log_error(f"加载任务配置失败: {e}")
            raise TrainingError(f"加载任务配置失败: {e}")

    async def update_task_config(self, task_id: str, new_config: BaseTrainingConfig) -> bool:
        """更新任务配置并重新生成所有文件"""
        try:
            task = self.get_task(task_id)
            if not task:
                raise TrainingNotFoundError(f"任务不存在: {task_id}")

            # 检查任务状态
            snapshot = await self._state_manager.get_state(task_id)
            if snapshot and snapshot.state.is_active():
                raise TrainingError("任务正在运行中，无法更新配置")

            # 更新配置
            with self._lock:
                task.config = new_config

            # 重新生成训练工件
            await self._generate_training_artifacts(task)

            # 保存任务
            self._save_task_to_file(task)

            log_info(f"更新任务配置成功: {task_id}")
            return True

        except Exception as e:
            log_error(f"更新任务配置失败: {e}")
            raise TrainingError(f"更新任务配置失败: {e}")

    async def duplicate_task(self, source_task_id: str, new_name: str) -> str:
        """复制任务"""
        try:
            source_task = self.get_task(source_task_id)
            if not source_task:
                raise TrainingNotFoundError(f"源任务不存在: {source_task_id}")

            # 创建新任务
            new_task_id = await self.create_task(
                name=new_name,
                dataset_id=source_task.dataset_id,
                training_type=source_task.training_type,
                config=source_task.config
            )

            log_info(f"复制任务成功: {source_task_id} -> {new_task_id}")
            return new_task_id

        except Exception as e:
            log_error(f"复制任务失败: {e}")
            raise TrainingError(f"复制任务失败: {e}")

    async def regenerate_task_files(self, task_id: str) -> bool:
        """重新生成任务文件"""
        try:
            task = self.get_task(task_id)
            if not task:
                raise TrainingNotFoundError(f"任务不存在: {task_id}")

            # 检查任务状态
            snapshot = await self._state_manager.get_state(task_id)
            if snapshot and snapshot.state.is_active():
                raise TrainingError("任务正在运行中，无法重新生成文件")

            # 重新生成工件
            await self._generate_training_artifacts(task)

            # 保存任务
            self._save_task_to_file(task)

            log_info(f"重新生成任务文件成功: {task_id}")
            return True

        except Exception as e:
            log_error(f"重新生成任务文件失败: {e}")
            return False

    def refresh_task_files(self, task_id: str) -> None:
        """刷新任务文件信息"""
        try:
            task = self.get_task(task_id)
            if task:
                self._scan_output_files(task)

        except Exception as e:
            log_error(f"刷新任务文件失败: {e}")

    def _scan_output_files(self, task: TrainingTask) -> None:
        """扫描输出文件"""
        try:
            task_dir = self._find_task_dir(task.id)
            if not task_dir:
                log_error(f"任务目录不存在: {task.id}")
                return

            output_dir = task_dir / "output"

            # 重置文件列表
            task.checkpoint_files = []
            task.sample_images = []

            if output_dir.exists():
                # 扫描checkpoint文件
                for file_path in output_dir.rglob("*.safetensors"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(task_dir).as_posix()
                        task.checkpoint_files.append(rel_path)

                # 扫描样本图片
                for file_path in output_dir.rglob("*.png"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(task_dir).as_posix()
                        task.sample_images.append(rel_path)

        except Exception as e:
            log_error(f"扫描输出文件失败: {e}")

    # -------------------------
    # 样例/产物列表（对外提供）
    # -------------------------
    def list_task_samples(self, task_id: str) -> list[dict]:
        """返回样例图片列表，每项包含 filename 与相对路径 rel_path。

        优先读取 Task.sample_images；若为空，则按约定扫描 task_id/output/sample 下常见图片格式。
        rel_path 均以任务目录为基准（如 output/sample/xxx.png）。
        """
        from pathlib import Path as _P
        with self._lock:
            task = self._tasks.get(task_id)
        if not task:
            raise TrainingNotFoundError(
                message=f"任务不存在: {task_id}",
                detail={"task_id": task_id},
                error_code="TRAINING_NOT_FOUND",
            )

        rel_list: list[str] = list(getattr(task, 'sample_images', []) or [])
        # 兼容历史数据中的反斜杠路径
        rel_list = [rp.replace('\\', '/') for rp in rel_list]
        items: list[dict] = []

        if not rel_list:
            try:
                task_dir = self._find_task_dir(task.id)
                if not task_dir:
                    return items

                sample_dir = task_dir / 'output' / 'sample'
                if sample_dir.exists():
                    for img_file in sample_dir.iterdir():
                        if img_file.is_file() and img_file.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                            rel_path = img_file.relative_to(task_dir).as_posix()
                            rel_list.append(rel_path)
                rel_list.sort()
                with self._lock:
                    task.sample_images = rel_list
            except Exception as e:
                log_error(f"扫描样例图片失败: {e}")

        for rel_path in rel_list:
            filename = _P(rel_path).name
            items.append({"filename": filename, "rel_path": rel_path})
        return items

    def list_task_artifacts(self, task_id: str) -> list[dict]:
        """返回产物权重列表，每项包含 filename 与相对路径 rel_path。

        优先读取 Task.checkpoint_files；若为空，则扫描 task_id/output 下 *.safetensors。
        rel_path 以任务目录为基准（如 output/xxx.safetensors）。
        """
        from pathlib import Path as _P
        with self._lock:
            task = self._tasks.get(task_id)
        if not task:
            raise TrainingNotFoundError(
                message=f"任务不存在: {task_id}",
                detail={"task_id": task_id},
                error_code="TRAINING_NOT_FOUND",
            )

        rel_list: list[str] = list(getattr(task, 'checkpoint_files', []) or [])
        rel_list = [rp.replace('\\', '/') for rp in rel_list]
        items: list[dict] = []

        if not rel_list:
            try:
                task_dir = self._find_task_dir(task.id)
                if not task_dir:
                    return items

                output_dir = task_dir / 'output'
                if output_dir.exists():
                    for model_file in output_dir.rglob('*.safetensors'):
                        if model_file.is_file():
                            rel_path = model_file.relative_to(task_dir).as_posix()
                            rel_list.append(rel_path)
                rel_list.sort()
                with self._lock:
                    task.checkpoint_files = rel_list
            except Exception as e:
                log_error(f"扫描模型产物失败: {e}")

        for rel_path in rel_list:
            filename = _P(rel_path).name
            items.append({"filename": filename, "rel_path": rel_path})
        return items

    async def _run_training_async(self, task_id: str):
        """异步运行训练"""
        try:
            task = self.get_task(task_id)
            if not task:
                return

            # 转换到运行状态
            await self._state_manager.transition_state(
                task_id, TrainingState.RUNNING, f"trainer_start_{task_id}"
            )

            # 创建并启动训练器
            from .trainers.musubi_trainer import MusubiTrainer
            trainer = MusubiTrainer(task_id, self._event_bus)
            self._trainers[task_id] = trainer

            # 缓存阶段日志也通过WS推送：定义log回调，线程安全投递到主loop
            def _log_callback(message: str):
                try:
                    self._event_bus.emit_threadsafe('training.log', {
                        'task_id': task_id,
                        'message': message,
                        'level': 'info',
                        'timestamp': time.time()
                    })
                except Exception as e:
                    log_error(f"缓存日志回调失败: {e}")

            # 执行训练（同步调用，不需要await）——传入log回调以便缓存阶段行级推送
            success = trainer.run_training(task, log_callback=_log_callback)

            # 根据结果转换最终状态
            # 检查是否被取消（通过trainer的_cancelled标志）
            if hasattr(trainer, '_cancelled') and trainer._cancelled:
                final_state = TrainingState.CANCELLED
            else:
                final_state = TrainingState.COMPLETED if success else TrainingState.FAILED

            await self._state_manager.transition_state(
                task_id, final_state, f"trainer_end_{task_id}",
                metadata={'success': success, 'cancelled': trainer._cancelled if hasattr(trainer, '_cancelled') else False}
            )

        except Exception as e:
            log_error(f"训练执行异常: {e}")
            await self._state_manager.transition_state(
                task_id, TrainingState.FAILED, f"trainer_error_{task_id}",
                metadata={'error': str(e)}
            )
        finally:
            # 清理训练器
            self._trainers.pop(task_id, None)

    async def _sync_task_state(self, payload: Dict[str, Any]):
        """同步任务状态（响应状态管理器事件）"""
        transition = payload['transition']
        snapshot = payload['snapshot']
        task_id = transition.task_id

        task = self.get_task(task_id)
        if task:
            # 更新任务对象的状态
            with self._lock:
                task.state = snapshot.state
                if transition.is_restart():
                    # 重启时重置进度相关信息
                    task.progress = 0.0
                    task.current_step = 0
                    task.current_epoch = 0
                    task.loss = 0.0
                    task.logs = []
                    task.error_message = ""

                # 更新时间戳
                if snapshot.state == TrainingState.RUNNING and not task.started_at:
                    task.started_at = datetime.now()
                elif snapshot.state.is_terminal() and not task.completed_at:
                    task.completed_at = datetime.now()

            # 保存到文件
            self._save_task_to_file(task)

    def _create_task_directory_structure(self, task_dir: Path):
        """创建任务目录结构"""
        dirs = [
            task_dir,
            task_dir / "cache",
            task_dir / "output",
            task_dir / "samples",
            task_dir / "logs"
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    async def _generate_training_artifacts(self, task: TrainingTask):
        """生成训练工件"""
        try:
            # 使用训练器生成工件
            from .trainers.musubi_trainer import MusubiTrainer
            trainer = MusubiTrainer(task.id, self._event_bus)
            scripts_info = trainer.build_artifacts(task, force=True)
            task.scripts_info = scripts_info

        except Exception as e:
            log_error(f"生成训练工件失败: {e}")
            raise

    def _save_task_to_file(self, task: TrainingTask):
        """保存任务到文件"""
        try:
            from dataclasses import asdict

            task_dir = self._find_task_dir(task.id)
            if not task_dir:
                log_error(f"保存任务失败：任务目录不存在: {task.id}")
                return

            task_file = task_dir / "task.json"

            # 获取当前状态信息
            snapshot = None
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果在异步上下文中，创建task获取状态
                    future = asyncio.ensure_future(self._state_manager.get_state(task.id))
                    # 注意：这里不能await，因为我们在同步函数中
                    # 实际应用中可能需要重构为异步
                    pass
            except:
                pass

            task_data = {
                'id': task.id,
                'name': task.name,
                'dataset_id': getattr(task, 'dataset_id', ''),
                'training_type': getattr(task, 'training_type', ''),
                'config': asdict(task.config),
                'config_class': task.config.__class__.__name__,
                'state': task.state.value if hasattr(task.state, 'value') else str(task.state),
                'progress': task.progress,
                'current_step': task.current_step,
                'total_steps': task.total_steps,
                'current_epoch': task.current_epoch,
                'loss': task.loss,
                'learning_rate': task.learning_rate,
                'eta_seconds': task.eta_seconds,
                'speed': task.speed,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'updated_at': datetime.now().isoformat(),
                'logs': task.logs,
                'error_message': task.error_message,
                'output_dir': getattr(task, 'output_dir', ''),
                'checkpoint_files': getattr(task, 'checkpoint_files', []),
                'sample_images': getattr(task, 'sample_images', []),
                'scripts_info': getattr(task, 'scripts_info', None),
                'editable': not task.state.is_active(),
                'version': '2.0'  # 新版本标识
            }

            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            log_error(f"保存任务文件失败: {e}")

    def load_tasks(self):
        """加载现有任务"""
        try:
            for task_dir in self.tasks_dir.iterdir():
                if not task_dir.is_dir():
                    continue

                # 解析目录名提取 task_id
                task_id = self._parse_task_id_from_dirname(task_dir.name)
                if not task_id:
                    log_error(f"无法解析任务ID，跳过目录: {task_dir.name}")
                    continue

                task_file = task_dir / "task.json"
                if not task_file.exists():
                    continue

                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)

                    # 重建任务对象
                    task = self._rebuild_task_from_data(task_data)
                    if task:
                        self._tasks[task.id] = task

                        # 先做进程一致性对齐：若文件为 running 但无训练器，先同步标记为 failed
                        if task.state == TrainingState.RUNNING and task.id not in self._trainers:
                            with self._lock:
                                task.state = TrainingState.FAILED
                                task.completed_at = datetime.now()
                            self._save_task_to_file(task)
                            async def _to_failed_startup():
                                await self._state_manager.transition_state(
                                    task.id, TrainingState.FAILED, f"recover_on_start_{task.id}",
                                    metadata={'reason': 'recovered_on_startup', 'prev_state': 'running'}
                                )
                            try:
                                asyncio.create_task(_to_failed_startup())
                            except RuntimeError:
                                pass

                        # 然后保证状态管理器中存在对应状态
                        asyncio.create_task(self._ensure_state_exists(task))

                except Exception as e:
                    log_error(f"加载任务文件失败 {task_file}: {e}")
                    continue

            log_info(f"加载了 {len(self._tasks)} 个训练任务")

        except Exception as e:
            log_error(f"加载训练任务失败: {e}")

    def _rebuild_task_from_data(self, task_data: dict) -> Optional[TrainingTask]:
        """从数据重建任务对象"""
        try:
            # 重建配置对象
            config_class_name = task_data.get("config_class", "QwenImageConfig")
            config_data = task_data.get("config", {})

            try:
                from .models import get_model
                training_type = task_data.get("training_type", "qwen_image_lora")
                spec = get_model(training_type)
                config_cls = spec.config_cls
                config = config_cls(**config_data)
            except Exception as e:
                log_error(f"重建配置失败: {e}")
                from .models import QwenImageConfig
                config = QwenImageConfig(**config_data)

            # 重建任务对象
            task = TrainingTask(
                id=task_data["id"],
                name=task_data["name"],
                config=config,
                dataset_id=task_data.get("dataset_id", ""),
                training_type=task_data.get("training_type", "qwen_image_lora"),
                state=self._safe_parse_state(task_data.get("state", "pending")),
                progress=task_data.get("progress", 0.0),
                current_step=task_data.get("current_step", 0),
                total_steps=task_data.get("total_steps", 0),
                current_epoch=task_data.get("current_epoch", 0),
                loss=task_data.get("loss", 0.0),
                learning_rate=task_data.get("learning_rate", 0.0),
                eta_seconds=task_data.get("eta_seconds"),
                speed=task_data.get("speed"),
                speed_unit=task_data.get("speed_unit", "it/s"),
                created_at=datetime.fromisoformat(task_data["created_at"]) if task_data.get("created_at") else None,
                started_at=datetime.fromisoformat(task_data["started_at"]) if task_data.get("started_at") else None,
                completed_at=datetime.fromisoformat(task_data["completed_at"]) if task_data.get("completed_at") else None,
                logs=task_data.get("logs", []),
                error_message=task_data.get("error_message", ""),
                output_dir=task_data.get("output_dir", ""),
                checkpoint_files=task_data.get("checkpoint_files", []),
                sample_images=task_data.get("sample_images", []),
            )

            # 加载scripts_info
            task.scripts_info = task_data.get("scripts_info")

            return task

        except Exception as e:
            log_error(f"重建任务对象失败: {e}")
            return None

    def _load_historical_logs(self, task: TrainingTask):
        """从train.log文件读取历史日志"""
        try:
            task_dir = self._find_task_dir(task.id)
            if not task_dir:
                return

            log_file = task_dir / "train.log"

            if not log_file.exists():
                # 如果没有日志文件，保持任务对象中现有的日志（可能来自JSON）
                if task.logs:
                    log_info(f"train.log不存在，使用任务对象中的 {len(task.logs)} 条日志: {task.id}")
                return

            # 读取日志文件
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_lines = f.readlines()

                # 清理行末的换行符并过滤空行
                historical_logs = [line.rstrip('\n\r') for line in log_lines if line.strip()]

                # 如果文件中有日志内容，则使用文件中的日志
                if historical_logs:
                    task.logs = historical_logs
                    log_info(f"从train.log加载了 {len(historical_logs)} 条历史日志: {task.id}")
                else:
                    # 文件存在但为空，使用任务对象中的日志
                    log_info(f"train.log文件为空，保持现有 {len(task.logs)} 条日志: {task.id}")

            except UnicodeDecodeError:
                # 如果编码有问题，尝试其他编码
                try:
                    with open(log_file, 'r', encoding='gbk') as f:
                        log_lines = f.readlines()
                    historical_logs = [line.rstrip('\n\r') for line in log_lines if line.strip()]
                    if historical_logs:
                        task.logs = historical_logs
                        log_info(f"使用GBK编码从train.log加载了 {len(historical_logs)} 条历史日志: {task.id}")
                except Exception as encoding_error:
                    log_error(f"读取训练日志文件编码失败 {log_file}: {encoding_error}")

        except Exception as e:
            log_error(f"加载历史日志失败 {task.id}: {e}")
            # 失败时不影响任务加载，保持现有日志

    def _safe_parse_state(self, state_value: str) -> TrainingState:
        """安全解析状态值"""
        try:
            return TrainingState(state_value)
        except (ValueError, TypeError) as e:
            log_error(f"无效的状态值 '{state_value}': {e}, 使用默认状态 PENDING")
            return TrainingState.PENDING

    def get_task_dir(self, task_id: str) -> Optional[Path]:
        """获取任务目录路径（公共接口）
        
        支持新的目录命名格式: {task_id}--{safe_task_name}
        
        Args:
            task_id: 任务ID（8位短ID）
            
        Returns:
            任务目录的 Path 对象，如果未找到则返回 None
        """
        return self._find_task_dir(task_id)

    def _find_task_dir(self, task_id: str) -> Optional[Path]:
        """根据 task_id 查找任务目录（仅支持新格式）

        新格式: {task_id}--{safe_task_name}
        正则: ^{task_id}--

        Args:
            task_id: 8位短ID

        Returns:
            任务目录路径，未找到返回None
        """
        import re

        # 扫描 tasks_dir 查找匹配 task_id 前缀的目录
        pattern = re.compile(rf'^{re.escape(task_id)}--')

        try:
            for dir_path in self.tasks_dir.iterdir():
                if dir_path.is_dir() and pattern.match(dir_path.name):
                    return dir_path
        except Exception as e:
            log_error(f"扫描任务目录失败: {e}")

        return None

    def _parse_task_id_from_dirname(self, dirname: str) -> Optional[str]:
        """从目录名解析 task_id（固定8位ID）

        格式: {task_id}--{safe_task_name}
        正则: ^([a-z0-9]{8})--

        Args:
            dirname: 目录名

        Returns:
            task_id（8位），解析失败返回None
        """
        import re

        # 新格式: 8位短ID
        match = re.match(r'^([a-z0-9]{8})--', dirname)
        if match:
            return match.group(1)

        return None

    async def _ensure_state_exists(self, task: TrainingTask):
        """确保状态管理器中存在对应状态"""
        try:
            snapshot = await self._state_manager.get_state(task.id)
            if not snapshot:
                # 状态管理器中不存在，直接创建目标状态
                await self._state_manager.transition_state(
                    task.id, task.state, f"load_{task.id}"
                )
        except Exception as e:
            log_error(f"同步状态失败: {e}")


# 全局训练管理器实例
_global_training_manager: Optional[TrainingManager] = None


    # -------------------------
    # 样例/产物列表（对外提供）
    # -------------------------
def get_training_manager() -> TrainingManager:
    """获取全局训练管理器实例"""
    global _global_training_manager
    if _global_training_manager is None:
        raise RuntimeError("TrainingManager is not initialized. Call initialize_training_manager(state_manager, event_bus, main_loop) at app startup.")
    return _global_training_manager
def initialize_training_manager(state_manager: TrainingStateManager, event_bus: EventBus, main_loop: asyncio.AbstractEventLoop) -> TrainingManager:
    """初始化训练管理器（用于应用启动）"""
    global _global_training_manager
    _global_training_manager = TrainingManager(state_manager, event_bus, main_loop)
    log_info("训练管理器初始化完成")
    return _global_training_manager
