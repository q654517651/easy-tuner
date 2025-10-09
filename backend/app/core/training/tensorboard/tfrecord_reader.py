"""
TFRecord 读取器 - 直接解析 events.out.tfevents.* 文件
"""

import struct
from typing import Iterator, Optional
from pathlib import Path
from backend.app.utils.logger import log_info, log_warn, log_error


def crc32c(data: bytes) -> int:
    """简单的CRC32C实现（可选校验，默认关闭）"""
    # 为了简化，暂时返回0（不校验）
    # 生产环境可以使用 crc32c 库或自实现
    return 0


class TFRecordReader:
    """TFRecord格式读取器"""

    def __init__(self, file_path: Path, verify_crc: bool = False):
        self.file_path = file_path
        self.verify_crc = verify_crc

    def read_records(self) -> Iterator[bytes]:
        """
        读取TFRecord格式的事件文件
        格式: [length:8][len_crc:4][payload:length][payload_crc:4]
        """
        try:
            with open(self.file_path, 'rb') as f:
                while True:
                    # 读取记录长度 (8字节 little-endian uint64)
                    length_data = f.read(8)
                    if len(length_data) < 8:
                        break  # 文件结束

                    length = struct.unpack('<Q', length_data)[0]

                    # 读取长度CRC (4字节)
                    len_crc_data = f.read(4)
                    if len(len_crc_data) < 4:
                        break

                    len_crc = struct.unpack('<I', len_crc_data)[0]

                    # CRC校验（可选）
                    if self.verify_crc:
                        expected_crc = crc32c(length_data)
                        if len_crc != expected_crc:
                            log_warn(f"长度CRC校验失败: expected={expected_crc}, got={len_crc}")
                            continue

                    # 读取payload
                    payload = f.read(length)
                    if len(payload) < length:
                        break

                    # 读取payload CRC (4字节)
                    payload_crc_data = f.read(4)
                    if len(payload_crc_data) < 4:
                        break

                    payload_crc = struct.unpack('<I', payload_crc_data)[0]

                    # CRC校验（可选）
                    if self.verify_crc:
                        expected_crc = crc32c(payload)
                        if payload_crc != expected_crc:
                            log_warn(f"Payload CRC校验失败: expected={expected_crc}, got={payload_crc}")
                            continue

                    yield payload

        except (IOError, struct.error) as e:
            log_error(f"读取TFRecord文件失败 {self.file_path}", exc=e)
            return


def find_latest_event_file(logs_dir: Path) -> Optional[Path]:
    """查找最新的TensorBoard事件文件"""
    if not logs_dir.exists():
        return None

    # 搜索可能的路径
    search_dirs = [
        logs_dir,
        logs_dir / "network_train",
        logs_dir / "train"
    ]

    candidates = []
    for search_dir in search_dirs:
        if search_dir.exists():
            # 查找 events.out.tfevents.* 文件
            for event_file in search_dir.glob("events.out.tfevents.*"):
                candidates.append(event_file)

    if not candidates:
        return None

    # 返回最新修改的文件
    return max(candidates, key=lambda x: x.stat().st_mtime)


def find_event_file_for_task(workspace: Path, task_id: str) -> Optional[Path]:
    """为特定任务查找事件文件"""
    logs_root = workspace / "tasks" / task_id / "logs"

    if not logs_root.exists():
        return None

    # 兼容两种布局：
    # A) logs/ 下直接是 events.out.tfevents.*
    # B) logs/<run_dir>/events.out.tfevents.*（或 network_train/train 子目录）
    try:
        # 先直接在 logs_root 下尝试查找事件文件
        direct = find_latest_event_file(logs_root)
        if direct:
            return direct

        # 再尝试在子目录中查找最新 run 目录
        log_dirs = [d for d in logs_root.iterdir() if d.is_dir()]
        if log_dirs:
            latest_log_dir = max(log_dirs, key=lambda x: x.stat().st_mtime)
            return find_latest_event_file(latest_log_dir)

        return None

    except Exception as e:
        log_error("查找事件文件失败", exc=e)
        return None
