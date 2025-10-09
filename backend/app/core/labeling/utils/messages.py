"""
消息与数据构造工具：构建聊天 messages、图像转 base64 等
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional


def image_to_base64(file_path: str | Path) -> str:
    p = Path(file_path)
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def build_messages_for_image(prompt: str, image_path: str) -> List[Dict[str, Any]]:
    b64 = image_to_base64(image_path)
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }
    ]


def build_messages_for_text(prompt: str, content: Optional[str] = None) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    if content:
        messages.append({"role": "user", "content": content})
    return messages

