"""
统一日志系统 - 供 FastAPI 后端使用
"""

import logging
import sys
import queue
import threading
from pathlib import Path
from typing import Optional, Callable, List, Any
from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class EasyTunerLogger:
    """统一日志系统"""

    def __init__(self, name: str = "EasyTuner"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 日志存储（供 UI 快速读取）
        self.logs: List[str] = []
        self.max_logs = 1000

        # 避免重复添加 handler
        if not self.logger.handlers:
            self._setup_handlers()

        # UI 回调列表
        self._ui_callbacks: list[Callable[[str, LogLevel], None]] = []

        # 日志队列与处理线程
        self.log_queue = queue.Queue()
        self.lock = threading.Lock()

        # 后台日志处理线程
        self.log_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.log_thread.start()

    def _setup_handlers(self):
        """初始化日志处理器"""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 控制台 - 强制UTF-8编码（避免Windows GBK问题）
        import io

        # Windows环境下替换stdout为UTF-8编码的TextIOWrapper
        if sys.platform == 'win32':
            try:
                if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
                    sys.stdout = io.TextIOWrapper(
                        sys.stdout.buffer,
                        encoding='utf-8',
                        errors='replace',
                        line_buffering=True
                    )
                if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, io.TextIOWrapper):
                    sys.stderr = io.TextIOWrapper(
                        sys.stderr.buffer,
                        encoding='utf-8',
                        errors='replace',
                        line_buffering=True
                    )
            except Exception:
                pass  # 如果替换失败，继续使用原有的stdout

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 文件 - 强制UTF-8编码
        try:
            backend_dir = Path(__file__).parent.parent.parent
            log_dir = backend_dir / "logs"
            log_dir.mkdir(exist_ok=True)

            file_handler = logging.FileHandler(
                log_dir / f"tagtracker_{datetime.now().strftime('%Y%m%d')}.log",
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Failed to setup file logging: {e}")

    def register_ui_callback(self, callback: Callable[[str, LogLevel], None]):
        """注册 UI 回调（用于前端展示日志）"""
        with self.lock:
            self._ui_callbacks.append(callback)

    def remove_ui_callback(self, callback: Callable[[str, LogLevel], None]):
        """移除 UI 回调"""
        with self.lock:
            if callback in self._ui_callbacks:
                self._ui_callbacks.remove(callback)

    def _notify_ui(self, message: str, level: LogLevel):
        """通知已注册的 UI 回调"""
        with self.lock:
            for callback in self._ui_callbacks:
                try:
                    callback(message, level)
                except Exception as e:
                    # 回调异常不影响日志系统
                    self.logger.error(f"UI callback error: {e}")

    def _process_logs(self):
        """后台处理日志队列"""
        while True:
            try:
                log_entry = self.log_queue.get(timeout=1)
                self._add_log_internal(log_entry)
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"日志线程异常: {e}")

    def _add_log_internal(self, log_entry: str):
        """内部添加日志记录"""
        with self.lock:
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted_log = f"[{timestamp}] {log_entry}"

            self.logs.append(formatted_log)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)

            for callback in self._ui_callbacks:
                try:
                    callback(formatted_log, LogLevel.INFO)
                except Exception as e:
                    print(f"回调执行错误: {e}")

    def get_all_logs(self) -> List[str]:
        with self.lock:
            return self.logs.copy()

    def get_logs_text(self) -> str:
        with self.lock:
            return "\n".join(self.logs)

    def clear_logs(self):
        with self.lock:
            self.logs.clear()
            for callback in self._ui_callbacks:
                try:
                    callback("CLEAR_TERMINAL", LogLevel.INFO)
                except Exception as e:
                    print(f"回调执行错误: {e}")

    def debug(self, message: str, **kwargs):
        self.logger.debug(message, **kwargs)
        self.log_queue.put(f"[DEBUG] {message}")
        self._notify_ui(f"[DEBUG] {message}", LogLevel.DEBUG)

    def info(self, message: str, **kwargs):
        self.logger.info(message, **kwargs)
        self.log_queue.put(f"[INFO] {message}")
        self._notify_ui(f"[INFO] {message}", LogLevel.INFO)

    def warning(self, message: str, *args: Any, **kwargs):
        self.logger.warning(message, *args, **kwargs)
        try:
            formatted = (message % args) if args else message
        except Exception:
            formatted = f"{message} | args={args}"
        self.log_queue.put(f"[WARNING] {formatted}")
        self._notify_ui(f"[WARNING] {formatted}", LogLevel.WARNING)

    def error(
        self,
        message: str,
        *args: Any,
        exception: Optional[BaseException] = None,
        exc: Optional[BaseException] = None,
        **kwargs: Any
    ):
        """错误日志；支持异常对象并输出堆栈。"""
        _ex = exception if exception is not None else exc
        if _ex is not None:
            self.logger.error(message, *args, exc_info=(type(_ex), _ex, _ex.__traceback__), **kwargs)
            try:
                formatted = (message % args) if args else message
            except Exception:
                formatted = f"{message} | args={args}"
            ui_msg = f"{formatted}: {str(_ex)}"
            self.log_queue.put(f"[ERROR] {ui_msg}")
            self._notify_ui(f"[ERROR] {ui_msg}", LogLevel.ERROR)
        else:
            self.logger.error(message, *args, **kwargs)
            try:
                formatted = (message % args) if args else message
            except Exception:
                formatted = f"{message} | args={args}"
            self.log_queue.put(f"[ERROR] {formatted}")
            self._notify_ui(f"[ERROR] {formatted}", LogLevel.ERROR)

    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs):
        if exception:
            self.logger.critical(f"{message}: {str(exception)}", **kwargs)
            self.log_queue.put(f"[CRITICAL] {message}: {str(exception)}")
            self._notify_ui(f"[CRITICAL] {message}: {str(exception)}", LogLevel.CRITICAL)
        else:
            self.logger.critical(message, **kwargs)
            self.log_queue.put(f"[CRITICAL] {message}")
            self._notify_ui(f"[CRITICAL] {message}", LogLevel.CRITICAL)

    def success(self, message: str, **kwargs):
        self.logger.info(f"SUCCESS: {message}", **kwargs)
        self.log_queue.put(f"[SUCCESS] {message}")
        self._notify_ui(f"[SUCCESS] {message}", LogLevel.INFO)

    def progress(self, current: int, total: int, message: str):
        percentage = round(current / total * 100) if total > 0 else 0
        progress_bar = "█" * (percentage // 5) + "·" * (20 - percentage // 5)
        progress_message = f"[{progress_bar}] {percentage}% - {message}"
        self.logger.info(f"PROGRESS: {progress_message}")
        self.log_queue.put(f"[PROGRESS] {progress_message}")
        self._notify_ui(f"[PROGRESS] {progress_message}", LogLevel.INFO)


# 全局日志实例
logger = EasyTunerLogger()


# 便捷函数
def get_logger(name: str = "EasyTuner") -> EasyTunerLogger:
    return EasyTunerLogger(name)


def log_debug(message: str, **kwargs):
    logger.debug(message, **kwargs)


def log_info(message: str, **kwargs):
    logger.info(message, **kwargs)


def log_warning(message: str, **kwargs):
    logger.warning(message, **kwargs)


def log_warn(message: str, *args: Any, **kwargs: Any):
    """warning 别名；与 logger.warning 等价。"""
    logger.warning(message, *args, **kwargs)


def log_error(
    message: str,
    *args: Any,
    exception: Optional[BaseException] = None,
    exc: Optional[BaseException] = None,
    **kwargs: Any,
):
    """错误日志；支持 exc/exception 传入异常对象并输出堆栈。"""
    logger.error(message, *args, exception=exception, exc=exc, **kwargs)


def log_success(message: str, **kwargs):
    logger.success(message, **kwargs)


def log_progress(current: int, total: int, message: str):
    logger.progress(current, total, message)

