import { useEffect, useMemo, useRef, useState } from "react";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import type { ReactZoomPanPinchRef } from "react-zoom-pan-pinch";
import { Slider } from "@heroui/react";

// 兼容不同版本的 react-zoom-pan-pinch：优先 state，其次 instance.transformState
function getRZPPState(inst: any): { scale: number; positionX: number; positionY: number } | null {
  if (!inst) return null;
  const s = inst.state ?? inst.instance?.transformState ?? inst.transformState;
  if (!s) return null;
  const { scale, positionX, positionY } = s;
  if ([scale, positionX, positionY].some(v => typeof v !== "number" || Number.isNaN(v))) return null;
  return { scale, positionX, positionY };
}

export interface CropCardProps {
  url: string;
  filename: string;
  targetWidth: number;   // 仅用于容器宽高比
  targetHeight: number;  // 仅用于容器宽高比
  initialCrop?: {
    zoom: number;     // 以 scale 表示（相对原图 CSS 尺寸）
    offsetX: number;  // 以 px 表示：相对“居中位置”的平移（右为正）
    offsetY: number;  // 以 px 表示：相对“居中位置”的平移（下为正）
  };
  onCropChange?: (params: CropParams) => void;
  autosaveDelay?: number;
  flushSignal?: number;
}

export interface CropParams {
  zoom: number;    // 当前 scale
  offsetX: number; // 当前 positionX - 居中positionX（见下）
  offsetY: number; // 当前 positionY - 居中positionY（见下）
  // 绝对位移，等同于 TransformWrapper 的 positionX/positionY，便于后端直接使用
  positionX?: number;
  positionY?: number;
  cropRect: {
    x: number;      // [0,1] 相对原图
    y: number;
    width: number;
    height: number;
  };
}

