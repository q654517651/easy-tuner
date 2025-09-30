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
    loop = asyncio.get_event_loop()
    # 计划在 100ms 后退出进程
    loop.call_later(0.1, lambda: os._exit(0))
    return BaseResponse(message="shutdown scheduled")

