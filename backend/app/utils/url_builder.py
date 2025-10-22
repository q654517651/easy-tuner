"""
URL构建工具模块

提供统一的URL生成函数,确保返回完整的绝对URL而非相对URL。
特别适配工作区路径可动态配置的场景。
"""

from typing import Optional
from pathlib import Path
from fastapi import Request


def build_workspace_url(
    request: Optional[Request],
    relative_path: str,
    fallback_origin: str = ""
) -> str:
    """
    构建workspace URL（兼容云服务器和Electron）

    Args:
        request: FastAPI Request对象（保留参数以兼容现有代码，但不再使用）
        relative_path: 相对workspace的路径 (如 "datasets/xxx/images/1.jpg")
        fallback_origin: 兜底的origin（保留参数以兼容现有代码，但不再使用）

    Returns:
        相对URL路径
        - 始终返回: "/workspace/datasets/xxx/images/1.jpg"
        - 浏览器会自动基于当前页面 origin 解析
        - Vite 代理会转发 /workspace 到后端 8000 端口
        - Electron 也能正常处理（前端 joinApiUrl 会处理）

    Examples:
        >>> build_workspace_url(request, "datasets/abc/images/1.jpg")
        "/workspace/datasets/abc/images/1.jpg"

        >>> build_workspace_url(None, "datasets/abc/images/1.jpg")
        "/workspace/datasets/abc/images/1.jpg"
    """
    # 规范化相对路径:移除开头的斜杠
    rel = relative_path.lstrip('/')
    
    # 🔧 始终返回相对路径（兼容所有部署场景）
    # - 云服务器: 浏览器基于 http://服务器IP:6006 解析，Vite 代理转发到后端
    # - 开发环境: 浏览器基于 http://localhost:5173 解析，Vite 代理转发到后端
    # - Electron: 前端 joinApiUrl 会将相对路径转换为 http://127.0.0.1:动态端口
    return f"/workspace/{rel}"


def build_workspace_urls(
    request: Optional[Request],
    relative_paths: list[str],
    fallback_origin: str = ""
) -> list[str]:
    """
    批量构建workspace URLs（兼容云服务器和Electron）

    Args:
        request: FastAPI Request对象
        relative_paths: 相对路径列表
        fallback_origin: 兜底的origin（空字符串表示返回相对路径）

    Returns:
        完整URL或相对URL列表
    """
    return [build_workspace_url(request, path, fallback_origin) for path in relative_paths]


def is_absolute_url(url: str) -> bool:
    """
    判断是否为完整的绝对URL

    Args:
        url: 待检查的URL字符串

    Returns:
        True if absolute URL, False otherwise
    """
    return url.startswith(('http://', 'https://', 'ftp://', 'file://'))


def normalize_relative_path(path: str) -> str:
    """
    规范化相对路径:
    - 统一使用正斜杠
    - 移除开头的斜杠
    - 移除多余的斜杠

    Args:
        path: 原始路径

    Returns:
        规范化后的路径

    Examples:
        >>> normalize_relative_path("\\datasets\\abc\\1.jpg")
        "datasets/abc/1.jpg"

        >>> normalize_relative_path("/datasets/abc//1.jpg")
        "datasets/abc/1.jpg"
    """
    # 转换为Path对象,自动处理反斜杠
    p = Path(path)

    # 使用as_posix()转为正斜杠格式
    normalized = p.as_posix()

    # 移除开头的斜杠
    normalized = normalized.lstrip('/')

    return normalized
