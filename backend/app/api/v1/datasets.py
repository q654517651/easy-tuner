"""
数据集API路由
"""

from fastapi import APIRouter, Query, Path, HTTPException, Depends, UploadFile, File, Form, Body
from typing import List, Optional

from ...models.dataset import (
    DatasetBrief, DatasetDetail, CreateDatasetRequest,
    ImportMediaRequest, UpdateCaptionRequest, DatasetStats,
    RenameDatasetRequest
)
from ...models.response import DataResponse, ListResponse, BaseResponse
from ...services.dataset_service import DatasetService, get_dataset_service
from ...core.exceptions import APIException
from ...core.dataset.models import DatasetType

router = APIRouter()

@router.get("/datasets", response_model=ListResponse[DatasetBrief])
async def list_datasets(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=100, description="每页数量"),
    service: DatasetService = Depends(get_dataset_service)
):
    """获取数据集列表"""
    try:
        # 获取数据集列表（同步调用）
        all_datasets = service.list_datasets()

        # 手动分页处理
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        datasets = all_datasets[start_idx:end_idx]
        total = len(all_datasets)
        return ListResponse(
            data=datasets,
            total=total,
            page=page,
            page_size=page_size,
            message=f"获取到 {len(datasets)} 个数据集"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"list_datasets未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取数据集列表失败: {str(e)}")

@router.get("/datasets/types")
async def get_dataset_types():
    """获取所有数据集类型枚举"""
    types = [
        {
            "value": ds_type.value,
            "label": ds_type.display_name
        }
        for ds_type in DatasetType
    ]
    return {"success": True, "data": types}

@router.get("/datasets/{dataset_id}", response_model=DataResponse[DatasetDetail])
async def get_dataset(
    dataset_id: str = Path(..., description="数据集ID"),
    media_page: int = Query(1, ge=1, description="媒体文件页码"),
    media_page_size: int = Query(50, ge=1, le=100, description="媒体文件每页数量"),
    service: DatasetService = Depends(get_dataset_service)
):
    """获取数据集详情"""
    try:
        # 调用服务获取数据集详情（包含媒体文件分页）
        dataset = service.get_dataset(
            dataset_id=dataset_id,
            media_page=media_page,
            media_page_size=media_page_size
        )

        # 检查数据集是否存在
        if dataset is None:
            raise HTTPException(status_code=404, detail="数据集不存在")
        return DataResponse(
            data=dataset,
            message=f"获取数据集详情成功: {dataset.name}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/datasets", response_model=DataResponse[DatasetDetail], status_code=201)
