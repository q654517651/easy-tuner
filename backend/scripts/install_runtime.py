#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TagTragger Runtime 安装器 - 统一 Windows/Linux 安装流程

特性：
- Windows: 下载嵌入式 Python 3.11.9 + pip 安装依赖
- Linux: 创建 venv + pip 安装依赖
- 自动克隆 musubi-tuner (支持国内镜像)
- 生成 runtime_manifest.json 清单
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path


# ==================== 输出工具 ====================

# 全局输出回调（用于捕获日志发送到 WebSocket）
_output_callback = None

# 全局取消标志（用于优雅终止安装）
_cancel_flag = False

def set_output_callback(callback):
    """设置输出回调函数（用于 WebSocket 日志推送）"""
    global _output_callback
    _output_callback = callback

def set_cancel_flag():
    """设置取消标志（用于终止安装）"""
    global _cancel_flag
    _cancel_flag = True

def is_cancelled() -> bool:
    """检查是否已取消"""
    return _cancel_flag

def reset_cancel_flag():
    """重置取消标志（用于新的安装任务）"""
    global _cancel_flag
    _cancel_flag = False

class Colors:
    """终端颜色"""
    INFO = '\033[96m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'

def info(msg: str):
    line = f"{Colors.INFO}[INFO]{Colors.ENDC} {msg}"
    print(line)
    if _output_callback:
        _output_callback(f"[INFO] {msg}")

def success(msg: str):
    line = f"{Colors.SUCCESS}[SUCCESS]{Colors.ENDC} {msg}"
    print(line)
    if _output_callback:
        _output_callback(f"[SUCCESS] {msg}")

def warning(msg: str):
    line = f"{Colors.WARNING}[WARNING]{Colors.ENDC} {msg}"
    print(line)
    if _output_callback:
        _output_callback(f"[WARNING] {msg}")

def error(msg: str):
    line = f"{Colors.ERROR}[ERROR]{Colors.ENDC} {msg}"
    print(line)
    if _output_callback:
        _output_callback(f"[ERROR] {msg}")


# ==================== 依赖定义 ====================

# Windows 依赖 (CUDA 12.8)
REQUIREMENTS_WINDOWS = """
--index-url https://download.pytorch.org/whl/cu128
--extra-index-url https://pypi.org/simple

accelerate==1.7.0
av==14.0.1
bitsandbytes==0.45.4
diffusers==0.33.1
easydict==1.13
einops==0.8.1
ftfy==6.3.1
huggingface-hub==0.34.4
opencv-python==4.10.0.84
pillow==11.3.0
safetensors==0.4.5
sentencepiece==0.2.0
toml==0.10.2
torch==2.8.0
torchvision==0.23.0
tqdm==4.67.1
transformers==4.55.0
voluptuous==0.15.2
numpy==2.3.0
tensorboard==2.19.0
# triton-windows==3.3.1.post19 去掉不影响安装，并且win会发生编译错误
hatchling
editables
""".strip()

# Windows 额外依赖 (预编译轮子)
REQUIREMENTS_WINDOWS_EXTRA = [
    ("flash-attn", "https://github.com/sdbds/flash-attention-for-windows/releases/download/2.8.2/flash_attn-2.8.2+cu128torch2.8.0cxx11abiFALSEfullbackward-cp311-cp311-win_amd64.whl"),
    ("sageattention", "https://github.com/sdbds/SageAttention-for-windows/releases/download/2.20_torch280%2Bcu128/sageattention-2.2.0+cu128torch2.8.0-cp311-cp311-win_amd64.whl"),
]

# Linux 依赖 (CUDA 12.8)
REQUIREMENTS_LINUX = """
--index-url https://pypi.org/simple
--extra-index-url https://download.pytorch.org/whl/cu128

accelerate==1.6.0
av==14.0.1
bitsandbytes
diffusers==0.32.1
einops==0.7.0
ftfy==6.3.1
easydict==1.13
huggingface-hub==0.34.3
opencv-python==4.10.0.84
pillow>=10.2.0
safetensors==0.4.5
sentencepiece==0.2.1
toml==0.10.2
torch>=2.7.1
torchvision>=0.22.1
tqdm==4.67.1
transformers==4.54.1
voluptuous==0.15.2
tensorboard
hatchling
editables
""".strip()


