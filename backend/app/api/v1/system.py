"""
系统信息API路由
"""

from fastapi import APIRouter, HTTPException, Body
from typing import List
from datetime import datetime

from ...models.response import DataResponse
from ...models.system import GPUMetrics, SystemGPUResponse
from ...services.gpu_monitor import gpu_monitor, GPUMonitorError
from ...core.config import get_config, save_config
from pathlib import Path
import os

router = APIRouter()

@router.get("/system/gpus", response_model=DataResponse[List[str]])
async def get_system_gpus():
    """获取系统GPU列表（保持向后兼容）"""
    try:
        gpu_info = gpu_monitor.get_gpu_info()
        gpu_list = [f"GPU {gpu.id}: {gpu.name}" for gpu in gpu_info]
        if not gpu_list:
            gpu_list = ["未检测到GPU设备"]

        return DataResponse(
            data=gpu_list,
            message=f"获取到 {len(gpu_info)} 个GPU设备"
        )
    except GPUMonitorError as e:
        # 降级到模拟数据
        gpu_list = ["模拟GPU (GPU监控不可用)"]
        return DataResponse(
            data=gpu_list,
            message=f"GPU监控不可用，返回模拟数据: {str(e)}"
        )
    except Exception as e:
        # 返回错误但不中断
        gpu_list = ["GPU检测失败"]
        return DataResponse(
            data=gpu_list,
            message=f"GPU检测失败: {str(e)}"
        )


@router.get("/system/gpus/metrics", response_model=DataResponse[SystemGPUResponse])
async def get_gpu_metrics():
    """获取GPU详细指标信息"""
    try:
        gpu_info = gpu_monitor.get_gpu_info()

        # 如果没有检测到GPU，返回模拟数据用于开发测试
        if not gpu_info:
            gpu_info = gpu_monitor.get_mock_data()

        response_data = SystemGPUResponse(
            gpus=gpu_info,
            timestamp=datetime.now().isoformat(),
            total_gpus=len(gpu_info)
        )

        return DataResponse(
            data=response_data,
            message=f"成功获取 {len(gpu_info)} 个GPU的详细指标"
        )

    except GPUMonitorError as e:
        # 降级到模拟数据
        mock_data = gpu_monitor.get_mock_data()
        response_data = SystemGPUResponse(
            gpus=mock_data,
            timestamp=datetime.now().isoformat(),
            total_gpus=len(mock_data)
        )

        return DataResponse(
            data=response_data,
            message=f"GPU监控不可用，返回模拟数据: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取GPU指标失败: {str(e)}"
        )


@router.get("/system/gpus/{gpu_id}/metrics", response_model=DataResponse[GPUMetrics])
async def get_gpu_metrics_by_id(gpu_id: int):
    """获取指定GPU的详细指标"""
    try:
        gpu_info = gpu_monitor.get_gpu_info_by_id(gpu_id)

        if gpu_info is None:
            # 尝试从模拟数据中获取
            mock_data = gpu_monitor.get_mock_data()
            for gpu in mock_data:
                if gpu.id == gpu_id:
                    gpu_info = gpu
                    break

        if gpu_info is None:
            raise HTTPException(
                status_code=404,
                detail=f"GPU {gpu_id} 不存在"
            )

        return DataResponse(
            data=gpu_info,
            message=f"成功获取GPU {gpu_id}的指标信息"
        )

    except HTTPException:
        raise
    except GPUMonitorError as e:
        raise HTTPException(
            status_code=503,
            detail=f"GPU监控服务不可用: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取GPU {gpu_id}指标失败: {str(e)}"
        )