async def create_dataset(
    request: CreateDatasetRequest,
    service: DatasetService = Depends(get_dataset_service)
):
    """创建数据集"""
    try:
        success, message, dataset_id = service.create_dataset(request)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        # 创建成功后获取数据集详情
        dataset = service.get_dataset(dataset_id)
        return DataResponse(
            data=dataset,
            message=f"创建数据集成功: {dataset.name}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.post("/datasets/{dataset_id}/upload", response_model=DataResponse[dict])
async def upload_media_files(
    dataset_id: str = Path(..., description="数据集ID"),
    files: List[UploadFile] = File(..., description="上传的媒体文件"),
    service: DatasetService = Depends(get_dataset_service)
):
    """上传媒体文件到数据集"""
    try:
        result = await service.upload_media_files(dataset_id, files)
        return DataResponse(
            data=result,
            message=f"上传完成: 成功 {result['success_count']}/{result['total_files']} 个文件"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"upload_media_files未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传文件失败: {str(e)}")

@router.put("/datasets/{dataset_id}/media/{filename}/caption", response_model=BaseResponse)
async def update_media_caption(
    request: UpdateCaptionRequest,
    dataset_id: str = Path(..., description="数据集ID"),
    filename: str = Path(..., description="文件名"),
    service: DatasetService = Depends(get_dataset_service)
):
    """更新媒体文件标注"""
    try:
        success = service.update_label(dataset_id, filename, request.caption)
        if success:
            return BaseResponse(message="更新标注成功")
        else:
            raise HTTPException(status_code=500, detail="更新标注失败")
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"update_media_caption未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"更新标注失败: {str(e)}")

@router.delete("/datasets/{dataset_id}/media/{filename}", response_model=BaseResponse)
async def delete_media_file(
    dataset_id: str = Path(..., description="数据集ID"),
    filename: str = Path(..., description="文件名"),
    service: DatasetService = Depends(get_dataset_service)
):
    """删除数据集中的媒体文件"""
    try:
        success, message = service.delete_media_file(dataset_id, filename)
        if success:
            return BaseResponse(message=message)
        else:
            raise HTTPException(status_code=500, detail=message)
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"delete_media_file未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@router.put("/datasets/{dataset_id}/rename", response_model=DataResponse[DatasetDetail])
async def rename_dataset(
    dataset_id: str = Path(..., description="数据集ID"),
    request: RenameDatasetRequest = Body(..., description="重命名请求"),
    service: DatasetService = Depends(get_dataset_service)
):
    """重命名数据集"""
    try:
        success, message = service.rename_dataset(dataset_id, request.new_name)
        if not success:
            raise HTTPException(status_code=400, detail=message)

        # 重命名成功后获取数据集详情
        dataset = service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="数据集不存在")

        return DataResponse(
            data=dataset,
            message=f"数据集重命名成功: {request.new_name}"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"rename_dataset未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"重命名数据集失败: {str(e)}")

@router.delete("/datasets/{dataset_id}", response_model=BaseResponse)
async def delete_dataset(
    dataset_id: str = Path(..., description="数据集ID"),
    service: DatasetService = Depends(get_dataset_service)
):
    """删除数据集"""
    try:
        success, message = service.delete_dataset(dataset_id)
        if success:
            return BaseResponse(message="删除数据集成功")
        else:
            raise HTTPException(status_code=500, detail="删除数据集失败")
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/datasets-stats", response_model=DataResponse[DatasetStats])
async def get_dataset_stats(
    service: DatasetService = Depends(get_dataset_service)
):
    """获取数据集统计信息"""
    try:
        # 暂时返回简化的统计信息
        stats = DatasetStats(
            total_datasets=len(service.list_datasets()),
            total_media_files=0,
            total_labeled_files=0,
            storage_usage=0,
            by_type={}
        )
        return DataResponse(
            data=stats,
            message="获取统计信息成功"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/datasets/{dataset_id}/tags/stats", response_model=DataResponse[List[dict]])
async def get_dataset_tag_stats(
    dataset_id: str = Path(..., description="数据集ID"),
    service: DatasetService = Depends(get_dataset_service)
):
    """获取数据集标签统计"""
    try:
        tag_stats = service.get_dataset_tag_stats(dataset_id)
        if tag_stats is None:
            raise HTTPException(status_code=404, detail="数据集不存在")

        return DataResponse(
            data=tag_stats,
            message=f"获取数据集 {dataset_id} 标签统计成功"
        )
    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"get_dataset_tag_stats未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取标签统计失败: {str(e)}")

@router.post("/datasets/{dataset_id}/control-images", response_model=DataResponse[dict])
async def upload_control_image(
    dataset_id: str = Path(..., description="数据集ID"),
    original_filename: str = Form(..., description="原图文件名"),
    control_index: int = Form(..., description="控制图索引 (0-2)"),
    control_file: UploadFile = File(..., description="控制图文件"),
    service: DatasetService = Depends(get_dataset_service)
):
    """上传控制图"""
    try:
        result = await service.upload_control_image(dataset_id, original_filename, control_index, control_file)

        if result["success"]:
            return DataResponse(
                data=result,
                message=f"成功上传控制图 {result['control_filename']}"
            )
        else:
            raise HTTPException(status_code=400, detail=result["error"])

    except APIException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        import traceback
        print(f"upload_control_image未处理异常: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传控制图失败: {str(e)}")