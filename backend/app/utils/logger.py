"""
统一日志系统 - 适配FastAPI后端
"""

import logging
import sys
import queue
import threading
from pathlib import Path
from typing import Optional, Callable, List
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
        
        # 日志存储和限制
        self.logs: List[str] = []
        self.max_logs = 1000  # 最大日志条数
        
        # 避免重复添加handler
        if not self.logger.handlers:
            self._setup_handlers()
        
        # UI回调函数列表
        self._ui_callbacks: list[Callable[[str, LogLevel], None]] = []
        
        # 日志队列和处理线程
        self.log_queue = queue.Queue()
        self.lock = threading.Lock()
        
        # 启动日志处理线程
        self.log_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.log_thread.start()
    
    def _setup_handlers(self):
        """设置日志处理器"""
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器
        try:
            # backend目录下的logs目录
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
        """注册UI回调函数，用于在界面上显示日志"""
        with self.lock:
            self._ui_callbacks.append(callback)
    
    def remove_ui_callback(self, callback: Callable[[str, LogLevel], None]):
        """移除UI回调函数"""
        with self.lock:
            if callback in self._ui_callbacks:
                self._ui_callbacks.remove(callback)
    
    def _notify_ui(self, message: str, level: LogLevel):
        """通知所有UI回调"""
        with self.lock:
            for callback in self._ui_callbacks:
                try:
                    callback(message, level)
                except Exception as e:
                    # 避免UI回调错误影响日志系统
                    self.logger.error(f"UI callback error: {e}")
    
    def _process_logs(self):
        """处理日志队列的后台线程"""
        while True:
            try:
                log_entry = self.log_queue.get(timeout=1)
                self._add_log_internal(log_entry)
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"日志处理错误: {e}")
    
    def _add_log_internal(self, log_entry: str):
        """内部添加日志方法"""
        with self.lock:
            # 添加时间戳
            timestamp = datetime.now().strftime('%H:%M:%S')
            formatted_log = f"[{timestamp}] {log_entry}"
            
            self.logs.append(formatted_log)
            
            # 限制日志数量
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)
            
            # 通知所有回调函数
            for callback in self._ui_callbacks:
                try:
                    callback(formatted_log, LogLevel.INFO)
                except Exception as e:
                    print(f"回调函数执行错误: {e}")
    
    def get_all_logs(self) -> List[str]:
        """获取所有日志"""
        with self.lock:
            return self.logs.copy()
    
    def get_logs_text(self) -> str:
        """获取所有日志的文本形式"""
        with self.lock:
            return "\n".join(self.logs)
    
    def clear_logs(self):
        """清空日志"""
        with self.lock:
            self.logs.clear()
            for callback in self._ui_callbacks:
                try:
                    callback("CLEAR_TERMINAL", LogLevel.INFO)
                except Exception as e:
                    print(f"回调函数执行错误: {e}")
    
    def debug(self, message: str, **kwargs):
        """调试日志"""
        self.logger.debug(message, **kwargs)
        self.log_queue.put(f"[DEBUG] {message}")
        self._notify_ui(f"[DEBUG] {message}", LogLevel.DEBUG)
    
    def info(self, message: str, **kwargs):
        """信息日志"""
        self.logger.info(message, **kwargs)
        self.log_queue.put(f"[INFO] {message}")
        self._notify_ui(f"[INFO] {message}", LogLevel.INFO)
    
    def warning(self, message: str, **kwargs):
        """警告日志"""
        self.logger.warning(message, **kwargs)
        self.log_queue.put(f"[WARNING] {message}")
        self._notify_ui(f"[WARNING] {message}", LogLevel.WARNING)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """错误日志"""
        if exception:
            self.logger.error(f"{message}: {str(exception)}", **kwargs)
            self.log_queue.put(f"[ERROR] {message}: {str(exception)}")
            self._notify_ui(f"[ERROR] {message}: {str(exception)}", LogLevel.ERROR)
        else:
            self.logger.error(message, **kwargs)
            self.log_queue.put(f"[ERROR] {message}")
            self._notify_ui(f"[ERROR] {message}", LogLevel.ERROR)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs):
        """严重错误日志"""
        if exception:
            self.logger.critical(f"{message}: {str(exception)}", **kwargs)
            self.log_queue.put(f"[CRITICAL] {message}: {str(exception)}")
            self._notify_ui(f"[CRITICAL] {message}: {str(exception)}", LogLevel.CRITICAL)
        else:
            self.logger.critical(message, **kwargs)
            self.log_queue.put(f"[CRITICAL] {message}")
            self._notify_ui(f"[CRITICAL] {message}", LogLevel.CRITICAL)
    
    def success(self, message: str, **kwargs):
        """成功日志（自定义级别）"""
        self.logger.info(f"SUCCESS: {message}", **kwargs)
        self.log_queue.put(f"[SUCCESS] {message}")
        self._notify_ui(f"[SUCCESS] {message}", LogLevel.INFO)
    
    def progress(self, current: int, total: int, message: str):
        """进度日志（自定义级别）"""
        percentage = round(current / total * 100) if total > 0 else 0
        progress_bar = "█" * (percentage // 5) + "░" * (20 - percentage // 5)
        progress_message = f"[{progress_bar}] {percentage}% - {message}"
        self.logger.info(f"PROGRESS: {progress_message}")
        self.log_queue.put(f"[PROGRESS] {progress_message}")
        self._notify_ui(f"[PROGRESS] {progress_message}", LogLevel.INFO)

# 全局日志实例
logger = EasyTunerLogger()

# 便捷函数
def get_logger(name: str = "EasyTuner") -> EasyTunerLogger:
    """获取日志实例"""
    return EasyTunerLogger(name)

def log_debug(message: str, **kwargs):
    """快捷调试日志"""
    logger.debug(message, **kwargs)

def log_info(message: str, **kwargs):
    """快捷信息日志"""
    logger.info(message, **kwargs)

def log_warning(message: str, **kwargs):
    """快捷警告日志"""
    logger.warning(message, **kwargs)

def log_error(message: str, exception: Optional[Exception] = None, **kwargs):
    """快捷错误日志"""
    logger.error(message, exception, **kwargs)

def log_success(message: str, **kwargs):
    """快捷成功日志"""
    logger.success(message, **kwargs)

def log_progress(current: int, total: int, message: str):
    """快捷进度日志"""
    logger.progress(current, total, message)