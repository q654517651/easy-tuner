"""
Dataset data models - FastAPI Backend version
数据集数据模型

===== 模块说明 =====
该模块定义了数据集管理的核心数据结构，主要包含：

1. Dataset类：数据集主要数据模型
   - 数据集基本信息（ID、名称、描述、时间戳）
   - 图像文件管理（文件名到标签的映射）
   - 标签数据管理和统计
   - 数据序列化和反序列化支持

===== 主要功能 =====
- 数据集CRUD操作：创建、读取、更新、删除
- 图像管理：添加图像、更新标签、移除图像
- 统计信息：总数、已标注数、完成率计算
- 数据持久化：字典格式转换，支持JSON序列化
- 类型验证：支持image、video、single_control_image、multi_control_image等类型

===== 使用场景 =====
- DatasetManager中作为核心数据结构
- API响应的数据绑定和显示
- 与workspace文件系统的数据同步
- 训练任务的数据集配置

===== 数据结构说明 =====
Dataset.items: Dict[str, Dict[str, Any]] = {文件名: {属性字典}}
- 键：文件名（如"image_001.jpg"）
- 值：属性字典，包含label等信息

Dataset.tags: List[str] = 数据集级别的标签列表
- 用于分类和检索数据集
- 与具体图像标签分开管理
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from ...utils.logger import log_error


class DatasetType(Enum):
    """数据集类型"""
    IMAGE = "image"
    VIDEO = "video"
    SINGLE_CONTROL_IMAGE = "single_control_image"  # 单图控制
    MULTI_CONTROL_IMAGE = "multi_control_image"    # 多图控制

    @property
    def display_name(self) -> str:
        """获取中文显示名称"""
        display_names = {
            "image": "图像数据集",
            "video": "视频数据集",
            "single_control_image": "单图控制数据集",
            "multi_control_image": "多图控制数据集"
        }
        return display_names.get(self.value, self.value)

    @property
    def type_tag(self) -> str:
        """获取数据集类型标签（用于目录命名）"""
        tag_mapping = {
            "image": "i",
            "video": "v",
            "single_control_image": "s",
            "multi_control_image": "m"
        }
        return tag_mapping[self.value]

    @property
    def family_dir(self) -> str:
        """获取数据集类型对应的家族目录名"""
        family_mapping = {
            "image": "image_datasets",
            "video": "video_datasets",
            "single_control_image": "control_image_datasets",
            "multi_control_image": "control_image_datasets"
        }
        return family_mapping[self.value]

    @classmethod
    def from_tag(cls, tag: str) -> Optional['DatasetType']:
        """从类型标签获取数据集类型"""
        tag_to_type = {
            "i": cls.IMAGE,
            "v": cls.VIDEO,
            "s": cls.SINGLE_CONTROL_IMAGE,
            "m": cls.MULTI_CONTROL_IMAGE
        }
        return tag_to_type.get(tag)


# 数据集类型常量
DATASET_TYPES = [e.value for e in DatasetType]


@dataclass
class Dataset:
    """数据集模型"""
    dataset_id: str
    name: str
    dataset_type: str = "image"  # image, video, image_control (创建后不可更改)
    description: str = ""
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # 统一数据存储
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if self.modified_time is None:
            self.modified_time = self.created_time

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'dataset_id': self.dataset_id,
            'name': self.name,
            'dataset_type': self.dataset_type,
            'description': self.description,
            'created_time': self.created_time,
            'modified_time': self.modified_time,
            'items': self.items,
            'tags': self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Dataset':
        """从字典创建"""
        # 兼容旧格式 - 将images转换为items
        items = data.get('items', {})
        if not items and 'images' in data:
            # 旧格式转换
            images = data.get('images', {})
            items = {filename: {"label": label} for filename, label in images.items()}
        
        return cls(
            dataset_id=data['dataset_id'],
            name=data['name'],
            dataset_type=data.get('dataset_type', 'image'),
            description=data.get('description', ''),
            created_time=data.get('created_time'),
            modified_time=data.get('modified_time'),
            items=items,
            tags=data.get('tags', [])
        )

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = len(self.items)
        labeled = len([item for item in self.items.values() if item.get('label', '').strip()])
        return {
            'total': total,
            'labeled': labeled,
            'unlabeled': total - labeled,
            'completion_rate': round(labeled / total * 100) if total > 0 else 0
        }

    def add_item(self, filename: str, **data) -> bool:
        """添加数据项"""
        try:
            if self.dataset_type == "image":
                self.items[filename] = {"label": data.get('label', '')}
            elif self.dataset_type == "video":
                self.items[filename] = {
                    "label": data.get('label', ''),
                    "duration": data.get('duration', 0.0),
                    "fps": data.get('fps', 0.0),
                    "frame_count": data.get('frame_count', 0),
                    "thumbnail": data.get('thumbnail', '')
                }
            elif self.dataset_type in [DatasetType.SINGLE_CONTROL_IMAGE.value, DatasetType.MULTI_CONTROL_IMAGE.value]:
                self.items[filename] = {
                    "label": data.get('label', ''),
                    "control_images": data.get('control_images', [])  # 支持多个控制图
                }
            self._update_modified_time()
            return True
        except Exception as e:
            log_error(f"添加数据项失败: {e}")
            return False

    def update_label(self, filename: str, label: str) -> bool:
        """更新标签"""
        if filename in self.items:
            self.items[filename]['label'] = label
            self._update_modified_time()
            return True
        return False

    def remove_item(self, filename: str) -> bool:
        """移除数据项"""
        if filename in self.items:
            del self.items[filename]
            self._update_modified_time()
            return True
        return False

    def get_label(self, filename: str) -> str:
        """获取标签"""
        return self.items.get(filename, {}).get('label', '')

    def has_item(self, filename: str) -> bool:
        """检查是否包含数据项"""
        return filename in self.items

    def get_item_count(self) -> int:
        """获取数据项数量"""
        return len(self.items)

    def get_labeled_count(self) -> int:
        """获取已标注数量"""
        return len([item for item in self.items.values() if item.get('label', '').strip()])

    def get_unlabeled_items(self) -> List[str]:
        """获取未标注的数据项列表"""
        return [filename for filename, item in self.items.items() if not item.get('label', '').strip()]

    def _update_modified_time(self):
        """更新修改时间"""
        self.modified_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def validate_type(self) -> bool:
        """验证数据集类型"""
        return self.dataset_type in DATASET_TYPES