"""
内部控制路由（仅供桌面应用/Electron 调用）
"""

from fastapi import APIRouter
from ..models.response import BaseResponse
import asyncio
import os

router = APIRouter()


@router.post("/__internal__/shutdown", response_model=BaseResponse)
async def internal_shutdown():
    """优雅关停后端进程（用于 Electron 主进程在退出时调用）。
    - 先执行清理，然后强制退出进程。
    """
    from ..utils.logger import log_info, log_error
    log_info("收到关闭信号，准备退出...")

    loop = asyncio.get_running_loop()  # 使用 get_running_loop，在协程中更可靠

    async def graceful_shutdown():
        """执行清理后退出"""
        try:
            log_info("开始执行清理流程...")

            # 1. 取消所有活跃的训练任务
            try:
                from ..core.training.manager import get_training_manager
                manager = get_training_manager()
                active_tasks = [task for task in manager.list_tasks() if task.state.is_active()]
                if active_tasks:
                    log_info(f"取消 {len(active_tasks)} 个活跃训练任务...")
                    for task in active_tasks:
                        try:
                            await manager.cancel_task(task.id)
                        except Exception as e:
                            log_error(f"取消任务失败 {task.id}: {e}")
            except Exception as e:
                log_error(f"取消训练任务失败: {e}")

            # 2. 取消所有后台异步任务
            try:
                tasks = [t for t in asyncio.all_tasks(loop) if not t.done() and t != asyncio.current_task()]
                if tasks:
                    log_info(f"取消 {len(tasks)} 个后台任务...")
                    for task in tasks:
                        task.cancel()
                    # 使用 gather 稳妥收尾，避免 CancelledError 噪音
                    await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                log_error(f"取消后台任务失败: {e}")

            # 3. 关闭所有 WebSocket 连接
            try:
                from ..core.websocket.manager import get_websocket_manager
                ws_manager = get_websocket_manager()
                await ws_manager.close_all()
            except Exception as e:
                log_error(f"关闭 WebSocket 连接失败: {e}")

            log_info("清理完成，准备退出")

        except Exception as e:
            log_error(f"清理流程异常: {e}")
        finally:
            # 无论如何都要退出
            log_info("强制退出后端进程")
            os._exit(0)

    # 在后台异步执行清理，最多 1.5 秒
    asyncio.create_task(graceful_shutdown())

    # 立即返回响应（避免阻塞前端）
    return BaseResponse(message="shutdown scheduled")

