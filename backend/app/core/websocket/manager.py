"""
新的统一WebSocket管理器 - 简化设计，事件驱动
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect

from ..state.models import TrainingState, TrainingEvent
from ..state.events import EventBus

logger = logging.getLogger(__name__)


class WebSocketManager:
    """简化的WebSocket管理器 - 统一消息格式，事件驱动"""

    def __init__(self):
        self._event_bus = None  # 稍后由EventBus设置
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connections: Dict[str, WebSocket] = {}  # client_id -> websocket
        self._subscriptions: Dict[str, Set[str]] = {}  # client_id -> {task_ids}
        self._sequence_counters: Dict[str, int] = {}  # task_id -> sequence
        self._lock: Optional[asyncio.Lock] = None  # 在绑定loop后创建，避免跨loop

    def set_event_bus(self, event_bus):
        """设置事件总线并订阅事件（在EventBus初始化后调用）"""
        self._event_bus = event_bus
        # 绑定主事件循环
        try:
            loop = getattr(event_bus, "_loop", None)
        except Exception:
            loop = None
        self._loop = loop or asyncio.get_event_loop()
        # 在绑定的事件循环中创建锁，避免跨loop绑定
        try:
            # 如果当前就在绑定的事件循环线程内，使用 create_task 避免死锁
            try:
                current = asyncio.get_running_loop()
            except RuntimeError:
                current = None
            if current is not None and current is self._loop:
                self._loop.create_task(self._create_lock_async())
            else:
                fut = asyncio.run_coroutine_threadsafe(self._create_lock_async(), self._loop)
                fut.result()
        except Exception as e:
            logger.error(f"创建WebSocketManager锁失败: {e}")
        self._setup_event_handlers()

    async def _create_lock_async(self):
        # 若已存在则忽略
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def _await_on_loop(self, coro_factory):
        """统一在绑定的事件循环上执行异步操作，避免跨loop使用锁"""
        current = None
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if self._loop is not None and current is not self._loop:
            fut = asyncio.run_coroutine_threadsafe(coro_factory(), self._loop)
            return fut.result()
        return await coro_factory()

    async def safe_send(self, websocket: WebSocket, message: str) -> bool:
        """安全发送WebSocket消息，避免在关闭后发送"""
        try:
            if websocket.client_state.name == "DISCONNECTED":
                return False
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.debug(f"WebSocket发送失败: {e}")
            return False

    def _setup_event_handlers(self):
        """设置事件处理器"""
        self._event_bus.subscribe('state.transitioned', self._handle_state_transition)
        self._event_bus.subscribe('training.log', self._handle_training_log)
        self._event_bus.subscribe('training.log_batch', self._handle_training_log_batch)
        self._event_bus.subscribe('training.metric', self._handle_training_metric)
        # 兼容：将 training.progress 视为 metric 推送（当前 Trainer 发送的是 training.progress）
        self._event_bus.subscribe('training.progress', self._handle_training_metric)
        self._event_bus.subscribe('file.changed', self._handle_file_change)

    async def add_connection(self, client_id: str, websocket: WebSocket, task_id: str) -> None:
        """添加WebSocket连接（在绑定loop上执行）"""
        async def _inner():
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                self._connections[client_id] = websocket
                if client_id not in self._subscriptions:
                    self._subscriptions[client_id] = set()
                self._subscriptions[client_id].add(task_id)
                logger.info(f"WebSocket连接已添加: {client_id} -> {task_id}")
        await self._await_on_loop(_inner)

    async def remove_connection(self, client_id: str) -> None:
        """移除WebSocket连接（在绑定loop上执行）"""
        async def _inner():
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                self._connections.pop(client_id, None)
                self._subscriptions.pop(client_id, None)
                logger.info(f"WebSocket连接已移除: {client_id}")
        await self._await_on_loop(_inner)

    async def broadcast_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """广播事件到相关连接"""
        task_id = payload.get('task_id')
        if not task_id:
            return

        # 构建WebSocket消息
        message = await self._build_websocket_message(event_type, task_id, payload)

        # 发送给订阅该任务的所有客户端
        await self._broadcast_to_task_subscribers(task_id, message)

    async def _build_websocket_message(self, event_type: str, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """构建标准WebSocket消息"""
        # 从状态管理器获取当前epoch
        from ..state.manager import get_state_manager
        state_manager = get_state_manager()
        snapshot = await state_manager.get_state(task_id)
        current_epoch = snapshot.epoch if snapshot else 1

        # 获取序列号
        sequence = await self._get_next_sequence(task_id)

        return {
            'version': 1,
            'type': self._map_event_to_type(event_type),
            'task_id': task_id,
            'epoch': current_epoch,
            'sequence': sequence,
            'timestamp': time.time(),
            'payload': payload
        }

    def _map_event_to_type(self, event_type: str) -> str:
        """映射事件类型到WebSocket消息类型"""
        mapping = {
            'state.transitioned': 'state',
            'training.log': 'log',
            'training.metric': 'metric',
            'training.progress': 'metric',
            'file.changed': 'file'
        }
        return mapping.get(event_type, event_type)

    async def _get_next_sequence(self, task_id: str) -> int:
        """获取下一个序列号"""
        if task_id not in self._sequence_counters:
            self._sequence_counters[task_id] = 0
        self._sequence_counters[task_id] += 1
        return self._sequence_counters[task_id]

    async def _broadcast_to_task_subscribers(self, task_id: str, message: Dict[str, Any]) -> None:
        """向订阅特定任务的所有客户端广播消息（在绑定loop上执行）"""
        async def _inner():
            disconnected_clients = []
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                for client_id, websocket in self._connections.items():
                    if task_id not in self._subscriptions.get(client_id, set()):
                        continue
                    try:
                        await websocket.send_text(json.dumps(message, ensure_ascii=False))
                    except Exception as e:
                        logger.error(f"WebSocket发送失败 {client_id}: {e}")
                        disconnected_clients.append(client_id)
            for client_id in disconnected_clients:
                await self.remove_connection(client_id)
        await self._await_on_loop(_inner)

    async def _handle_state_transition(self, payload: Dict[str, Any]) -> None:
        """处理状态转换事件"""
        transition = payload['transition']
        snapshot = payload['snapshot']

        websocket_payload = {
            'from_state': transition.from_state.value,
            'to_state': transition.to_state.value,
            'cause_id': transition.cause_id,
            'metadata': transition.metadata
        }

        # 构建并广播消息
        message = {
            'version': 1,
            'type': 'state',
            'task_id': transition.task_id,
            'epoch': snapshot.epoch,
            'sequence': await self._get_next_sequence(transition.task_id),
            'timestamp': time.time(),
            'payload': websocket_payload
        }

        await self._broadcast_to_task_subscribers(transition.task_id, message)

        # 终态处理：自动关闭WebSocket连接（带最终状态）
        if transition.to_state.is_terminal():
            await self._close_task_connections(transition.task_id, final_state=transition.to_state.value)

    async def _handle_training_log(self, payload: Dict[str, Any]) -> None:
        """处理训练日志事件"""
        task_id = payload['task_id']
        message = await self._build_websocket_message('training.log', task_id, payload)
        await self._broadcast_to_task_subscribers(task_id, message)

    async def _handle_training_log_batch(self, payload: Dict[str, Any]) -> None:
        """处理训练日志批次事件（向后端订阅者发送 log_batch）"""
        task_id = payload.get('task_id')
        if not task_id:
            return
        # 从状态管理器获取当前epoch
        from ..state.manager import get_state_manager
        state_manager = get_state_manager()
        snapshot = await state_manager.get_state(task_id)
        epoch = snapshot.epoch if snapshot else 1
        seq = await self._get_next_sequence(task_id)
        # 构造与前端兼容的结构：顶层包含 lines/sinceOffset/newOffset
        message = {
            'version': 1,
            'type': 'log_batch',
            'task_id': task_id,
            'epoch': epoch,
            'sequence': seq,
            'timestamp': time.time(),
            'lines': payload.get('lines', []),
            'sinceOffset': payload.get('since_offset', 0),
            'newOffset': payload.get('new_offset', 0),
            'payload': payload,
        }
        await self._broadcast_to_task_subscribers(task_id, message)

    async def _handle_training_metric(self, payload: Dict[str, Any]) -> None:
        """处理训练指标事件"""
        task_id = payload['task_id']
        message = await self._build_websocket_message('training.metric', task_id, payload)
        await self._broadcast_to_task_subscribers(task_id, message)

    async def _handle_file_change(self, payload: Dict[str, Any]) -> None:
        """处理文件变化事件"""
        task_id = payload['task_id']
        message = await self._build_websocket_message('file.changed', task_id, payload)
        await self._broadcast_to_task_subscribers(task_id, message)

    async def _close_task_connections(self, task_id: str, final_state: Optional[str] = None) -> None:
        """关闭特定任务的所有WebSocket连接（在绑定loop上执行）；不再发送额外 final 消息，前端以 state 终态为准"""
        async def _inner():
            disconnected_clients = []
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                for client_id, websocket in self._connections.items():
                    if task_id in self._subscriptions.get(client_id, set()):
                        try:
                            await websocket.close(code=1000, reason="Task finalized")
                            disconnected_clients.append(client_id)
                        except Exception as e:
                            logger.error(f"关闭WebSocket连接失败 {client_id}: {e}")
                            disconnected_clients.append(client_id)
            for client_id in disconnected_clients:
                await self.remove_connection(client_id)
        await self._await_on_loop(_inner)

        logger.info(f"已关闭任务 {task_id} 的所有WebSocket连接")

    async def send_current_state(self, client_id: str, task_id: str) -> None:
        """发送当前状态快照给指定客户端"""
        if client_id not in self._connections:
            return

        try:
            from ..state.manager import get_state_manager
            state_manager = get_state_manager()
            snapshot = await state_manager.get_state(task_id)

            if snapshot:
                message = {
                    'version': 1,
                    'type': 'state',
                    'task_id': task_id,
                    'epoch': snapshot.epoch,
                    'sequence': 0,  # 初始消息序列号为0
                    'timestamp': time.time(),
                    'payload': {
                        'current_state': snapshot.state.value,
                        'epoch': snapshot.epoch,
                        'last_transition': {
                            'from_state': snapshot.last_transition.from_state.value,
                            'to_state': snapshot.last_transition.to_state.value,
                            'cause_id': snapshot.last_transition.cause_id,
                            'timestamp': snapshot.last_transition.timestamp.isoformat()
                        }
                    }
                }

                websocket = self._connections[client_id]
                await websocket.send_text(json.dumps(message, ensure_ascii=False))
                logger.debug(f"发送当前状态给客户端 {client_id}: {snapshot.state.value}")

        except Exception as e:
            logger.error(f"发送当前状态失败 {client_id}: {e}")

    async def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息（在绑定loop上执行）"""
        async def _inner():
            async with self._lock:
                return {
                    'total_connections': len(self._connections),
                    'total_subscriptions': sum(len(subs) for subs in self._subscriptions.values()),
                    'connections_per_task': {
                        task_id: sum(1 for subs in self._subscriptions.values() if task_id in subs)
                        for task_id in (set().union(*self._subscriptions.values()) if self._subscriptions else set())
                    }
                }
        return await self._await_on_loop(_inner)


# 全局WebSocket管理器实例
_global_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """获取全局WebSocket管理器实例（需在应用启动时通过 initialize_websocket_manager 创建）"""
    global _global_websocket_manager
    if _global_websocket_manager is None:
        _global_websocket_manager = WebSocketManager()
    return _global_websocket_manager


def initialize_websocket_manager() -> WebSocketManager:
    """初始化WebSocket管理器（用于应用启动）"""
    global _global_websocket_manager
    _global_websocket_manager = WebSocketManager()
    logger.info("WebSocket管理器初始化完成")
    return _global_websocket_manager
