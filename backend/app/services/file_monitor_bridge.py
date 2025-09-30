"""
文件监控桥接（新架构）
- 监听状态机事件：任务进入 running 开始监控；进入终态停止监控
- 通过 EventBus 广播统一的 file.changed 事件，供 WebSocketManager 转发为 type: 'file'
"""

import asyncio
from typing import Dict, Optional

from ..core.state.models import TrainingState
from ..core.state.manager import TrainingStateManager
from ..core.state.events import EventBus
from ..utils.logger import log_info, log_error
from .file_monitor import get_file_monitor


class _FileMonitorBridge:
    def __init__(self, event_bus: EventBus, state_manager: TrainingStateManager):
        self._event_bus = event_bus
        self._state_manager = state_manager
        self._started: Dict[str, bool] = {}

        # 订阅状态迁移事件
        self._event_bus.subscribe('state.transitioned', self._on_state_transition)

        # 异步初始化：为已在运行的任务补挂监控
        try:
            asyncio.create_task(self._attach_existing_running_tasks())
        except RuntimeError:
            # 非事件循环环境下，忽略（通常不会发生，因为在 lifespan 中初始化）
            pass

    async def _attach_existing_running_tasks(self):
        try:
            running_ids = await self._state_manager.get_active_tasks()
            if not running_ids:
                return
            for task_id in running_ids:
                await self._ensure_monitor_started(task_id)
        except Exception as e:
            log_error(f"初始化文件监控失败: {e}")

    def _is_active(self, state: TrainingState) -> bool:
        try:
            return state.is_active()
        except Exception:
            return state == TrainingState.RUNNING

    def _is_terminal(self, state: TrainingState) -> bool:
        try:
            return state.is_terminal()
        except Exception:
            return state in (TrainingState.COMPLETED, TrainingState.FAILED, TrainingState.CANCELLED)

    def _mark_started(self, task_id: str, ok: bool):
        self._started[task_id] = ok

    async def _on_state_transition(self, payload: dict):
        try:
            transition = payload.get('transition')
            if not transition:
                return

            task_id = transition.task_id
            to_state = transition.to_state

            if self._is_active(to_state):
                await self._ensure_monitor_started(task_id)
            elif self._is_terminal(to_state):
                self._stop_monitor(task_id)

        except Exception as e:
            log_error(f"处理状态迁移以挂载文件监控失败: {e}")

    async def _ensure_monitor_started(self, task_id: str):
        # 已经启动过则忽略
        if self._started.get(task_id):
            return

        try:
            monitor = get_file_monitor()

            # 定义文件变化回调：通过 EventBus 广播统一事件
            async def file_change_callback(task_id_cb: str, file_type: str, filename: str, action: str):
                try:
                    await self._event_bus.emit('file.changed', {
                        'task_id': task_id_cb,
                        'file_type': file_type,      # "sample_image" | "model_file"
                        'filename': filename,
                        'action': action,            # "created" | "modified"
                    })
                except Exception as e:
                    log_error(f"广播文件变更失败: {e}")

            ok = monitor.start_monitoring(task_id, file_change_callback)
            self._mark_started(task_id, ok)
            if ok:
                log_info(f"文件监控已启动: {task_id}")
            else:
                log_error(f"文件监控启动失败（watchdog 未安装或其他原因）: {task_id}")

        except Exception as e:
            log_error(f"启动文件监控异常: {e}")

    def _stop_monitor(self, task_id: str):
        try:
            monitor = get_file_monitor()
            monitor.stop_monitoring(task_id)
            self._started[task_id] = False
            log_info(f"文件监控已停止: {task_id}")
        except Exception as e:
            log_error(f"停止文件监控失败: {e}")


_bridge_instance: Optional[_FileMonitorBridge] = None


def initialize_file_monitor_bridge(event_bus: EventBus, state_manager: TrainingStateManager):
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = _FileMonitorBridge(event_bus, state_manager)
        log_info("文件监控桥接初始化完成")
    return _bridge_instance

