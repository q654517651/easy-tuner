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
from .api import internal as internal_module
from .api.v1 import settings as settings_module
from .api.websocket_new import websocket_router
from .core.config import get_config
from .core.exceptions import setup_exception_handlers
from .core.schema_manager import schema_manager
from .core.state.manager import initialize_state_manager
from .core.state.events import initialize_event_bus
from .core.websocket.manager import initialize_websocket_manager
from .services.file_monitor_bridge import initialize_file_monitor_bridge
from .core.training.manager_new import initialize_training_manager

# 获取配置
settings = get_config()
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期管理"""

    # ① 保存主事件循环引用
    loop = asyncio.get_running_loop()
    app.state.main_loop = loop
    logger.info("Main event loop captured and stored at app.state.main_loop")

    # 启动时初始化
    print("初始化模型路径Schema...")
    schema_manager.initialize()
    print(f"Schema初始化完成，加载了 {len(schema_manager.get_schema())} 个模型配置")

    # 初始化新架构组件（注意顺序：先WebSocket，再EventBus）
    print("初始化WebSocket管理器...")
    websocket_manager = initialize_websocket_manager()
    print("初始化事件总线...")
    event_bus = initialize_event_bus(websocket_manager, loop)
    # 设置WebSocket管理器的事件总线引用
    websocket_manager.set_event_bus(event_bus)
    print("初始化状态管理器...")
    state_manager = initialize_state_manager(event_bus)
    print("初始化文件监控桥接...")
    initialize_file_monitor_bridge(event_bus, state_manager)
    print("初始化训练管理器...")
    training_manager = initialize_training_manager(state_manager, event_bus, loop)
    print("新架构组件初始化完成")

    yield

    # 关闭时清理（如果需要）
    print("🛑 应用关闭中...")


# 创建FastAPI应用
app = FastAPI(
    title="EasyTuner API",
    description="EasyTuner 数据集管理和AI训练平台 API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173","http://127.0.0.1:5173",
        "http://localhost:5174","http://127.0.0.1:5174",
        "http://localhost:5175", "http://127.0.0.1:5175",

    ],  # React开发服务器
    allow_credentials=True,
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
app.include_router(internal_module.router, tags=["internal"])  # /__internal__/shutdown

# 注册WebSocket路由
app.include_router(websocket_router, prefix="/ws")

# 挂载静态文件服务 - 用于提供数据集图片（目录不存在时不崩溃）
workspace_path = Path(settings.storage.workspace_root)
workspace_static = StaticFiles(directory=str(workspace_path), check_dir=False)
app.state.workspace_static = workspace_static
app.mount("/workspace", workspace_static, name="workspace")

@app.get("/")
async def root():
    return {"message": "Welcome to EasyTuner API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
