"""
父进程监控模块

用于检测 Electron 父进程是否存活，如果父进程退出则自动关闭后端。
这是一个保险机制，确保即使 Electron 异常退出也不会留下孤儿进程。
"""

import os
import sys
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _is_process_alive(pid: int) -> bool:
    """
    检查指定 PID 的进程是否存活

    Windows: 使用 tasklist 命令检查（CSV 解析）
    Unix: 使用 os.kill(pid, 0) 检查
    """
    if sys.platform == 'win32':
        import subprocess
        import csv
        from io import StringIO

        try:
            # 使用 tasklist 查找进程（静默模式，不输出到控制台）
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}', '/NH', '/FO', 'CSV'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # 隐藏窗口
            )

            # 检查输出是否为空
            output = result.stdout.strip()
            if not output:
                return False

            # CSV 格式解析（格式: "进程名","PID","会话名","会话编号","内存使用"）
            # 只要第二列严格匹配 PID，就认为进程存在
            try:
                reader = csv.reader(StringIO(output))
                for row in reader:
                    if len(row) >= 2 and row[1].strip() == str(pid):
                        return True
                return False
            except Exception as csv_err:
                # CSV 解析失败（极端情况），返回 False（保守策略）
                logger.warning(f"CSV 解析失败 (PID={pid}): {csv_err}")
                return False

        except Exception as e:
            logger.warning(f"检查进程 {pid} 存活状态失败: {e}")
            return False
    else:
        # Unix 系统：使用 os.kill(pid, 0)
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


async def _parent_monitor_task(
    parent_pid: int,
    check_interval: float = 3.0,
    grace_period: float = 5.0,
    failure_threshold: int = 3
):
    """
    父进程监控任务

    Args:
        parent_pid: 父进程 PID（Electron 主进程）
        check_interval: 检查间隔（秒）
        grace_period: 启动宽限期（秒），启动后该时间内不检查
        failure_threshold: 连续失败阈值，连续 N 次检查失败才判定父进程退出
    """
    logger.info(
        f"[父进程监控] 开始监控父进程 PID={parent_pid}，"
        f"检查间隔={check_interval}秒，宽限期={grace_period}秒，失败阈值={failure_threshold}次"
    )

    try:
        # 启动宽限期：等待后端和父进程完全就绪
        if grace_period > 0:
            logger.info(f"[父进程监控] 宽限期 {grace_period}秒，暂不检查")
            await asyncio.sleep(grace_period)

        consecutive_failures = 0

        while True:
            await asyncio.sleep(check_interval)

            is_alive = _is_process_alive(parent_pid)
            if not is_alive:
                consecutive_failures += 1
                logger.warning(
                    f"[父进程监控] 检测到父进程 PID={parent_pid} 不存在 "
                    f"(连续失败: {consecutive_failures}/{failure_threshold})"
                )

                # 达到连续失败阈值，触发自杀
                if consecutive_failures >= failure_threshold:
                    logger.error(
                        f"[父进程监控] 父进程连续 {consecutive_failures} 次检查失败，"
                        f"确认已退出，触发自杀机制"
                    )

                    # 触发优雅关闭
                    logger.info("[父进程监控] 正在执行优雅关闭...")
                    import signal
                    os.kill(os.getpid(), signal.SIGTERM)

                    # 如果 3 秒后还没退出，强制退出
                    await asyncio.sleep(3)
                    logger.error("[父进程监控] 优雅关闭超时，强制退出")
                    os._exit(1)
            else:
                # 父进程存在，重置失败计数
                if consecutive_failures > 0:
                    logger.info(f"[父进程监控] 父进程 PID={parent_pid} 检测正常，重置失败计数")
                    consecutive_failures = 0

    except asyncio.CancelledError:
        logger.info("[父进程监控] 监控任务已取消")
    except Exception as e:
        logger.error(f"[父进程监控] 监控任务异常: {e}")


_monitor_task: Optional[asyncio.Task] = None


def start_parent_monitor(loop: asyncio.AbstractEventLoop) -> None:
    """
    启动父进程监控

    从环境变量读取父进程 PID（ELECTRON_PPID）并启动监控任务。
    如果父进程退出，后端将自动关闭。

    Args:
        loop: asyncio 事件循环
    """
    global _monitor_task

    # 从环境变量读取父进程 PID
    parent_pid = os.environ.get('ELECTRON_PPID')
    if not parent_pid:
        logger.info("[父进程监控] 未检测到 ELECTRON_PPID 环境变量，跳过父进程监控")
        return

    try:
        parent_pid = int(parent_pid)
    except ValueError:
        logger.warning(f"[父进程监控] ELECTRON_PPID 格式错误: {parent_pid}")
        return

    # 验证父进程是否存在
    if not _is_process_alive(parent_pid):
        logger.warning(f"[父进程监控] 父进程 PID={parent_pid} 不存在，跳过监控")
        return

    # 启动监控任务
    _monitor_task = loop.create_task(_parent_monitor_task(parent_pid))
    logger.info(f"[父进程监控] 监控任务已启动")


def stop_parent_monitor() -> None:
    """
    停止父进程监控
    """
    global _monitor_task

    if _monitor_task and not _monitor_task.done():
        logger.info("[父进程监控] 停止监控任务...")
        _monitor_task.cancel()
        _monitor_task = None
