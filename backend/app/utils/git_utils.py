"""
Git 相关工具函数（已适配工作区 runtime 架构）

说明：
- musubi-tuner 不再作为项目子模块管理，安装器会将其克隆到「工作区/runtime/engines/musubi-tuner」。
- 本工具统一通过 EnvironmentManager 获取仓库路径，而不是从项目根拼接。
"""

import subprocess
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from ..utils.logger import log_info

# 将本模块的 print 重定向到项目 logger，统一日志出口
def _print_to_logger(*args, **kwargs):
    try:
        msg = " ".join(str(a) for a in args)
    except Exception:
        msg = " ".join(repr(a) for a in args)
    log_info(msg)

print = _print_to_logger

class GitSubmoduleInfo:
    """Git 仓库信息（兼容旧名，实际使用工作区路径）"""

    def __init__(self, path: str):
        # 兼容旧签名，但不再使用传入的 project_root
        # 统一从全局环境管理器获取工作区内的 musubi 仓库路径
        from ..core.environment import get_paths

        self.path = Path(path)
        self.submodule_path = get_paths().musubi_dir

    def get_submodule_version(self) -> Dict[str, Any]:
        """获取当前 musubi 仓库版本信息"""
        try:
            if not self.submodule_path.exists():
                return {
                    "status": "not_found",
                    "message": "musubi-tuner 仓库不存在（未安装）",
                    "version": "",
                    "commit_hash": "",
                    "commit_date": "",
                    "branch": ""
                }

            # 获取当前提交哈希
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "message": "无法获取git信息",
                    "version": "",
                    "commit_hash": "",
                    "commit_date": "",
                    "branch": ""
                }

            commit_hash = result.stdout.strip()

            # 获取提交日期
            date_result = subprocess.run(
                ["git", "log", "-1", "--format=%ci"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            commit_date = date_result.stdout.strip() if date_result.returncode == 0 else ""

            # 获取当前分支
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "未知"

            # 尝试获取最近的tag作为版本号
            tag_result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            version = tag_result.stdout.strip() if tag_result.returncode == 0 else f"commit-{commit_hash[:8]}"

            return {
                "status": "installed",
                "message": "仓库状态正常",
                "version": version,
                "commit_hash": commit_hash,
                "commit_date": commit_date,
                "branch": branch
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "message": "Git命令超时",
                "version": "",
                "commit_hash": "",
                "commit_date": "",
                "branch": ""
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"检查失败: {str(e)}",
                "version": "",
                "commit_hash": "",
                "commit_date": "",
                "branch": ""
            }

    def get_local_releases(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取本地已有的发布历史（不做网络请求，快速）"""
        try:
            if not self.submodule_path.exists():
                print(f"错误：musubi-tuner 仓库目录不存在: {self.submodule_path}")
                return []

            # 直接读取本地标签（不做 git fetch）
            result = subprocess.run(
                ["git", "tag", "--sort=-version:refname", "-l"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                print(f"错误：无法获取 git 标签: {result.stderr.strip()}")
                return []

            tags = result.stdout.strip().split('\n')
            tags = [tag.strip() for tag in tags if tag.strip()][:limit]

            if not tags:
                print("警告：未找到任何版本标签（仓库可能未打 tag）")
                return []

            releases = []
            for tag in tags:
                # 获取tag的提交信息
                log_result = subprocess.run(
                    ["git", "log", "-1", "--format=%H|%ci|%s", tag],
                    cwd=self.submodule_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if log_result.returncode == 0:
                    parts = log_result.stdout.strip().split('|')
                    if len(parts) >= 3:
                        commit_hash = parts[0]
                        commit_date = parts[1]
                        commit_message = '|'.join(parts[2:])

                        releases.append({
                            "tag": tag,
                            "version": tag,
                            "commit_hash": commit_hash,
                            "date": commit_date,
                            "message": commit_message,
                            "description": commit_message
                        })

            return releases

        except subprocess.TimeoutExpired:
            print("错误：获取本地标签超时")
            return []
        except Exception as e:
            print(f"获取本地发布历史失败: {e}")
            return []

    def get_remote_releases(self, limit: int = 10, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        获取发布历史（优先使用缓存，再使用本地标签）

        注意：此方法不再执行 git fetch，只读取本地已有标签。
        如需从远程更新，请调用 fetch_and_update_releases()
        """
        # 使用工作区缓存路径（而非项目根目录）
        from ..core.environment import get_paths
        cache_file = get_paths().workspace_root / "cache" / "musubi_releases.json"

        # 如果使用缓存且缓存文件存在，先尝试读取缓存
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)

                    # 兼容旧格式（直接是列表）和新格式（带时间戳的字典）
                    if isinstance(cached_data, list):
                        # 旧格式：直接返回列表
                        print("使用旧格式缓存（列表）")
                        return cached_data[:limit]
                    elif isinstance(cached_data, dict) and "releases" in cached_data:
                        # 新格式：直接返回缓存（不检查时间戳，缓存永久有效直到手动刷新）
                        print("使用缓存的发布历史")
                        return cached_data["releases"][:limit]
            except Exception as e:
                print(f"读取缓存失败: {e}")

        # 没有缓存时，读取本地标签
        print("从本地 git 标签获取发布历史...")
        releases = self.get_local_releases(limit)

        # 保存到缓存
        if releases:
            self._save_releases_cache(releases, cache_file)

        return releases

    def fetch_and_update_releases(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        从远程仓库拉取最新标签并更新发布历史（网络操作，较慢）

        此方法会执行 git fetch，用于"检查更新"功能
        """
        # 使用工作区缓存路径（而非项目根目录）
        from ..core.environment import get_paths
        cache_file = get_paths().workspace_root / "cache" / "musubi_releases.json"

        try:
            if not self.submodule_path.exists():
                print(f"错误：musubi-tuner 仓库目录不存在: {self.submodule_path}")
                print("提示：请在设置页执行“安装/修复训练环境”完成安装")
                return []

            # 从远程获取最新标签
            print("正在从远程仓库获取最新标签...")
            fetch_result = subprocess.run(
                ["git", "fetch", "origin", "--tags", "--force"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=60
            )

            if fetch_result.returncode != 0:
                print(f"警告：无法从远程获取标签（可能是网络问题）: {fetch_result.stderr.strip()}")
                print("将使用本地已有的标签...")
            else:
                # 若为浅克隆，尽量补全历史，否则大多数 tag 无法解析到提交
                shallow_file = self.submodule_path / ".git" / "shallow"
                is_shallow = shallow_file.exists()
                if is_shallow:
                    print("检测到浅克隆，尝试补全历史以解析更多标签...")
                    # 1) 尝试 unshallow（可能失败，忽略错误）
                    try:
                        unshallow_res = subprocess.run(
                            ["git", "fetch", "--unshallow"],
                            cwd=self.submodule_path,
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        if unshallow_res.returncode != 0:
                            # 2) 回退：按当前分支加深历史
                            br = subprocess.run(
                                ["git", "branch", "--show-current"],
                                cwd=self.submodule_path,
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            current_branch = br.stdout.strip() or "main"
                            deepen_res = subprocess.run(
                                ["git", "fetch", "origin", "--deepen", "5000", current_branch],
                                cwd=self.submodule_path,
                                capture_output=True,
                                text=True,
                                timeout=120
                            )
                            if deepen_res.returncode != 0:
                                print(f"警告：加深历史失败，将尽力使用现有提交。原因: {deepen_res.stderr.strip()}")
                    except subprocess.TimeoutExpired:
                        print("警告：补全历史操作超时，将使用当前可用的标签信息。")

            # 获取最近的标签列表
            result = subprocess.run(
                ["git", "tag", "--sort=-version:refname", "-l"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                print(f"错误：无法获取 git 标签: {result.stderr.strip()}")
                return []

            tags = result.stdout.strip().split('\n')
            tags = [tag.strip() for tag in tags if tag.strip()][:limit]

            if not tags:
                print("警告：未找到任何版本标签")
                print(f"提示：请确认仓库 {self.submodule_path} 是否存在可用标签")
                return []

            print(f"找到 {len(tags)} 个版本标签")

            releases = []
            for tag in tags:
                # 获取tag的提交信息
                log_result = subprocess.run(
                    ["git", "log", "-1", "--format=%H|%ci|%s", tag],
                    cwd=self.submodule_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if log_result.returncode == 0:
                    parts = log_result.stdout.strip().split('|')
                    if len(parts) >= 3:
                        commit_hash = parts[0]
                        commit_date = parts[1]
                        commit_message = '|'.join(parts[2:])  # 防止commit message中有|符号

                        releases.append({
                            "tag": tag,
                            "version": tag,
                            "commit_hash": commit_hash,
                            "date": commit_date,
                            "message": commit_message,
                            "description": commit_message  # 使用commit message作为更新原因
                        })
                else:
                    # 对于浅克隆尚未覆盖到的 tag，尝试使用 tag 注释信息做降级（若为注释标签）
                    ann = subprocess.run(
                        ["git", "for-each-ref", f"refs/tags/{tag}", "--format=%(objectname)|%(taggerdate)|%(subject)"],
                        cwd=self.submodule_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if ann.returncode == 0 and ann.stdout.strip():
                        parts = ann.stdout.strip().split('|')
                        if len(parts) >= 3:
                            obj_hash = parts[0]
                            tag_date = parts[1]
                            subject = '|'.join(parts[2:])
                            releases.append({
                                "tag": tag,
                                "version": tag,
                                "commit_hash": obj_hash[:40],  # 可能是 tag 对象或提交对象哈希
                                "date": tag_date,
                                "message": subject,
                                "description": subject,
                            })

            # 保存到缓存文件
            if releases:
                self._save_releases_cache(releases, cache_file)

            return releases

        except subprocess.TimeoutExpired:
            return []
        except Exception as e:
            print(f"获取发布历史失败: {e}")
            return []

    def _save_releases_cache(self, releases: List[Dict[str, Any]], cache_file: Path):
        """保存发布历史到缓存文件"""
        try:
            # 确保缓存目录存在
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            # 添加缓存时间戳
            cache_data = {
                "cached_at": datetime.now().isoformat(),
                "releases": releases
            }

            # 保存带时间戳的字典（而不是直接保存 releases 列表）
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            print(f"发布历史已缓存到: {cache_file} (共 {len(releases)} 个版本)")
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def clear_releases_cache(self):
        """清除发布历史缓存"""
        # 使用工作区缓存路径（而非项目根目录）
        from ..core.environment import get_paths
        cache_file = get_paths().workspace_root / "cache" / "musubi_releases.json"
        try:
            if cache_file.exists():
                cache_file.unlink()
                print("发布历史缓存已清除")
                return True
        except Exception as e:
            print(f"清除缓存失败: {e}")
        return False


def check_submodule_status(project_root: str = None) -> Dict[str, Any]:
    """检查musubi子模块状态的便捷函数"""
    if project_root is None:
        # 从环境管理器获取项目根目录
        from ..core.environment import get_paths

        try:
            paths = get_paths()
            project_root = str(paths.project_root)
        except Exception:
            return {
                "status": "error",
                "message": "无法找到项目根目录"
            }

    git_info = GitSubmoduleInfo(project_root)
    return git_info.get_submodule_version()


def get_musubi_releases(project_root: str = None, limit: int = 10, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    获取musubi发布历史的便捷函数

    Args:
        project_root: 项目根目录
        limit: 返回的版本数量
        force_refresh: 是否强制从远程更新（执行 git fetch）

    Returns:
        发布历史列表
    """
    if project_root is None:
        # 从环境管理器获取项目根目录
        from ..core.environment import get_paths

        try:
            paths = get_paths()
            project_root = str(paths.project_root)
        except Exception:
            return []

    git_info = GitSubmoduleInfo(project_root)

    if force_refresh:
        # 强制刷新：执行 git fetch 从远程更新
        return git_info.fetch_and_update_releases(limit)
    else:
        # 默认：使用缓存或本地标签（无网络请求）
        return git_info.get_remote_releases(limit, use_cache=True)


def clear_musubi_cache(project_root: str = None) -> bool:
    """清除musubi发布历史缓存的便捷函数"""
    if project_root is None:
        # 从环境管理器获取项目根目录
        from ..core.environment import get_paths

        try:
            paths = get_paths()
            project_root = str(paths.project_root)
        except Exception:
            return False

    git_info = GitSubmoduleInfo(project_root)
    return git_info.clear_releases_cache()
