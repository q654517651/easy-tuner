"""
Dataset utilities - 数据集工具函数 (FastAPI Backend version)
"""

import os
import re
import string
import random
import threading
from pathlib import Path
from typing import Tuple, List, Dict, Sequence, Optional, Any

from .models import DatasetType


# 全局线程锁
_lock = threading.Lock()


def gen_short_id(k: int = 8) -> str:
    """生成短ID
    
    Args:
        k: ID长度，默认8位
        
    Returns:
        随机生成的短ID字符串
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=k))


def parse_ds_dirname(dirname: str) -> Tuple[str, str, Optional[str], str]:
    """解析数据集目录名 - 支持v1命名协议

    支持格式:
    1. v1格式: "{dataset_id}--{type_tag}--{safe_name}" (控制图数据集)
    2. 旧格式: "{dataset_id}__{safe_name}"
    3. 兜底格式: "{dataset_id}" 或任意字符串

    Args:
        dirname: 目录名称

    Returns:
        (dataset_id, display_name, control_subtype, version)
        - control_subtype: 's'=single, 'm'=multi, None=非控制图
        - version: 'v1'=新协议, 'legacy'=旧格式, 'fallback'=兜底
    """
    import re

    # v1格式：{dataset_id}--{type_tag}--{safe_name}
    # safe_name 现在可以包含中文等 Unicode 字符
    v1_match = re.match(r'^([a-z0-9]{8,12})--([sm])--(.+)$', dirname)
    if v1_match:
        ds_id, tag, safe_name = v1_match.groups()
        # 将下划线转回空格显示
        display_name = safe_name.replace('_', ' ')
        return ds_id, display_name, tag, 'v1'

    # 兼容旧格式：{dataset_id}__{safe_name}
    if '__' in dirname:
        parts = dirname.split('__', 1)
        ds_id, safe_name = parts[0], parts[1]
        display_name = safe_name.replace('_', ' ')
        return ds_id, display_name, None, 'legacy'

    # 兜底：纯ID或任意字符串
    return dirname, dirname, None, 'fallback'


def safeify_name(name: str) -> str:
    """将名称转换为安全的目录名（保留中文，移除非法字符）

    Args:
        name: 原始名称

    Returns:
        安全的目录名，移除Windows非法字符、控制字符，保留中文
    """
    import re
    import unicodedata
    
    if not name:
        return 'dataset'
    
    # 1. Unicode 归一化（NFC）- 统一字符表示形式
    normalized = unicodedata.normalize('NFC', name)
    
    # 2. 移除 Windows 非法字符: < > : " / \ | ? *
    # 注意：路径分隔符已在这里移除
    illegal_chars = r'[<>:"/\\|?*]'
    safe = re.sub(illegal_chars, '_', normalized)
    
    # 3. 移除控制字符（\x00-\x1f, \x7f-\x9f）
    safe = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe)
    
    # 4. 移除不可见空白字符（保留普通空格）
    # \u200b 零宽空格, \u200c 零宽不连字, \u200d 零宽连字, \ufeff 字节顺序标记
    safe = re.sub(r'[\u200b-\u200d\ufeff]', '', safe)
    
    # 5. 将连续空格替换为单个下划线，并去除首尾空格
    safe = re.sub(r'\s+', '_', safe.strip())
    
    # 6. 去除首尾的点号和下划线（Windows 不允许）
    safe = safe.strip('._')
    
    # 7. 限制长度（考虑中文占用更多字节）
    # Windows 路径限制260字符，预留空间给目录前缀
    max_bytes = 180  # 保守估计
    if len(safe.encode('utf-8')) > max_bytes:
        # 逐字符截断，确保不超过字节限制
        result = ''
        for char in safe:
            test = result + char
            if len(test.encode('utf-8')) > max_bytes:
                break
            result = test
        safe = result.rstrip('._')
    
    return safe if safe else 'dataset'


# ========== 统一命名管理 (混合式方案) ==========

def generate_unified_dataset_dirname(dataset_id: str, dataset_type: str, display_name: str) -> str:
    """生成统一格式数据集目录名: {id}--{tag}--{safe_name}

    Args:
        dataset_id: 数据集ID
        dataset_type: 数据集类型 (DatasetType枚举值)
        display_name: 显示名称

    Returns:
        统一格式的目录名
    """
    from .models import DatasetType

    # 获取类型标签
    ds_type_enum = DatasetType(dataset_type)
    tag = ds_type_enum.type_tag

    # 生成安全名称
    safe_name = safeify_name(display_name)

    return f"{dataset_id.lower()}--{tag}--{safe_name}"


def parse_unified_dataset_dirname(dirname: str) -> tuple[str, str | None, str, str]:
    """解析统一格式数据集目录名 (混合式解析)

    Args:
        dirname: 目录名

    Returns:
        tuple[dataset_id, dataset_type, display_name, version]
        - dataset_type: None表示需要根据父目录推断
        - version: 'v1'=统一格式, 'legacy'=旧格式, 'fallback'=兜底
    """
    from .models import DatasetType
    import re

    # v1统一格式: {id}--{tag}--{safe_name}
    # safe_name 现在可以包含中文等 Unicode 字符
    v1_match = re.match(r'^([a-z0-9]{6,12})--([ivsm])--(.+)$', dirname)
    if v1_match:
        ds_id, tag, safe_name = v1_match.groups()
        dataset_type_enum = DatasetType.from_tag(tag)
        if dataset_type_enum:
            # 将下划线转回空格以恢复显示名称
            display_name = safe_name.replace('_', ' ')
            return ds_id, dataset_type_enum.value, display_name, "v1"

    # legacy格式: {id}__{safe_name}
    if '__' in dirname:
        parts = dirname.split('__', 1)
        ds_id, safe_name = parts[0], parts[1]
        display_name = safe_name.replace('_', ' ')
        return ds_id, None, display_name, "legacy"

    # fallback: 任意字符串
    return dirname, None, dirname, "fallback"


def get_unified_family_dir(workspace_root: Path, dataset_type: str) -> Path:
    """获取数据集类型对应的家族目录 (统一方案)

    Args:
        workspace_root: 工作区根目录
        dataset_type: 数据集类型 (DatasetType枚举值)

    Returns:
        家族目录路径
    """
    from .models import DatasetType

    ds_type_enum = DatasetType(dataset_type)
    family_dir_name = ds_type_enum.family_dir

    return workspace_root / "datasets" / family_dir_name


def load_dataset_with_family_validation(dir_path: Path) -> dict[str, Any]:
    """加载数据集并进行家族目录一致性校验 (混合式方案)

    Args:
        dir_path: 数据集目录路径

    Returns:
        数据集信息字典
    """
    from ...utils.logger import log_warning

    # 解析目录名
    ds_id, dtype_from_tag, display_name, version = parse_unified_dataset_dirname(dir_path.name)

    # 确定最终类型 (tag权威，目录兜底)
    if dtype_from_tag:
        final_type = dtype_from_tag
    else:
        # legacy/fallback: 根据父目录推断
        parent_name = dir_path.parent.name
        if parent_name == "image_datasets":
            final_type = DatasetType.IMAGE.value
        elif parent_name == "video_datasets":
            final_type = DatasetType.VIDEO.value
        elif parent_name == "control_image_datasets":
            final_type = DatasetType.SINGLE_CONTROL_IMAGE.value  # 默认单图控制
        else:
            final_type = DatasetType.IMAGE.value  # 最终兜底

    # 家族目录一致性校验 (非阻断)
    from .models import DatasetType
    expected_family = DatasetType(final_type).family_dir
    actual_family = dir_path.parent.name
    family_consistent = actual_family == expected_family

    if not family_consistent:
        log_warning(f"[FAMILY_MISMATCH] Dataset {ds_id} type='{final_type}' but in '{actual_family}/', expected in '{expected_family}/' (using tag authority)")

    return {
        "id": ds_id,
        "type": final_type,
        "name": display_name,
        "path": dir_path,
        "version": version,
        "family_consistent": family_consistent
    }


def create_unified_dataset_directory(workspace_root: Path, dataset_id: str, dataset_type: str, display_name: str) -> Path:
    """创建统一格式数据集目录 (混合式方案)

    Args:
        workspace_root: 工作区根目录
        dataset_id: 数据集ID
        dataset_type: 数据集类型
        display_name: 显示名称

    Returns:
        创建的数据集目录路径
    """
    from ...utils.logger import log_info
    from .models import DatasetType

    # 1. 生成v1格式目录名
    dirname = generate_unified_dataset_dirname(dataset_id, dataset_type, display_name)

    # 2. 获取家族目录
    family_dir = get_unified_family_dir(workspace_root, dataset_type)
    family_dir.mkdir(parents=True, exist_ok=True)

    # 3. 处理重名 (在家族目录内确保唯一)
    final_dirname = dirname
    counter = 2
    while (family_dir / final_dirname).exists():
        safe_name_with_counter = safeify_name(f"{display_name} {counter}")
        final_dirname = generate_unified_dataset_dirname(dataset_id, dataset_type, safe_name_with_counter)
        counter += 1

    # 4. 创建目录
    dataset_path = family_dir / final_dirname
    dataset_path.mkdir(parents=True, exist_ok=True)

    log_info(f"Created unified dataset directory: {dataset_path} (type={dataset_type})")
    return dataset_path


def generate_control_dirname(dataset_id: str, subtype: str, display_name: str) -> str:
    """生成控制图数据集目录名（v1协议）

    Args:
        dataset_id: 数据集ID
        subtype: DatasetType.SINGLE_CONTROL_IMAGE.value 或 DatasetType.MULTI_CONTROL_IMAGE.value
        display_name: 显示名称

    Returns:
        v1格式的目录名: {dataset_id}--{tag}--{safe_name}
    """
    tag = 's' if subtype == DatasetType.SINGLE_CONTROL_IMAGE.value else 'm'
    safe_name = safeify_name(display_name)
    return f"{dataset_id.lower()}--{tag}--{safe_name}"


def next_control_index(ds_dir: Path, source_basename: str) -> int:
    """获取控制图像的下一个索引
    
    Args:
        ds_dir: 数据集目录
        source_basename: 源文件基础名(不含扩展名)
        
    Returns:
        下一个可用的索引号
    """
    controls_dir = ds_dir / "controls"
    if not controls_dir.exists():
        return 0
    
    max_index = -1
    pattern = f"{re.escape(source_basename)}_(\\d+)\\."
    
    for file in controls_dir.iterdir():
        match = re.match(pattern, file.name)
        if match:
            index = int(match.group(1))
            max_index = max(max_index, index)
    
    return max_index + 1


def get_dataset_warehouse_path(workspace_root: Path, dataset_type: str) -> Path:
    """获取数据集类型对应的仓库路径

    Args:
        workspace_root: 工作区根目录
        dataset_type: 数据集类型枚举值

    Returns:
        仓库目录路径

    Raises:
        ValueError: 当数据集类型不支持时
    """
    # 所有仓库都在datasets子目录下
    datasets_root = workspace_root / "datasets"

    if dataset_type == DatasetType.IMAGE.value:
        return datasets_root / "image_datasets"
    elif dataset_type == DatasetType.SINGLE_CONTROL_IMAGE.value or dataset_type == DatasetType.MULTI_CONTROL_IMAGE.value:
        return datasets_root / "control_image_datasets"
    elif dataset_type == DatasetType.VIDEO.value:
        return datasets_root / "video_datasets"
    else:
        raise ValueError(f"不支持的数据集类型: {dataset_type}，支持的类型: {[t.value for t in DatasetType]}")


def get_dataset_subdirs(dataset_type: str) -> List[str]:
    """获取数据集类型对应的子目录列表

    Args:
        dataset_type: 数据集类型枚举值

    Returns:
        子目录名称列表

    Raises:
        ValueError: 当数据集类型不支持时
    """
    if dataset_type == DatasetType.IMAGE.value:
        return []  # 直接存放在根目录
    elif dataset_type == DatasetType.SINGLE_CONTROL_IMAGE.value or dataset_type == DatasetType.MULTI_CONTROL_IMAGE.value:
        return ["targets", "controls"]
    elif dataset_type == DatasetType.VIDEO.value:
        return []  # 视频文件直接存放在根目录
    else:
        raise ValueError(f"不支持的数据集类型: {dataset_type}，支持的类型: {[t.value for t in DatasetType]}")


def atomic_write_text(path: Path, text: str):
    """原子性写入文本文件
    
    Args:
        path: 目标文件路径
        text: 要写入的文本内容
    """
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)


def generate_unique_name(base_path: Path, name: str) -> str:
    """生成唯一文件名
    
    Args:
        base_path: 基础目录路径
        name: 原始文件名
        
    Returns:
        唯一的文件名
    """
    if not (base_path / name).exists():
        return name
    
    # 分离文件名和扩展名
    stem = Path(name).stem
    suffix = Path(name).suffix
    
    counter = 2
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        if not (base_path / new_name).exists():
            return new_name
        counter += 1


def find_paired_files(files: Sequence[Path]) -> Tuple[List[Tuple[Path, Optional[Path]]], List[Path]]:
    """查找配对的媒体文件和标签文件
    
    Args:
        files: 文件路径列表
        
    Returns:
        (配对列表[(媒体文件, 标签文件或None)], 失败列表[孤立的txt文件])
    """
    # 媒体文件扩展名白名单
    MEDIA_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp',  # 图像
                  '.mp4', '.mov', '.mkv', '.webm', '.avi'}  # 视频
    
    # 按basename分组文件
    groups: Dict[str, Dict[str, Path]] = {}
    
    for file_path in files:
        path_obj = Path(file_path)
        basename = path_obj.stem
        ext = path_obj.suffix.lower()
        
        if basename not in groups:
            groups[basename] = {}
        
        if ext in MEDIA_EXTS:
            groups[basename]['media'] = path_obj
        elif ext == '.txt':
            groups[basename]['label'] = path_obj
    
    # 生成配对结果
    paired = []
    failed = []
    
    for basename, files_dict in groups.items():
        media_file = files_dict.get('media')
        label_file = files_dict.get('label')
        
        if media_file:
            # 有媒体文件，标签文件可选
            paired.append((media_file, label_file))
        elif label_file:
            # 只有标签文件，没有对应媒体文件
            failed.append(label_file)
    
    return paired, failed


def is_media_file(file_path: Path) -> bool:
    """检查是否为媒体文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否为支持的媒体文件
    """
    MEDIA_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp',
                  '.mp4', '.mov', '.mkv', '.webm', '.avi'}
    return file_path.suffix.lower() in MEDIA_EXTS


def is_image_file(file_path: Path) -> bool:
    """检查是否为图像文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否为支持的图像文件
    """
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    return file_path.suffix.lower() in IMAGE_EXTS


def is_video_file(file_path: Path) -> bool:
    """检查是否为视频文件
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否为支持的视频文件
    """
    VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.webm', '.avi'}
    return file_path.suffix.lower() in VIDEO_EXTS


def safe_filename(filename: str) -> str:
    """确保文件名安全（防止路径穿透）
    
    Args:
        filename: 原始文件名
        
    Returns:
        安全的文件名（仅basename部分）
    """
    return Path(filename).name