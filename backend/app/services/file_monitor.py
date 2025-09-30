"""
文件监控服务 - 监控训练过程中的文件变化
"""

import asyncio
import threading
from typing import Dict, Set, Callable, Optional
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("警告: watchdog 库未安装，文件监控功能将被禁用")

from ..utils.logger import log_info, log_error


class TrainingFileHandler(FileSystemEventHandler):
    """训练文件事件处理器"""

    def __init__(self, task_id: str, notify_func: Callable):
        super().__init__()
        self.task_id = task_id
        self.notify = notify_func

    def on_created(self, event):
        """文件创建事件"""
        if event.is_file:
            self._handle_file_event(event.src_path, "created")

    def on_modified(self, event):
        """文件修改事件"""
        if event.is_file:
            self._handle_file_event(event.src_path, "modified")

    def _handle_file_event(self, file_path: str, action: str):
        """处理文件事件"""
        try:
            file_path_obj = Path(file_path)

            # 检测文件类型
            if file_path_obj.parent.name == "sample" and file_path_obj.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                asyncio.run_coroutine_threadsafe(
                    self.notify(self.task_id, "sample_image", file_path_obj.name, action),
                    asyncio.get_event_loop()
                )
            elif file_path_obj.suffix == ".safetensors":
                asyncio.run_coroutine_threadsafe(
                    self.notify(self.task_id, "model_file", file_path_obj.name, action),
                    asyncio.get_event_loop()
                )
        except Exception as e:
            log_error(f"处理文件事件失败: {e}")


class TrainingFileMonitor:
    """训练文件监控器"""

    def __init__(self):
        self._observers: Dict[str, Observer] = {}
        self._callbacks: Dict[str, Set[Callable]] = {}
        self._lock = threading.Lock()

    def start_monitoring(self, task_id: str, callback: Callable) -> bool:
        """开始监控训练任务的输出目录"""
        if not WATCHDOG_AVAILABLE:
            log_error("watchdog 库未安装，无法启动文件监控")
            return False

        try:
            with self._lock:
                task_output_dir = Path(f"workspace/tasks/{task_id}/output")

                # 确保目录存在
                task_output_dir.mkdir(parents=True, exist_ok=True)

                # 如果还没有监控这个任务，创建新的监控器
                if task_id not in self._observers:
                    observer = Observer()
                    handler = TrainingFileHandler(task_id, self._notify_callbacks)
                    observer.schedule(handler, str(task_output_dir), recursive=True)
                    observer.start()
                    self._observers[task_id] = observer
                    log_info(f"开始监控训练任务文件: {task_id}")

                # 注册回调
                if task_id not in self._callbacks:
                    self._callbacks[task_id] = set()
                self._callbacks[task_id].add(callback)

                return True

        except Exception as e:
            log_error(f"启动文件监控失败: {e}")
            return False

    def stop_monitoring(self, task_id: str, callback: Optional[Callable] = None):
        """停止监控训练任务"""
        try:
            with self._lock:
                if task_id in self._callbacks:
                    if callback:
                        # 移除特定回调
                        self._callbacks[task_id].discard(callback)
                        if not self._callbacks[task_id]:
                            # 如果没有回调了，停止监控
                            self._stop_task_observer(task_id)
                    else:
                        # 移除所有回调并停止监控
                        self._callbacks[task_id].clear()
                        self._stop_task_observer(task_id)

        except Exception as e:
            log_error(f"停止文件监控失败: {e}")

    def _stop_task_observer(self, task_id: str):
        """停止特定任务的监控器"""
        if task_id in self._observers:
            try:
                self._observers[task_id].stop()
                self._observers[task_id].join()
                del self._observers[task_id]
                del self._callbacks[task_id]
                log_info(f"停止监控训练任务文件: {task_id}")
            except Exception as e:
                log_error(f"停止任务监控器失败: {e}")

    async def _notify_callbacks(self, task_id: str, file_type: str, filename: str, action: str):
        """通知所有回调函数"""
        try:
            if task_id in self._callbacks:
                for callback in self._callbacks[task_id].copy():  # 复制以避免并发修改
                    try:
                        await callback(task_id, file_type, filename, action)
                    except Exception as e:
                        log_error(f"回调函数执行失败: {e}")
        except Exception as e:
            log_error(f"通知回调失败: {e}")

    def cleanup(self):
        """清理所有监控器"""
        try:
            with self._lock:
                for task_id in list(self._observers.keys()):
                    self._stop_task_observer(task_id)
        except Exception as e:
            log_error(f"清理文件监控器失败: {e}")


# 全局文件监控器实例
_file_monitor_instance: Optional[TrainingFileMonitor] = None
_monitor_lock = threading.Lock()


def get_file_monitor() -> TrainingFileMonitor:
    """获取文件监控器实例"""
    global _file_monitor_instance
    if _file_monitor_instance is None:
        with _monitor_lock:
            if _file_monitor_instance is None:
                _file_monitor_instance = TrainingFileMonitor()
    return _file_monitor_instance