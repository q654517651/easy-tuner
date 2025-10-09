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
        """
        修复训练环境

        Args:
            use_china_mirror: 是否使用国内镜像源

        Returns:
            Tuple[bool, str]: (成功状态, 消息)
        """
        try:
            log_info("开始修复训练环境...")

            # 验证安装脚本是否存在
            if not self.setup_script.exists():
                error_msg = f"安装脚本不存在: {self.setup_script}"
                log_error(error_msg)
                return False, error_msg

            # 运行安装脚本
            log_info(f"运行安装脚本: {self.setup_script}")

            # 检测PowerShell版本
            ps_cmd = await self._detect_powershell()

            # 构建PowerShell命令参数
            ps_args = [ps_cmd, "-ExecutionPolicy", "Bypass", "-File", str(self.setup_script)]
            if use_china_mirror:
                ps_args.append("-UseChinaMirror")
                log_info("使用国内镜像源")

            # 使用asyncio运行PowerShell脚本 (修复编码参数问题)
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *ps_args,
                    cwd=str(self.runtime_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=300.0  # 5分钟超时
            )

            stdout_b, stderr_b = await process.communicate()
            stdout = stdout_b.decode("utf-8", "ignore") if stdout_b else ""
            stderr = stderr_b.decode("utf-8", "ignore") if stderr_b else ""

            # 检查执行结果
            if process.returncode == 0:
                # 验证安装结果
                python_exe = self.python_dir / "python.exe"
                uv_exe = self.python_dir / "Scripts" / "uv.exe"

                if python_exe.exists() and uv_exe.exists():
                    log_success("训练环境修复成功")
                    return True, "训练环境修复成功"
                else:
                    error_msg = "安装完成但Python环境不完整"
                    log_error(error_msg)
                    return False, f"{error_msg}\nStdout: {stdout}\nStderr: {stderr}"
            else:
                error_msg = f"安装脚本执行失败 (退出代码: {process.returncode})"
                log_error(error_msg)
                return False, f"{error_msg}\nStdout: {stdout}\nStderr: {stderr}"

        except Exception as e:
            error_msg = f"修复训练环境时发生错误: {str(e)}"
            log_error(error_msg)
            return False, error_msg

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