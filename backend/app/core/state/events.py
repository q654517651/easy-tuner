"""
事件总线系统 - 统一事件管理和分发
"""

import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class EventBus:
    """统一事件总线 - 解耦组件间通信（与主事件循环同生共死）"""

    def __init__(self, websocket_manager, loop: asyncio.AbstractEventLoop):
        self._handlers: Dict[str, List[Callable]] = {}
        self._websocket_manager = websocket_manager
        self._sequence_counters: Dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._loop = loop  # 主事件循环引用，供线程安全投递使用

    def set_websocket_manager(self, websocket_manager):
        """如确有需要可后设，但通常在 __init__ 已传入"""
        self._websocket_manager = websocket_manager

    async def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """发布事件"""
        try:
            # 1. 本地处理器处理
            handlers = self._handlers.get(event_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(payload)
                    else:
                        handler(payload)
                except Exception as e:
                    logger.error(f"事件处理器失败 {event_type}: {e}", exc_info=True)

            # 2. WebSocket广播
            if self._websocket_manager:
                await self._websocket_manager.broadcast_event(event_type, payload)

            logger.debug(f"事件发布成功: {event_type}")

        except Exception as e:
            logger.error(f"事件发布失败 {event_type}: {e}", exc_info=True)

    def emit_threadsafe(self, event_type: str, payload: Dict[str, Any]) -> None:
        """线程安全地发布事件（不阻塞调用线程）"""
        try:
            # 投递到主事件循环，不等待结果
            asyncio.run_coroutine_threadsafe(
                self.emit(event_type, payload),
                self._loop
            )
        except Exception as e:
            logger.error(f"线程安全事件发布失败 {event_type}: {e}")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"事件订阅: {event_type} -> {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅事件"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.debug(f"取消事件订阅: {event_type} -> {handler.__name__}")
            except ValueError:
                pass

    async def get_next_sequence(self, task_id: str) -> int:
        """获取下一个序列号"""
        async with self._lock:
            if task_id not in self._sequence_counters:
                self._sequence_counters[task_id] = 0
            self._sequence_counters[task_id] += 1
            return self._sequence_counters[task_id]

    async def reset_sequence(self, task_id: str) -> None:
        """重置序列号（用于epoch重启）"""
        async with self._lock:
            self._sequence_counters[task_id] = 0
            logger.debug(f"重置序列号: {task_id}")

    def get_subscribed_events(self) -> List[str]:
        """获取所有已订阅的事件类型"""
        return list(self._handlers.keys())

    def get_handler_count(self, event_type: str) -> int:
        """获取指定事件类型的处理器数量"""
        return len(self._handlers.get(event_type, []))

    async def emit_log(self, task_id: str, message: str, level: str = "info") -> None:
        """发送训练日志事件"""
        timestamp = datetime.now()
        formatted_message = f"[{timestamp.isoformat()}] [{level.upper()}] {message}"

        await self.emit('training.log', {
            'task_id': task_id,
            'message': formatted_message,
            'level': level,
            'timestamp': timestamp.timestamp()
        })

    async def emit_metric(self, task_id: str, metric_name: str, value: float, step: int) -> None:
        """发送训练指标事件"""
        await self.emit('training.metric', {
            'task_id': task_id,
            'metric_name': metric_name,
            'value': value,
            'step': step,
            'timestamp': datetime.now().timestamp()
        })

    async def emit_file_change(self, task_id: str, file_type: str, filename: str, action: str) -> None:
        """发送文件变化事件"""
        await self.emit('file.changed', {
            'task_id': task_id,
            'file_type': file_type,
            'filename': filename,
            'action': action,
            'timestamp': datetime.now().timestamp()
        })


# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例（必须先由 initialize_event_bus 初始化）"""
    global _global_event_bus
    if _global_event_bus is None:
        raise RuntimeError("EventBus 未初始化，请在应用启动时调用 initialize_event_bus")
    return _global_event_bus


def initialize_event_bus(websocket_manager, loop: asyncio.AbstractEventLoop) -> EventBus:
    """初始化事件总线（用于应用启动）"""
    global _global_event_bus
    _global_event_bus = EventBus(websocket_manager, loop)
    logger.info("事件总线初始化完成")
    return _global_event_bus