export function CropCard(props: CropCardProps) {
  const {
    url,
    targetWidth,
    targetHeight,
    initialCrop,
    onCropChange,
    autosaveDelay = 800,
  } = props;

  // 容器与原图尺寸
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [img, setImg] = useState<{ w: number; h: number } | null>(null);

  // 变换状态（来自 react-zoom-pan-pinch）
  const [transform, setTransform] = useState<{ scale: number; x: number; y: number }>({
    scale: 1, x: 0, y: 0,
  });

  // 保存 TransformWrapper 的 ref
  const transformRef = useRef<ReactZoomPanPinchRef | null>(null);

  // ---- 量容器像素 ----
  useEffect(() => {
    if (!boxRef.current) return;
    const el = boxRef.current;
    const ro = new ResizeObserver(() => setBox({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setBox({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  // ---- 读原图尺寸 ----
  useEffect(() => {
    if (!url) return;
    const pic = new Image();
    pic.onload = () => setImg({ w: pic.naturalWidth, h: pic.naturalHeight });
    pic.src = url;
  }, [url]);

  const aspect = Math.max(1, targetWidth) / Math.max(1, targetHeight);
  const ready = img && box.w > 0 && box.h > 0;

  // 计算 cover 所需最小缩放（长边贴边）
  const minScale = useMemo(() => {
    if (!ready) return 1;
    const EPS = 0.01;
    return Math.max(box.w / img!.w, box.h / img!.h) + EPS;
  }, [ready, box.w, box.h, img]);

  // 滑杆最大值：minScale 的 3 倍（即 300%）
  const sliderMax = useMemo(() => minScale * 3, [minScale]);
  // 绝对最大值：minScale 的 10 倍（滚轮可以达到）
  const maxScale = useMemo(() => minScale * 10, [minScale]);

  // 计算首帧初始 scale 与"居中位置"
  const initialScale = useMemo(() => {
    if (!ready) return 1;
    // 如果有 initialCrop，使用它；否则使用 minScale（短边顶边，即 100%）
    return initialCrop?.zoom ?? minScale;
  }, [ready, initialCrop?.zoom, minScale]);

  const centeredPos = useMemo(() => {
    if (!ready) return { x: 0, y: 0 };
    const s = initialScale;
    const cx = (box.w - img!.w * s) / 2;
    const cy = (box.h - img!.h * s) / 2;
    return { x: cx, y: cy };
  }, [ready, box.w, box.h, img, initialScale]);

  // 初始位置：在“居中”的基础上加上 initialCrop 偏移
  const initialPos = useMemo(() => {
    if (!ready) return { x: 0, y: 0 };
    return {
      x: centeredPos.x + (initialCrop?.offsetX ?? 0),
      y: centeredPos.y + (initialCrop?.offsetY ?? 0),
    };
  }, [ready, centeredPos.x, centeredPos.y, initialCrop?.offsetX, initialCrop?.offsetY]);

  // 重新挂载 TransformWrapper 以应用新的 initialScale/initialPosition
  const wrapperKey = ready
    ? `${url}`
    : "loading";

  // 根据当前 transform 计算裁剪参数（归一化，基于原图像素）
  const computeCropRect = (state: { scale: number; x: number; y: number }) => {
    if (!ready) return { x: 0, y: 0, width: 1, height: 1 };

    const s = state.scale;
    const posX = state.x;
    const posY = state.y;

    // 视口在“内容坐标系（原图CSS尺寸）”中的窗口
    // x_c_min = (0 - posX) / s
    // y_c_min = (0 - posY) / s
    // 可见宽高 = box.w / s, box.h / s
    const x_c = (0 - posX) / s;
    const y_c = (0 - posY) / s;
    const w_c = box.w / s;
    const h_c = box.h / s;

    // 归一化到原图（原图 CSS 尺寸= natural 尺寸）
    const x_n = x_c / img!.w;
    const y_n = y_c / img!.h;
    const w_n = w_c / img!.w;
    const h_n = h_c / img!.h;

    // clamp 防守（limitToBounds 开了其实不会越界）
    const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
    return {
      x: clamp01(x_n),
      y: clamp01(y_n),
      width: clamp01(w_n),
      height: clamp01(h_n),
    };
  };

  // 防抖回调
  const saveTimerRef = useRef<number | null>(null);
  const emit = (st: { scale: number; x: number; y: number }) => {
    if (!onCropChange) return;
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    const cropRect = computeCropRect(st);
    const offsetX = st.x - centeredPos.x;
    const offsetY = st.y - centeredPos.y;
    saveTimerRef.current = window.setTimeout(() => {
      // 计算像素裁剪框（基于原图像素）
      const px = img ? {
        x: Math.round(cropRect.x * img.w),
        y: Math.round(cropRect.y * img.h),
        width: Math.round(cropRect.width * img.w),
        height: Math.round(cropRect.height * img.h),
      } : null;
      onCropChange({
        zoom: st.scale,
        offsetX,
        offsetY,
        positionX: st.x,
        positionY: st.y,
        cropRect,
        // 附带像素裁剪框，便于后端直接使用
        ...(px ? { pixelRect: px, imageSize: { width: img!.w, height: img!.h } } : {} as any),
      } as any);
    }, props.autosaveDelay ?? 800);
  };

  // 父组件要求立即回传最新transform（用于点击确认前flush）
  useEffect(() => {
    if (!ready || !onCropChange) return;
    const inst = transformRef.current;
    const s = inst ? getRZPPState(inst) : null;
    if (!s) return;
    const st = { scale: s.scale, x: s.positionX, y: s.positionY };
    const cropRect = computeCropRect(st);
    const offsetX = st.x - centeredPos.x;
    const offsetY = st.y - centeredPos.y;
    const px = img ? {
      x: Math.round(cropRect.x * img.w),
      y: Math.round(cropRect.y * img.h),
      width: Math.round(cropRect.width * img.w),
      height: Math.round(cropRect.height * img.h),
    } : null;
    onCropChange({
      zoom: st.scale,
      offsetX,
      offsetY,
      positionX: st.x,
      positionY: st.y,
      cropRect,
      ...(px ? { pixelRect: px, imageSize: { width: img!.w, height: img!.h } } : {} as any),
    } as any);
  }, [props.flushSignal]);

  // 目标尺寸变化时，若当前scale不足以cover，自动放大到minScale并保持居中
  useEffect(() => {
    if (!ready) return;
    const inst = transformRef.current;
    const s = inst ? getRZPPState(inst) : null;
    if (!s) return;
    if (s.scale + 1e-6 >= minScale) return;
    const centerX = box.w / 2;
    const centerY = box.h / 2;
    const imgCenterX = (centerX - s.positionX) / s.scale;
    const imgCenterY = (centerY - s.positionY) / s.scale;
    const newScale = minScale;
    const newX = centerX - imgCenterX * newScale;
    const newY = centerY - imgCenterY * newScale;
    inst!.setTransform(newX, newY, newScale, 0);
    const st = { scale: newScale, x: newX, y: newY };
    setTransform(st);
    const cropRect = computeCropRect(st);
    const offsetX = st.x - centeredPos.x;
    const offsetY = st.y - centeredPos.y;
    const px = img ? {
      x: Math.round(cropRect.x * img.w),
      y: Math.round(cropRect.y * img.h),
      width: Math.round(cropRect.width * img.w),
      height: Math.round(cropRect.height * img.h),
    } : null;
    onCropChange?.({
      zoom: st.scale,
      offsetX,
      offsetY,
      positionX: st.x,
      positionY: st.y,
      cropRect,
      ...(px ? { pixelRect: px, imageSize: { width: img!.w, height: img!.h } } : {} as any),
    } as any);
  }, [targetWidth, targetHeight, minScale]);

  return (
    <div className="rounded-2xl bg-content1 dark:bg-white/5 shadow-sm overflow-hidden">
      {/* 视口（=裁剪框） */}
      <div
        ref={boxRef}
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: `${Math.max(1, targetWidth)} / ${Math.max(1, targetHeight)}`,
          background: "transparent",
          overflow: "hidden",
        }}
      >
        {ready && (
          <TransformWrapper
            ref={transformRef}
            key={wrapperKey}
            initialScale={initialScale}
            minScale={minScale}
            maxScale={maxScale}
            wheel={{ step: 0.05 }}  // 滚轮可以突破滑杆限制
            initialPositionX={initialPos.x}
            initialPositionY={initialPos.y}
            limitToBounds   // 防止露白
            doubleClick={{ disabled: true }}
            panning={{ velocityDisabled: true }}
            onTransformed={(ctx: any) => {
              const s = getRZPPState(ctx);
              if (!s) return;
              const st = { scale: s.scale, x: s.positionX, y: s.positionY };
              setTransform(st);
              emit(st);
            }}
          >
            {() => (
              <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }}>
                <img
                  src={url}
                  alt={props.filename}
                  draggable={false}
                  style={{
                    display: "block",
                    maxWidth: "none",
                    maxHeight: "none",
                    width: "auto",
                    height: "auto",
                    userSelect: "none",
                    pointerEvents: "none",
                  }}
                />
              </TransformComponent>
            )}
          </TransformWrapper>
        )}

        {!ready && (
          <div className="absolute inset-0 grid place-items-center text-sm text-default-500">
            加载中…
          </div>
        )}
      </div>

      {/* 控制条 */}
      <div className="p-4 bg-content1 dark:bg-white/5 flex items-center gap-4 border-t border-divider">
        <svg className="w-5 h-5 text-default-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
        </svg>

        <Slider
          value={Math.min(transform.scale, sliderMax)}
          minValue={minScale}
          maxValue={sliderMax}
          step={0.01}
          onChange={(value) => {
            const inst = transformRef.current;
            if (!inst || !ready) return;

            const newScaleRaw = typeof value === 'number' ? value : value[0];
            const newScale = Math.max(minScale, Math.min(newScaleRaw, sliderMax));

            const s = getRZPPState(inst);
            if (!s) return;

            const centerX = box.w / 2;
            const centerY = box.h / 2;
            // 当前中心点对应到图像坐标（以"当前"缩放为基准）
            const imgCenterX = (centerX - s.positionX) / s.scale;
            const imgCenterY = (centerY - s.positionY) / s.scale;
            // 新的位置：让图像的同一点仍然对齐到容器中心
            const newX = centerX - imgCenterX * newScale;
            const newY = centerY - imgCenterY * newScale;

            inst.setTransform(newX, newY, newScale, 0);
          }}
          className="flex-1"
          aria-label="Zoom"
          isDisabled={!ready}
        />

        <span className="text-sm font-medium text-default-700 text-right whitespace-nowrap">
          {ready ? `${Math.round((transform.scale / minScale) * 100)}%` : `100%`}
        </span>
      </div>
    </div>
  );
}
