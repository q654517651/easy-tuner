#!/usr/bin/env python3
"""
EasyTuner FastAPI 后端启动脚本
"""

# ---- Windows 事件循环策略设置（必须在最开始） ----
import sys
if sys.platform == 'win32':
    import asyncio
    # 使用 ProactorEventLoop 以支持子进程（create_subprocess_exec）
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# sys.path.insert(0, str(project_root / "src"))  # 新架构不再需要
sys.path.insert(0, str(project_root / "backend"))

def main():
    """启动FastAPI服务器"""

    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(project_root))

    # 导入 app 对象（这会执行 app.__init__.py 中的策略设置）
    from app.main import app

    # 启动服务器（传递对象而非字符串）
    uvicorn.run(
        app,  # 直接传递 app 对象，确保策略在主进程和子进程中都生效
        host="127.0.0.1",
        port=8000,
        reload=False,
        reload_dirs=[str(Path(__file__).parent)],
        log_level="info",
        access_log=True,
        ws_ping_interval=20,
        ws_ping_timeout=20
    )

if __name__ == "__main__":
    main()