from __future__ import annotations

from typing import Any, List, Optional, Sequence

import httpx

from .base import LabelingProvider, LabelResult, ImageInput, TextInput
from ..utils.messages import build_messages_for_image, build_messages_for_text
from ...config import get_config


class LMStudioProvider(LabelingProvider):
    """LM Studio Provider - 直接调用 OpenAI 兼容 API（使用 HTTP 请求，不依赖 OpenAI SDK）"""

    name = "lm_studio"
    capabilities: Sequence[str] = ("label_image", "translate_text")

    def __init__(self):
        # 不再缓存配置，每次使用时动态获取最新配置
        pass

    def _get_config(self) -> dict:
        """获取 LM Studio 配置（自动填充默认值）"""
        config = get_config()
        user_config = config.labeling.models.get('lm_studio', {})
        
        # 从 registry 获取默认值
        from .registry import PROVIDER_METADATA
        metadata = PROVIDER_METADATA.get('lm_studio')
        
        # 先用默认值初始化
        lm_config = {}
        if metadata:
            for field in metadata.config_fields:
                if field.default is not None:
                    lm_config[field.key] = field.default
        
        # 用户配置覆盖默认值
        lm_config.update(user_config)
        
        # 验证必填字段
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

        results: List[LabelResult] = []

        for img in images:
            try:
                # 转换输入为路径
                img_path = img if isinstance(img, str) else str(img)

                # 构建消息
                use_prompt = prompt if prompt is not None else (get_config().labeling.default_prompt or "描述这张图片")
                messages = build_messages_for_image(use_prompt, img_path)

                # 构建请求体（不包含 model 参数）
                payload = {
                    "messages": messages,
                    "max_tokens": config.get('max_tokens', 2000),
                    "temperature": config.get('temperature', 0.7),
                }

                # 发送 HTTP 请求
                base_url = config.get('base_url', '').rstrip('/')
                url = f"{base_url}/chat/completions"
                
                headers = {
                    "Content-Type": "application/json",
                }
                
                # 如果有 API Key，添加到请求头
                api_key = config.get('api_key', 'lm-studio')
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    data = response.json()
                    text = (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
                    
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

        try:
            content = text or ""
            prompt = get_config().labeling.translation_prompt or "请翻译以下内容"
            messages = build_messages_for_text(prompt, content)

            # 构建请求体（不包含 model 参数）
            payload = {
                "messages": messages,
                "max_tokens": config.get('max_tokens', 2000),
                "temperature": config.get('temperature', 0.7),
            }

            # 发送 HTTP 请求
            base_url = config.get('base_url', '').rstrip('/')
            url = f"{base_url}/chat/completions"
            
            headers = {
                "Content-Type": "application/json",
            }
            
            # 如果有 API Key，添加到请求头
            api_key = config.get('api_key', 'lm-studio')
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                out = (data.get("choices", [{}])[0].get("message", {}).get("content", "") or "").strip()
                
            ok = bool(out)
            return LabelResult(ok=ok, text=out or "", meta={"provider": self.name})

        except Exception as e:
            return LabelResult(
                ok=False,
                error_code="PROVIDER_ERROR",
                detail=f"翻译失败: {str(e)}",
                meta={"provider": self.name}
            )
