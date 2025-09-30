import React, { useState } from 'react';
import { ControlStrip } from './ControlStrip';
import { useHoverVideo } from '../../hooks/useHoverVideo';
import type { MediaDisplayProps, ControlImage } from '../../types/dataset-card';

// 背景模糊组件
interface BackgroundBlurProps {
  url: string;
}

function BackgroundBlur({ url }: BackgroundBlurProps) {
  return (
    <img
      src={url}
      alt=""
      className="absolute inset-0 w-full h-full object-cover scale-110 blur-xl brightness-[0.6]"
      loading="lazy"
    />
  );
}

// 类型标签组件
interface TypeBadgeProps {
  mediaType: 'image' | 'video' | 'single_control_image' | 'multi_control_image';
  currentIndex?: number;
}

function TypeBadge({ mediaType, currentIndex = 0 }: TypeBadgeProps) {
  if (mediaType === 'video') {
    return (
      <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded">
        VIDEO
      </div>
    );
  }

  if ((mediaType === 'single_control_image' || mediaType === 'multi_control_image') && currentIndex > 0) {
    return (
      <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded">
        控制图 {currentIndex}
      </div>
    );
  }

  return null;
}

// 图像视图组件
interface ImageViewProps {
  url: string;
  filename: string;
}

function ImageView({ url, filename }: ImageViewProps) {
  return (
    <img
      src={url}
      alt={filename}
      className="relative z-10 w-full h-full object-contain"
      loading="lazy"
      onError={(e) => {
        console.error(`图片加载失败: ${url}`, e);
      }}
    />
  );
}

// 视频视图组件
interface VideoViewProps {
  url: string;
  filename: string;
}

function VideoView({ url, filename }: VideoViewProps) {
  const { videoRef, isHovering, hoverBind } = useHoverVideo();

  return (
    <div className="relative max-h-full max-w-full" {...hoverBind}>
      <video
        ref={videoRef}
        src={url}
        className="max-h-full max-w-full object-contain"
        muted
        loop
        playsInline
        preload="metadata"
      />

      {/* 播放状态指示器 */}
      {!isHovering && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-black/50 rounded-full p-3">
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}

// 控制图主视图组件
interface ControlMainViewProps {
  url: string;
  filename: string;
  controlImages: Array<ControlImage>;
  activeIndex: number;
}

function ControlMainView({ url, filename, controlImages, activeIndex }: ControlMainViewProps) {
  // 确定当前显示的图片
  const mainUrl = activeIndex === 0 ? url : controlImages[activeIndex - 1]?.url;
  const mainFilename = activeIndex === 0 ? filename : controlImages[activeIndex - 1]?.filename || filename;

  if (!mainUrl) {
    return (
      <div className="max-h-full max-w-full flex items-center justify-center text-gray-400">
        <div className="text-center">
          <div className="text-4xl mb-2">📷</div>
          <div className="text-sm">等待上传控制图</div>
        </div>
      </div>
    );
  }

  return <ImageView url={mainUrl} filename={mainFilename} />;
}

export function MediaDisplay({
  mediaType,
  url,
  filename,
  controlImages = [],
  onUploadControl,
  selected,
  labeling,
  onSelect
}: MediaDisplayProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  // 处理媒体区域点击选中
  const handleMediaClick = () => {
    // 如果正在打标中，禁用选择
    if (labeling) return;

    if (onSelect) {
      onSelect(!selected);
    }
  };

  return (
    <div
      className="relative h-[260px] overflow-hidden rounded-t-2xl cursor-pointer"
      onClick={handleMediaClick}
    >
      {/* 背景模糊层：同图源 */}
      <BackgroundBlur url={url} />

      {/* 渐变蒙版：统一类 */}
      <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-black/20 via-black/20 to-black/25" />

      {/* 内容层：object-contain，长边贴边 */}
      <div className="absolute inset-0 flex">
        <div className="flex-1 relative">
          {/* 为控制图类型预留底部空间 */}
          <div
            className={`w-full h-full ${
              (mediaType === 'single_control_image' || mediaType === 'multi_control_image')
                ? 'pb-20' // 为控制图条预留空间
                : ''
            }`}
          >
            {mediaType === 'image' && (
              <ImageView url={url} filename={filename} />
            )}
            {mediaType === 'video' && (
              <VideoView url={url} filename={filename} />
            )}
            {(mediaType === 'single_control_image' || mediaType === 'multi_control_image') && (
              <ControlMainView
                url={url}
                filename={filename}
                controlImages={controlImages}
                activeIndex={activeIndex}
              />
            )}
          </div>
        </div>

        {/* 控制图条（单图控制和多图控制类型） - 在底部横向排列，高z-index */}
        {(mediaType === 'single_control_image' || mediaType === 'multi_control_image') && (
          <div
            className="absolute bottom-2 left-2 right-2 z-20"
            onClick={(e) => e.stopPropagation()} // 阻止事件冒泡到MediaDisplay
          >
            <ControlStrip
              images={[
                { url, filename }, // 原图
                controlImages[0] || {},
                controlImages[1] || {},
                controlImages[2] || {}
              ] as [ControlImage, ControlImage, ControlImage, ControlImage]}
              activeIndex={activeIndex}
              onPick={(index) => {
                setActiveIndex(index);
              }}
              onUpload={(index) => {
                if (onUploadControl && index >= 1 && index <= 3) {
                  onUploadControl(index as 1 | 2 | 3);
                }
              }}
              controlType={mediaType}
            />
          </div>
        )}
      </div>

      {/* 底部类型标签 */}
      <TypeBadge mediaType={mediaType} currentIndex={activeIndex} />
    </div>
  );
}