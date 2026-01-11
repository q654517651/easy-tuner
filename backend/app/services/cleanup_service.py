"""临时文件清理服务"""
from pathlib import Path
import time
import logging

from ..core.environment import get_paths

logger = logging.getLogger(__name__)

# 临时文件最大存活时间：24小时（秒）
TEMP_FILE_MAX_AGE = 24 * 60 * 60


def cleanup_expired_temp_files():
    """清理超过 24 小时的临时控制图"""
    try:
        temp_dir = get_paths().workspace_root / "temp" / "control_images"

        if not temp_dir.exists():
            return

        current_time = time.time()
        cleaned_count = 0

        for temp_file in temp_dir.glob("control_*"):
            if not temp_file.is_file():
                continue

            # 检查文件修改时间
            try:
                file_age = current_time - temp_file.stat().st_mtime

                if file_age > TEMP_FILE_MAX_AGE:
                    temp_file.unlink(missing_ok=True)
                    cleaned_count += 1
                    logger.info(f"已清理过期临时文件: {temp_file.name}")
            except Exception as e:
                logger.exception(f"清理临时文件失败 {temp_file.name}: {e}")

        if cleaned_count > 0:
            logger.info(f"临时文件清理完成，共清理 {cleaned_count} 个文件")

    except Exception as e:
        logger.exception(f"临时文件清理任务失败: {e}")

