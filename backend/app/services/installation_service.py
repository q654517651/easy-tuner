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
        self._paths = paths
        self.runtime_dir = paths.runtime_dir
        self.python_dir = paths.runtime_dir / "python"
        self.setup_script = paths.setup_script

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
        """运行安装进程（直接调用安装器，避免子进程）"""
        try:
            installation.state = InstallationState.RUNNING
            installation.started_at = datetime.now()
            await self._emit_state(installation.id, InstallationState.RUNNING)

            if installation.use_china_mirror:
                await self._emit_log(installation.id, "🌏 使用国内镜像源（清华 TUNA + Gitee）")

            await self._emit_log(installation.id, "开始安装 Runtime 环境...")
            await self._emit_log(installation.id, f"目标目录: {self.runtime_dir}")

            # 导入安装器
            try:
                import sys
                import importlib.util

                # 查找 install_runtime.py 的完整路径
                # 在打包环境中，scripts 目录位于 resources/backend/scripts（通过 extraResources 配置）
                script_path = self._paths.backend_root / "scripts" / "install_runtime.py"

                await self._emit_log(installation.id, f"正在加载安装脚本: {script_path}")

                if not script_path.exists():
                    # 提供调试信息
                    await self._emit_log(installation.id, f"backend_root: {self._paths.backend_root}")
                    await self._emit_log(installation.id, f"backend_root exists: {self._paths.backend_root.exists()}")
                    if self._paths.backend_root.exists():
                        try:
                            scripts_dir = self._paths.backend_root / "scripts"
                            await self._emit_log(installation.id, f"scripts_dir exists: {scripts_dir.exists()}")
                            if scripts_dir.exists():
                                files = list(scripts_dir.iterdir())
                                await self._emit_log(installation.id, f"scripts_dir contents: {[f.name for f in files]}")
                        except Exception as debug_e:
                            await self._emit_log(installation.id, f"无法列出 scripts 目录: {debug_e}")
                    raise ImportError(f"安装脚本不存在: {script_path}")

                # 动态加载模块
                spec = importlib.util.spec_from_file_location("install_runtime", script_path)
                if spec is None or spec.loader is None:
                    raise ImportError(f"无法加载安装脚本: {script_path}")

                install_runtime_module = importlib.util.module_from_spec(spec)
                sys.modules["install_runtime"] = install_runtime_module
                spec.loader.exec_module(install_runtime_module)

                run_install = install_runtime_module.run_install
                set_output_callback = install_runtime_module.set_output_callback
                set_cancel_flag = install_runtime_module.set_cancel_flag

                await self._emit_log(installation.id, "✅ 安装脚本加载成功")

                # 设置输出回调（捕获安装器的日志）
                async def log_callback(line: str):
                    await self._emit_log(installation.id, line)

                # 创建同步回调包装器
                loop = asyncio.get_event_loop()
                def sync_callback(line: str):
                    asyncio.run_coroutine_threadsafe(log_callback(line), loop)

                set_output_callback(sync_callback)

                # 保存取消函数引用
                installation._cancel_installer = set_cancel_flag

            except Exception as e:
                error_msg = f"无法导入安装器: {e}"
                log_error(error_msg)
                await self._emit_log(installation.id, f"❌ {error_msg}")
                await self._finalize_installation(installation, InstallationState.FAILED, error_msg)
                return

            # 在线程池中运行安装器（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            returncode = await loop.run_in_executor(
                None,
                run_install,
                str(self.runtime_dir),
                installation.use_china_mirror
            )

            # 检查取消状态
            if installation.state == InstallationState.CANCELLED:
                await self._emit_log(installation.id, "安装已取消")
                await self._finalize_installation(installation, InstallationState.CANCELLED, "用户取消安装")
                return

            # 检查安装结果
            if returncode == 0:
                # 验证安装结果
                if self._validate_installation():
                    await self._emit_log(installation.id, "✅ 安装成功！")
                    await self._finalize_installation(installation, InstallationState.COMPLETED, None)
                else:
                    error_msg = "安装脚本完成但环境验证失败"
                    await self._emit_log(installation.id, f"❌ {error_msg}")
                    await self._finalize_installation(installation, InstallationState.FAILED, error_msg)
            elif returncode == 2:
                # 退出码 2 表示已取消
                await self._emit_log(installation.id, "⚠️ 安装已被用户取消")
                await self._finalize_installation(installation, InstallationState.CANCELLED, "用户取消安装")
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

    def _validate_installation(self) -> bool:
        """
        验证安装结果（轻量级检测，复用环境管理器）

        注意：安装完成后，环境管理器的缓存路径可能还是旧的，需要刷新
        """
        # ✨ 刷新环境管理器缓存（重要：安装后路径可能已变化）
        from ..core.environment import get_env_manager
        env_manager = get_env_manager()

        # 重新初始化以刷新路径检测
        env_manager.reset()
        fresh_paths = env_manager.initialize(validate=False)

        # 使用最新的路径状态
        python_ok = fresh_paths.runtime_python_exists
        musubi_ok = fresh_paths.musubi_exists

        if not python_ok:
            log_error(f"Python 环境验证失败: {fresh_paths.runtime_python} 不存在")
        if not musubi_ok:
            log_error(f"Musubi 验证失败: {fresh_paths.musubi_dir} 不存在或不是 Git 仓库")

        return python_ok and musubi_ok

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
            # 设置取消标志（优先使用新的取消信号机制）
            if hasattr(installation, '_cancel_installer') and installation._cancel_installer:
                log_info(f"设置安装器取消标志: {installation_id}")
                installation._cancel_installer()  # 调用 install_runtime.set_cancel_flag()

            installation.state = InstallationState.CANCELLED
            await self._emit_log(installation_id, "正在取消安装...")

            # 旧的进程终止逻辑（保留作为兜底，但当前架构下 process 为 None）
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
            else:
                log_info(f"使用取消信号机制终止安装（非子进程模式）: {installation_id}")

            await self._emit_log(installation_id, "✅ 取消信号已发送，安装器将在下个检查点停止")
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
        # 追加到内存缓冲，供 WS 新连接回放
        inst = self._installations.get(installation_id)
        if inst is not None:
            try:
                inst.logs.append(line)
                if len(inst.logs) > 2000:
                    inst.logs = inst.logs[-2000:]
            except Exception:
                pass

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
