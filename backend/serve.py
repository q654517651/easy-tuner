"""
打包运行入口(无 reload)

用于 PyInstaller 打包为单文件 exe。
保持运行目录旁挂 runtime/ 与 workspace/ 目录。
"""

# ---- Windows 编码设置（必须在最开始） ----
import sys
import io

# 修复Windows GBK编码问题（支持emoji等Unicode字符）
if sys.platform == 'win32':
    # 设置控制台编码为UTF-8
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )
    except Exception:
        pass

# ---- Windows 事件循环策略设置 ----
if sys.platform == 'win32':
    import asyncio
    # 使用 ProactorEventLoop 以支持子进程（create_subprocess_exec）
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ---- 路径设置必须在任何 import 之前 ----
import os
import types
from pathlib import Path



# 兼容 PyInstaller 单文件
if getattr(sys, "frozen", False):  # running from EXE
    # 打包环境：EXE 在根目录，资源在 resources/backend
    project_root = Path(sys.executable).parent
    base_dir = project_root / "resources" / "backend"
else:
    # 开发环境：serve.py 在 backend/ 目录下
    base_dir = Path(__file__).parent  # backend/
    # 项目根是 backend 的父目录
    project_root = base_dir.parent

# 放入 sys.path,兼容 from app... 以及(历史遗留)from backend.app...
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

# 过渡期:把 backend.app 指到 app,避免遗留导入崩溃
try:
    import app as _app
    _backend = types.ModuleType("backend")
    _backend.app = _app
    sys.modules.setdefault("backend", _backend)
    sys.modules.setdefault("backend.app", _app)
except Exception:
    pass

# 环境变量(可选)
os.environ.setdefault("PYTHONPATH", str(project_root))
os.environ.setdefault("TAGTRAGGER_ROOT", str(project_root))


# ---- 现在可以正常 import 了 ----
import uvicorn
import atexit
import signal


def write_runtime_files(port: int):
    """写入运行时状态文件"""
    # 运行时文件应该放在项目根目录，而非 base_dir（打包环境下 base_dir 会多一层 resources/backend）
    runtime_dir = project_root / ".runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # 写入端口号
    (runtime_dir / "backend.port").write_text(str(port))
    # 写入进程 ID
    (runtime_dir / "backend.pid").write_text(str(os.getpid()))


def cleanup_runtime_files():
    """清理运行时状态文件"""
    # 运行时文件应该放在项目根目录，而非 base_dir
    runtime_dir = project_root / ".runtime"
    if runtime_dir.exists():
        for file in ["backend.port", "backend.pid"]:
            try:
                (runtime_dir / file).unlink(missing_ok=True)
            except Exception:
                pass


def signal_handler(signum, frame):
    """信号处理器"""
    cleanup_runtime_files()
    sys.exit(0)


def main():
    # 注册清理函数
    atexit.register(cleanup_runtime_files)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 获取端口（优先环境变量）
    port = int(os.environ.get("BACKEND_PORT", "8000"))

    # 写入运行时文件
    write_runtime_files(port)

    try:
        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=True,
            ws_ping_interval=20,
            ws_ping_timeout=20,
            reload=False,
        )
    finally:
        cleanup_runtime_files()


if __name__ == "__main__":
    main()
