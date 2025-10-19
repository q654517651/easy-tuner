# -*- coding: utf-8 -*-
"""
Musubi训练器修复服务

提供训练环境和训练器的自动修复功能
"""

import subprocess
import asyncio
import os
from pathlib import Path
from typing import Tuple, Dict, Any
import time

from ..utils.logger import log_info, log_error, log_success


class MusubiFixService:
    """Musubi训练器修复服务"""

    def __init__(self):
        # 使用全局环境管理器获取路径
        from ..core.environment import get_paths

        paths = get_paths()
        self.project_root = paths.project_root
        self.runtime_dir = paths.runtime_dir
        self.python_dir = paths.runtime_dir / "python"
        self.musubi_dir = paths.musubi_dir
        self.setup_script = paths.setup_script

    async def _detect_powershell(self) -> str:
        """检测可用的PowerShell版本"""
        # 优先尝试 pwsh (PowerShell 7+)，fallback到 powershell (Windows内置)
        for ps_cmd in ["pwsh", "powershell"]:
            try:
                process = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        ps_cmd, "-v",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    ),
                    timeout=5.0
                )
                await process.communicate()
                if process.returncode == 0:
                    return ps_cmd
            except Exception:
                continue
        return "powershell"  # 最后的fallback

    async def fix_environment(self, use_china_mirror: bool = False) -> Tuple[bool, str]:
        """修复训练环境：统一走后端 Python 安装脚本（venv 方案）"""
        try:
            log_info("开始修复训练环境...")
            return await self._fix_with_python_installer(use_china_mirror)
        except Exception as e:
            error_msg = f"修复训练环境时发生异常: {str(e)}"
            log_error(error_msg)
            return False, error_msg

    async def _fix_with_python_installer(self, use_china_mirror: bool) -> Tuple[bool, str]:
        from ..core.environment import get_paths
        paths = get_paths()
        install_script = paths.backend_root / "scripts" / "install_runtime.py"
        if not install_script.exists():
            return False, f"安装脚本不存在: {install_script}"
        import sys
        cmd = [
            sys.executable,
            str(install_script),
            "--runtime-dir", str(self.runtime_dir),
        ]
        if use_china_mirror:
            cmd.append("--use-china-mirror")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(paths.backend_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout_b, _ = await process.communicate()
        out = stdout_b.decode("utf-8", "ignore") if stdout_b else ""
        if process.returncode == 0:
            # ✨ 使用环境管理器统一提供的 Python 路径
            from ..core.environment import get_paths
            paths = get_paths()
            py = paths.runtime_python
            if py and py.exists():
                return True, "训练环境修复成功"
            return False, "安装完成但未检测到 Runtime Python\n" + out
        return False, f"安装脚本执行失败（退出码 {process.returncode}）\n" + out
    async def fix_trainer_installation(self) -> Tuple[bool, str]:
        """
        修复训练器安装

        更新musubi-tuner子模块到最新版本
        """
        try:
            log_info("开始修复训练器安装...")

            # 验证musubi-tuner目录是否存在
            if not self.musubi_dir.exists():
                error_msg = f"musubi-tuner目录不存在: {self.musubi_dir}"
                log_error(error_msg)
                return False, error_msg

            # 检查是否为git仓库
            if not (self.musubi_dir / ".git").exists():
                error_msg = "musubi-tuner不是有效的git仓库"
                log_error(error_msg)
                return False, error_msg

            # 1. 获取远程更新
            log_info("获取远程更新...")
            fetch_process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "git", "fetch", "origin",
                    cwd=str(self.musubi_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=60.0  # 1分钟超时
            )

            fetch_stdout_b, fetch_stderr_b = await fetch_process.communicate()
            fetch_stderr = fetch_stderr_b.decode("utf-8", "ignore") if fetch_stderr_b else ""

            if fetch_process.returncode != 0:
                error_msg = f"获取远程更新失败: {fetch_stderr}"
                log_error(error_msg)
                return False, error_msg

            # 2. 强制更新到最新版本
            log_info("更新到最新版本...")
            reset_process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "git", "reset", "--hard", "origin/main",
                    cwd=str(self.musubi_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=30.0  # 30秒超时
            )

            reset_stdout_b, reset_stderr_b = await reset_process.communicate()
            reset_stderr = reset_stderr_b.decode("utf-8", "ignore") if reset_stderr_b else ""

            if reset_process.returncode != 0:
                error_msg = f"更新失败: {reset_stderr}"
                log_error(error_msg)
                return False, error_msg

            # 3. 获取更新后的版本信息
            log_process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "git", "log", "--oneline", "-1",
                    cwd=str(self.musubi_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=10.0  # 10秒超时
            )

            log_stdout_b, _ = await log_process.communicate()
            log_stdout = log_stdout_b.decode("utf-8", "ignore") if log_stdout_b else ""

            version_info = log_stdout.strip() if log_stdout else "未知版本"
            success_msg = f"训练器更新成功: {version_info}"
            log_success(success_msg)
            return True, success_msg

        except Exception as e:
            error_msg = f"修复训练器安装时发生错误: {str(e)}"
            log_error(error_msg)
            return False, error_msg

    async def check_environment_status(self) -> Dict[str, Any]:
        """
        检查训练环境状态

        Returns:
            Dict包含环境状态信息
        """
        try:
            status = {
                "python_installed": False,
                "uv_installed": False,
                "musubi_available": False,
                "python_version": None,
                "uv_version": None,
                "musubi_version": None,
                "errors": []
            }

            # 检查Python
            python_exe = self.python_dir / "python.exe"
            if python_exe.exists():
                status["python_installed"] = True
                try:
                    # 获取Python版本 (修复编码参数 + stderr兼容)
                    process = await asyncio.wait_for(
                        asyncio.create_subprocess_exec(
                            str(python_exe), "--version",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        ),
                        timeout=10.0
                    )
                    stdout_b, stderr_b = await process.communicate()

                    # Python --version 有时输出到stderr，需要兼容处理
                    stdout = stdout_b.decode("utf-8", "ignore") if stdout_b else ""
                    stderr = stderr_b.decode("utf-8", "ignore") if stderr_b else ""
                    version_output = stdout.strip() or stderr.strip()

                    if process.returncode == 0 and version_output:
                        status["python_version"] = version_output
                except Exception as e:
                    status["errors"].append(f"获取Python版本失败: {str(e)}")

            # 检查uv
            uv_exe = self.python_dir / "Scripts" / "uv.exe"
            if uv_exe.exists():
                status["uv_installed"] = True
                try:
                    # 获取uv版本 (修复编码参数)
                    process = await asyncio.wait_for(
                        asyncio.create_subprocess_exec(
                            str(uv_exe), "--version",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        ),
                        timeout=10.0
                    )
                    stdout_b, stderr_b = await process.communicate()
                    stdout = stdout_b.decode("utf-8", "ignore") if stdout_b else ""

                    if process.returncode == 0 and stdout.strip():
                        status["uv_version"] = stdout.strip()
                except Exception as e:
                    status["errors"].append(f"获取uv版本失败: {str(e)}")

            # 检查musubi-tuner
            if self.musubi_dir.exists() and (self.musubi_dir / ".git").exists():
                status["musubi_available"] = True
                try:
                    # 获取musubi版本 (修复编码参数)
                    process = await asyncio.wait_for(
                        asyncio.create_subprocess_exec(
                            "git", "log", "--oneline", "-1",
                            cwd=str(self.musubi_dir),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        ),
                        timeout=10.0
                    )
                    stdout_b, _ = await process.communicate()
                    stdout = stdout_b.decode("utf-8", "ignore") if stdout_b else ""

                    if process.returncode == 0 and stdout.strip():
                        status["musubi_version"] = stdout.strip()
                except Exception as e:
                    status["errors"].append(f"获取musubi版本失败: {str(e)}")

            return status

        except Exception as e:
            return {
                "python_installed": False,
                "uv_installed": False,
                "musubi_available": False,
                "python_version": None,
                "uv_version": None,
                "musubi_version": None,
                "errors": [f"检查环境状态时发生错误: {str(e)}"]
            }


# 全局实例
musubi_fix_service = MusubiFixService()


