"""
文件访问工具
"""

import mimetypes
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


class FileUtils:
    """文件访问工具集"""

    @staticmethod
    def validate_task_file_path(task_id: str, subpath: str) -> Path:
        """校验任务文件相对路径，防止目录穿越，并返回绝对路径。

        - 允许 subpath 含多级子目录（如 'output/sample/xxx.png')
        - 统一将反斜杠替换为正斜杠，并去掉前导斜杠
        - 仅允许访问 task 根目录下的文件
        """
        task_root = Path("workspace") / "tasks" / task_id
        safe_rel = (subpath or "").replace("\\", "/").lstrip("/")

        try:
            file_path = (task_root / safe_rel).resolve()
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail="无效的文件路径")

        # 安全校验：必须位于任务根目录内
        try:
            file_path.relative_to(task_root.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="禁止访问超出任务目录的路径")

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        return file_path

    @staticmethod
    def create_file_response(file_path: Path) -> StreamingResponse:
        """创建文件响应（图片 inline，其它附件下载）"""
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        if file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
            disposition = "inline"
        else:
            disposition = f'attachment; filename="{file_path.name}"'

        headers = {"Content-Disposition": disposition}

        def file_stream():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(file_stream(), headers=headers, media_type=content_type)

