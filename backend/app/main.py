"""
FastAPI主应用入口
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn
import asyncio
import logging

from .api.v1 import datasets, labeling, training, system
from .api.v1 import images as images_module
from .api import internal as internal_module
from .api.v1 import settings as settings_module
from .api.websocket import websocket_router
from .core.config import get_config
from .core.exceptions import setup_exception_handlers
from .core.schema_manager import schema_manager
from .core.state.manager import initialize_state_manager
from .core.state.events import initialize_event_bus
from .core.websocket.manager import initialize_websocket_manager
from .services.file_monitor_bridge import initialize_file_monitor_bridge
from .core.training.manager import initialize_training_manager
from .core.environment import init_environment
from .utils.logger import log_info, log_warn, log_error
from .utils.parent_monitor import start_parent_monitor, stop_parent_monitor
from .services.cleanup_service import cleanup_expired_temp_files

# 获取配置
settings = get_config()
logger = logging.getLogger("uvicorn.error")


# 定时清理任务（异步）
async def periodic_cleanup_task():
    """定时清理过期临时文件（每小时执行一次）"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1小时
            await asyncio.to_thread(cleanup_expired_temp_files)
        except asyncio.CancelledError:
            log_info("定时清理任务已取消")
            break
        except Exception as e:
            log_error(f"定时清理任务执行失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理"""

    # ① 保存主事件循环引用
    loop = asyncio.get_running_loop()
    app.state.main_loop = loop
    logger.info("Main event loop captured and stored at app.state.main_loop")

    # 启动时初始化
    # ① 初始化环境管理器（最高优先级，不强制验证，允许后续通过 API 修复）
    log_info("初始化环境管理器...")
    try:
        paths = init_environment(validate=False)
        log_info(f"环境初始化完成: project_root={paths.project_root}")
    except Exception as e:
        log_error(f"环境初始化失败: {e}")
        # 不中断启动，允许用户通过 API 设置

    log_info("初始化模型路径Schema...")
    schema_manager.initialize()
    log_info(f"Schema初始化完成，加载了 {len(schema_manager.get_schema())} 个模型配置")

    # 初始化新架构组件（注意顺序：先WebSocket，再EventBus）
    log_info("初始化WebSocket管理器...")
    websocket_manager = initialize_websocket_manager()
    log_info("初始化事件总线...")
    event_bus = initialize_event_bus(websocket_manager, loop)
    # 设置WebSocket管理器的事件总线引用
    websocket_manager.set_event_bus(event_bus)
    log_info("初始化状态管理器...")
    state_manager = initialize_state_manager(event_bus)
    log_info("初始化文件监控桥接...")
    initialize_file_monitor_bridge(event_bus, state_manager)
    log_info("初始化训练管理器...")
    training_manager = initialize_training_manager(state_manager, event_bus, loop)
    log_info("新架构组件初始化完成")

    # ② 启动父进程监控（自杀保险机制）
    log_info("启动父进程监控...")
    start_parent_monitor(loop)

    # ③ 启动定时清理任务
    log_info("启动定时清理任务...")
    cleanup_task = asyncio.create_task(periodic_cleanup_task())

    yield

    # 关闭时清理
    log_info("🛑 应用关闭中...")

    # 取消定时清理任务
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    stop_parent_monitor()
    log_info("父进程监控已停止")


# 创建FastAPI应用
app = FastAPI(
    title="EasyTuner API",
    description="EasyTuner 数据集管理和AI训练平台 API",
    version="0.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
# CORS：开发态允许本地端口，打包态（file:// → Origin:null）通过正则放行
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173","http://127.0.0.1:5173",
        "http://localhost:5174","http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:6006", "http://127.0.0.1:6006",  # 云服务器端口
        "http://0.0.0.0:6006",  # 云服务器监听所有接口
    ],
    allow_origin_regex=r".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 设置异常处理器
setup_exception_handlers(app)

# 注册API路由
app.include_router(datasets.router, prefix="/api/v1", tags=["datasets"])
app.include_router(labeling.router, prefix="/api/v1", tags=["labeling"])
app.include_router(training.router, prefix="/api/v1", tags=["training"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(settings_module.router, prefix="/api/v1", tags=["settings"])
app.include_router(images_module.router, prefix="/api/v1", tags=["images"])
app.include_router(internal_module.router, tags=["internal"])  # /__internal__/shutdown

# 注册WebSocket路由
app.include_router(websocket_router, prefix="/ws")

# 动态静态文件路由 - 支持运行时切换工作区路径
@app.get("/workspace/{path:path}")
async def serve_workspace_file(path: str):
    """
    动态静态文件服务端点

    每次请求都从配置读取 workspace_root，每次请求都生效
    """
    from fastapi.responses import FileResponse

    cfg = get_config()
    workspace_root = Path(cfg.storage.workspace_root).resolve()
    file_path = (workspace_root / path.lstrip("/")).resolve()

    # 安全：禁止越界
    if not str(file_path).startswith(str(workspace_root)):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Not Found")

    if not file_path.is_file():
        raise HTTPException(status_code=403, detail="Not a file")

    # 直接返回文件（FileResponse 自带 Content-Length/Last-Modified）
    return FileResponse(
        path=file_path,
        # 简单缓存头
        headers={"Cache-Control": "no-cache"}
    )

@app.get("/")
async def root():
    return {"message": "Welcome to EasyTuner API"}

@app.get("/health")
async def health_check():
    """简单健康检查（向后兼容）"""
    return {"status": "healthy"}

@app.get("/healthz")
async def healthz():
    """快速健康检查 - 仅验证 HTTP 层就绪"""
    return {"status": "ok", "phase": "ready"}

@app.get("/readyz")
async def readyz():
    """业务级就绪检查 - 验证所有组件已初始化"""
    try:
        # 检查关键组件是否已初始化
        if not hasattr(app.state, 'main_loop'):
            return {"status": "initializing", "phase": "initializing", "ready": False}
        return {"status": "ok", "phase": "ready", "ready": True}
    except Exception as e:
        return {"status": "error", "phase": "initializing", "ready": False, "error": str(e)}

