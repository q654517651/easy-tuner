from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Sequence

from .base import LabelingProvider, LabelResult, ImageInput, TextInput
from ..utils.messages import build_messages_for_image, build_messages_for_text
from ...config import get_config


class LMStudioProvider(LabelingProvider):
    """LM Studio Provider - 直接调用 OpenAI 兼容 API（合并原 lm_studio_client 逻辑）"""

    name = "lm_studio"
    capabilities: Sequence[str] = ("label_image", "translate_text")

    def __init__(self):
        self.config = get_config()

    def _ensure_sdk(self):
        """确保 OpenAI SDK 可用"""
        try:
            from openai import OpenAI  # noqa: F401
        except Exception as e:
            raise RuntimeError(f"OpenAI SDK 不可用，请安装: pip install openai\n详细错误: {e}")

    def _get_config(self) -> dict:
        """获取 LM Studio 配置"""
        lm_config = self.config.labeling.models.get('lm_studio', {})
        if not lm_config:
            raise ValueError("LM Studio 模型未配置，请在设置页配置 Base URL")

        base_url = lm_config.get('base_url', '')
        if not base_url:
            raise ValueError(
                "LM Studio 配置不完整:\n"
                f"  - Base URL: 未配置\n"
                "请在设置页配置本地服务地址（如 http://127.0.0.1:1234/v1）"
            )

        return lm_config

    # TODO: 未来用于测试服务连通性（不阻断调用）
    async def test_connection(self) -> bool:
        """测试连接（暂时禁用，标记为 TODO）"""
        try:
            config = self._get_config()
            return bool(config.get('base_url'))
        except Exception:
            return False

    async def generate_labels(
        self, images: Sequence[ImageInput], prompt: Optional[str] = None, **options: Any
    ) -> List[LabelResult]:
        """批量生成标注"""
        # 配置检查
        try:
            config = self._get_config()
        except ValueError as e:
            return [
                LabelResult(ok=False, error_code="CONFIG_ERROR", detail=str(e), meta={"provider": self.name})
                for _ in images
            ]

        self._ensure_sdk()
        from openai import OpenAI

        loop = asyncio.get_running_loop()
        results: List[LabelResult] = []

        for img in images:
            try:
                # 转换输入为路径
                img_path = img if isinstance(img, str) else str(img)

                # 构建消息
                use_prompt = prompt if prompt is not None else (self.config.labeling.default_prompt or "描述这张图片")
                messages = build_messages_for_image(use_prompt, img_path)

                # 同步调用包装为异步
                def _call_lm_studio():
                    client = OpenAI(
                        api_key=config.get('api_key', 'lm-studio'),  # LM Studio 不需要真实 API Key
                        base_url=config.get('base_url', ''),
                    )
                    resp = client.chat.completions.create(
                        model=config.get('model_name', 'local-model'),
                        messages=messages,
                        max_tokens=config.get('max_tokens', 2000),
                        temperature=config.get('temperature', 0.7),
                    )
                    return (resp.choices[0].message.content or "").strip()

                text = await loop.run_in_executor(None, _call_lm_studio)
                ok = bool(text)
                results.append(LabelResult(ok=ok, text=text or "", meta={"provider": self.name}))

            except Exception as e:
                results.append(LabelResult(
                    ok=False,
                    error_code="PROVIDER_ERROR",
                    detail=f"LM Studio 调用失败: {str(e)}",
                    meta={"provider": self.name}
                ))

        return results

    async def translate(
        self, text: TextInput, *, source_lang: Optional[str] = None, target_lang: str = "zh", **options: Any
    ) -> LabelResult:
        """翻译文本"""
        # 配置检查
        try:
            config = self._get_config()
        except ValueError as e:
            return LabelResult(ok=False, error_code="CONFIG_ERROR", detail=str(e), meta={"provider": self.name})

        self._ensure_sdk()
        from openai import OpenAI

        loop = asyncio.get_running_loop()

        try:
            content = text or ""
            prompt = self.config.labeling.translation_prompt or "请翻译以下内容"
            messages = build_messages_for_text(prompt, content)

            def _call_lm_studio():
                client = OpenAI(
                    api_key=config.get('api_key', 'lm-studio'),
                    base_url=config.get('base_url', ''),
                )
                resp = client.chat.completions.create(
                    model=config.get('model_name', 'local-model'),
                    messages=messages,
                    max_tokens=config.get('max_tokens', 2000),
                    temperature=config.get('temperature', 0.7),
                )
                return (resp.choices[0].message.content or "").strip()

            out = await loop.run_in_executor(None, _call_lm_studio)
            ok = bool(out)
            return LabelResult(ok=ok, text=out or "", meta={"provider": self.name})

        except Exception as e:
            return LabelResult(
                ok=False,
                error_code="PROVIDER_ERROR",
                detail=f"翻译失败: {str(e)}",
                meta={"provider": self.name}
            )
