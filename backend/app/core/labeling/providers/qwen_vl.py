from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, List, Optional, Sequence

from .base import LabelingProvider, LabelResult, ImageInput, TextInput, ProviderMetadata
from ..clients.qwen_vl_client import QwenVLClient
from ...config import get_config


class QwenVLProvider(LabelingProvider):
    """Qwen-VL Provider - 通过 QwenVLClient 调用子进程进行推理"""

    name = "local_qwen_vl"
    capabilities: Sequence[str] = ("label_image",)  # 暂不支持翻译

    def __init__(self):
        self.config = get_config()
        self._client = QwenVLClient()

    @classmethod
    def get_metadata(cls) -> ProviderMetadata:
        """返回 Provider 元数据"""
        from .registry import PROVIDER_METADATA
        return PROVIDER_METADATA["local_qwen_vl"]

    async def test_connection(self) -> bool:
        """检查配置是否完整"""
        try:
            return self._client.quick_config_check()
        except Exception:
            return False

    async def generate_labels(
        self, images: Sequence[ImageInput], prompt: Optional[str] = None, **options: Any
    ) -> List[LabelResult]:
        """批量生成标注"""
        # 先检查配置
        if not self._client.quick_config_check():
            error_msg = "Qwen-VL 服务未配置，请在设置中配置权重文件路径"
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
                return [LabelResult(ok=False, error_code="UNSUPPORTED_INPUT", detail="Qwen-VL 暂不支持 bytes 输入", meta={"provider": self.name})]
            else:
                image_paths.append(str(img))

        # 获取 prompt
        use_prompt = prompt if prompt is not None else (self.config.labeling.default_prompt or "")

        # 调用客户端（在执行器中运行，避免阻塞事件循环）
        loop = asyncio.get_running_loop()
        try:
            # 批量调用（使用 lambda 包装命名参数）
            result_dicts = await loop.run_in_executor(
                None,
                lambda: self._client.call_label_for_images_batch(
                    prompt=use_prompt,
                    image_paths=image_paths
                )
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
            return [
                LabelResult(ok=False, error_code="CLIENT_ERROR", detail=error_msg, meta={"provider": self.name})
                for _ in images
            ]

    async def translate(self, text: TextInput, *, source_lang: Optional[str] = None, target_lang: str = "zh", **options: Any) -> LabelResult:
        """暂不支持翻译"""
        return LabelResult(
            ok=False,
            error_code="NOT_IMPLEMENTED",
            detail="Qwen-VL Provider 暂不支持翻译功能",
            meta={"provider": self.name}
        )