# ==================== Musubi 克隆 ====================

def clone_musubi(runtime_dir: Path, use_mirror: bool) -> bool:
    """克隆 musubi-tuner 训练引擎"""
    engines_dir = runtime_dir / "engines"
    musubi_dir = engines_dir / "musubi-tuner"

    engines_dir.mkdir(parents=True, exist_ok=True)

    # 检查是否已存在
    if musubi_dir.exists() and (musubi_dir / ".git").exists():
        info(f"Musubi-tuner 已存在: {musubi_dir}")
        return True

    # 始终使用 GitHub 源（不使用 Gitee 镜像，避免登录问题）
    # 注：use_mirror 仅影响 PyPI 镜像源，不影响 Git 克隆
    git_url = "https://github.com/kohya-ss/musubi-tuner.git"
    info("从 GitHub 克隆 musubi-tuner...")

    # 克隆
    info("正在克隆（可能需要几分钟）...")
    info(f"Git URL: {git_url}")
    info(f"目标目录: {musubi_dir}")

    try:
        # 使用 Popen 实时输出进度
        process = subprocess.Popen(
            ["git", "clone", "--progress", "--depth", "1", git_url, str(musubi_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        # Git 的进度输出在 stderr
        if process.stderr:
            for line in process.stderr:
                line = line.strip()
                if line:
                    # 输出 Git 进度（去除 ANSI 转义码）
                    import re
                    clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    info(f"  {clean_line}")

        returncode = process.wait(timeout=300)

        if returncode == 0:
            success(f"Musubi-tuner 克隆完成: {musubi_dir}")
            return True
        else:
            # 读取剩余错误输出
            if process.stderr:
                stderr = process.stderr.read()
                error(f"Git clone 失败: {stderr}")
            else:
                error("Git clone 失败（未知错误）")
            return False

    except FileNotFoundError:
        error("未检测到 Git，请先安装 Git")
        error("下载地址: https://git-scm.com/downloads")
        return False
    except subprocess.TimeoutExpired:
        error("Git clone 超时（超过 5 分钟），请检查网络连接")
        if process:
            process.kill()
        return False
    except Exception as e:
        error(f"Git clone 异常: {e}")
        import traceback
        error(traceback.format_exc())
        return False


# ==================== Python 查找 (避免打包EXE) ====================

def find_system_python() -> str | None:
    """
    查找系统 Python 3.10+（避免使用打包的 EXE）
    返回 Python 可执行文件路径
    """
    import re

    def parse_version(version_str: str) -> tuple[int, int] | None:
        match = re.search(r'(\d+)\.(\d+)', version_str)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None

    def is_blacklisted(path: str) -> bool:
        path_lower = path.lower()
        basename = os.path.basename(path_lower)
        blacklist = ['easytunerbackend', 'tagtragger', '_mei', 'frozen']
        return any(kw in path_lower or kw in basename for kw in blacklist)

    if platform.system() == 'Windows':
        candidates = ['py', 'python3.11', 'python3.10', 'python3', 'python']
        # 对于 py launcher，需要额外参数
        py_versions = ['-3.11', '-3.10', '-3']
    else:
        # Linux: 优先使用系统默认的 python3（而非特定版本号）
        candidates = ['python3', 'python', 'python3.12', 'python3.11', 'python3.10']
        py_versions = []

    for cmd in candidates:
        full_path = shutil.which(cmd)
        if not full_path:
            continue

        if is_blacklisted(full_path):
            continue

        # 特殊处理 py launcher
        if cmd == 'py' and platform.system() == 'Windows':
            for ver_arg in py_versions:
                try:
                    result = subprocess.run(
                        ['py', ver_arg, '--version'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        version = parse_version(result.stdout + result.stderr)
                        if version and version >= (3, 10):
                            # py launcher 需要返回带参数的命令
                            info(f"找到系统 Python: py {ver_arg} (Python {version[0]}.{version[1]})")
                            return f"py {ver_arg}"  # 返回完整命令
                except:
                    continue
            continue

        # 普通 python 命令
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                version = parse_version(result.stdout + result.stderr)
                if version and version >= (3, 10):
                    info(f"找到系统 Python: {full_path} (Python {version[0]}.{version[1]})")
                    return full_path

        except:
            continue

    return None


# ==================== Windows: 嵌入式 Python ====================

def install_python_windows(runtime_dir: Path) -> Path | None:
    """下载并配置嵌入式 Python 3.11.9"""
    python_version = "3.11.9"
    python_dir = runtime_dir / "python"
    python_exe = python_dir / "python.exe"

    if python_exe.exists():
        info(f"Python 已存在: {python_exe}")
        return python_exe

    info(f"下载 Python {python_version} 嵌入式版本...")
    url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}-embed-amd64.zip"
    zip_path = runtime_dir / "python-embed.zip"

    try:
        # 下载
        urllib.request.urlretrieve(url, zip_path)
        info("下载完成，正在解压...")

        # 解压
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(python_dir)

        # 删除临时文件
        zip_path.unlink()

        # 修补 _pth 文件（启用 site-packages）
        pth_file = python_dir / "python311._pth"
        if pth_file.exists():
            pth_content = "python311.zip\n.\nLib\\site-packages\nimport site\n"
            pth_file.write_text(pth_content, encoding='utf-8')

        # 下载 get-pip.py
        info("安装 pip...")
        get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
        get_pip_path = runtime_dir / "get-pip.py"
        urllib.request.urlretrieve(get_pip_url, get_pip_path)

        # 安装 pip
        subprocess.run(
            [str(python_exe), str(get_pip_path)],
            check=True,
            capture_output=True
        )
        get_pip_path.unlink()

        success(f"Python 安装完成: {python_exe}")
        return python_exe

    except Exception as e:
        error(f"Python 安装失败: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return None


# ==================== Linux: venv ====================

def install_python_linux(runtime_dir: Path) -> Path | None:
    """创建 Python venv"""
    python_dir = runtime_dir / "python"
    python_exe = python_dir / "bin" / "python3"

    if python_exe.exists():
        info(f"Python 虚拟环境已存在: {python_dir}")
        return python_exe

    # 查找系统 Python
    system_python = find_system_python()
    if not system_python:
        error("未找到系统 Python 3.10+，请先安装 Python")
        error("推荐安装 Python 3.11: https://www.python.org/downloads/")
        return None

    info(f"使用系统 Python: {system_python}")
    info("创建虚拟环境...")

    try:
        subprocess.run(
            system_python.split() + ['-m', 'venv', str(python_dir)],
            check=True
        )
        success(f"虚拟环境创建完成: {python_dir}")
        return python_exe

    except Exception as e:
        error(f"虚拟环境创建失败: {e}")
        return None


# ==================== 依赖安装 ====================

def install_dependencies(python_exe: Path, runtime_dir: Path, use_mirror: bool, is_windows: bool) -> bool:
    """安装 Python 依赖"""
    info("安装 Python 依赖...")

    # 升级 pip
    try:
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
            capture_output=True
        )
    except:
        warning("pip 升级失败（忽略）")

    # 写入 requirements
    if is_windows:
        req_file = runtime_dir / "requirements-windows.txt"
        req_file.write_text(REQUIREMENTS_WINDOWS, encoding='utf-8')
    else:
        req_file = runtime_dir / "requirements-linux.txt"
        req_file.write_text(REQUIREMENTS_LINUX, encoding='utf-8')

    # 设置镜像源
    env = os.environ.copy()
    if use_mirror:
        info("使用清华 TUNA 镜像源")
        env['PIP_INDEX_URL'] = "https://pypi.tuna.tsinghua.edu.cn/simple/"

    # 安装依赖
    info("安装依赖包（可能需要几分钟）...")
    info(f"Requirements 文件: {req_file}")
    try:
        process = subprocess.Popen(
            [str(python_exe), "-m", "pip", "install", "-r", str(req_file)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # 实时输出（通过回调传递）
        if process.stdout:
            for line in process.stdout:
                line = line.strip()
                if line:
                    # 过滤掉过于冗长的日志
                    if any(skip in line.lower() for skip in ['requirement already satisfied', 'using cached']):
                        continue
                    # 显示重要信息
                    if any(keyword in line.lower() for keyword in ['installing', 'collecting', 'downloading', 'successfully', 'error', 'warning']):
                        info(f"  {line}")
                    elif _output_callback:
                        # 其他信息仅通过回调发送（不打印到控制台）
                        _output_callback(f"[INFO]   {line}")

        returncode = process.wait()
        if returncode != 0:
            error(f"依赖安装失败（退出码: {returncode}）")
            return False

    except Exception as e:
        error(f"依赖安装异常: {e}")
        import traceback
        error(traceback.format_exc())
        return False

    # Windows: 安装额外依赖（预编译轮子）
    if is_windows:
        info("安装 Windows 专用依赖...")
        for pkg_name, wheel_url in REQUIREMENTS_WINDOWS_EXTRA:
            try:
                info(f"  正在下载并安装 {pkg_name}...")
                info(f"  源: {wheel_url}")
                result = subprocess.run(
                    [str(python_exe), "-m", "pip", "install", wheel_url],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    success(f"  {pkg_name} 安装成功")
                else:
                    warning(f"  {pkg_name} 安装失败（非关键依赖）: {result.stderr}")
            except subprocess.TimeoutExpired:
                warning(f"  {pkg_name} 安装超时（非关键依赖）")
            except Exception as e:
                warning(f"  {pkg_name} 安装失败（非关键依赖）: {e}")

    success("依赖安装完成")

    # ✨ 步骤 3.5: 将 musubi-tuner 注册到 Python 环境（解决模块导入问题）
    info("将 musubi-tuner 注册到 Python 环境...")
    musubi_dir = runtime_dir / "engines" / "musubi-tuner"  # ✅ 根目录，不是 src
    if musubi_dir.exists() and (musubi_dir / "pyproject.toml").exists():
        try:
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install", "-e", str(musubi_dir),
                 "--no-deps", "--no-build-isolation"],
                env=env,  # 使用相同的环境变量（镜像源）
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                success("✅ musubi-tuner 已注册到 Python 环境（可编辑模式）")
                info("  从此无需手动设置 PYTHONPATH，训练脚本可直接 import musubi_tuner")
            else:
                warning(f"musubi-tuner 注册失败: {result.stderr}")
                warning("  训练时将依赖 PYTHONPATH 环境变量（可能不稳定）")
        except subprocess.TimeoutExpired:
            warning("musubi-tuner 注册超时")
        except Exception as e:
            warning(f"musubi-tuner 注册异常: {e}")
    else:
        warning("musubi-tuner 目录或 pyproject.toml 不存在，跳过注册")

    return True


# ==================== 清单生成 ====================

def generate_manifest(runtime_dir: Path, python_exe: Path):
    """生成 runtime_manifest.json"""
    manifest = {
        "created_at": datetime.now().isoformat(),
        "platform": platform.system(),
        "python_version": "",
        "pip_version": "",
        "torch_version": "",
        "musubi_commit": "",
    }

    try:
        # Python 版本
        result = subprocess.run(
            [str(python_exe), "--version"],
            capture_output=True,
            text=True
        )
        manifest["python_version"] = result.stdout.strip()

        # pip 版本
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "--version"],
            capture_output=True,
            text=True
        )
        manifest["pip_version"] = result.stdout.strip()

        # PyTorch 版本
        result = subprocess.run(
            [str(python_exe), "-c", "import torch; print(torch.__version__)"],
            capture_output=True,
            text=True
        )
        manifest["torch_version"] = result.stdout.strip()

        # Musubi commit
        musubi_dir = runtime_dir / "engines" / "musubi-tuner"
        if (musubi_dir / ".git").exists():
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(musubi_dir),
                capture_output=True,
                text=True
            )
            manifest["musubi_commit"] = result.stdout.strip()[:8]

    except:
        pass

    # 写入文件
    manifest_file = runtime_dir / "runtime_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    info(f"清单文件已生成: {manifest_file}")


# ==================== 核心安装逻辑 ====================

def run_install(runtime_dir_str: str, use_china_mirror: bool = False) -> int:
    """
    核心安装逻辑（可被外部调用）

    Args:
        runtime_dir_str: Runtime 根目录路径字符串
        use_china_mirror: 是否使用国内镜像源

    Returns:
        int: 退出码（0=成功，1=失败，2=已取消）
    """
    # 重置取消标志（新任务开始）
    reset_cancel_flag()

    runtime_dir = Path(runtime_dir_str).resolve()
    is_windows = platform.system() == "Windows"

    info(f"Runtime 目录: {runtime_dir}")
    info(f"平台: {platform.system()} {platform.machine()}")
    info(f"使用国内镜像: {'是' if use_china_mirror else '否'}")

    # 创建目录结构
    runtime_dir.mkdir(parents=True, exist_ok=True)

    # 检查取消标志
    if is_cancelled():
        warning("安装已取消（在步骤 1 之前）")
        return 2

    # 步骤1: 克隆 Musubi
    info("步骤 1/3: 克隆 musubi-tuner...")
    if not clone_musubi(runtime_dir, use_china_mirror):
        if is_cancelled():
            warning("Musubi 克隆已取消")
            return 2
        error("Musubi 克隆失败")
        return 1

    # 检查取消标志
    if is_cancelled():
        warning("安装已取消（步骤 1 完成后）")
        return 2

    # 步骤2: 安装 Python
    info(f"步骤 2/3: 安装 Python 环境（{platform.system()}）...")
    if is_windows:
        python_exe = install_python_windows(runtime_dir)
    else:
        python_exe = install_python_linux(runtime_dir)

    if not python_exe or not python_exe.exists():
        if is_cancelled():
            warning("Python 安装已取消")
            return 2
        error("Python 环境安装失败")
        return 1

    # 检查取消标志
    if is_cancelled():
        warning("安装已取消（步骤 2 完成后）")
        return 2

    # 步骤3: 安装依赖
    info("步骤 3/3: 安装 Python 依赖...")
    if not install_dependencies(python_exe, runtime_dir, use_china_mirror, is_windows):
        if is_cancelled():
            warning("依赖安装已取消")
            return 2
        error("依赖安装失败")
        return 1

    # 检查取消标志（最后一次）
    if is_cancelled():
        warning("安装已取消（步骤 3 完成后）")
        return 2

    # 生成清单
    generate_manifest(runtime_dir, python_exe)

    success("🎉 Runtime 环境安装完成!")
    return 0


# ==================== 命令行入口 ====================

def main():
    """命令行入口（仅解析参数并调用 run_install）"""
    parser = argparse.ArgumentParser(
        description="TagTragger Runtime 安装器（统一 Windows/Linux）"
    )
    parser.add_argument(
        "--runtime-dir",
        required=True,
        help="Runtime 根目录（通常为 workspace/runtime）"
    )
    parser.add_argument(
        "--use-china-mirror",
        action="store_true",
        help="使用国内镜像源（清华 TUNA + Gitee）"
    )
    args = parser.parse_args()

    return run_install(args.runtime_dir, args.use_china_mirror)


if __name__ == "__main__":
    sys.exit(main())
