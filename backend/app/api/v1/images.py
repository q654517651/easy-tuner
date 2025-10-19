"""
图片处理 API：批量裁剪（覆盖原图）

约定：
- 一律使用 cover 模式（长边贴边，铺满画布，不留空白）。
- 覆盖写回数据集内原图，不能撤销。
- 前端推荐上传 transform（scale, offset_x, offset_y），后端统一反算源裁剪框。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from starlette.concurrency import run_in_threadpool
from pathlib import Path

from ...core.environment import get_paths
from ...utils.logger import log_info, log_warning, log_error

from PIL import Image, ImageOps


router = APIRouter()


class TransformParams(BaseModel):
    scale: float = Field(gt=0)
    offset_x: float = 0.0
    offset_y: float = 0.0


class SourceRect(BaseModel):
    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ImageCropItem(BaseModel):
    id: Optional[str] = None
    source_path: str
    transform: Optional[TransformParams] = None
    source_rect: Optional[SourceRect] = None


class BatchCropRequest(BaseModel):
    target_width: int = Field(gt=0)
    target_height: int = Field(gt=0)
    images: List[ImageCropItem]


def _resolve_in_workspace(path_str: str) -> Path:
    """解析路径到工作区内（支持绝对/相对），并做越界校验。"""
    ws = get_paths().workspace_root.resolve()
    p = Path(path_str)
    if not p.is_absolute():
        p = (ws / p).resolve()
    else:
        p = p.resolve()
    try:
        # Python 3.9+
        if not p.is_relative_to(ws):
            raise HTTPException(status_code=403, detail="越界路径：仅允许工作区内文件")
    except AttributeError:
        # 兼容性退化
        if not str(p).startswith(str(ws)):
            raise HTTPException(status_code=403, detail="越界路径：仅允许工作区内文件")
    return p


def _compute_src_rect_from_transform(
    img_w: int,
    img_h: int,
    canvas_w: int,
    canvas_h: int,
    scale: float,
    offset_x: float,
    offset_y: float,
) -> Dict[str, Any]:
    """根据前端变换参数反算源裁剪框，强制 cover，无留白。返回 rect 和可能调整后的 scale。"""
    # cover 模式要求：scale 至少能覆盖画布
    min_scale = max(canvas_w / img_w, canvas_h / img_h)
    applied_scale = max(scale, min_scale)

    # 反算在源图中的可视矩形（未约束）
    src_w = canvas_w / applied_scale
    src_h = canvas_h / applied_scale
    x0 = (0 - offset_x) / applied_scale
    y0 = (0 - offset_y) / applied_scale

    # 仅平移到图内，保持尺寸不变（避免留白）
    max_x0 = max(0.0, img_w - src_w)
    max_y0 = max(0.0, img_h - src_h)
    x0 = min(max(x0, 0.0), max_x0)
    y0 = min(max(y0, 0.0), max_y0)

    return {
        "x": float(x0),
        "y": float(y0),
        "w": float(src_w),
        "h": float(src_h),
        "scale": float(applied_scale),
    }


def _crop_cover_and_overwrite(
    in_path: Path,
    canvas_w: int,
    canvas_h: int,
    transform: Optional[TransformParams],
    source_rect: Optional[SourceRect],
) -> Dict[str, Any]:
    """执行单张图片裁剪并覆盖原图。返回输出信息。"""
    if not in_path.exists():
        return {"success": False, "message": f"文件不存在: {in_path}"}

    try:
        with Image.open(in_path) as im0:
            # EXIF 方向矫正
            im = ImageOps.exif_transpose(im0)
            img_w, img_h = im.size

            applied = {}

            if transform is not None:
                t = transform
                if t.scale <= 0:
                    return {"success": False, "message": "scale 必须 > 0"}
                calc = _compute_src_rect_from_transform(
                    img_w, img_h, canvas_w, canvas_h, t.scale, t.offset_x, t.offset_y
                )
                left_f = calc["x"]
                top_f = calc["y"]
                w_f = calc["w"]
                h_f = calc["h"]
                applied = {
                    "scale": calc["scale"],
                    "offset_x": t.offset_x,
                    "offset_y": t.offset_y,
                    "src_rect": {"x": left_f, "y": top_f, "width": w_f, "height": h_f},
                }
            elif source_rect is not None:
                # 直接使用源裁剪框，然后等比拉伸/缩放到目标尺寸（覆盖）
                sr = source_rect
                left_f, top_f = float(sr.x), float(sr.y)
                w_f, h_f = float(sr.width), float(sr.height)
                # 约束在图内（尽量平移），保证尺寸不变
                w_f = min(w_f, img_w)
                h_f = min(h_f, img_h)
                max_x0 = max(0.0, img_w - w_f)
                max_y0 = max(0.0, img_h - h_f)
                left_f = min(max(left_f, 0.0), max_x0)
                top_f = min(max(top_f, 0.0), max_y0)
                applied = {
                    "scale": None,
                    "offset_x": None,
                    "offset_y": None,
                    "src_rect": {"x": left_f, "y": top_f, "width": w_f, "height": h_f},
                }
            else:
                # 若未提供参数，按 cover 居中裁切
                min_scale = max(canvas_w / img_w, canvas_h / img_h)
                src_w = canvas_w / min_scale
                src_h = canvas_h / min_scale
                left_f = (img_w - src_w) / 2.0
                top_f = (img_h - src_h) / 2.0
                applied = {
                    "scale": min_scale,
                    "offset_x": (canvas_w - img_w * min_scale) / 2.0,
                    "offset_y": (canvas_h - img_h * min_scale) / 2.0,
                    "src_rect": {"x": left_f, "y": top_f, "width": src_w, "height": src_h},
                }

            # 将浮点裁剪框转换为像素整数，保证边界不越界
            left = int(round(left_f))
            top = int(round(top_f))
            right = int(round(left_f + w_f))
            bottom = int(round(top_f + h_f))

            # 纠正可能的越界
            if right > img_w:
                shift = right - img_w
                left -= shift
                right -= shift
            if bottom > img_h:
                shift = bottom - img_h
                top -= shift
                bottom -= shift
            left = max(0, left)
            top = max(0, top)

            # 裁剪并缩放到目标尺寸（cover）
            cropped = im.crop((left, top, right, bottom))
            out_img = cropped.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)

            # 覆盖保存原图（无撤销）
            save_kwargs: Dict[str, Any] = {}
            fmt = (im0.format or "").upper()
            # JPEG 压缩质量设置
            if fmt in {"JPEG", "JPG"}:
                save_kwargs.update({"quality": 95, "optimize": True})
            # PNG 保留默认
            tmp_path = in_path.with_name(f".{in_path.name}.crop_tmp{in_path.suffix}")
            try:
                out_img.save(tmp_path, **save_kwargs)
                import os, time
                for _ in range(10):
                    try:
                        os.replace(tmp_path, in_path)
                        break
                    except Exception:
                        time.sleep(0.05)
                else:
                    raise RuntimeError("无法替换原图: 文件被占用")
            finally:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

            return {
                "success": True,
                "output_path": str(in_path),
                "width": canvas_w,
                "height": canvas_h,
                "applied": applied,
            }
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"裁剪失败: {in_path} - {e}")
        return {"success": False, "message": str(e)}


@router.post("/images/crop/batch")
async def crop_images_batch(request: BatchCropRequest):
    """批量裁剪并覆盖原图（cover 模式，必须填满画布）。"""
    canvas_w = int(request.target_width)
    canvas_h = int(request.target_height)
    if canvas_w <= 0 or canvas_h <= 0:
        raise HTTPException(status_code=400, detail="目标尺寸必须为正整数")

    def _run() -> Dict[str, Any]:
        results = []
        for item in request.images:
            try:
                p = _resolve_in_workspace(item.source_path)
            except HTTPException as he:
                results.append({
                    "id": item.id,
                    "success": False,
                    "message": he.detail,
                    "source_path": item.source_path,
                })
                continue

            res = _crop_cover_and_overwrite(
                p, canvas_w, canvas_h, item.transform, item.source_rect
            )
            res.update({
                "id": item.id,
                "source_path": str(p),
            })
            results.append(res)

        return {
            "success": True,
            "message": "裁剪完成",
            "data": {
                "items": results,
            }
        }

    return await run_in_threadpool(_run)
