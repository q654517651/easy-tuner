from __future__ import annotations

import requests
from typing import Any, Dict, List, Optional

from ..utils.messages import build_messages_for_image, build_messages_for_text
from ...config import get_config


class LMStudioClient:
    """轻量 LM Studio HTTP 客户端封装。"""

    def __init__(self):
        self.config = get_config()

    def call_label_for_image(
        self,
        *,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: int = 60,
    ) -> str:
        lm_config = self.config.labeling.models.get('lm_studio', {})
        url = f"{lm_config.get('base_url', 'http://127.0.0.1:1234/v1')}/chat/completions"
        messages = build_messages_for_image(prompt, image_path)
        payload = {
            "model": model or lm_config.get('model_name', 'local-model'),
            "messages": messages,
            "max_tokens": max_tokens or lm_config.get('max_tokens', 2000),
            "temperature": temperature or lm_config.get('temperature', 0.7),
            "stream": False,
        }
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

    def call_translate(
        self,
        *,
        prompt: str,
        content: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: int = 60,
    ) -> str:
        lm_config = self.config.labeling.models.get('lm_studio', {})
        url = f"{lm_config.get('base_url', 'http://127.0.0.1:1234/v1')}/chat/completions"
        messages = build_messages_for_text(prompt, content)
        payload = {
            "model": model or lm_config.get('model_name', 'local-model'),
            "messages": messages,
            "max_tokens": max_tokens or lm_config.get('max_tokens', 2000),
            "temperature": temperature or lm_config.get('temperature', 0.7),
            "stream": False,
        }
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

    def quick_config_check(self) -> bool:
        lm_config = self.config.labeling.models.get('lm_studio', {})
        # 只要配置了 base_url 就认为可用
        return bool(lm_config.get('base_url'))

