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
        request: FastAPI Request对象 (用于获取当前请求的origin)
        relative_path: 相对workspace的路径 (如 "datasets/xxx/images/1.jpg")
        fallback_origin: 兜底的origin,当request为None时使用（空字符串表示返回相对路径）

    Returns:
        完整URL或相对URL
        - 有request时: "http://host:port/workspace/datasets/xxx/images/1.jpg"
        - 无request时: "/workspace/datasets/xxx/images/1.jpg" (相对路径，兼容云服务器)

    Examples:
        >>> build_workspace_url(request, "datasets/abc/images/1.jpg")
        "http://127.0.0.1:8000/workspace/datasets/abc/images/1.jpg"

        >>> build_workspace_url(None, "datasets/abc/images/1.jpg")
        "/workspace/datasets/abc/images/1.jpg"
    """
    # 规范化相对路径:移除开头的斜杠
    rel = relative_path.lstrip('/')

    # 优先使用request的origin（Electron 模式或有明确 request 时）
    if request:
        origin = f"{request.url.scheme}://{request.url.netloc}"
        return f"{origin}/workspace/{rel}"
    
    # 🔧 无 request 时：返回相对路径（兼容云服务器）
    # 浏览器会自动基于当前页面 origin 解析，Vite 代理会转发到后端
    if fallback_origin:
        return f"{fallback_origin}/workspace/{rel}"
    else:
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