@router.get("/system/info", response_model=DataResponse[dict])
async def get_system_info():
    """获取系统信息"""
    import platform
    import psutil

    system_info = {
        "platform": platform.platform(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": psutil.virtual_memory().total,
        "memory_available": psutil.virtual_memory().available,
    }

    return DataResponse(
        data=system_info,
        message="获取系统信息成功"
    )


# ---------- Workspace 与 Runtime 状态 ----------

def _path_writable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        test_file = p / ".__writable_test__"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("ok")
        try:
            test_file.unlink()
        except Exception:
            pass
        return True
    except Exception:
        return False


@router.get("/system/workspace/status", response_model=DataResponse[dict])
async def workspace_status():
    try:
        cfg = get_config()
        workspace_root = cfg.storage.workspace_root

        # 判断是否未设置（仍为默认相对路径）
        if not workspace_root or workspace_root.strip() in ('.', './workspace', 'workspace', ''):
            return DataResponse(data={
                'path': workspace_root or '',
                'exists': False,
                'writable': False,
                'reason': 'NOT_SET',
            }, message="工作区未设置")

        # 已设置，解析为绝对路径进行检查
        root = Path(workspace_root).resolve()
        exists = root.exists()

        if not exists:
            reason = "NOT_FOUND"
            writable = False
        elif not _path_writable(root):
            reason = "NOT_WRITABLE"
            writable = False
        else:
            reason = "OK"
            writable = True

        return DataResponse(data={
            'path': str(root),
            'exists': exists,
            'writable': writable,
            'reason': reason,
        }, message="工作区状态")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工作区状态失败: {str(e)}")


@router.post("/system/workspace/select", response_model=DataResponse[dict])
async def select_workspace(payload: dict = Body(...)):
    new_path = (payload or {}).get('path')
    if not new_path or not str(new_path).strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "HTTPError", "error_code": "INVALID_PATH", "message": "无效的工作区路径"}
        )

    root = Path(new_path).resolve()

    # 检查目录是否存在（不自动创建）
    if not root.exists():
        raise HTTPException(
            status_code=400,
            detail={"error": "HTTPError", "error_code": "NOT_FOUND", "message": f"目录不存在: {root}"}
        )

    # 检查是否可写
    if not _path_writable(root):
        raise HTTPException(
            status_code=400,
            detail={"error": "HTTPError", "error_code": "NOT_WRITABLE", "message": f"目录无写入权限: {root}"}
        )

    # 更新环境管理器中的workspace路径（会自动保存配置）
    from ...core.environment import get_env_manager
    get_env_manager().update_workspace(str(root))

    # 动态更新静态目录挂载
    try:
        from ...main import app as fastapi_app
        if hasattr(fastapi_app.state, 'workspace_static'):
            fastapi_app.state.workspace_static.directory = str(root)
    except Exception:
        pass

    # 通知管理器刷新工作区
    tm_ok = False
    dm_ok = False
    try:
        from ...core.training.manager import get_training_manager
        tm = get_training_manager()
        if hasattr(tm, 'update_workspace'):
            tm_ok = bool(tm.update_workspace(str(root)))
    except Exception as e:
        import logging
        logging.exception("更新训练工作区失败")
    try:
        from ...core.dataset.manager import get_dataset_manager
        dm = get_dataset_manager()
        if hasattr(dm, 'update_workspace'):
            dm_ok = bool(dm.update_workspace(str(root)))
    except Exception:
        import logging
        logging.exception("更新数据集工作区失败")

    ready = bool(tm_ok and dm_ok)
    return DataResponse(
        data={
            'path': str(root),
            'ready': ready,
            'tasks_loaded': tm_ok,
            'datasets_loaded': dm_ok,
            'reason': 'OK'
        },
        message="工作区已设置"
    )


@router.get("/system/runtime/status", response_model=DataResponse[dict])
async def runtime_status():
    from ...core.environment import get_paths

    paths = get_paths()
    python_ok = paths.runtime_python_exists
    engines_ok = paths.engines_dir.exists()

    # 判断 reason
    if not python_ok:
        reason = "PYTHON_MISSING"
    elif not engines_ok:
        reason = "ENGINES_MISSING"
    else:
        reason = "OK"

    return DataResponse(data={
        'cwd': str(paths.project_root),
        'runtime_path': str(paths.runtime_dir),
        'python_present': python_ok,
        'engines_present': engines_ok,
        'reason': reason,
    }, message="运行时状态")
