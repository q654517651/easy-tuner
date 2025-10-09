from __future__ import annotations

from typing import Any, List, Dict, Optional

from ..utils.messages import build_messages_for_image, build_messages_for_text
from ...config import get_config


class GPTClient:
    """轻量 GPT 客户端封装。

    说明：
    - 不做复杂的限流/重试；后续按需要在 Provider 层补。
    - 依赖 openai SDK 时按需导入；若不可用则抛异常。
    """

    def __init__(self):
        self.config = get_config()

    def _ensure_sdk(self):
        try:
            from openai import OpenAI  # noqa: F401
        except Exception as e:
            raise RuntimeError(f"OpenAI SDK 不可用: {e}")

    def call_label_for_image(
        self,
        *,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        self._ensure_sdk()
        from openai import OpenAI

        messages = build_messages_for_image(prompt, image_path)
        gpt_config = self.config.labeling.models.get('gpt', {})
        client = OpenAI(
            api_key=gpt_config.get('api_key', ''),
            base_url=gpt_config.get('base_url', ''),
        )
        resp = client.chat.completions.create(
            model=model or gpt_config.get('model_name', 'gpt-4o'),
            messages=messages,
            max_tokens=max_tokens or gpt_config.get('max_tokens', 2000),
            temperature=temperature or gpt_config.get('temperature', 0.7),
        )
        return (resp.choices[0].message.content or "").strip()

    def call_translate(
        self,
        *,
        prompt: str,
        content: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        self._ensure_sdk()
        from openai import OpenAI

        messages = build_messages_for_text(prompt, content)
        gpt_config = self.config.labeling.models.get('gpt', {})
        client = OpenAI(
            api_key=gpt_config.get('api_key', ''),
            base_url=gpt_config.get('base_url', ''),
        )
        resp = client.chat.completions.create(
            model=model or gpt_config.get('model_name', 'gpt-4o'),
            messages=messages,
            max_tokens=max_tokens or gpt_config.get('max_tokens', 2000),
            temperature=temperature or gpt_config.get('temperature', 0.7),
        )
        return (resp.choices[0].message.content or "").strip()

    def quick_config_check(self) -> bool:
        gpt_config = self.config.labeling.models.get('gpt', {})
        # 只要配置了 api_key 和 base_url 就认为可用，不需要 enabled 字段
        return bool(gpt_config.get('api_key') and gpt_config.get('base_url'))

