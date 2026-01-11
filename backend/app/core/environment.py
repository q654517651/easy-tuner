"""
全局环境管理器 - 统一管理项目路径和运行时环境

线程安全的单例模式，支持懒加载和缓存
"""
import os
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from threading import Lock


@dataclass
class RuntimePaths:
    """运行时路径集合"""
    # 核心路径
    project_root: Path
    backend_root: Path
    workspace_root: Path

    # Runtime 相关
    runtime_dir: Path
    runtime_python: Optional[Path]
    runtime_python_exists: bool

    # Musubi 相关
    musubi_dir: Path
    musubi_src: Path
    musubi_exists: bool
    setup_script: Path

    # Engines
    engines_dir: Path


class EnvironmentManager:
    """全局环境管理器（线程安全的单例）"""

    _instance: Optional['EnvironmentManager'] = None
    _lock = Lock()  # 类级锁，用于单例创建
    _init_lock = Lock()  # 实例级锁，用于初始化
    _initialized: bool = False
    _paths: Optional[RuntimePaths] = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self, workspace_root: Optional[str] = None, validate: bool = True) -> RuntimePaths:
        """
        初始化环境管理器（幂等操作，线程安全）

        Args:
            workspace_root: 工作区根目录（可选，从配置读取）
            validate: 是否执行完整性验证

        Returns:
            RuntimePaths: 缓存的路径集合
        """
        # 快速路径：已初始化则直接返回
        if self._initialized and self._paths is not None:
            return self._paths

        # 双重检查锁定（DCL）
        with self._init_lock:
            if self._initialized and self._paths is not None:
                return self._paths

            self._do_initialize(workspace_root, validate)
            return self._paths

    def _do_initialize(self, workspace_root: Optional[str], validate: bool):
        """实际的初始化逻辑（已在锁内）"""
        from pathlib import Path
        from ..utils.logger import log_info, log_warning

        log_info("[EnvironmentManager] 初始化环境管理器...")

        # 1) 项目根（应为 resources）
        project_root = self._detect_project_root()

        # 🔒 双保险：若误返回了 .../resources/backend，则立刻回退到父级 resources
        if project_root.name.lower() == "backend" and (project_root.parent / "backend").exists():
            project_root = project_root.parent

        # 2) backend_root 固定为 resources/backend
        backend_root = (project_root / "backend").resolve()
        if not backend_root.exists():
            log_warning(f"[EnvironmentManager] backend_root 不存在: {backend_root}")

        # 3) workspace：入参优先，否则读配置
        if workspace_root is None:
            from .config import get_config
            workspace_root = get_config().storage.workspace_root
        ws_path = Path(workspace_root).resolve()

        # 4) ✨ 新架构: runtime_dir 指向 workspace/runtime（不再是 resources/runtime）
        runtime_dir = (ws_path / "runtime").resolve()
        if not runtime_dir.exists():
            log_warning(f"[EnvironmentManager] runtime_dir 不存在: {runtime_dir}，将在首次安装时创建")

        # 5) runtime python（跨平台检测）
        runtime_python = self._detect_runtime_python(runtime_dir)

        # 6) ✨ 新架构：引擎路径优先使用打包的训练器
        # 优先级：backend/engines/musubi-tuner（打包） > workspace/runtime/engines/musubi-tuner（旧架构）
        musubi_bundled = backend_root / "engines" / "musubi-tuner"
        musubi_workspace = runtime_dir / "engines" / "musubi-tuner"

        if musubi_bundled.exists() and (musubi_bundled / "src").exists():
            # 使用打包的训练器（推荐）
            musubi_dir = musubi_bundled
            engines_dir = backend_root / "engines"
            log_info(f"[EnvironmentManager] ✅ 使用打包的训练器: {musubi_dir}")
        elif musubi_workspace.exists() and (musubi_workspace / "src").exists():
            # 兼容旧架构（workspace 中的训练器）
            musubi_dir = musubi_workspace
            engines_dir = runtime_dir / "engines"
            log_warning(f"[EnvironmentManager] ⚠️ 使用 workspace 中的训练器（旧架构）: {musubi_dir}")
        else:
            # 默认使用打包路径（即使不存在，也为后续错误提示准备）
            musubi_dir = musubi_bundled
            engines_dir = backend_root / "engines"
            log_warning(f"[EnvironmentManager] ⚠️ 训练器不存在: {musubi_dir}")

        musubi_src = musubi_dir / "src"

        # 7) 安装脚本路径（保留旧路径用于向后兼容，但实际使用 Python 脚本）
        setup_script = runtime_dir / "setup_portable_uv.ps1"

        self._paths = RuntimePaths(
            project_root=project_root,  # == resources
            backend_root=backend_root,  # == resources/backend
            workspace_root=ws_path,
            runtime_dir=runtime_dir,  # ✨ workspace/runtime（新架构）
            runtime_python=runtime_python,
            runtime_python_exists=runtime_python is not None and runtime_python.exists(),
            musubi_dir=musubi_dir,
            musubi_src=musubi_src,
            musubi_exists=musubi_dir.exists() and (musubi_dir / ".git").exists(),
            setup_script=setup_script,
            engines_dir=engines_dir,
        )

        if validate:
            self._validate_environment()

        self._initialized = True
        log_info(f"[EnvironmentManager] 初始化完成: project_root={project_root} (应为 resources)")
        log_info(f"[EnvironmentManager] backend_root={backend_root}")
        log_info(f"[EnvironmentManager] ✨ runtime_dir={runtime_dir} (workspace-based)")
        log_info(f"[EnvironmentManager] workspace_root={ws_path}")
        log_info(f"[EnvironmentManager] musubi_dir={musubi_dir} (bundled={musubi_dir == musubi_bundled})")

    def _detect_project_root(self) -> Path:
        """
        始终返回【项目根 = resources 目录】：
        - 打包(PyInstaller)场景：EXE 位于 resources/backend/EasyTunerBackend.exe
          -> 返回 exe.parent.parent == resources
        - 开发场景：向上查找同时包含 backend/ 与 runtime/ 的目录；再不行用 CWD 兜底。
        """
        import os
        import sys
        from pathlib import Path

        # 1) 环境变量强制指定
        env_root = os.environ.get("TAGTRAGGER_ROOT")
        if env_root:
            root = Path(env_root).resolve()
            if root.exists():
                return root

        # 2) 打包环境：exe 在 .../resources/backend
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent  # .../resources/backend
            # ✅ 规则固定：backend 的父级才是 resources
            if exe_dir.name.lower() == "backend":
                return exe_dir.parent  # -> .../resources

            # 次优兜底：如果父级长得像 resources（包含 runtime 或 backend）
            parent_dir = exe_dir.parent
            if (parent_dir / "runtime").exists() or (parent_dir / "backend").exists():
                return parent_dir

        # 3) 开发环境：从当前文件向上找包含 backend/app 的目录
        # 🔧 修复：不再要求 runtime 必须存在（runtime 会在需要时自动创建）
        current = Path(__file__).resolve()
        for p in (current, *current.parents):
            if (p / "backend" / "app").exists():
                # 优先选择同时包含其他典型目录的路径（更可靠）
                if (p / "web").exists() or (p / "assets").exists() or (p / "README.md").exists():
                    return p
                # 如果只有 backend，也接受（最小要求）
                return p

        # 4) CWD 兜底：如果当前目录包含 backend/app
        cwd = Path.cwd()
        if (cwd / "backend" / "app").exists():
            return cwd

        raise RuntimeError(
            "无法检测项目根目录。请确保在项目根目录下运行，或设置环境变量 TAGTRAGGER_ROOT。"
        )

    def _detect_backend_root(self, project_root: Path) -> Path:
        """检测 backend 根目录（接收 project_root 作为参数，避免依赖未初始化的 self._paths）"""
        current = Path(__file__).resolve()
        for p in (current, *current.parents):
            if p.name == "backend" and (p / "app").exists():
                return p

        # Fallback: 项目根 + backend
        return project_root / "backend"

    def _detect_runtime_python(self, runtime_dir: Path) -> Optional[Path]:
        """检测 Runtime Python 可执行文件（平台兼容）"""
        if sys.platform == "win32":
            # Windows: 嵌入式 Python 的 python.exe 在根目录（不在 Scripts 子目录）
            python_exe = runtime_dir / "python" / "python.exe"
        else:
            # Linux/macOS: venv 的 python3 在 bin 子目录
            python_exe = runtime_dir / "python" / "bin" / "python3"

        return python_exe if python_exe.exists() else None

    def _validate_environment(self):
        """验证环境完整性（记录警告，不阻断启动）"""
        from ..utils.logger import log_warning

        warnings = []

        # 1. Workspace 检查
        if not self._paths.workspace_root.exists():
            warnings.append(f"Workspace 不存在: {self._paths.workspace_root}")

        # 2. Runtime Python 检查
        if not self._paths.runtime_python_exists:
            warnings.append(f"Runtime Python 不存在: {self._paths.runtime_python}")

        # 3. Musubi 检查
        if not self._paths.musubi_exists:
            warnings.append(f"Musubi 子模块未初始化: {self._paths.musubi_dir}")

        # 4. 记录日志（警告不中断启动）
        for msg in warnings:
            log_warning(f"[EnvironmentManager] {msg}")

    def get_paths(self) -> RuntimePaths:
        """获取缓存的路径（如果未初始化则自动初始化）"""
        if not self._initialized or self._paths is None:
            return self.initialize(validate=False)
        return self._paths

    def update_workspace(self, new_workspace: str):
        """
        更新 workspace 路径并刷新缓存

        注意：这只更新内存中的 workspace_root，不重新检测其他路径
        """
        from ..utils.logger import log_info

        with self._init_lock:
            log_info(f"[EnvironmentManager] 更新 workspace: {new_workspace}")

            if self._paths is None:
                # 如果未初始化，直接初始化并使用新 workspace
                self.initialize(workspace_root=new_workspace, validate=False)
            else:
                # 更新已有路径
                self._paths.workspace_root = Path(new_workspace).resolve()

            # 同步更新配置文件
            from .config import get_config, save_config
            cfg = get_config()
            cfg.storage.workspace_root = new_workspace
            save_config(cfg)

    def refresh_from_config(self):
        """
        从最新配置刷新 workspace_root

        适用于 reload_config() 后调用，确保环境管理器与配置文件同步
        """
        from ..utils.logger import log_info
        from .config import get_config

        with self._init_lock:
            if self._paths is None:
                return  # 未初始化则跳过

            cfg = get_config()
            new_workspace = Path(cfg.storage.workspace_root).resolve()

            if new_workspace != self._paths.workspace_root:
                log_info(f"[EnvironmentManager] 从配置刷新 workspace: {new_workspace}")
                self._paths.workspace_root = new_workspace

    def reset(self):
        """
        重置环境管理器（用于测试或完全重新初始化）

        调用后需要再次 initialize() 才能使用
        """
        from ..utils.logger import log_info

        with self._init_lock:
            log_info("[EnvironmentManager] 重置环境管理器")
            self._initialized = False
            self._paths = None


# 全局单例实例
_env_manager = EnvironmentManager()


def get_env_manager() -> EnvironmentManager:
    """获取全局环境管理器实例"""
    return _env_manager


def get_paths() -> RuntimePaths:
    """快捷方式：获取运行时路径（线程安全）"""
    return _env_manager.get_paths()


def init_environment(workspace_root: Optional[str] = None, validate: bool = True) -> RuntimePaths:
    """快捷方式：初始化环境（线程安全）"""
    return _env_manager.initialize(workspace_root, validate)
