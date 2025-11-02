from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, List, Optional, Sequence

from .base import LabelingProvider, LabelResult, ImageInput, TextInput, ProviderMetadata
from ...config import get_config
from ....utils.logger import log_warning, log_error, log_info


class QwenVLProvider(LabelingProvider):
    """Qwen-VL Provider - 通过子进程调用 Python 脚本进行推理（合并原 qwen_vl_client 逻辑）"""

    name = "local_qwen_vl"
    capabilities: Sequence[str] = ("label_image",)  # 暂不支持翻译

    def __init__(self):
        # 不再缓存配置，每次使用时动态获取最新配置
        pass

    @classmethod
    def get_metadata(cls) -> ProviderMetadata:
        """返回 Provider 元数据"""
        from .registry import PROVIDER_METADATA
        return PROVIDER_METADATA["local_qwen_vl"]

    def _get_config(self) -> dict:
        """获取 Qwen-VL 配置（自动填充默认值）"""
        config = get_config()
        user_config = config.labeling.models.get('local_qwen_vl', {})
        
        # 从 registry 获取默认值
        from .registry import PROVIDER_METADATA
        metadata = PROVIDER_METADATA.get('local_qwen_vl')
        
        # 先用默认值初始化
        qwen_config = {}
        if metadata:
            for field in metadata.config_fields:
                if field.default is not None:
                    qwen_config[field.key] = field.default
        
        # 用户配置覆盖默认值
        qwen_config.update(user_config)
        
        # 验证必填字段
        weights_path = qwen_config.get('weights_path', '')
        if not weights_path:
            raise ValueError(
                "Qwen-VL 配置不完整:\n"
                "  - 权重文件路径: 未配置\n"
                "请在设置页配置模型权重文件路径（.safetensors 格式）"
            )

        weights_file = Path(weights_path)
        if not weights_file.exists():
            raise FileNotFoundError(
                f"Qwen-VL 权重文件不存在:\n"
                f"  - 配置路径: {weights_path}\n"
                f"  - 绝对路径: {weights_file.resolve()}\n"
                "请检查路径是否正确"
            )

        return qwen_config

    def _get_runtime_python(self) -> Path:
        """获取 Runtime Python 可执行文件路径"""
        from ....core.environment import get_paths

        paths = get_paths()
        runtime_python = paths.runtime_python

        if runtime_python is None or not runtime_python.exists():
            import sys as _sys
            expected = paths.runtime_dir / ("python/" + ("Scripts/python.exe" if _sys.platform == "win32" else "bin/python3"))
            raise FileNotFoundError(
                f"Runtime Python 不存在:\n"
                f"  - 期望路径: {expected}\n"
                "请确保 runtime/python 虚拟环境已正确安装"
            )

        return runtime_python

    def _get_script_path(self) -> Path:
        """获取打标脚本路径（兼容开发和打包环境）"""
        from ....core.environment import get_paths

        paths = get_paths()
        script_name = "caption_qwen25vl.py"

        # 尝试多个可能的路径（按优先级）
        candidate_paths = [
            paths.backend_root / "scripts" / script_name,                      # 1. backend_root/scripts
            paths.project_root / "backend" / "scripts" / script_name,         # 2. project_root/backend/scripts
            Path(__file__).parent.parent.parent / "scripts" / script_name,    # 3. 相对于当前文件
        ]

        for script_path in candidate_paths:
            if script_path.exists():
                log_info(f"[QwenVL] 找到脚本: {script_path}")
                return script_path

        # 如果都不存在，抛出详细错误
        error_msg = (
            f"打标脚本不存在: {script_name}\n"
            "尝试的路径:\n"
        )
        for i, p in enumerate(candidate_paths, 1):
            error_msg += f"  {i}. {p.resolve()}\n"

        raise FileNotFoundError(error_msg)

    # TODO: 未来用于测试服务连通性（不阻断调用）
    async def test_connection(self) -> bool:
        """测试连接（暂时禁用，标记为 TODO）"""
        try:
            _ = self._get_config()
            _ = self._get_runtime_python()
            _ = self._get_script_path()
            return True
        except Exception as e:
            log_warning(f"[QwenVL] 配置检查失败: {str(e)}")
            return False

    async def generate_labels(
        self, images: Sequence[ImageInput], prompt: Optional[str] = None, **options: Any
    ) -> List[LabelResult]:
        """批量生成标注"""
        # 配置检查
        try:
            config = self._get_config()
            runtime_python = self._get_runtime_python()
            script_path = self._get_script_path()
        except (ValueError, FileNotFoundError) as e:
            error_msg = str(e)
            log_error(f"[QwenVL] 配置错误: {error_msg}")
            return [
                LabelResult(ok=False, error_code="CONFIG_ERROR", detail=error_msg, meta={"provider": self.name})
                for _ in images
            ]

        # 转换为文件路径
        image_paths: List[str] = []
        for img in images:
            if isinstance(img, (str, Path)):
                image_paths.append(str(img))
            elif isinstance(img, bytes):
                # bytes 不支持，返回错误
                return [LabelResult(
                    ok=False,
                    error_code="UNSUPPORTED_INPUT",
                    detail="Qwen-VL 暂不支持 bytes 输入",
                    meta={"provider": self.name}
                )]
            else:
                image_paths.append(str(img))

        # 获取 prompt
        use_prompt = prompt if prompt is not None else (get_config().labeling.default_prompt or "")

        # 获取权重路径
        weights_path = config.get('weights_path', '')

        # 在执行器中运行子进程调用
        loop = asyncio.get_running_loop()

        try:
            result_dicts = await loop.run_in_executor(
                None,
                self._call_subprocess,
                runtime_python,
                script_path,
                weights_path,
                image_paths,
                use_prompt,
                options.get('timeout', 600)  # 默认 10 分钟超时
            )

            # 将结果转换为 LabelResult
            results = []
            for result_dict in result_dicts:
                if result_dict.get("success"):
                    results.append(LabelResult(
                        ok=True,
                        text=result_dict.get("caption", ""),
                        meta={"provider": self.name, "image": result_dict.get("image")}
                    ))
                else:
                    results.append(LabelResult(
                        ok=False,
                        error_code="INFERENCE_ERROR",
                        detail=result_dict.get("error", "推理失败"),
                        meta={"provider": self.name, "image": result_dict.get("image")}
                    ))

            return results

        except Exception as e:
            # 整批失败
            error_msg = str(e)
            log_error(f"[QwenVL] 批量推理失败: {error_msg}")
            return [
                LabelResult(ok=False, error_code="CLIENT_ERROR", detail=error_msg, meta={"provider": self.name})
                for _ in images
            ]

    def _call_subprocess(
        self,
        runtime_python: Path,
        script_path: Path,
        weights_path: str,
        image_paths: List[str],
        prompt: str,
        timeout: int
    ) -> List[dict]:
        """
        调用子进程执行推理（同步方法，在 executor 中运行）

        Returns:
            [{"image": str, "caption": str, "success": bool, "error": str}, ...]
        """
        # 构建命令行参数
        cmd = [
            str(runtime_python),
            str(script_path),
            weights_path,
            "--images", *[str(p) for p in image_paths],
            "--prompt", prompt,
        ]

        # 设置环境变量
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # 传递 workspace 路径给子进程脚本
        try:
            from ....core.environment import get_paths
            paths = get_paths()
            
            # 设置环境变量，脚本会使用此路径构建 musubi_src
            env["EASYTUNER_WORKSPACE"] = str(paths.workspace_root)
            log_info(f"[QwenVL] Set EASYTUNER_WORKSPACE: {paths.workspace_root}")
            
            musubi_src = paths.musubi_src  # workspace/runtime/engines/musubi-tuner/src
            log_info(f"[QwenVL] musubi_src: {musubi_src}, exists: {musubi_src.exists()}")

            if musubi_src.exists():
                # 同时添加到 PYTHONPATH 作为备用
                pythonpath = str(musubi_src)
                if "PYTHONPATH" in env:
                    env["PYTHONPATH"] = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
                else:
                    env["PYTHONPATH"] = pythonpath
                log_info(f"[QwenVL] Added PYTHONPATH: {pythonpath}")
            else:
                log_warning(f"[QwenVL] musubi-tuner src not found: {musubi_src}")
        except Exception as e:
            import traceback
            log_error(f"[QwenVL] Failed to set environment: {str(e)}\n{traceback.format_exc()}")

        log_info(f"[QwenVL] 启动子进程: {' '.join(cmd[:3])} ...")

        # 调用子进程
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',  # 替换无法解码的字节
                env=env
            )

            if result.returncode != 0:
                # 解析错误信息
                try:
                    error_data = json.loads(result.stderr)
                    error_msg = error_data.get("error", result.stderr)
                except:
                    error_msg = result.stderr or "未知错误"
                raise RuntimeError(f"Qwen-VL 推理失败（退出码 {result.returncode}）: {error_msg}")

            # 解析 JSON 输出
            if not result.stdout or not result.stdout.strip():
                raise RuntimeError(
                    f"Qwen-VL 脚本未返回任何输出（可能因编码错误或脚本异常）\n"
                    f"Stderr: {result.stderr}"
                )

            # 倒序查找最后一条 JSON 行（处理多行输出）
            stdout_lines = result.stdout.strip().splitlines()
            json_line = None

            for line in reversed(stdout_lines):
                line_stripped = line.strip()
                if line_stripped.startswith('[') or line_stripped.startswith('{'):
                    json_line = line_stripped
                    break

            if json_line is None:
                raise RuntimeError(
                    f"未找到 JSON 输出\n"
                    f"Output: {result.stdout}\n"
                    f"Stderr: {result.stderr}"
                )

            results = json.loads(json_line)
            log_info(f"[QwenVL] 推理完成，处理了 {len(results)} 张图片")
            return results

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Qwen-VL 推理超时（{timeout}秒）")
        except Exception as e:
            raise RuntimeError(f"调用 Qwen-VL 脚本失败: {str(e)}")

    async def translate(
        self, text: TextInput, *, source_lang: Optional[str] = None, target_lang: str = "zh", **options: Any
    ) -> LabelResult:
        """暂不支持翻译"""
        return LabelResult(
            ok=False,
            error_code="NOT_IMPLEMENTED",
            detail="Qwen-VL Provider 暂不支持翻译功能",
            meta={"provider": self.name}
        )


