#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen2.5-VL 批量图像打标脚本
支持单图或多图批量推理，使用 musubi-tuner 加载器
"""

import sys
import json
import argparse
import warnings
from pathlib import Path
from contextlib import redirect_stdout

# 添加 musubi-tuner 到 Python 路径（在导入前）
# musubi-tuner 位置: workspace/runtime/engines/musubi-tuner/src
import os

# 从环境变量获取 workspace 路径（由调用者传递）
workspace_root = os.environ.get("EASYTUNER_WORKSPACE")
if not workspace_root:
    print("[ERROR] EASYTUNER_WORKSPACE environment variable not set", file=sys.stderr)
    sys.exit(1)

musubi_src = Path(workspace_root) / "runtime" / "engines" / "musubi-tuner" / "src"

if musubi_src.exists():
    sys.path.insert(0, str(musubi_src))
    print(f"[DEBUG] Added to sys.path: {musubi_src}", file=sys.stderr)
else:
    print(f"[ERROR] musubi-tuner src not found: {musubi_src}", file=sys.stderr)
    print(f"[ERROR] workspace: {workspace_root}", file=sys.stderr)
    sys.exit(1)

import torch
from PIL import Image
from transformers import AutoProcessor

# 禁用所有警告信息（避免污染 stdout）
warnings.filterwarnings("ignore")

# 确保库的日志不输出到 stdout
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)

# 直接用 musubi 的加载器（支持单个 .safetensors）
from musubi_tuner.qwen_image.qwen_image_utils import load_qwen2_5_vl

DEFAULT_PROMPT = (
    "You are a professional image annotator. "
    "Describe the image in one detailed, information-dense sentence."
)

def main():
    parser = argparse.ArgumentParser(description="Qwen2.5-VL 图像打标")
    parser.add_argument("weights_path", type=Path, help="模型权重文件路径 (.safetensors)")
    parser.add_argument("--images", type=str, nargs='+', required=True, help="图像路径列表")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT, help="打标提示词")
    parser.add_argument("--max_tokens", type=int, default=128, help="最大生成 token 数")

    args = parser.parse_args()

    # 验证权重文件
    if not args.weights_path.exists():
        print(json.dumps({"error": f"权重文件不存在: {args.weights_path}"}), file=sys.stderr)
        sys.exit(1)
    if args.weights_path.suffix != ".safetensors":
        print(json.dumps({"error": f"权重文件必须是 .safetensors 格式"}), file=sys.stderr)
        sys.exit(1)

    # 验证图像文件
    image_paths = [Path(p) for p in args.images]
    for img_path in image_paths:
        if not img_path.exists():
            print(json.dumps({"error": f"图像文件不存在: {img_path}"}), file=sys.stderr)
            sys.exit(1)

    try:
        # 将所有模型加载、推理过程的 stdout 重定向到 stderr，避免污染 JSON 输出
        with redirect_stdout(sys.stderr):
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            print(f"[DEBUG] 使用设备: {device}", file=sys.stderr)

            # 加载处理器
            IMAGE_FACTOR = 28
            min_pixels = 256 * IMAGE_FACTOR * IMAGE_FACTOR
            max_size = 1280
            max_pixels = max_size * IMAGE_FACTOR * IMAGE_FACTOR
            print(f"[DEBUG] 加载处理器...", file=sys.stderr)
            processor = AutoProcessor.from_pretrained(
                "Qwen/Qwen2.5-VL-7B-Instruct",
                min_pixels=min_pixels,
                max_pixels=max_pixels,
            )

            # 加载模型（只加载一次）
            print(f"[DEBUG] 加载模型: {args.weights_path}", file=sys.stderr)
            _, model = load_qwen2_5_vl(
                str(args.weights_path),
                dtype=torch.bfloat16,
                device=device,
                disable_mmap=False
            )
            model.eval()
            print(f"[DEBUG] 模型加载完成", file=sys.stderr)

            # 批量推理
            results = []
            for img_path in image_paths:
                try:
                    # 加载图像
                    image = Image.open(img_path).convert("RGB")

                    # 构造消息
                    messages = [{
                        "role": "user",
                        "content": [
                            {"type": "image", "image": image},
                            {"type": "text", "text": args.prompt}
                        ],
                    }]

                    # 生成输入
                    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                    inputs = processor(text=[text], images=image, padding=True, return_tensors="pt").to(device)

                    # 推理
                    with torch.no_grad():
                        out_ids = model.generate(
                            **inputs,
                            max_new_tokens=args.max_tokens,
                            pad_token_id=processor.tokenizer.eos_token_id,
                        )

                    # 解码
                    gen_trim = [o[len(i):] for i, o in zip(inputs.input_ids, out_ids)]
                    caption = processor.batch_decode(
                        gen_trim,
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=False
                    )[0]

                    results.append({
                        "image": str(img_path),
                        "caption": caption.strip(),
                        "success": True
                    })

                except Exception as e:
                    results.append({
                        "image": str(img_path),
                        "caption": "",
                        "success": False,
                        "error": str(e)
                    })

            # 清理显存
            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()

        # 退出 redirect_stdout 上下文后，恢复 stdout，只输出最终 JSON
        print(json.dumps(results, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
