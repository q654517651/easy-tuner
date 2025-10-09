# -*- coding: utf-8 -*-
"""
安装服务 - 提供实时安装进度推送
"""

import asyncio
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
from enum import Enum

from ..core.state.events import EventBus, get_event_bus
from ..utils.logger import log_info, log_error, log_success


class InstallationState(str, Enum):
    """安装状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Installation:
    """安装任务"""
    def __init__(self, installation_id: str, use_china_mirror: bool):
        self.id = installation_id
        self.use_china_mirror = use_china_mirror
        self.state = InstallationState.PENDING
        self.process: Optional[asyncio.subprocess.Process] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.logs: list[str] = []


class InstallationService:
    """安装服务"""

    def __init__(self):
        self._installations: Dict[str, Installation] = {}
        self._event_bus: EventBus = get_event_bus()

        # 获取路径
        from ..core.environment import get_paths
        paths = get_paths()
        self.runtime_dir = paths.runtime_dir
        self.python_dir = paths.runtime_dir / "python"
        self.setup_script = paths.setup_script

    async def _detect_powershell(self) -> str:
        """检测可用的PowerShell版本"""
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
        return "powershell"

    async def start_installation(self, use_china_mirror: bool = False) -> str:
        """
        启动安装任务

        Args:
            use_china_mirror: 是否使用国内镜像源

        Returns:
            installation_id: 安装任务ID

        Raises:
            RuntimeError: 如果已有安装任务正在运行
        """
        # 检查是否已有正在运行的安装任务
        for inst_id, inst in self._installations.items():
            if inst.state in [InstallationState.PENDING, InstallationState.RUNNING]:
                raise RuntimeError(f"已有安装任务正在进行中 (ID: {inst_id})，请等待完成后再试")

        installation_id = str(uuid.uuid4())[:8]
        installation = Installation(installation_id, use_china_mirror)
        self._installations[installation_id] = installation

        log_info(f"创建安装任务: {installation_id}")

        # 异步启动安装进程
        asyncio.create_task(self._run_installation(installation))

        return installation_id

    async def _run_installation(self, installation: Installation):
        """运行安装进程"""
        try:
            # 验证安装脚本
            if not self.setup_script.exists():
                error_msg = f"安装脚本不存在: {self.setup_script}"
                log_error(error_msg)
                await self._emit_log(installation.id, error_msg)
                await self._finalize_installation(installation, InstallationState.FAILED, error_msg)
                return

            # 诊断：检查事件循环类型
            loop = asyncio.get_running_loop()
            policy = asyncio.get_event_loop_policy()
            await self._emit_log(installation.id,
                f"[诊断] EventLoop={type(loop).__name__}, Policy={type(policy).__name__}")

            # 检测 PowerShell
            ps_cmd = await self._detect_powershell()
            await self._emit_log(installation.id, f"使用 PowerShell: {ps_cmd}")

            # 构建命令
            ps_args = [ps_cmd, "-ExecutionPolicy", "Bypass", "-File", str(self.setup_script)]
            if installation.use_china_mirror:
                ps_args.append("-UseChinaMirror")
                await self._emit_log(installation.id, "使用国内镜像源")

            # 启动进程
            installation.state = InstallationState.RUNNING
            installation.started_at = datetime.now()
            await self._emit_state(installation.id, InstallationState.RUNNING)
            await self._emit_log(installation.id, f"开始安装: {' '.join(ps_args)}")

            process = await asyncio.create_subprocess_exec(
                *ps_args,
                cwd=str(self.runtime_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # 合并 stderr 到 stdout
            )
            installation.process = process

            # 逐行读取输出
            if process.stdout:
                async for line in process.stdout:
                    decoded = line.decode('utf-8', errors='ignore').rstrip('\n\r')
                    if decoded.strip():
                        installation.logs.append(decoded)
                        await self._emit_log(installation.id, decoded)

            # 等待进程结束
            returncode = await process.wait()

            # 检查结果
            if installation.state == InstallationState.CANCELLED:
                await self._emit_log(installation.id, "安装已取消")
                await self._finalize_installation(installation, InstallationState.CANCELLED, "用户取消安装")
                return

            if returncode == 0:
                # 验证安装结果
                python_exe = self.python_dir / "python.exe"
                uv_exe = self.python_dir / "Scripts" / "uv.exe"

                if python_exe.exists() and uv_exe.exists():
                    await self._emit_log(installation.id, "✅ 安装成功！")
                    await self._finalize_installation(installation, InstallationState.COMPLETED, None)
                else:
                    error_msg = "安装完成但 Python 环境不完整"
                    await self._emit_log(installation.id, f"❌ {error_msg}")
                    await self._finalize_installation(installation, InstallationState.FAILED, error_msg)
            else:
                error_msg = f"安装脚本执行失败（退出代码: {returncode}）"
                await self._emit_log(installation.id, f"❌ {error_msg}")
                await self._finalize_installation(installation, InstallationState.FAILED, error_msg)

        except asyncio.CancelledError:
            await self._emit_log(installation.id, "安装任务被取消")
            await self._finalize_installation(installation, InstallationState.CANCELLED, "任务被取消")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            error_msg = f"安装过程发生错误: {type(e).__name__}: {str(e)}"
            log_error(f"{error_msg}\n{error_detail}")
            await self._emit_log(installation.id, f"❌ {error_msg}")
            await self._emit_log(installation.id, f"详细错误: {error_detail}")
            await self._finalize_installation(installation, InstallationState.FAILED, error_msg)

    async def cancel_installation(self, installation_id: str) -> Tuple[bool, str]:
        """
        取消安装任务

        Args:
            installation_id: 安装任务ID

        Returns:
            Tuple[bool, str]: (成功状态, 消息)
        """
        installation = self._installations.get(installation_id)
        if not installation:
            return False, "安装任务不存在"

        if installation.state not in [InstallationState.PENDING, InstallationState.RUNNING]:
            return False, f"无法取消：当前状态为 {installation.state}"

        try:
            installation.state = InstallationState.CANCELLED
            await self._emit_log(installation_id, "正在取消安装...")

            if installation.process:
                process = installation.process

                # 1. 先尝试优雅终止
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    log_info(f"安装进程已优雅终止: {installation_id}")
                except asyncio.TimeoutError:
                    # 2. 超时则强制杀死
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=2.0)
                        log_info(f"安装进程已强制终止: {installation_id}")
                    except Exception as e:
                        log_error(f"强制终止失败: {e}")

                # 3. Windows 特殊处理：taskkill 杀进程树
                import sys
                if sys.platform == "win32" and process.pid:
                    try:
                        import subprocess
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=3.0
                        )
                    except Exception:
                        pass

            await self._emit_log(installation_id, "安装已取消")
            await self._emit_state(installation_id, InstallationState.CANCELLED)
            return True, "安装已取消"

        except Exception as e:
            error_msg = f"取消安装失败: {str(e)}"
            log_error(error_msg)
            return False, error_msg

    def get_installation(self, installation_id: str) -> Optional[Installation]:
        """获取安装任务"""
        return self._installations.get(installation_id)

    async def _emit_log(self, installation_id: str, line: str):
        """发送日志事件"""
        await self._event_bus.emit('installation.log', {
            'installation_id': installation_id,
            'line': line,
            'timestamp': datetime.now().isoformat()
        })

    async def _emit_state(self, installation_id: str, state: InstallationState):
        """发送状态事件"""
        await self._event_bus.emit('installation.state', {
            'installation_id': installation_id,
            'state': state.value,
            'timestamp': datetime.now().isoformat()
        })

    async def _finalize_installation(self, installation: Installation, state: InstallationState, error_message: Optional[str]):
        """完成安装任务"""
        installation.state = state
        installation.completed_at = datetime.now()
        installation.error_message = error_message
        await self._emit_state(installation.id, state)
        log_info(f"安装任务完成: {installation.id} - {state.value}")


# 全局实例
_installation_service_instance: Optional[InstallationService] = None


def get_installation_service() -> InstallationService:
    """获取安装服务实例"""
    global _installation_service_instance
    if _installation_service_instance is None:
        _installation_service_instance = InstallationService()
    return _installation_service_instance
