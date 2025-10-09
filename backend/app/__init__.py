"""
EasyTuner FastAPI Backend
"""

# ---- Windows 事件循环策略设置（必须在最开始） ----
# 这段代码确保 uvicorn reload 模式的子进程也能正确设置策略
import sys
if sys.platform == 'win32':
    import asyncio
    # 使用 ProactorEventLoop 以支持子进程（create_subprocess_exec）
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

__version__ = "2.0.0"