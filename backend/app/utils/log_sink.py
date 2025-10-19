from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from ..utils.logger import log_error
from ..utils.logger import log_info
from ..core.config import get_config


class LogSink:
    """统一日志写入与广播：
    - 负责将行级日志 append 写入 train.log
    - 通过 EventBus 广播 training.log 事件
    - 做最基础的去重与 CR 覆盖合并
    """

    def __init__(self, task_id: str, event_bus=None, workspace_root: Optional[str] = None):
        self.task_id = task_id
        self._event_bus = event_bus
        
        # 获取任务目录（支持新的 task_id--name 格式）
        from ..core.training.manager import get_training_manager
        training_manager = get_training_manager()
        task_dir = training_manager.get_task_dir(task_id)
        
        if task_dir:
            self._log_path = task_dir / 'train.log'
        else:
            # 回退到旧格式（兼容性，用于任务创建时目录尚未创建的情况）
            root = Path(workspace_root or 'workspace')
            self._log_path = root / 'tasks' / task_id / 'train.log'
        
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._log_path.open('a', encoding='utf-8')
        self._last_line: Optional[str] = None
        self._lines_written: int = 0
        self._buf: list[str] = []
        self._last_flush_ts: float = time.time()
        # 读取配置中的批推参数，保持默认值作为兜底
        try:
            cfg = get_config()
            self._flush_threshold_lines = max(1, int(getattr(getattr(cfg, 'logging', object()), 'log_batch_lines', 25)))
            self._flush_max_interval = float(getattr(getattr(cfg, 'logging', object()), 'log_batch_interval', 0.5))
        except Exception:
            self._flush_threshold_lines = 25
            self._flush_max_interval = 0.5  # 秒

    def write_line(self, line: str, phase: Optional[str] = None, level: str = 'info') -> None:
        try:
            if not isinstance(line, str):
                line = str(line)

            # 处理 CR 覆盖：若包含 \r，仅保留最后一段
            if '\r' in line:
                line = line.split('\r')[-1]

            # 简单相邻去重：相同内容则跳过
            if self._last_line == line:
                return

            self._fh.write(line + "\n")
            # 为了稳定优先：逐行 flush（后续可做批量 flush 优化）
            self._fh.flush()

            self._last_line = line
            self._lines_written += 1
            # 缓冲到批次
            self._buf.append(line)
            now = time.time()
            if (len(self._buf) >= self._flush_threshold_lines) or (now - self._last_flush_ts >= self._flush_max_interval):
                self._flush_batch()
        except Exception as e:
            log_error(f"写入日志失败: {e}")

    def close(self):
        try:
            # 关闭前尽量把批次刷出
            self._flush_batch()
            if self._fh:
                self._fh.close()
        except Exception:
            pass

    def _flush_batch(self):
        if not self._buf:
            return
        if self._event_bus is None:
            self._buf.clear()
            self._last_flush_ts = time.time()
            return
        try:
            batch = list(self._buf)
            new_offset = self._lines_written
            since_offset = max(new_offset - len(batch), 0)
            payload = {
                'task_id': self.task_id,
                'lines': batch,
                'since_offset': since_offset,
                'new_offset': new_offset,
                'timestamp': time.time(),
            }
            self._event_bus.emit_threadsafe('training.log_batch', payload)
        except Exception as e:
            log_error(f"日志批次广播失败: {e}")
        finally:
            self._buf.clear()
            self._last_flush_ts = time.time()
