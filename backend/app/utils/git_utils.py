"""
Git 相关工具函数
"""

import subprocess
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class GitSubmoduleInfo:
    """Git子模块信息"""

    def __init__(self, path: str):
        self.path = Path(path)
        self.submodule_path = self.path / "runtime" / "engines" / "musubi-tuner"

    def get_submodule_version(self) -> Dict[str, Any]:
        """获取子模块当前版本信息"""
        try:
            if not self.submodule_path.exists():
                return {
                    "status": "not_found",
                    "message": "musubi-tuner子模块不存在",
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
                "message": "子模块状态正常",
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

    def get_remote_releases(self, limit: int = 10, use_cache: bool = True) -> List[Dict[str, Any]]:
        """获取远程仓库的发布历史"""
        cache_file = self.path / "workspace" / "cache" / "musubi_releases.json"

        # 如果使用缓存且缓存文件存在，先尝试读取缓存
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    # 检查缓存是否还有效（这里可以加时间戳检查，暂时直接返回缓存）
                    if cached_data and isinstance(cached_data, list):
                        return cached_data[:limit]
            except Exception as e:
                print(f"读取缓存失败: {e}")

        try:
            if not self.submodule_path.exists():
                return []

            # 首先尝试更新远程分支信息
            subprocess.run(
                ["git", "fetch", "origin", "--tags"],
                cwd=self.submodule_path,
                capture_output=True,
                timeout=30
            )

            # 获取最近的标签列表
            result = subprocess.run(
                ["git", "tag", "--sort=-version:refname", "-l"],
                cwd=self.submodule_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                return []

            tags = result.stdout.strip().split('\n')
            tags = [tag.strip() for tag in tags if tag.strip()][:limit]

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

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(releases, f, ensure_ascii=False, indent=2)

            print(f"发布历史已缓存到: {cache_file}")
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def clear_releases_cache(self):
        """清除发布历史缓存"""
        cache_file = self.path / "workspace" / "cache" / "musubi_releases.json"
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
        # 尝试从当前工作目录推导项目根目录
        current_dir = Path.cwd()
        while current_dir.parent != current_dir:
            if (current_dir / "runtime" / "engines" / "musubi-tuner").exists():
                project_root = str(current_dir)
                break
            current_dir = current_dir.parent

        if project_root is None:
            return {
                "status": "error",
                "message": "无法找到项目根目录"
            }

    git_info = GitSubmoduleInfo(project_root)
    return git_info.get_submodule_version()


def get_musubi_releases(project_root: str = None, limit: int = 10, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """获取musubi发布历史的便捷函数"""
    if project_root is None:
        # 尝试从当前工作目录推导项目根目录
        current_dir = Path.cwd()
        while current_dir.parent != current_dir:
            if (current_dir / "runtime" / "engines" / "musubi-tuner").exists():
                project_root = str(current_dir)
                break
            current_dir = current_dir.parent

        if project_root is None:
            return []

    git_info = GitSubmoduleInfo(project_root)
    return git_info.get_remote_releases(limit, use_cache=not force_refresh)


def clear_musubi_cache(project_root: str = None) -> bool:
    """清除musubi发布历史缓存的便捷函数"""
    if project_root is None:
        current_dir = Path.cwd()
        while current_dir.parent != current_dir:
            if (current_dir / "runtime" / "engines" / "musubi-tuner").exists():
                project_root = str(current_dir)
                break
            current_dir = current_dir.parent

        if project_root is None:
            return False

    git_info = GitSubmoduleInfo(project_root)
    return git_info.clear_releases_cache()