"""
统一状态模型定义 - 系统的单一真实源
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime


class TrainingState(str, Enum):
    """统一的训练状态枚举 - 整个系统的单一真实源"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        """判断是否为终态"""
        return self in [self.COMPLETED, self.FAILED, self.CANCELLED]

    def is_active(self) -> bool:
        """判断是否为活跃状态（需要WebSocket连接）"""
        return self in [self.RUNNING]


@dataclass
class StateTransition:
    """状态转换记录"""
    from_state: TrainingState
    to_state: TrainingState
    task_id: str
    cause_id: str
    epoch: int
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    def is_restart(self) -> bool:
        """判断是否为重启转换"""
        return (
            self.from_state.is_terminal() and
            self.to_state == TrainingState.RUNNING
        )


@dataclass
class TaskStateSnapshot:
    """任务状态快照"""
    task_id: str
    state: TrainingState
    epoch: int  # 状态机版本号，每次重启递增
    last_transition: StateTransition
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式用于序列化"""
        return {
            'task_id': self.task_id,
            'state': self.state.value,
            'epoch': self.epoch,
            'last_transition': {
                'from_state': self.last_transition.from_state.value,
                'to_state': self.last_transition.to_state.value,
                'cause_id': self.last_transition.cause_id,
                'timestamp': self.last_transition.timestamp.isoformat(),
                'metadata': self.last_transition.metadata
            },
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


@dataclass
class TrainingEvent:
    """训练事件模型"""
    type: str  # "state", "log", "metric", "file"
    task_id: str
    epoch: int
    sequence: int
    timestamp: float
    payload: Dict[str, Any]

    def to_websocket_message(self) -> Dict[str, Any]:
        """转换为WebSocket消息格式"""
        return {
            'version': 1,
            'type': self.type,
            'task_id': self.task_id,
            'epoch': self.epoch,
            'sequence': self.sequence,
            'timestamp': self.timestamp,
            'payload': self.payload
        }


# 状态转换约束定义（简化：去掉PREPARING状态）
VALID_STATE_TRANSITIONS = {
    TrainingState.PENDING: [TrainingState.RUNNING, TrainingState.FAILED, TrainingState.CANCELLED],
    TrainingState.RUNNING: [TrainingState.COMPLETED, TrainingState.FAILED, TrainingState.CANCELLED],
    TrainingState.FAILED: [TrainingState.RUNNING],  # 重启直接到RUNNING
    TrainingState.CANCELLED: [TrainingState.RUNNING],  # 重启直接到RUNNING
    TrainingState.COMPLETED: [TrainingState.RUNNING],  # 重启直接到RUNNING
}


def is_valid_transition(from_state: TrainingState, to_state: TrainingState) -> bool:
    """检查状态转换是否合法"""
    return to_state in VALID_STATE_TRANSITIONS.get(from_state, [])


def is_restart_transition(from_state: TrainingState, to_state: TrainingState) -> bool:
    """检查是否为重启转换"""
    return from_state.is_terminal() and to_state == TrainingState.RUNNING