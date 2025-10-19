"""
Dataset Service for FastAPI backend

This service provides all dataset-related operations for the EasyTuner application.
Uses the real DatasetManager from the core module.
"""

from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import threading
import tempfile
import shutil
from fastapi import UploadFile, Request
from pathlib import Path

from ..models.dataset import DatasetBrief, DatasetDetail, DatasetStats, CreateDatasetRequest, UpdateDatasetRequest
from ..core.dataset.manager import get_dataset_manager
from ..core.dataset.models import Dataset as CoreDataset, DatasetType
from ..core.exceptions import DatasetNotFoundError
from ..utils.logger import log_info, log_success, log_error
from ..utils.url_builder import build_workspace_url


class DatasetService:
    """Dataset service with real business logic using DatasetManager"""
    
    def __init__(self):
        self._dataset_manager = get_dataset_manager()
        self._lock = threading.Lock()
    
    def _convert_core_to_brief(self, core_dataset: CoreDataset) -> DatasetBrief:
        """Convert core Dataset to API DatasetBrief model"""
        stats = core_dataset.get_stats()

        return DatasetBrief(
            id=core_dataset.dataset_id,
            name=core_dataset.name,
            type=core_dataset.dataset_type,
            total_count=stats['total'],
            labeled_count=stats['labeled'],
            created_at=core_dataset.created_time,
            updated_at=core_dataset.modified_time
        )

    def _convert_core_to_detail(self, core_dataset: CoreDataset, request: Optional[Request] = None, media_page: int = 1, media_page_size: int = 50) -> DatasetDetail:
        """Convert core Dataset to API DatasetDetail model with media items"""
        from ..models.dataset import MediaItem, MediaType
        from pathlib import Path
        from ..core.config import get_config
        from datetime import datetime

        stats = core_dataset.get_stats()

        # 获取 workspace_root（提前计算，避免循环内重复）
        workspace_root = Path(get_config().storage.workspace_root).resolve()

        # 获取媒体文件列表
        media_items = []
        if hasattr(core_dataset, 'items') and core_dataset.items:
            items_list = list(core_dataset.items.items())

            # 分页处理
            start_idx = (media_page - 1) * media_page_size
            end_idx = start_idx + media_page_size
            paginated_items = items_list[start_idx:end_idx]

            for filename, item_data in paginated_items:
                # 使用 DatasetManager 获取实际文件路径
                actual_file_path = self._dataset_manager.get_dataset_image_path(core_dataset.dataset_id, filename)

                if actual_file_path:
                    # 将绝对路径转换为相对于 workspace_root 的路径，并构建完整URL
                    try:
                        abs_file = Path(actual_file_path).resolve()
                        rel_file = abs_file.relative_to(workspace_root)
                        file_path = rel_file.as_posix()
                        # ✅ 使用完整URL
                        file_url = build_workspace_url(request, file_path)
                    except Exception as e:
                        # 兜底：记录错误并使用默认路径
                        log_error(f"Build URL fallback: file={actual_file_path}", e)
                        file_path = f"datasets/{core_dataset.dataset_id}/images/{filename}"
                        file_url = build_workspace_url(request, file_path)
                else:
                    # 如果找不到文件，使用默认路径
                    log_info(f"File not found for dataset {core_dataset.dataset_id}, filename {filename}")
                    file_path = f"datasets/{core_dataset.dataset_id}/images/{filename}"
                    file_url = build_workspace_url(request, file_path)

                # 不再使用缩略图，直接使用原图
                thumbnail_url = file_url

                # 处理控制图信息（仅用于控制图数据集）
                control_images = None
                if core_dataset.dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value]:
                    # 首先检查item_data中是否已有control_images信息
                    if "control_images" in item_data and item_data["control_images"]:
                        # 使用已加载的控制图信息
                        control_images = self._format_control_images(core_dataset.dataset_id, item_data["control_images"], request)
                    else:
                        # 回退：重新扫描目录
                        control_images = self._get_control_images_for_item(core_dataset.dataset_id, filename, item_data, request)

                media_item = MediaItem(
                    id=f"{core_dataset.dataset_id}_{filename}",
                    filename=filename,
                    file_path=file_path,
                    url=file_url,
                    thumbnail_url=thumbnail_url,
                    media_type=MediaType.IMAGE,
                    caption=item_data.get("label", ""),
                    control_images=control_images,
                    file_size=0,  # 暂时不计算文件大小
                    dimensions=None,  # 暂时不获取图片尺寸
                    created_at=core_dataset.created_time,
                    updated_at=core_dataset.modified_time
                )
                media_items.append(media_item)

        return DatasetDetail(
            id=core_dataset.dataset_id,
            name=core_dataset.name,
            type=core_dataset.dataset_type,
            description=core_dataset.description,
            total_count=stats['total'],
            labeled_count=stats['labeled'],
            created_at=core_dataset.created_time,
            updated_at=core_dataset.modified_time,
            config={},
            media_items=media_items,
            media_total=len(core_dataset.items) if hasattr(core_dataset, 'items') else 0,
            media_page=media_page,
            media_page_size=media_page_size
        )
    
    def create_dataset(self, request: CreateDatasetRequest) -> Tuple[bool, str, Optional[str]]:
        """Create a new dataset and return success, message, and dataset_id"""
        success, message = self._dataset_manager.create_dataset(
            name=request.name,
            description=request.description or "",
            dataset_type=request.type.value  # 使用枚举的字符串值
        )

        if success:
            # 成功创建后，通过名称查找数据集ID
            datasets = self._dataset_manager.list_datasets()
            for ds in datasets:
                if ds.name == request.name:
                    return success, message, ds.dataset_id

        return success, message, None
    
    def get_dataset(self, dataset_id: str, request: Optional[Request] = None, media_page: int = 1, media_page_size: int = 50) -> Optional[DatasetDetail]:
        """Get a dataset by ID with media items"""
        core_dataset = self._dataset_manager.get_dataset(dataset_id)
        if core_dataset:
            return self._convert_core_to_detail(core_dataset, request, media_page, media_page_size)
        return None

    def list_datasets(self) -> List[DatasetBrief]:
        """Get all datasets"""
        core_datasets = self._dataset_manager.list_datasets()
        return [self._convert_core_to_brief(ds) for ds in core_datasets]
    
    # Note: 更新数据集接口未暴露且无引用，已移除以简化服务接口。

    def rename_dataset(self, dataset_id: str, new_name: str) -> Tuple[bool, str]:
        """重命名数据集"""
        with self._lock:
            try:
                success, message = self._dataset_manager.rename_dataset(dataset_id, new_name)
                if success:
                    log_success(f"数据集重命名成功: {dataset_id} -> {new_name}")
                else:
                    log_error(f"数据集重命名失败: {dataset_id}", None)
                return success, message
            except Exception as e:
                log_error(f"重命名数据集异常: {dataset_id} -> {new_name}", e)
                return False, f"重命名失败: {str(e)}"
    
    def delete_dataset(self, dataset_id: str) -> Tuple[bool, str]:
        """Delete a dataset"""
        return self._dataset_manager.delete_dataset(dataset_id)
    
    def get_dataset_stats(self, dataset_id: str) -> Optional[DatasetStats]:
        """Get dataset statistics"""
        core_dataset = self._dataset_manager.get_dataset(dataset_id)
        if not core_dataset:
            return None
        
        stats = core_dataset.get_stats()
        
        return DatasetStats(
            total_images=stats['total'],
            labeled_images=stats['labeled'],
            unlabeled_images=stats['unlabeled'],
            completion_rate=stats['completion_rate']
        )
    
    def import_images(self, dataset_id: str, image_paths: List[str]) -> Tuple[int, str]:
        """Import images to dataset"""
        return self._dataset_manager.import_files_to_dataset(dataset_id, image_paths)
    
    def update_label(self, dataset_id: str, filename: str, label: str) -> bool:
        """Update label for a specific image"""
        return self._dataset_manager.update_dataset_label(dataset_id, filename, label)
    
    def batch_update_labels(self, dataset_id: str, labels: Dict[str, str]) -> Tuple[int, str]:
        """Batch update labels"""
        return self._dataset_manager.batch_update_labels(dataset_id, labels)
    
    def search_datasets(self, keyword: str) -> List[DatasetBrief]:
        """Search datasets by keyword"""
        # 暂时简化搜索，后续完善
        all_datasets = self.list_datasets()
        filtered = [ds for ds in all_datasets if keyword.lower() in ds.name.lower()]
        return filtered
    
    def get_dataset_images(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Get all images in a dataset"""
        core_dataset = self._dataset_manager.get_dataset(dataset_id)
        if not core_dataset:
            return []
        
        images = []
        for filename, item_data in core_dataset.items.items():
            image_path = self._dataset_manager.get_dataset_image_path(dataset_id, filename)
            images.append({
                "filename": filename,
                "label": item_data.get("label", ""),
                "path": image_path,
                "control_image": item_data.get("control_image", "")
            })
        
        return images
    
    def get_image_path(self, dataset_id: str, filename: str) -> Optional[str]:
        """Get the full path of an image in the dataset"""
        return self._dataset_manager.get_dataset_image_path(dataset_id, filename)
    
    def export_dataset(self, dataset_id: str, export_path: str, format_type: str = "folder") -> Tuple[bool, str]:
        """Export dataset"""
        return self._dataset_manager.export_dataset(dataset_id, export_path, format_type)

    def get_dataset_tag_stats(self, dataset_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get tag statistics for a dataset"""
        try:
            core_dataset = self._dataset_manager.get_dataset(dataset_id)
            if not core_dataset:
                return None

            # 统计所有标签
            tag_count = {}
            tag_images = {}  # 记录每个标签出现在哪些图片中

            for filename, item_data in core_dataset.items.items():
                label = item_data.get("label", "")
                if label.strip():
                    # 按逗号分割标签（支持中文和英文逗号）
                    import re
                    tags = [tag.strip() for tag in re.split('[,，]', label) if tag.strip()]
                    for tag in tags:
                        if tag not in tag_count:
                            tag_count[tag] = 0
                            tag_images[tag] = []
                        tag_count[tag] += 1
                        tag_images[tag].append(f"{dataset_id}_{filename}")

            # 转换为API格式
            tag_stats = []
            for tag, count in tag_count.items():
                tag_stats.append({
                    "tag": tag,
                    "count": count,
                    "images": tag_images[tag]
                })

            # 按使用次数降序排序
            tag_stats.sort(key=lambda x: x["count"], reverse=True)

            log_info(f"获取数据集 {dataset_id} 标签统计，共 {len(tag_stats)} 个标签")
            return tag_stats

        except Exception as e:
            log_error(f"获取数据集标签统计失败: {dataset_id}", e)
            return None

    def _format_control_images(self, dataset_id: str, control_image_filenames: List[str], request: Optional[Request] = None) -> Optional[List[Any]]:
        """格式化已有的控制图信息"""
        from ..models.dataset import ControlImage
        from pathlib import Path
        from ..core.config import get_config

        if not control_image_filenames:
            return None

        try:
            workspace_root = Path(get_config().storage.workspace_root).resolve()
            control_images = []

            for control_filename in control_image_filenames:
                # 使用 DatasetManager 获取控制图的实际路径
                # 注意：这里假设控制图在 controls/ 目录下
                # 如果 DatasetManager 没有提供获取控制图路径的方法，我们需要手动构建
                dataset_info = self._dataset_manager.datasets.get(dataset_id)
                if not dataset_info:
                    logger.debug(f"数据集 {dataset_id} 不存在于内存中")
                    continue

                # 获取控制图路径
                dataset_path = dataset_info['path']
                control_path = dataset_path / 'controls' / control_filename

                if control_path.exists():
                    try:
                        abs_control = control_path.resolve()
                        rel_control = abs_control.relative_to(workspace_root)
                        control_rel_path = rel_control.as_posix()
                        # ✅ 使用完整URL
                        control_url = build_workspace_url(request, control_rel_path)
                    except Exception as e:
                        log_error(f"Build control URL fallback: file={control_path}", e)
                        # 兜底逻辑
                        warehouse_name = dataset_info['warehouse'].name
                        dataset_dir_name = dataset_path.name
                        control_rel_path = f"datasets/{warehouse_name}/{dataset_dir_name}/controls/{control_filename}"
                        control_url = build_workspace_url(request, control_rel_path)
                else:
                    # 文件不存在，使用默认路径
                    warehouse_name = dataset_info['warehouse'].name
                    dataset_dir_name = dataset_path.name
                    control_rel_path = f"datasets/{warehouse_name}/{dataset_dir_name}/controls/{control_filename}"
                    control_url = build_workspace_url(request, control_rel_path)

                control_images.append(ControlImage(
                    filename=control_filename,
                    url=control_url,
                    thumbnail_url=control_url  # 不再使用缩略图
                ))

            control_images.sort(key=lambda x: x.filename)
            return control_images if control_images else None

        except Exception as e:
            log_error(f"格式化控制图信息失败: {dataset_id}", e)
            return None

    def _get_control_images_for_item(self, dataset_id: str, filename: str, item_data: Dict[str, Any], request: Optional[Request] = None) -> Optional[List[Any]]:
        """获取指定原图的控制图列表"""
        from ..models.dataset import ControlImage
        from pathlib import Path
        from ..core.config import get_config

        try:
            # 获取数据集路径
            core_dataset = self._dataset_manager.get_dataset(dataset_id)
            if not core_dataset:
                return None

            # 获取正确的数据集路径
            dataset_info = self._dataset_manager.datasets.get(dataset_id)
            if not dataset_info:
                return None

            workspace_root = Path(get_config().storage.workspace_root).resolve()
            dataset_path = dataset_info['path']
            controls_dir = dataset_path / "controls"

            if not controls_dir.exists():
                return None

            control_images = []
            base_filename = Path(filename).stem  # 获取文件名（不含扩展名）

            # 查找控制图文件：支持多种命名模式
            # 1. 同名文件（不同扩展名）: image1.jpg -> image1.png
            # 2. 带索引的文件: image1.jpg -> image1_0.png, image1_1.png, image1_2.png
            # 3. 四位数字: image1.jpg -> image1_0000.png, image1_0001.png

            for control_file in controls_dir.iterdir():
                if not control_file.is_file():
                    continue

                control_basename = control_file.stem

                # 检查是否匹配
                if (control_basename == base_filename or
                    control_basename.startswith(f"{base_filename}_")):

                    # 使用相对路径构建 URL
                    try:
                        abs_control = control_file.resolve()
                        rel_control = abs_control.relative_to(workspace_root)
                        control_rel_path = rel_control.as_posix()
                        # ✅ 使用完整URL
                        control_url = build_workspace_url(request, control_rel_path)
                    except Exception as e:
                        log_error(f"Build control URL fallback: file={control_file}", e)
                        # 兜底逻辑
                        warehouse_name = dataset_info['warehouse'].name
                        control_rel_path = f"datasets/{warehouse_name}/{dataset_path.name}/controls/{control_file.name}"
                        control_url = build_workspace_url(request, control_rel_path)

                    control_images.append(ControlImage(
                        url=control_url,
                        filename=control_file.name,
                        thumbnail_url=control_url  # 不再使用缩略图
                    ))

            # 按文件名排序，确保显示顺序一致
            control_images.sort(key=lambda x: x.filename)

            return control_images if control_images else None

        except Exception as e:
            log_error(f"获取控制图失败: {dataset_id}/{filename}", e)
            return None

    def delete_media_file(self, dataset_id: str, filename: str) -> Tuple[bool, str]:
        """Delete a media file from dataset"""
        with self._lock:
            try:
                # 检查数据集是否存在
                core_dataset = self._dataset_manager.get_dataset(dataset_id)
                if not core_dataset:
                    return False, f"Dataset {dataset_id} not found"

                # 检查文件是否存在
                if filename not in core_dataset.items:
                    return False, f"File {filename} not found in dataset"

                # 获取文件路径
                file_path = self._dataset_manager.get_dataset_image_path(dataset_id, filename)
                if file_path and Path(file_path).exists():
                    # 删除实际文件
                    Path(file_path).unlink()
                    log_info(f"已删除文件: {file_path}")

                # 删除标签文件（如果存在）
                if file_path:
                    label_path = Path(file_path).with_suffix('.txt')
                    if label_path.exists():
                        label_path.unlink()
                        log_info(f"已删除标签文件: {label_path}")

                # 从数据集中移除记录
                del core_dataset.items[filename]
                core_dataset._update_modified_time()

                log_success(f"成功删除文件 {filename} 从数据集 {dataset_id}")
                return True, f"成功删除文件 {filename}"

            except Exception as e:
                log_error(f"删除文件失败: {filename}", e)
                return False, f"删除文件失败: {str(e)}"

    async def upload_media_files(self, dataset_id: str, files: List[UploadFile]) -> Dict[str, Any]:
        """Upload media files to dataset"""
        with self._lock:
            # 检查数据集是否存在
            core_dataset = self._dataset_manager.get_dataset(dataset_id)
            if not core_dataset:
                raise DatasetNotFoundError(
                    message=f"Dataset {dataset_id} not found",
                    detail={"dataset_id": dataset_id},
                    error_code="DATASET_NOT_FOUND",
                )

            total_files = len(files)
            success_count = 0
            failed_count = 0
            errors = []

            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_files = []

                # 先保存所有文件到临时目录
                for file in files:
                    try:
                        # 检查文件类型
                        if not file.filename:
                            continue

                        # 创建临时文件路径
                        temp_file_path = Path(temp_dir) / file.filename

                        # 保存文件内容
                        with open(temp_file_path, "wb") as temp_file:
                            content = await file.read()
                            temp_file.write(content)

                        temp_files.append(str(temp_file_path))
                        log_info(f"已保存临时文件: {file.filename}")

                    except Exception as e:
                        log_error(f"保存临时文件失败: {file.filename}", e)
                        errors.append(f"{file.filename}: {str(e)}")
                        failed_count += 1

                # 使用DatasetManager导入文件
                if temp_files:
                    try:
                        imported_count, message = self._dataset_manager.import_files_to_dataset(
                            dataset_id, temp_files
                        )
                        success_count = imported_count
                        failed_count = total_files - success_count
                        log_success(f"成功导入 {success_count} 个文件到数据集 {dataset_id}")
                    except Exception as e:
                        log_error(f"批量导入文件失败", e)
                        errors.append(f"批量导入失败: {str(e)}")
                        failed_count = total_files

            return {
                "total_files": total_files,
                "success_count": success_count,
                "failed_count": failed_count,
                "errors": errors
            }

    async def upload_control_image(self, dataset_id: str, original_filename: str, control_index: int, control_file: UploadFile, request: Optional[Request] = None) -> Dict[str, Any]:
        """为指定原图上传控制图"""
        with self._lock:
            try:
                # 检查数据集是否存在且为控制图类型
                core_dataset = self._dataset_manager.get_dataset(dataset_id)
                if not core_dataset:
                    raise DatasetNotFoundError(
                        message=f"Dataset {dataset_id} not found",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                if core_dataset.dataset_type not in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value]:
                    raise ValueError("只有控制图数据集支持上传控制图")

                # 检查原图是否存在
                if original_filename not in core_dataset.items:
                    raise ValueError(f"原图 {original_filename} 不存在")

                # 检查控制图索引范围 (0-2，最多3张控制图)
                if not 0 <= control_index <= 2:
                    raise ValueError("控制图索引必须在 0-2 之间")

                # 创建临时文件
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(control_file.filename).suffix) as temp_file:
                    content = await control_file.read()
                    temp_file.write(content)
                    temp_file_path = temp_file.name

                try:
                    # 构建控制图文件名
                    original_stem = Path(original_filename).stem
                    control_filename = f"{original_stem}_{control_index}{Path(control_file.filename).suffix}"

                    # 获取正确的数据集路径
                    dataset_info = self._dataset_manager.datasets.get(dataset_id)
                    if not dataset_info:
                        raise DatasetNotFoundError(
                            message=f"Dataset {dataset_id} not found in memory",
                            detail={"dataset_id": dataset_id},
                            error_code="DATASET_NOT_FOUND",
                        )

                    dataset_path = dataset_info['path']
                    controls_dir = dataset_path / "controls"
                    controls_dir.mkdir(parents=True, exist_ok=True)

                    control_dest_path = controls_dir / control_filename

                    # 复制文件到目标位置
                    import shutil
                    shutil.copy2(temp_file_path, control_dest_path)

                    log_info(f"成功上传控制图: {dataset_id}/{control_filename}")

                    # 构建正确的URL路径 (使用完整URL)
                    warehouse_dir = dataset_info['warehouse']
                    warehouse_name = warehouse_dir.name
                    dataset_dir_name = dataset_info['path'].name  # 实际的目录名，如 rlrr9k08--m--ttt
                    control_rel_path = f"datasets/{warehouse_name}/{dataset_dir_name}/controls/{control_filename}"
                    # ✅ 使用完整URL
                    control_url = build_workspace_url(request, control_rel_path)

                    return {
                        "success": True,
                        "control_filename": control_filename,
                        "control_url": control_url,
                        "control_index": control_index
                    }

                finally:
                    # 清理临时文件
                    import os
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass

            except Exception as e:
                log_error(f"上传控制图失败: {dataset_id}/{original_filename}", e)
                return {
                    "success": False,
                    "error": str(e)
                }

    def delete_control_image(self, dataset_id: str, original_filename: str, control_index: int) -> Dict[str, Any]:
        """删除指定原图的控制图"""
        with self._lock:
            try:
                # 检查数据集是否存在且为控制图类型
                core_dataset = self._dataset_manager.get_dataset(dataset_id)
                if not core_dataset:
                    raise DatasetNotFoundError(
                        message=f"Dataset {dataset_id} not found",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                if core_dataset.dataset_type not in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value]:
                    raise ValueError("只有控制图数据集支持删除控制图")

                # 检查原图是否存在
                if original_filename not in core_dataset.items:
                    raise ValueError(f"原图 {original_filename} 不存在")

                # 检查控制图索引范围 (0-2，最多3张控制图)
                if not 0 <= control_index <= 2:
                    raise ValueError("控制图索引必须在 0-2 之间")

                # 构建控制图文件名
                original_stem = Path(original_filename).stem
                
                # 获取数据集路径
                dataset_info = self._dataset_manager.datasets.get(dataset_id)
                if not dataset_info:
                    raise DatasetNotFoundError(
                        message=f"Dataset {dataset_id} not found in memory",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                dataset_path = dataset_info['path']
                controls_dir = dataset_path / "controls"

                # 查找并删除控制图文件（支持不同扩展名）
                deleted = False
                for ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
                    control_filename = f"{original_stem}_{control_index}{ext}"
                    control_file_path = controls_dir / control_filename
                    
                    if control_file_path.exists():
                        control_file_path.unlink()
                        deleted = True
                        log_info(f"成功删除控制图: {dataset_id}/{control_filename}")
                        break

                if not deleted:
                    raise ValueError(f"控制图 {original_stem}_{control_index}.* 不存在")

                return {
                    "success": True,
                    "message": f"成功删除控制图"
                }

            except Exception as e:
                log_error(f"删除控制图失败: {dataset_id}/{original_filename}", e)
                raise


# Global service instance
_dataset_service_instance = None
_lock = threading.Lock()

def get_dataset_service() -> DatasetService:
    """Get the global dataset service instance"""
    global _dataset_service_instance
    if _dataset_service_instance is None:
        with _lock:
            if _dataset_service_instance is None:
                _dataset_service_instance = DatasetService()
    return _dataset_service_instance
