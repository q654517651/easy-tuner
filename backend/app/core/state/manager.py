"""
中央状态管理器 - 整个系统状态变更的唯一入口
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set
from datetime import datetime

from .models import (
    TrainingState, StateTransition, TaskStateSnapshot,
    VALID_STATE_TRANSITIONS, is_valid_transition, is_restart_transition
)
from .events import EventBus

logger = logging.getLogger(__name__)


class TrainingStateManager:
    """中央状态管理器 - 整个系统状态变更的唯一入口"""

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._snapshots: Dict[str, TaskStateSnapshot] = {}
        self._transitions: Dict[str, List[StateTransition]] = {}
        self._duplicate_causes: Dict[str, Set[str]] = {}  # task_id -> {cause_ids}
        self._lock = asyncio.Lock()

    async def transition_if_current_in(
        self,
        task_id: str,
        allowed_from: set[TrainingState],
        to_state: TrainingState,
        cause_id: str,
        metadata: Optional[Dict[str, any]] = None
    ) -> tuple[bool, Optional[TrainingState]]:
        """原子性条件转换：只有当前状态在允许集合中时才执行转换"""
        async with self._lock:
            try:
                # 获取当前快照
                current = self._snapshots.get(task_id)
                if not current:
                    return False, None

                # 检查当前状态是否在允许集合中
                if current.state not in allowed_from:
                    return False, current.state

                # 执行转换逻辑（复用现有逻辑）
                if not is_valid_transition(current.state, to_state):
                    await self._emit_invalid_transition(task_id, current.state, to_state, cause_id)
                    return False, current.state

                # 幂等性检查
                if await self._is_duplicate_transition(task_id, cause_id):
                    return True, current.state  # 重复请求，返回成功

                # 执行状态转换
                is_restart = is_restart_transition(current.state, to_state)
                new_epoch = current.epoch + (1 if is_restart else 0)

                # 创建转换记录
                transition = StateTransition(
                    from_state=current.state,
                    to_state=to_state,
                    task_id=task_id,
                    cause_id=cause_id,
                    epoch=new_epoch,
                    timestamp=datetime.now(),
                    metadata=metadata
                )

                # 更新快照
                self._snapshots[task_id] = TaskStateSnapshot(
                    task_id=task_id,
                    state=to_state,
                    epoch=new_epoch,
                    last_transition=transition,
                    created_at=current.created_at,
                    updated_at=datetime.now()
                )

                # 记录转换历史
                if task_id not in self._transitions:
                    self._transitions[task_id] = []
                self._transitions[task_id].append(transition)

                # 记录cause_id防重复
                if task_id not in self._duplicate_causes:
                    self._duplicate_causes[task_id] = set()
                self._duplicate_causes[task_id].add(cause_id)

                # 如果是重启，重置序列号
                if is_restart:
                    await self._event_bus.reset_sequence(task_id)

                # 触发状态转换事件
                await self._event_bus.emit('state.transitioned', {
                    'transition': transition,
                    'snapshot': self._snapshots[task_id]
                })

                logger.info(f"条件状态转换成功: {task_id} {current.state.value} -> {to_state.value} (epoch: {new_epoch}, cause: {cause_id})")
                return True, current.state

            except Exception as e:
                logger.error(f"条件状态转换失败: {task_id} -> {to_state.value}: {e}", exc_info=True)
                return False, current.state if current else None

    async def transition_state(
        self,
        task_id: str,
        new_state: TrainingState,
        cause_id: str,
        metadata: Optional[Dict[str, any]] = None
    ) -> bool:
        """唯一的状态转换入口 - 保证原子性和一致性"""
        async with self._lock:
            try:
                # 1. 获取当前快照
                current = self._snapshots.get(task_id)
                if not current:
                    # 初始状态创建 - 允许直接创建任何合法状态（历史任务恢复）
                    current = self._create_initial_snapshot(task_id, new_state)
                    logger.info(f"创建初始状态快照: {task_id} -> {new_state}")
                    # 直接创建成功，不需要后续转换逻辑
                    return True

                # 2. 校验转换合法性
                if not is_valid_transition(current.state, new_state):
                    await self._emit_invalid_transition(task_id, current.state, new_state, cause_id)
                    return False

                # 3. 幂等性检查
                if await self._is_duplicate_transition(task_id, cause_id):
                    logger.debug(f"重复状态转换请求: {task_id} {cause_id}")
                    return True  # 重复请求，返回成功

                # 4. 执行状态转换
                is_restart = is_restart_transition(current.state, new_state)
                new_epoch = current.epoch + (1 if is_restart else 0)

                # 创建转换记录
                transition = StateTransition(
                    from_state=current.state,
                    to_state=new_state,
                    task_id=task_id,
                    cause_id=cause_id,
                    epoch=new_epoch,
                    timestamp=datetime.now(),
                    metadata=metadata
                )

                # 5. 更新快照
                self._snapshots[task_id] = TaskStateSnapshot(
                    task_id=task_id,
                    state=new_state,
                    epoch=new_epoch,
                    last_transition=transition,
                    created_at=current.created_at,
                    updated_at=datetime.now()
                )

                # 6. 记录转换历史
                if task_id not in self._transitions:
                    self._transitions[task_id] = []
                self._transitions[task_id].append(transition)

                # 7. 记录cause_id防重复
                if task_id not in self._duplicate_causes:
                    self._duplicate_causes[task_id] = set()
                self._duplicate_causes[task_id].add(cause_id)

                # 8. 如果是重启，重置序列号
                if is_restart:
                    await self._event_bus.reset_sequence(task_id)

                # 9. 触发状态转换事件
                await self._event_bus.emit('state.transitioned', {
                    'transition': transition,
                    'snapshot': self._snapshots[task_id]
                })

                logger.info(f"状态转换成功: {task_id} {current.state.value} -> {new_state.value} (epoch: {new_epoch}, cause: {cause_id})")
                return True

            except Exception as e:
                logger.error(f"状态转换失败: {task_id} -> {new_state.value}: {e}", exc_info=True)
                return False

    async def get_state(self, task_id: str) -> Optional[TaskStateSnapshot]:
        """获取任务当前状态快照"""
        return self._snapshots.get(task_id)

    async def get_transition_history(self, task_id: str) -> List[StateTransition]:
        """获取状态转换历史"""
        return self._transitions.get(task_id, [])

    async def list_all_snapshots(self) -> Dict[str, TaskStateSnapshot]:
        """获取所有任务状态快照"""
        return self._snapshots.copy()

    async def cleanup_task(self, task_id: str) -> None:
        """清理任务相关数据"""
        async with self._lock:
            self._snapshots.pop(task_id, None)
            self._transitions.pop(task_id, None)
            self._duplicate_causes.pop(task_id, None)
            logger.info(f"清理任务状态数据: {task_id}")

    def _create_initial_snapshot(self, task_id: str, initial_state: TrainingState = TrainingState.PENDING) -> TaskStateSnapshot:
        """创建初始状态快照"""
        now = datetime.now()
        initial_transition = StateTransition(
            from_state=initial_state,  # 使用传入的初始状态
            to_state=initial_state,
            task_id=task_id,
            cause_id="initial",
            epoch=1,
            timestamp=now,
            metadata={"initial": True, "loaded_state": initial_state.value}
        )

        snapshot = TaskStateSnapshot(
            task_id=task_id,
            state=initial_state,
            epoch=1,
            last_transition=initial_transition,
            created_at=now,
            updated_at=now
        )

        self._snapshots[task_id] = snapshot
        return snapshot

    async def _is_duplicate_transition(self, task_id: str, cause_id: str) -> bool:
        """检查是否为重复的状态转换请求"""
        return cause_id in self._duplicate_causes.get(task_id, set())

    async def _emit_invalid_transition(
        self,
        task_id: str,
        from_state: TrainingState,
        to_state: TrainingState,
        cause_id: str
    ) -> None:
        """发送非法状态转换事件"""
        logger.error(f"非法状态转换: {task_id} {from_state.value} -> {to_state.value} (cause: {cause_id})")

        await self._event_bus.emit('state.invalid_transition', {
            'task_id': task_id,
            'from_state': from_state.value,
            'to_state': to_state.value,
            'cause_id': cause_id,
            'timestamp': datetime.now().timestamp(),
            'valid_transitions': [s.value for s in VALID_STATE_TRANSITIONS.get(from_state, [])]
        })

    async def get_tasks_by_state(self, state: TrainingState) -> List[str]:
        """获取指定状态的所有任务ID"""
        return [
            task_id for task_id, snapshot in self._snapshots.items()
            if snapshot.state == state
        ]

    async def get_active_tasks(self) -> List[str]:
        """获取所有活跃状态的任务ID"""
        active_states = [TrainingState.RUNNING]
        return [
            task_id for task_id, snapshot in self._snapshots.items()
            if snapshot.state in active_states
        ]

    async def get_terminal_tasks(self) -> List[str]:
        """获取所有终态的任务ID"""
        terminal_states = [TrainingState.COMPLETED, TrainingState.FAILED, TrainingState.CANCELLED]
        return [
            task_id for task_id, snapshot in self._snapshots.items()
            if snapshot.state in terminal_states
        ]

    async def get_statistics(self) -> Dict[str, any]:
        """获取状态管理器统计信息"""
        stats = {
            'total_tasks': len(self._snapshots),
            'state_counts': {},
            'total_transitions': sum(len(transitions) for transitions in self._transitions.values()),
            'active_tasks': len(await self.get_active_tasks()),
            'terminal_tasks': len(await self.get_terminal_tasks())
        }

        # 统计各状态任务数量
        for state in TrainingState:
            tasks = await self.get_tasks_by_state(state)
            stats['state_counts'][state.value] = len(tasks)

        return stats


# 全局状态管理器实例
_global_state_manager: Optional[TrainingStateManager] = None


def get_state_manager() -> TrainingStateManager:
    """获取全局状态管理器实例"""
    global _global_state_manager
    if _global_state_manager is None:
        from .events import get_event_bus
        _global_state_manager = TrainingStateManager(get_event_bus())
    return _global_state_manager


def initialize_state_manager(event_bus: EventBus) -> TrainingStateManager:
    """初始化状态管理器（用于应用启动）"""
    global _global_state_manager
    _global_state_manager = TrainingStateManager(event_bus)
    logger.info("状态管理器初始化完成")
    return _global_state_manager