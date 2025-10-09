from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence

from .base import LabelingProvider, LabelResult, ImageInput, TextInput
from ..clients.lm_studio_client import LMStudioClient
from ...config import get_config


class LMStudioProvider(LabelingProvider):
    name = "lm_studio"
    capabilities: Sequence[str] = ("label_image", "translate_text")

    def __init__(self):
        self.config = get_config()
        self._client = LMStudioClient()

    async def test_connection(self) -> bool:
        return self._client.quick_config_check()

    async def generate_labels(
        self, images: Sequence[ImageInput], prompt: Optional[str] = None, **options: Any
    ) -> List[LabelResult]:
        # 先检查配置
        if not self._client.quick_config_check():
            error_msg = "LM Studio服务未配置，请在设置中配置 Base URL"
            return [
                LabelResult(ok=False, error_code="CONFIG_ERROR", detail=error_msg, meta={"provider": self.name})
                for _ in images
            ]

        loop = asyncio.get_running_loop()
        results: List[LabelResult] = []
        for img in images:
            try:
                img_path = img if isinstance(img, str) else str(img)
                text = await loop.run_in_executor(
                    None,
                    lambda: self._client.call_label_for_image(
                        prompt=prompt or (self.config.labeling.default_prompt or ""),
                        image_path=img_path,
                    ),
                )
                results.append(LabelResult(ok=bool(text), text=text, meta={"provider": self.name}))
            except Exception as e:
                results.append(LabelResult(ok=False, error_code="PROVIDER_ERROR", detail=str(e), meta={"provider": self.name}))
        return results

    async def translate(
        self, text: TextInput, *, source_lang: Optional[str] = None, target_lang: str = "zh", **options: Any
    ) -> LabelResult:
        loop = asyncio.get_running_loop()
        try:
            out = await loop.run_in_executor(
                None,
                lambda: self._client.call_translate(
                    prompt=self.config.labeling.translation_prompt or "",
                    content=text or "",
                ),
            )
            return LabelResult(ok=bool(out), text=out or "", meta={"provider": self.name})
        except Exception as e:
            return LabelResult(ok=False, error_code="PROVIDER_ERROR", detail=str(e), meta={"provider": self.name})

