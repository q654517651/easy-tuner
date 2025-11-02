from __future__ import annotations

import asyncio
from typing import Any, List, Optional, Sequence

from .base import LabelingProvider, LabelResult, ImageInput, TextInput
from ..utils.messages import build_messages_for_image, build_messages_for_text
from ...config import get_config


class GPTProvider(LabelingProvider):
    """GPT Provider - 直接调用 OpenAI SDK（合并原 gpt_client 逻辑）"""

    name = "gpt"
    capabilities: Sequence[str] = ("label_image", "translate_text")

    def __init__(self):
        # 不再缓存配置，每次使用时动态获取最新配置
        pass

    def _ensure_sdk(self):
        """确保 OpenAI SDK 可用"""
        try:
            from openai import OpenAI  # noqa: F401
        except Exception as e:
            raise RuntimeError(f"OpenAI SDK 不可用，请安装: pip install openai\n详细错误: {e}")

    def _get_config(self) -> dict:
        """获取 GPT 配置（自动填充默认值）"""
        config = get_config()
        user_config = config.labeling.models.get('gpt', {})
        
        # 从 registry 获取默认值
        from .registry import PROVIDER_METADATA
        metadata = PROVIDER_METADATA.get('gpt')
        
        # 先用默认值初始化
        gpt_config = {}
        if metadata:
            for field in metadata.config_fields:
                if field.default is not None:
                    gpt_config[field.key] = field.default
        
        # 用户配置覆盖默认值
        gpt_config.update(user_config)
        
        # 验证必填字段
        api_key = gpt_config.get('api_key', '')
        base_url = gpt_config.get('base_url', '')

        if not api_key or not base_url:
            raise ValueError(
                "GPT 配置不完整:\n"
                f"  - API Key: {'已配置' if api_key else '未配置'}\n"
                f"  - Base URL: {'已配置' if base_url else '未配置'}\n"
                "请在设置页完善配置"
            )

        return gpt_config

    # TODO: 未来用于测试服务连通性（不阻断调用）
    async def test_connection(self) -> bool:
        """测试连接（暂时禁用，标记为 TODO）"""
        try:
            config = self._get_config()
            return bool(config.get('api_key') and config.get('base_url'))
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
                if not isinstance(img, (str, bytes)):
                    img_path = str(img)
                else:
                    img_path = img if isinstance(img, str) else None

                if not img_path:
                    results.append(LabelResult(
                        ok=False,
                        error_code="INVALID_INPUT",
                        detail="bytes 输入暂不支持",
                        meta={"provider": self.name}
                    ))
                    continue

                # 构建消息
                use_prompt = prompt if prompt is not None else (get_config().labeling.default_prompt or "描述这张图片")
                messages = build_messages_for_image(use_prompt, img_path)

                # 同步调用包装为异步
                def _call_openai():
                    client = OpenAI(
                        api_key=config.get('api_key', ''),
                        base_url=config.get('base_url', ''),
                        timeout=60.0,  # 设置 60 秒超时（默认太短）
                    )
                    resp = client.chat.completions.create(
                        model=config.get('model_name', 'gpt-4o'),
                        messages=messages,
                        max_tokens=config.get('max_tokens', 2000),
                        temperature=config.get('temperature', 0.7),
                    )
                    return (resp.choices[0].message.content or "").strip()

                text = await loop.run_in_executor(None, _call_openai)
                ok = bool(text and not text.startswith("AI") and not text.startswith("错误"))
                results.append(LabelResult(ok=ok, text=text or "", meta={"provider": self.name}))

            except Exception as e:
                results.append(LabelResult(
                    ok=False,
                    error_code="PROVIDER_ERROR",
                    detail=f"GPT 调用失败: {str(e)}",
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
            prompt = get_config().labeling.translation_prompt or "请翻译以下内容"
            messages = build_messages_for_text(prompt, content)

            def _call_openai():
                client = OpenAI(
                    api_key=config.get('api_key', ''),
                    base_url=config.get('base_url', ''),
                    timeout=60.0,  # 设置 60 秒超时
                )
                resp = client.chat.completions.create(
                    model=config.get('model_name', 'gpt-4o'),
                    messages=messages,
                    max_tokens=config.get('max_tokens', 2000),
                    temperature=config.get('temperature', 0.7),
                )
                return (resp.choices[0].message.content or "").strip()

            out = await loop.run_in_executor(None, _call_openai)
            ok = bool(out and not out.startswith("AI") and not out.startswith("错误"))
            return LabelResult(ok=ok, text=out or "", meta={"provider": self.name})

        except Exception as e:
            return LabelResult(
                ok=False,
                error_code="PROVIDER_ERROR",
                detail=f"翻译失败: {str(e)}",
                meta={"provider": self.name}
            )
