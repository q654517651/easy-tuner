"""
文件处理工具
"""

import mimetypes
from pathlib import Path
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


class FileUtils:
    """文件处理工具类"""

    @staticmethod
    def validate_task_file_path(task_id: str, subpath: str) -> Path:
        """验证并解析任务文件路径，防止目录穿越"""
        task_root = Path(f"workspace/tasks/{task_id}")
        output_root = task_root / "output"

        # 解析目标路径
        target_path = output_root / subpath
        try:
            resolved_path = target_path.resolve()
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail="无效的文件路径")

        # 安全检查：必须在output目录内
        try:
            resolved_path.relative_to(output_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="禁止访问该路径")

        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        return resolved_path

    @staticmethod
    def create_file_response(file_path: Path) -> StreamingResponse:
        """创建简单的文件响应"""
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        # 图片显示为inline，其他文件为附件
        if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
            disposition = "inline"
        else:
            disposition = f'attachment; filename="{file_path.name}"'

        headers = {
            "Content-Disposition": disposition,
        }

        def file_stream():
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

        return StreamingResponse(
            file_stream(),
            headers=headers,
            media_type=content_type
        )