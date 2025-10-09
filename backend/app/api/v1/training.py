"""
训练管理API路由
"""

from fastapi import APIRouter, HTTPException, Depends, Path, Body, Request, Response
from typing import List
import logging

from ...models.training import (
    TrainingTaskBrief, TrainingTaskDetail, CreateTrainingTaskRequest,
    TrainingModelSpec, TrainingConfigSchema, CLIPreviewRequest, CLIPreviewResponse,
    TrainingStats
)
from ...models.response import DataResponse, ListResponse, BaseResponse
from ...services.training_service import TrainingService, get_training_service
from ...core.exceptions import APIException

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/training/status", response_model=BaseResponse)
async def get_training_status():
    """获取训练服务状态"""
    return BaseResponse(message="训练服务运行正常")

@router.get("/training/models", response_model=DataResponse[List[TrainingModelSpec]])
async def get_training_models(
    service: TrainingService = Depends(get_training_service)
):
    """获取可用的训练模型列表"""
    try:
        models = service.get_available_models()
        return DataResponse(
            data=models,
            message=f"获取到 {len(models)} 个训练模型"
        )
    except Exception as e:
        logger.exception("获取训练模型失败")
        raise HTTPException(status_code=500, detail=f"获取训练模型失败: {str(e)}")

@router.get("/training/config/{training_type}", response_model=DataResponse[TrainingConfigSchema])
async def get_training_config_schema(
    training_type: str = Path(..., description="训练类型"),
    service: TrainingService = Depends(get_training_service)
):
    """获取训练配置模式"""
    try:
        schema = service.get_training_config_schema(training_type)
        return DataResponse(
            data=schema,
            message=f"获取训练配置模式成功: {training_type}"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("获取配置模式失败")
        raise HTTPException(status_code=500, detail=f"获取配置模式失败: {str(e)}")

@router.post("/training/preview-cli", response_model=DataResponse[CLIPreviewResponse])
async def preview_cli_command(
    request: CLIPreviewRequest = Body(..., description="CLI预览请求"),
    service: TrainingService = Depends(get_training_service)
):
    """预览训练CLI命令"""
    try:
        preview = service.preview_cli_command(request)
        return DataResponse(
            data=preview,
            message="生成CLI命令预览成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("生成CLI预览失败")
        raise HTTPException(status_code=500, detail=f"生成CLI预览失败: {str(e)}")

@router.get("/training/tasks", response_model=ListResponse[TrainingTaskBrief])
async def list_training_tasks(
    service: TrainingService = Depends(get_training_service)
):
    """获取训练任务列表"""
    try:
        tasks = service.list_tasks()
        return ListResponse(
            data=tasks,
            total=len(tasks),
            page=1,
            page_size=len(tasks),
            message=f"获取到 {len(tasks)} 个训练任务"
        )
    except Exception as e:
        logger.exception("获取训练任务列表失败")
        raise HTTPException(status_code=500, detail=f"获取训练任务列表失败: {str(e)}")

@router.post("/training/tasks", response_model=DataResponse[str], status_code=201)
async def create_training_task(
    request: CreateTrainingTaskRequest = Body(..., description="创建训练任务请求"),
    service: TrainingService = Depends(get_training_service)
):
    """创建训练任务"""
    try:
        task_id = await service.create_task(request)
        return DataResponse(
            data=task_id,
            message=f"创建训练任务成功: {request.name}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.exception("创建训练任务失败")
        raise HTTPException(status_code=500, detail=f"创建训练任务失败: {str(e)}")

@router.get("/training/tasks/{task_id}", response_model=DataResponse[TrainingTaskDetail])
async def get_training_task(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """获取训练任务详情"""
    try:
        task = service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="训练任务不存在")

        return DataResponse(
            data=task,
            message=f"获取训练任务详情成功: {task.name}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取训练任务详情失败")
        raise HTTPException(status_code=500, detail=f"获取训练任务详情失败: {str(e)}")

@router.post("/training/tasks/{task_id}/start", response_model=BaseResponse)
async def start_training_task(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """开始训练任务"""
    try:
        # 检查 Python 运行时是否存在
        from ...core.environment import get_paths
        paths = get_paths()
        if not paths.runtime_python_exists:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "HTTPError",
                    "error_code": "PYTHON_MISSING",
                    "message": "缺少 Python 运行时，请先安装运行时环境"
                }
            )

        success, message = await service.start_task(task_id)
        if success:
            return BaseResponse(message=f"开始训练任务成功: {message}")
        else:
            raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("开始训练任务失败")
        raise HTTPException(status_code=500, detail=f"开始训练任务失败: {str(e)}")

@router.post("/training/tasks/{task_id}/stop", response_model=BaseResponse)
async def stop_training_task(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """停止训练任务"""
    try:
        success, message = await service.stop_task(task_id)
        if success:
            return BaseResponse(message=f"停止训练任务成功: {message}")
        # 若返回失败，做一次幂等性校验：如果任务已非活跃，则视为已停止
        task = service.get_task(task_id)
        if task and getattr(task, 'state', None) and str(task.state) != 'running' and task.state != 'running':
            return BaseResponse(message="任务已处于非运行状态，无需停止")
        raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("停止训练任务失败")
        raise HTTPException(status_code=500, detail=f"停止训练任务失败: {str(e)}")

@router.delete("/training/tasks/{task_id}", status_code=204)
async def delete_training_task(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """删除训练任务"""
    try:
        success, message = await service.delete_task(task_id)
        if success:
            return Response(status_code=204)
        else:
            raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除训练任务失败")
        raise HTTPException(status_code=500, detail=f"删除训练任务失败: {str(e)}")

@router.post("/training/tasks/{task_id}/refresh", response_model=BaseResponse)
async def refresh_training_files(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """刷新训练任务文件列表"""
    try:
        service.refresh_task_files(task_id)
        return BaseResponse(message="刷新文件列表成功")
    except Exception as e:
        logger.exception("刷新文件列表失败")
        raise HTTPException(status_code=500, detail=f"刷新文件列表失败: {str(e)}")

@router.get("/training/stats", response_model=DataResponse[TrainingStats])
async def get_training_stats(
    service: TrainingService = Depends(get_training_service)
):
    """获取训练统计信息"""
    try:
        stats = service.get_training_stats()
        return DataResponse(
            data=stats,
            message="获取训练统计信息成功"
        )
    except Exception as e:
        logger.exception("获取训练统计信息失败")
        raise HTTPException(status_code=500, detail=f"获取训练统计信息失败: {str(e)}")

@router.get("/training/tasks/{task_id}/samples")
async def get_task_samples(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """获取训练任务的采样图片列表"""
    try:
        samples = service.list_sample_images(task_id)
        return {"items": samples}
    except Exception as e:
        logger.exception("获取采样图片失败")
        raise HTTPException(status_code=500, detail=f"获取采样图片失败: {str(e)}")

@router.get("/training/tasks/{task_id}/artifacts")
async def get_task_artifacts(
    task_id: str = Path(..., description="训练任务ID"),
    service: TrainingService = Depends(get_training_service)
):
    """获取训练任务的模型文件列表"""
    try:
        artifacts = service.list_artifacts(task_id)
        return {"items": artifacts}
    except Exception as e:
        logger.exception("获取模型文件失败")
        raise HTTPException(status_code=500, detail=f"获取模型文件失败: {str(e)}")

@router.get("/training/tasks/{task_id}/files/{subpath:path}")
async def get_task_file(
    request: Request,
    task_id: str = Path(..., description="训练任务ID"),
    subpath: str = Path(..., description="文件子路径")
):
    """获取训练任务的文件（统一文件网关）"""
    try:
        from ...utils.files import FileUtils

        # 验证文件路径并获取文件
        file_path = FileUtils.validate_task_file_path(task_id, subpath)

        # 创建文件响应
        return FileUtils.create_file_response(file_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取文件失败")
        raise HTTPException(status_code=500, detail=f"获取文件失败: {str(e)}")

@router.get("/training/tasks/{task_id}/metrics")
async def get_training_metrics(
    task_id: str = Path(..., description="训练任务ID")
):
    """获取训练指标数据（Loss和学习率曲线）"""
    try:
        from ...services.tb_event_service import get_tb_event_service

        svc = get_tb_event_service()
        data = svc.parse_scalars(task_id, keep=("loss", "learning_rate", "epoch"))

        if not data:
            # 空状态返回 200 + 空数据
            return {"data": {}, "message": "暂无TensorBoard标量数据"}

        return {"data": data, "message": "获取训练指标成功"}

    except Exception as e:
        logger.exception("获取训练指标失败")
        raise HTTPException(status_code=500, detail=f"获取训练指标失败: {str(e)}")
