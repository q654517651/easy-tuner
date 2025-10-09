from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from ...config import get_config


class QwenVLClient:
    """Qwen-VL 客户端 - 通过子进程调用独立脚本进行推理"""

    def __init__(self):
        self.config = get_config()

    def call_label_for_image(
        self,
        *,
        prompt: str,
        image_path: str,
        weights_path: Optional[str] = None,
        timeout: int = 300,
    ) -> str:
        """
        单图打标

        Args:
            prompt: 打标提示词
            image_path: 图像路径
            weights_path: 权重文件路径（可选，不传则从配置读取）
            timeout: 超时时间（秒）

        Returns:
            生成的标注文本
        """
        results = self._call_batch(
            prompt=prompt,
            image_paths=[image_path],
            weights_path=weights_path,
            timeout=timeout
        )

        if not results or len(results) == 0:
            raise RuntimeError("未返回打标结果")

        result = results[0]
        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            raise RuntimeError(f"打标失败: {error_msg}")

        return result.get("caption", "")

    def call_label_for_images_batch(
        self,
        *,
        prompt: str,
        image_paths: List[str],
        weights_path: Optional[str] = None,
        timeout: int = 600,
    ) -> List[dict]:
        """
        批量打标（一次性加载模型，处理所有图片）

        Args:
            prompt: 打标提示词
            image_paths: 图像路径列表
            weights_path: 权重文件路径（可选）
            timeout: 超时时间（秒）

        Returns:
            结果列表，每个元素包含 {"image": str, "caption": str, "success": bool, "error": str}
        """
        return self._call_batch(
            prompt=prompt,
            image_paths=image_paths,
            weights_path=weights_path,
            timeout=timeout
        )

    def _call_batch(
        self,
        *,
        prompt: str,
        image_paths: List[str],
        weights_path: Optional[str] = None,
        timeout: int = 600,
    ) -> List[dict]:
        """
        内部批量调用方法

        Returns:
            [{"image": str, "caption": str, "success": bool, "error": str}, ...]
        """
        # 获取权重路径
        qwen_config = self.config.labeling.models.get('local_qwen_vl', {})
        weights = weights_path or qwen_config.get('weights_path', '')

        if not weights:
            raise ValueError("未配置 Qwen-VL 权重文件路径，请在设置页的打标设置中配置模型权重路径")

        weights_file = Path(weights)
        if not weights_file.exists():
            raise FileNotFoundError(f"Qwen-VL 权重文件不存在: {weights}")

        # 获取 runtime Python 路径（从环境管理器）
        from ....core.environment import get_paths

        paths = get_paths()
        runtime_python = paths.runtime_python

        if runtime_python is None or not runtime_python.exists():
            raise FileNotFoundError(
                f"Runtime Python 解释器不存在\n"
                f"请确保 runtime/python 目录已正确安装"
            )

        # 获取脚本路径
        script_path = paths.backend_root / "scripts" / "caption_qwen25vl.py"
        if not script_path.exists():
            raise FileNotFoundError(f"打标脚本不存在: {script_path}")

        # 构建命令行参数
        cmd = [
            str(runtime_python),
            str(script_path),
            str(weights_file),
            "--images", *[str(p) for p in image_paths],
            "--prompt", prompt,
        ]

        # 设置环境变量，强制子进程使用 UTF-8 编码
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # 调用子进程
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',  # 替换无法解码的字节为 � 符号，避免 UnicodeDecodeError
                env=env  # 传递环境变量
            )

            if result.returncode != 0:
                # 解析错误信息
                try:
                    error_data = json.loads(result.stderr)
                    error_msg = error_data.get("error", result.stderr)
                except:
                    error_msg = result.stderr or "未知错误"
                raise RuntimeError(f"Qwen-VL 推理失败: {error_msg}")

            # 解析 JSON 输出（检查是否为空）
            if not result.stdout or not result.stdout.strip():
                raise RuntimeError(f"Qwen-VL 脚本未返回任何输出（可能因编码错误或脚本异常）\nStderr: {result.stderr}")

            try:
                # 处理多行输出：倒序查找最后一条以 [ 或 { 开头的行（JSON 结果）
                # 这样即使脚本在 JSON 后又输出了额外内容也能正确解析
                stdout_lines = result.stdout.strip().splitlines()
                json_line = None

                for line in reversed(stdout_lines):  # 倒序找，拿到"最后"的 JSON
                    line_stripped = line.strip()
                    if line_stripped.startswith('[') or line_stripped.startswith('{'):
                        json_line = line_stripped
                        break

                if json_line is None:
                    raise RuntimeError(f"未找到 JSON 输出\nOutput: {result.stdout}\nStderr: {result.stderr}")

                results = json.loads(json_line)
                return results
            except json.JSONDecodeError as e:
                raise RuntimeError(f"无法解析打标结果 JSON: {e}\nOutput: {result.stdout}\nStderr: {result.stderr}")

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Qwen-VL 推理超时（{timeout}秒）")
        except Exception as e:
            raise RuntimeError(f"调用 Qwen-VL 脚本失败: {str(e)}")

    def quick_config_check(self) -> bool:
        """
        快速检查配置是否完整

        Returns:
            配置是否可用
        """
        from ....utils.logger import log_warning

        try:
            qwen_config = self.config.labeling.models.get('local_qwen_vl', {})
            weights = qwen_config.get('weights_path', '')

            if not weights:
                log_warning("[QwenVL] 配置检查失败: weights_path 未配置")
                return False

            # 检查权重文件是否存在
            weights_path = Path(weights)
            if not weights_path.exists():
                log_warning(f"[QwenVL] 配置检查失败: 权重文件不存在 - {weights}")
                return False

            # 检查 runtime Python 是否存在
            try:
                from ....core.environment import get_paths
                paths = get_paths()
                if paths.runtime_python is None or not paths.runtime_python_exists:
                    log_warning(f"[QwenVL] 配置检查失败: Runtime Python 不存在")
                    return False
            except Exception as e:
                log_warning(f"[QwenVL] 配置检查失败: {str(e)}")
                return False

            return True

        except Exception as e:
            log_warning(f"[QwenVL] 配置检查异常: {str(e)}")
            return False
