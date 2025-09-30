#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, torch
from pathlib import Path
from PIL import Image
from transformers import AutoProcessor

# 直接用 musubi 的加载器（支持单个 .safetensors）
from musubi_tuner.qwen_image.qwen_image_utils import load_qwen2_5_vl

DEFAULT_PROMPT = (
    "You are a professional image annotator. "
    "Describe the image in one detailed, information-dense sentence."
)

def main():
    if len(sys.argv) != 3:
        print("Usage: python caption_one_musubi.py <image_path> <model_file.safetensors>")
        sys.exit(1)

    img_path = Path(sys.argv[1])
    model_file = Path(sys.argv[2])

    if not img_path.exists():
        print(f"[ERR] Image not found: {img_path}"); sys.exit(2)
    if not (model_file.exists() and model_file.suffix == ".safetensors"):
        print(f"[ERR] Model file must be .safetensors: {model_file}"); sys.exit(3)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 处理器：固定用官方仓库（小文件，通常已缓存）
    # 同 musubi：指定 min/max_pixels（给 Qwen2.5-VL 的多尺度前处理）
    IMAGE_FACTOR = 28
    min_pixels = 256 * IMAGE_FACTOR * IMAGE_FACTOR
    max_size = 1280
    max_pixels = max_size * IMAGE_FACTOR * IMAGE_FACTOR
    processor = AutoProcessor.from_pretrained(
        "Qwen/Qwen2.5-VL-7B-Instruct",
        min_pixels=min_pixels,
        max_pixels=max_pixels,
    )

    # 模型：用 musubi 的加载器读取「单文件权重」
    # 这里用 bf16；如果你真想省显存，可以把 dtype 换成 torch.float8_e4m3fn
    _, model = load_qwen2_5_vl(str(model_file), dtype=torch.bfloat16, device=device, disable_mmap=False)
    model.eval()

    # 构造对话 + 图像
    image = Image.open(img_path).convert("RGB")
    messages = [{
        "role": "user",
        "content": [{"type": "image", "image": image},
                    {"type": "text", "text": DEFAULT_PROMPT}],
    }]

    # 模板 → 张量
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    # 这里不复用 musubi 的 bucket 实现，直接让 processor 处理尺寸即可
    inputs = processor(text=[text], images=image, padding=True, return_tensors="pt").to(device)

    with torch.no_grad():
        out_ids = model.generate(
            **inputs,
            max_new_tokens=128,
            pad_token_id=processor.tokenizer.eos_token_id,
        )

    # 去掉前缀（只保留新生成部分），然后解码
    gen_trim = [o[len(i):] for i, o in zip(inputs.input_ids, out_ids)]
    caption = processor.batch_decode(gen_trim, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    print(caption)

    # 写到同名 txt
    try:
        img_path.with_suffix(".txt").write_text(caption, encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    main()
