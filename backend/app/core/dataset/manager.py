"""
Dataset Manager - 数据集管理器 (FastAPI Backend version)
"""

import os
import json
import shutil
import threading
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple, Any, Sequence
from datetime import datetime

from .models import Dataset, DatasetType
from .utils import (
    gen_short_id, safeify_name, parse_ds_dirname, next_control_index,
    atomic_write_text, generate_unique_name, find_paired_files,
    safe_filename, is_image_file, is_video_file, is_media_file,
    get_dataset_warehouse_path, get_dataset_subdirs
)
from ...utils.logger import log_info, log_error, log_success
from ...core.exceptions import (
    DatasetNotFoundError,
    ValidationError,
)
from ...utils.validators import validate_dataset_name
from ..config import get_config


class DatasetManager:
    """数据集管理器 - FastAPI Backend版本"""

    def __init__(self):
        self.config = get_config()
        raw = getattr(self.config.storage, 'workspace_root', '') or ''
        try:
            self.workspace_root = Path(raw).expanduser().resolve(strict=False)
        except Exception:
            logging.exception("解析工作区路径失败：%r", raw)
            self.workspace_root = Path(raw or './workspace')
        
        # 新的分仓目录结构（都在datasets子目录下）
        self.datasets_root = self.workspace_root / self.config.storage.datasets_dir
        self.image_datasets_dir = self.datasets_root / "image_datasets"
        self.control_datasets_dir = self.datasets_root / "control_image_datasets"
        self.video_datasets_dir = self.datasets_root / "video_datasets"
        self.legacy_datasets_dir = self.datasets_root  # 向后兼容

        # 工作区就绪标记
        self._workspace_ready: bool = False
        # 延迟创建：仅在工作区存在时创建目录并加载
        if self.workspace_root.exists():
            try:
                self.image_datasets_dir.mkdir(parents=True, exist_ok=True)
                self.control_datasets_dir.mkdir(parents=True, exist_ok=True)
                self.video_datasets_dir.mkdir(parents=True, exist_ok=True)
                self.legacy_datasets_dir.mkdir(parents=True, exist_ok=True)
                self._workspace_ready = True
            except Exception:
                logging.exception("创建数据集目录失败：%s", self.datasets_root)
                self._workspace_ready = False

        # 线程安全锁
        self._lock = threading.Lock()

        # 内存中的数据集缓存: {dataset_id: {'dataset': Dataset, 'path': Path, 'warehouse': Path}}
        self.datasets: Dict[str, Dict[str, Any]] = {}

        # 加载现有数据集（在就绪时）
        if self._workspace_ready:
            try:
                self.load_all_datasets()
            except Exception:
                logging.exception("启动时加载数据集失败")

    def update_workspace(self, new_root: str | Path) -> bool:
        """切换数据集工作区。
        策略：锁内仅做路径切换与状态清理；长耗时加载放到锁外；加载成功后再置 ready=True。
        返回：是否加载成功并就绪。
        """
        logger = logging.getLogger(__name__)
        with self._lock:
            try:
                root = Path(new_root).expanduser().resolve(strict=False)
                self.workspace_root = root
                self.datasets_root = root / self.config.storage.datasets_dir
                self.image_datasets_dir = self.datasets_root / "image_datasets"
                self.control_datasets_dir = self.datasets_root / "control_image_datasets"
                self.video_datasets_dir = self.datasets_root / "video_datasets"
                self.legacy_datasets_dir = self.datasets_root
                # 切换期间标记未就绪并清空索引，避免半状态
                self._workspace_ready = False
                self.datasets.clear()
                if not root.exists():
                    logger.info("工作区不存在，已标记未就绪：%s", root)
                    return False
                try:
                    self.image_datasets_dir.mkdir(parents=True, exist_ok=True)
                    self.control_datasets_dir.mkdir(parents=True, exist_ok=True)
                    self.video_datasets_dir.mkdir(parents=True, exist_ok=True)
                    self.legacy_datasets_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    logger.exception("创建数据集目录失败：%s", self.datasets_root)
                    return False
            except Exception:
                logger.exception("更新数据集工作区路径失败")
                return False

        # 锁外加载（可能较慢）
        try:
            self.load_all_datasets()
            with self._lock:
                self._workspace_ready = True
            logger.info("数据集工作区已更新：%s（ready=True，datasets=%d）", self.workspace_root, len(self.datasets))
            return True
        except Exception:
            logging.exception("切换工作区后加载数据集失败")
            # 保持未就绪
            return False

    def create_dataset(self, name: str, dataset_type: str = "image") -> Tuple[bool, str]:
        """创建新数据集"""
        with self._lock:
            try:
                # 验证名称
                validate_dataset_name(name)

                # 生成短ID
                dataset_id = gen_short_id()

                # 使用统一的目录创建方法 (混合式方案)
                from .utils import create_unified_dataset_directory
                dataset_path = create_unified_dataset_directory(
                    workspace_root=self.workspace_root,
                    dataset_id=dataset_id,
                    dataset_type=dataset_type,
                    display_name=name  # 传入原始名称，由 safeify_name 处理
                )

                # 创建数据集对象
                dataset = Dataset(
                    dataset_id=dataset_id,
                    name=name,
                    dataset_type=dataset_type
                )

                # 根据类型创建子目录
                subdirs = get_dataset_subdirs(dataset_type)
                for subdir in subdirs:
                    (dataset_path / subdir).mkdir(exist_ok=True)

                # 保存到内存
                self.datasets[dataset_id] = {
                    'dataset': dataset,
                    'path': dataset_path,
                    'warehouse': dataset_path.parent  # 家族目录作为warehouse
                }

                log_success(f"创建数据集成功: {name} ({dataset_id})")
                return True, f"数据集 '{name}' 创建成功"

            except ValidationError as e:
                log_error(f"数据集名称验证失败: {e.message}")
                return False, e.message
            except Exception as e:
                log_error(f"创建数据集异常: {str(e)}", e)
                return False, f"创建失败: {str(e)}"

    def rename_dataset(self, dataset_id: str, new_name: str) -> Tuple[bool, str]:
        """重命名数据集"""
        with self._lock:
            try:
                if dataset_id not in self.datasets:
                    raise DatasetNotFoundError(
                        message=f"数据集未找到: {dataset_id}",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )
                
                validate_dataset_name(new_name)
                
                dataset_info = self.datasets[dataset_id]
                dataset = dataset_info['dataset']
                old_path = dataset_info['path']
                warehouse_path = dataset_info['warehouse']
                
                # 生成新的目录名（使用统一格式）
                safe_name = safeify_name(new_name)
                base_dirname = f"{dataset_id}__{safe_name}"
                new_dirname = base_dirname
                counter = 2
                while (warehouse_path / new_dirname).exists() and new_dirname != old_path.name:
                    safe_name_with_counter = safeify_name(f"{new_name} {counter}")
                    new_dirname = f"{dataset_id}__{safe_name_with_counter}"
                    counter += 1
                
                new_path = warehouse_path / new_dirname
                
                # 重命名目录
                if old_path != new_path:
                    old_path.rename(new_path)
                
                # 更新内存中的信息
                dataset.name = new_name
                dataset._update_modified_time()
                self.datasets[dataset_id]['path'] = new_path
                
                log_success(f"重命名数据集成功: {new_name}")
                return True, f"数据集重命名为 '{new_name}' 成功"
                
            except ValidationError as e:
                log_error(f"数据集名称验证失败: {e.message}")
                return False, e.message
            except DatasetNotFoundError as e:
                return False, e.message
            except Exception as e:
                log_error(f"重命名数据集异常: {str(e)}", e)
                return False, f"重命名失败: {str(e)}"

    def delete_dataset(self, dataset_id: str) -> Tuple[bool, str]:
        """删除数据集"""
        with self._lock:
            try:
                if dataset_id not in self.datasets:
                    raise DatasetNotFoundError(
                        message=f"数据集未找到: {dataset_id}",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                dataset_info = self.datasets[dataset_id]
                dataset = dataset_info['dataset']
                dataset_path = dataset_info['path']
                dataset_name = dataset.name

                # 删除数据目录
                if dataset_path.exists():
                    shutil.rmtree(dataset_path)

                # 从内存中删除
                del self.datasets[dataset_id]

                log_success(f"删除数据集成功: {dataset_name}")
                return True, f"数据集 '{dataset_name}' 删除成功"

            except DatasetNotFoundError as e:
                log_error(f"数据集不存在: {dataset_id}")
                return False, e.message
            except Exception as e:
                log_error(f"删除数据集异常: {str(e)}", e)
                return False, f"删除失败: {str(e)}"

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """获取数据集"""
        dataset_info = self.datasets.get(dataset_id)
        return dataset_info['dataset'] if dataset_info else None

    def list_datasets(self) -> List[Dataset]:
        """获取所有数据集列表"""
        return [info['dataset'] for info in self.datasets.values()]

    def search_datasets(self, keyword: str) -> List[Dataset]:
        """搜索数据集"""
        if not keyword:
            return self.list_datasets()

        keyword = keyword.lower()
        results = []

        for info in self.datasets.values():
            dataset = info['dataset']
            if (keyword in dataset.name.lower() or
                    keyword in ' '.join(dataset.tags).lower()):
                results.append(dataset)

        return results

    def get_dataset_path(self, dataset_id: str) -> Optional[Path]:
        """获取数据集目录路径"""
        # 优先从内存索引查找
        if dataset_id in self.datasets:
            return self.datasets[dataset_id]['path']
        
        # 内存中没有，扫描所有仓库目录查找
        search_dirs = [
            self.image_datasets_dir,
            self.control_datasets_dir,
            self.legacy_datasets_dir  # 向后兼容
        ]
        
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for dir_path in search_dir.iterdir():
                if dir_path.is_dir() and dir_path.name.startswith(f"{dataset_id}__"):
                    return dir_path
        
        return None

    def get_dataset_image_path(self, dataset_id: str, filename: str) -> Optional[str]:
        """获取数据集中文件的路径"""
        dataset_path = self.get_dataset_path(dataset_id)
        if not dataset_path:
            return None
        
        # 获取数据集类型以确定搜索目录
        dataset_info = self.datasets.get(dataset_id)
        if dataset_info:
            # 处理可能的数据结构不一致问题
            if isinstance(dataset_info, dict) and 'dataset' in dataset_info:
                dataset_type = dataset_info['dataset'].dataset_type
            elif hasattr(dataset_info, 'dataset_type'):
                dataset_type = dataset_info.dataset_type
            else:
                dataset_type = "image"  # 默认类型
            search_subdirs = get_dataset_subdirs(dataset_type)
            
            # 如果有子目录，在子目录中查找
            if search_subdirs:
                for subdir in search_subdirs:
                    file_path = dataset_path / subdir / filename
                    if file_path.exists():
                        return str(file_path)
            else:
                # 直接在数据集根目录查找
                file_path = dataset_path / filename
                if file_path.exists():
                    return str(file_path)
        
        # 兜底：按旧逻辑搜索（向后兼容）
        legacy_subdirs = ['images', 'videos', 'controls', 'targets']
        for subdir in legacy_subdirs:
            file_path = dataset_path / subdir / filename
            if file_path.exists():
                return str(file_path)
        
        # 直接在根目录查找
        file_path = dataset_path / filename
        if file_path.exists():
            return str(file_path)
                
        return None

    def resolve_image_src(self, dataset_id: str, filename: str) -> Dict[str, Any]:
        """解析文件资源路径（兼容旧接口）"""
        image_path = self.get_dataset_image_path(dataset_id, filename)
        
        if image_path:
            path_obj = Path(image_path)
            return {
                "src": path_obj.as_uri(),
                "abs": str(image_path),
                "local": str(image_path)
            }
        return {"src": "", "abs": "", "local": ""}

    def import_files_to_dataset(self, dataset_id: str, file_paths: List[str]) -> Tuple[int, str]:
        """根据数据集类型导入文件

        对于控制图数据集，仅导入原图到 targets/ 目录，控制图需通过手动上传接口单独添加
        """
        with self._lock:
            try:
                dataset_info = self.datasets.get(dataset_id)
                if not dataset_info:
                    raise DatasetNotFoundError(
                        message=f"数据集未找到: {dataset_id}",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                dataset = dataset_info['dataset']
                dataset_path = dataset_info['path']

                if dataset.dataset_type == "image":
                    success_count = self._import_images(dataset, dataset_path, file_paths)
                elif dataset.dataset_type == "video":
                    success_count = self._import_videos(dataset, dataset_path, file_paths)
                elif dataset.dataset_type in ["single_control_image", "multi_control_image"]:
                    # 控制图数据集：仅导入原图，控制图通过手动上传接口添加
                    success_count = self._import_control_originals(dataset, dataset_path, file_paths)
                else:
                    return 0, f"不支持的数据集类型: {dataset.dataset_type}"

                message = f"成功导入 {success_count}/{len(file_paths)} 个文件"
                log_success(message) if success_count > 0 else log_error(message)

                return success_count, message

            except DatasetNotFoundError as e:
                return 0, e.message
            except Exception as e:
                log_error(f"导入文件失败: {str(e)}", e)
                return 0, f"导入失败: {str(e)}"

    def _import_images(self, dataset: Dataset, dataset_path: Path, file_paths: List[str]) -> int:
        """导入图像文件"""
        success_count = 0
        # 对于image类型，直接存放在数据集根目录
        target_dir = dataset_path
        
        # 使用工具函数查找配对文件
        paired_files, failed_files = find_paired_files([Path(p) for p in file_paths])
        
        # 记录失败的孤立txt文件
        for failed_file in failed_files:
            log_error(f"跳过孤立的标签文件: {failed_file} (missing media)")
        
        for media_file, label_file in paired_files:
            try:
                # 安全文件名处理
                safe_name = safe_filename(media_file.name)
                unique_name = generate_unique_name(target_dir, safe_name)
                
                # 复制媒体文件
                dest_path = target_dir / unique_name
                shutil.copy2(media_file, dest_path)
                
                # 处理标签文件
                label = ""
                if label_file:
                    try:
                        label = label_file.read_text(encoding='utf-8').strip()
                    except Exception as e:
                        log_error(f"读取标签文件失败 {label_file}: {str(e)}")
                
                # 保存标签文件到目标位置
                if label_file:
                    label_dest = dest_path.with_suffix('.txt')
                    atomic_write_text(label_dest, label)  # 即使空标签也保存文件
                
                # 添加到数据集
                dataset.add_item(unique_name, label=label)
                success_count += 1
                
            except Exception as e:
                log_error(f"导入图像失败 {media_file}: {str(e)}")
        
        return success_count

    def _import_videos(self, dataset: Dataset, dataset_path: Path, file_paths: List[str]) -> int:
        """导入视频文件"""
        success_count = 0
        # 视频文件直接存放在数据集根目录，不需要videos子目录
        videos_dir = dataset_path
        
        # 使用工具函数查找配对文件
        paired_files, failed_files = find_paired_files([Path(p) for p in file_paths])
        
        # 记录失败的孤立txt文件
        for failed_file in failed_files:
            log_error(f"跳过孤立的标签文件: {failed_file} (missing media)")
        
        for media_file, label_file in paired_files:
            try:
                if not is_video_file(media_file):
                    continue
                    
                # 安全文件名处理
                safe_name = safe_filename(media_file.name)
                unique_name = generate_unique_name(videos_dir, safe_name)
                
                # 复制视频文件
                dest_path = videos_dir / unique_name
                shutil.copy2(media_file, dest_path)
                
                # 处理标签文件
                label = ""
                if label_file:
                    try:
                        label = label_file.read_text(encoding='utf-8').strip()
                    except Exception as e:
                        log_error(f"读取标签文件失败 {label_file}: {str(e)}")
                
                # 保存标签文件到目标位置
                if label_file:
                    label_dest = dest_path.with_suffix('.txt')
                    atomic_write_text(label_dest, label)  # 即使空标签也保存文件
                
                # 添加到数据集
                dataset.add_item(unique_name, label=label)
                success_count += 1
                
            except Exception as e:
                log_error(f"导入视频失败 {media_file}: {str(e)}")
        
        return success_count


    def _import_control_originals(self, dataset: Dataset, dataset_path: Path, file_paths: List[str]) -> int:
        """导入控制图数据集的原图（不包含控制图）"""
        success_count = 0
        targets_dir = dataset_path / "targets"
        targets_dir.mkdir(exist_ok=True)

        # 使用工具函数查找配对文件
        paired_files, failed_files = find_paired_files([Path(p) for p in file_paths])

        # 记录失败的孤立txt文件
        for failed_file in failed_files:
            log_error(f"跳过孤立的标签文件: {failed_file} (missing media)")

        for media_file, label_file in paired_files:
            try:
                # 安全文件名处理
                safe_name = safe_filename(media_file.name)
                unique_name = generate_unique_name(targets_dir, safe_name)

                # 复制媒体文件到targets目录
                dest_path = targets_dir / unique_name
                shutil.copy2(media_file, dest_path)

                # 处理标签文件
                label = ""
                if label_file:
                    try:
                        label = label_file.read_text(encoding='utf-8').strip()
                    except Exception as e:
                        log_error(f"读取标签文件失败 {label_file}: {str(e)}")

                # 保存标签文件到目标位置
                if label_file:
                    label_dest = dest_path.with_suffix('.txt')
                    atomic_write_text(label_dest, label)  # 即使空标签也保存文件

                # 添加到数据集（不指定control_image，表示还没有控制图）
                dataset.add_item(unique_name, label=label)
                success_count += 1

            except Exception as e:
                log_error(f"导入原图失败 {media_file}: {str(e)}")

        return success_count

    def update_dataset_label(self, dataset_id: str, filename: str, label: str) -> bool:
        """更新数据集中图片的标签"""
        with self._lock:
            try:
                dataset = self.get_dataset(dataset_id)
                if not dataset:
                    raise DatasetNotFoundError(
                        message=f"数据集未找到: {dataset_id}",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                # 更新数据集中的标签
                if dataset.update_label(filename, label):
                    # 同时更新对应的txt文件
                    self._save_label_file(dataset_id, filename, label)
                    return True
                return False

            except Exception as e:
                log_error(f"更新标签失败: {str(e)}", e)
                return False

    def batch_update_labels(self, dataset_id: str, labels_dict: Dict[str, str]) -> Tuple[int, str]:
        """批量更新标签"""
        with self._lock:
            try:
                dataset = self.get_dataset(dataset_id)
                if not dataset:
                    raise DatasetNotFoundError(
                        message=f"数据集未找到: {dataset_id}",
                        detail={"dataset_id": dataset_id},
                        error_code="DATASET_NOT_FOUND",
                    )

                success_count = 0

                for filename, label in labels_dict.items():
                    if dataset.update_label(filename, label):
                        self._save_label_file(dataset_id, filename, label)
                        success_count += 1

                message = f"成功更新 {success_count} 个标签"
                if success_count > 0:
                    log_success(message)

                return success_count, message

            except DatasetNotFoundError as e:
                return 0, e.message
            except Exception as e:
                log_error(f"批量更新标签失败: {str(e)}", e)
                return 0, f"更新失败: {str(e)}"

    def export_dataset(self, dataset_id: str, export_path: str, format_type: str = "folder") -> Tuple[bool, str]:
        """导出数据集"""
        try:
            dataset_info = self.datasets.get(dataset_id)
            if not dataset_info:
                raise DatasetNotFoundError(
                    message=f"数据集未找到: {dataset_id}",
                    detail={"dataset_id": dataset_id},
                    error_code="DATASET_NOT_FOUND",
                )

            dataset = dataset_info['dataset']
            dataset_path = dataset_info['path']
            export_path = Path(export_path)

            if format_type == "folder":
                # 导出为文件夹格式 (直接拷贝目录结构)
                dataset_export_dir = export_path / f"{dataset.name}_{dataset.dataset_id}"
                dataset_export_dir.mkdir(parents=True, exist_ok=True)

                # 根据数据集类型复制相应目录结构
                dataset_type = dataset.dataset_type
                export_subdirs = get_dataset_subdirs(dataset_type)
                
                if export_subdirs:
                    # 有子目录结构的数据集
                    for subdir in export_subdirs:
                        src_dir = dataset_path / subdir
                        if src_dir.exists():
                            dest_dir = dataset_export_dir / subdir
                            shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                else:
                    # 扁平结构的数据集，直接复制根目录内容
                    for file_path in dataset_path.iterdir():
                        if file_path.is_file():
                            shutil.copy2(file_path, dataset_export_dir / file_path.name)
                
                # 向后兼容：复制旧格式的子目录
                legacy_subdirs = ['images', 'videos', 'controls', 'targets']
                for subdir in legacy_subdirs:
                    src_dir = dataset_path / subdir
                    if src_dir.exists():
                        dest_dir = dataset_export_dir / subdir
                        if not dest_dir.exists():
                            shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)

                return True, f"数据集已导出到: {dataset_export_dir}"

            elif format_type == "json":
                # 导出为JSON格式
                json_file = export_path / f"{dataset.name}_{dataset.dataset_id}.json"

                export_data = {
                    'dataset_info': dataset.to_dict(),
                    'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)

                return True, f"数据集已导出到: {json_file}"

            else:
                return False, "不支持的导出格式"

        except DatasetNotFoundError as e:
            return False, e.message
        except Exception as e:
            log_error(f"导出数据集失败: {str(e)}", e)
            return False, f"导出失败: {str(e)}"

    def load_all_datasets(self):
        """加载所有数据集"""
        try:
            self.datasets.clear()

            # 扫描所有仓库目录
            warehouse_configs = [
                (self.image_datasets_dir, "image"),
                (self.control_datasets_dir, "control"),  # 特殊标记，需要进一步解析
                (self.video_datasets_dir, "video"),
                (self.legacy_datasets_dir, None)  # 旧版本，需要检测类型
            ]

            for warehouse_dir, default_type in warehouse_configs:
                if not warehouse_dir.exists():
                    continue
                    
                for dir_path in warehouse_dir.iterdir():
                    if not dir_path.is_dir():
                        continue

                    # 跳过仓库目录本身（在legacy扫描时）
                    if (warehouse_dir == self.legacy_datasets_dir and
                        dir_path.name in ['image_datasets', 'control_image_datasets', 'video_datasets']):
                        continue

                    try:
                        # 使用统一的加载和校验方法
                        from .utils import load_dataset_with_family_validation
                        dataset_info = load_dataset_with_family_validation(dir_path)

                        dataset_id = dataset_info["id"]
                        dataset_type = dataset_info["type"]
                        display_name = dataset_info["name"]

                        # 创建数据集对象
                        dataset = Dataset(
                            dataset_id=dataset_id,
                            name=display_name,
                            dataset_type=dataset_type
                        )

                        # 加载文件和标签
                        self._load_dataset_files(dataset, dir_path)

                        # 保存到内存
                        self.datasets[dataset_id] = {
                            'dataset': dataset,
                            'path': dir_path,
                            'warehouse': warehouse_dir,
                            'family_consistent': dataset_info["family_consistent"],
                            'version': dataset_info["version"]
                        }
                        
                    except Exception as e:
                        log_error(f"加载数据集失败 {dir_path}: {str(e)}")

            log_info(f"加载了 {len(self.datasets)} 个数据集")

        except Exception as e:
            log_error(f"加载数据集列表失败: {str(e)}", e)
            
            
    def _load_dataset_files(self, dataset: Dataset, dataset_path: Path):
        """加载数据集文件和标签"""
        # 获取应该搜索的子目录
        search_subdirs = get_dataset_subdirs(dataset.dataset_type)
        
        if search_subdirs:
            # 有子目录的情况（如control_image_datasets）
            if dataset.dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value]:
                # 控制图数据集特殊处理：只加载targets目录的文件作为主item
                targets_dir = dataset_path / "targets"
                controls_dir = dataset_path / "controls"

                if targets_dir.exists():
                    for file_path in targets_dir.iterdir():
                        if not file_path.is_file() or not is_media_file(file_path):
                            continue

                        # 加载标签
                        label_path = file_path.with_suffix('.txt')
                        label = ""
                        if label_path.exists():
                            try:
                                label = label_path.read_text(encoding='utf-8').strip()
                            except Exception as e:
                                log_error(f"读取标签文件失败 {label_path}: {str(e)}")

                        # 查找对应的控制图（文件名规则：原图stem_数字.扩展名）
                        target_stem = file_path.stem
                        control_images = []

                        if controls_dir.exists():
                            for control_file in controls_dir.iterdir():
                                if not control_file.is_file() or not is_media_file(control_file):
                                    continue

                                # 检查是否是当前原图的控制图
                                if control_file.stem.startswith(f"{target_stem}_"):
                                    control_images.append(control_file.name)

                        # 添加原图item，包含关联的控制图信息
                        extra_data = {
                            "label": label,
                            "control_images": control_images  # 支持多个控制图
                        }
                        dataset.add_item(file_path.name, **extra_data)
            else:
                # 其他类型数据集的子目录处理
                for subdir in search_subdirs:
                    subdir_path = dataset_path / subdir
                    if not subdir_path.exists():
                        continue

                    for file_path in subdir_path.iterdir():
                        if not file_path.is_file():
                            continue

                        if is_media_file(file_path):
                            extra_data = {"label": ""}
                            dataset.add_item(file_path.name, **extra_data)
        else:
            # 无子目录的情况（如image_datasets，直接在根目录）
            for file_path in dataset_path.iterdir():
                if not file_path.is_file():
                    continue
                    
                if is_media_file(file_path):
                    # 媒体文件，查找对应的txt标签
                    label_path = file_path.with_suffix('.txt')
                    label = ""
                    if label_path.exists():
                        try:
                            label = label_path.read_text(encoding='utf-8').strip()
                        except Exception as e:
                            log_error(f"读取标签文件失败 {label_path}: {str(e)}")
                    
                    dataset.add_item(file_path.name, label=label)
        
        # 兜底：按旧逻辑搜索（向后兼容）
        legacy_subdirs = ['images', 'videos', 'controls', 'targets']
        for subdir in legacy_subdirs:
            # 对于控制图数据集，跳过controls目录的兜底扫描（已在上面特殊处理）
            if dataset.dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value] and subdir == "controls":
                continue

            subdir_path = dataset_path / subdir
            if not subdir_path.exists():
                continue

            for file_path in subdir_path.iterdir():
                if not file_path.is_file():
                    continue

                if is_media_file(file_path) and not dataset.has_item(file_path.name):
                    # 媒体文件，查找对应的txt标签
                    label_path = file_path.with_suffix('.txt')
                    label = ""
                    if label_path.exists():
                        try:
                            label = label_path.read_text(encoding='utf-8').strip()
                        except Exception as e:
                            log_error(f"读取标签文件失败 {label_path}: {str(e)}")

                    # 添加额外数据
                    extra_data = {"label": label}
                    if subdir == "controls":
                        extra_data["control_image"] = file_path.name

                    dataset.add_item(file_path.name, **extra_data)

    def _save_label_file(self, dataset_id: str, filename: str, label: str):
        """保存标签到txt文件"""
        try:
            dataset_path = self.get_dataset_path(dataset_id)
            if not dataset_path:
                return
            
            # 获取数据集信息以确定搜索策略
            dataset_info = self.datasets.get(dataset_id)
            if dataset_info:
                # 处理可能的数据结构不一致问题
                if isinstance(dataset_info, dict) and 'dataset' in dataset_info:
                    dataset_type = dataset_info['dataset'].dataset_type
                elif hasattr(dataset_info, 'dataset_type'):
                    dataset_type = dataset_info.dataset_type
                else:
                    dataset_type = "image"  # 默认类型
                search_subdirs = get_dataset_subdirs(dataset_type)
                
                # 优先在新架构的子目录中查找
                if search_subdirs:
                    for subdir in search_subdirs:
                        file_path = dataset_path / subdir / filename
                        if file_path.exists():
                            # 对于控制图像数据集，只在targets目录保存标签
                            if dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value] and subdir == "controls":
                                # 控制图像不保存标签文件
                                return
                            label_path = file_path.with_suffix('.txt')
                            atomic_write_text(label_path, label)
                            return
                else:
                    # 直接在根目录查找
                    file_path = dataset_path / filename
                    if file_path.exists():
                        label_path = file_path.with_suffix('.txt')
                        atomic_write_text(label_path, label)
                        return
                
            # 兜底：在所有可能的目录中查找文件
            all_subdirs = ['images', 'videos', 'controls', 'targets']
            for subdir in all_subdirs:
                file_path = dataset_path / subdir / filename
                if file_path.exists():
                    # 对于控制图像数据集，不在controls目录保存标签
                    if dataset_info and isinstance(dataset_info, dict):
                        dataset_obj = dataset_info.get('dataset')
                        if dataset_obj and dataset_obj.dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value] and subdir == "controls":
                            return
                    label_path = file_path.with_suffix('.txt')
                    atomic_write_text(label_path, label)
                    return
            
            # 最后尝试根目录
            file_path = dataset_path / filename
            if file_path.exists():
                label_path = file_path.with_suffix('.txt')
                atomic_write_text(label_path, label)
                return
                
        except Exception as e:
            log_error(f"保存标签文件失败 {filename}: {str(e)}")


# 创建全局单例实例
_dataset_manager_instance = None
_lock = threading.Lock()


def get_dataset_manager() -> DatasetManager:
    """获取数据集管理器单例实例"""
    global _dataset_manager_instance
    if _dataset_manager_instance is None:
        with _lock:
            if _dataset_manager_instance is None:
                _dataset_manager_instance = DatasetManager()
    return _dataset_manager_instance
