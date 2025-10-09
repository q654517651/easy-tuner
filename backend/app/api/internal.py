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
    - 为避免阻塞响应，先返回成功，再调度一个极短延迟后退出进程。
    """
    from ..utils.logger import log_info
    log_info("收到关闭信号，准备退出...")

    loop = asyncio.get_event_loop()

    def force_exit():
        log_info("强制退出后端进程")
        os._exit(0)

    # 计划在 200ms 后强制退出进程（给响应留足时间）
    loop.call_later(0.2, force_exit)
    return BaseResponse(message="shutdown scheduled")

