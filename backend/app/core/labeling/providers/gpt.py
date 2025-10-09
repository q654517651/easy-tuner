from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Sequence

from .base import LabelingProvider, LabelResult, ImageInput, TextInput
from ..clients.gpt_client import GPTClient
from ...exceptions import LabelingError, ValidationError
from ...config import get_config


class GPTProvider(LabelingProvider):
    name = "gpt"
    capabilities: Sequence[str] = ("label_image", "translate_text")

    def __init__(self):
        self.config = get_config()
        self._client = GPTClient()

    async def test_connection(self) -> bool:
        try:
            # 轻量自检：配置检查
            return self._client.quick_config_check()
        except Exception:
            return False

    async def generate_labels(
        self, images: Sequence[ImageInput], prompt: Optional[str] = None, **options: Any
    ) -> List[LabelResult]:
        # 先检查配置
        if not self._client.quick_config_check():
            error_msg = "GPT服务未配置，请在设置中配置 API Key 和 Base URL"
            return [
                LabelResult(ok=False, error_code="CONFIG_ERROR", detail=error_msg, meta={"provider": self.name})
                for _ in images
            ]

        loop = asyncio.get_running_loop()
        results: List[LabelResult] = []
        for img in images:
            try:
                if not isinstance(img, (str, bytes)):
                    img_path = str(img)
                else:
                    img_path = img if isinstance(img, str) else None
                if not img_path:
                    results.append(LabelResult(ok=False, error_code="INVALID_INPUT", detail="bytes input not supported yet"))
                    continue
                text = await loop.run_in_executor(
                    None,
                    lambda: self._client.call_label_for_image(
                        prompt=prompt or (self.config.labeling.default_prompt or ""),
                        image_path=img_path,
                    ),
                )
                ok = bool(text and not text.startswith("AI"))
                results.append(LabelResult(ok=ok, text=text or "", meta={"provider": self.name}))
            except Exception as e:
                results.append(
                    LabelResult(ok=False, error_code="PROVIDER_ERROR", detail=str(e), meta={"provider": self.name})
                )
        return results

    async def translate(
        self, text: TextInput, *, source_lang: Optional[str] = None, target_lang: str = "zh", **options: Any
    ) -> LabelResult:
        loop = asyncio.get_running_loop()
        try:
            content = text or ""
            prompt = self.config.labeling.translation_prompt or ""
            out = await loop.run_in_executor(
                None,
                lambda: self._client.call_translate(
                    prompt=prompt,
                    content=content,
                ),
            )
            ok = bool(out and not out.startswith("AI"))
            return LabelResult(ok=ok, text=out or "", meta={"provider": self.name})
        except Exception as e:
            return LabelResult(ok=False, error_code="PROVIDER_ERROR", detail=str(e), meta={"provider": self.name})
