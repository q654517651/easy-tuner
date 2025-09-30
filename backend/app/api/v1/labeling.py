"""
打标服务API路由
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List

from ...models.labeling import (
    BatchLabelingRequest, LabelingProgress, LabelingResult, AvailableModel
)
from ...models.response import DataResponse, ListResponse, BaseResponse, TaskResponse
from ...services.labeling_service import get_labeling_service_api
from ...core.exceptions import APIException

router = APIRouter()

def get_labeling_service():
    """依赖注入：获取打标服务"""
    return get_labeling_service_api()

@router.get("/labeling/models", response_model=ListResponse[AvailableModel])
async def get_available_models(
    service = Depends(get_labeling_service)
):
    """获取可用的打标模型"""
    try:
        models = await service.get_available_models()
        return ListResponse(
            data=models,
            total=len(models),
            message=f"获取到 {len(models)} 个可用模型"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@router.post("/labeling/batch", response_model=TaskResponse, status_code=202)
async def start_batch_labeling(
    request: BatchLabelingRequest,
    service = Depends(get_labeling_service)
):
    """启动批量打标任务"""
    try:
        task_id = await service.start_batch_labeling(request)
        return TaskResponse(
            task_id=task_id,
            status="started",
            message=f"批量打标任务已启动，任务ID: {task_id}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动批量打标失败: {str(e)}")

@router.get("/labeling/progress/{task_id}", response_model=DataResponse[LabelingProgress])
async def get_labeling_progress(
    task_id: str = Path(..., description="任务ID"),
    service = Depends(get_labeling_service)
):
    """获取打标进度"""
    try:
        progress = await service.get_labeling_progress(task_id)
        return DataResponse(
            data=progress,
            message=f"获取任务进度成功: {progress.status.value}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务进度失败: {str(e)}")

@router.get("/labeling/result/{task_id}", response_model=DataResponse[LabelingResult])
async def get_labeling_result(
    task_id: str = Path(..., description="任务ID"),
    service = Depends(get_labeling_service)
):
    """获取打标结果"""
    try:
        result = await service.get_labeling_result(task_id)
        return DataResponse(
            data=result,
            message=f"获取任务结果成功: 成功 {result.successful_count}/{result.total_processed}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务结果失败: {str(e)}")

@router.post("/labeling/cancel/{task_id}", response_model=BaseResponse)
async def cancel_labeling_task(
    task_id: str = Path(..., description="任务ID"),
    service = Depends(get_labeling_service)
):
    """取消打标任务"""
    try:
        success = await service.cancel_labeling_task(task_id)
        if success:
            return BaseResponse(message="任务取消成功")
        else:
            raise HTTPException(status_code=500, detail="任务取消失败")
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")

@router.get("/labeling/history", response_model=ListResponse[LabelingProgress])
async def get_task_history(
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    service = Depends(get_labeling_service)
):
    """获取任务历史"""
    try:
        tasks = await service.get_task_history(limit=limit)
        return ListResponse(
            data=tasks,
            total=len(tasks),
            message=f"获取到 {len(tasks)} 个历史任务"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务历史失败: {str(e)}")

@router.get("/labeling/status")
async def get_labeling_status():
    """获取打标服务状态"""
    return {
        "service": "labeling",
        "status": "available", 
        "version": "2.0.0",
        "features": [
            "batch_labeling",
            "multiple_models", 
            "progress_tracking",
            "task_cancellation"
        ]
    }


class SingleLabelRequest(BaseModel):
    dataset_id: str
    filename: str
    prompt: str | None = None


@router.post("/labeling/single", response_model=DataResponse[dict])
async def label_single_image(
    request: SingleLabelRequest,
    service = Depends(get_labeling_service)
):
    """对单张图片进行打标，并返回生成的 caption"""
    try:
        result = await service.label_single(request.dataset_id, request.filename, request.prompt)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error") or "打标失败")
        return DataResponse(data=result, message="打标完成")
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"单张打标失败: {str(e)}")
