import React from 'react';
import { Button } from '@heroui/react';
import type { ControlImage } from '../../types/dataset-card';

interface ControlStripProps {
  images: [ControlImage, ControlImage, ControlImage, ControlImage]; // 固定4个位置：原图 + 3个控制图
  activeIndex: number;
  onPick: (index: number) => void;
  onUpload: (index: number) => void; // 1-3，语义清晰（控制图索引）
  controlType: 'single_control_image' | 'multi_control_image'; // 控制图类型
}

// 单个缩略图项组件
interface ThumbnailItemProps {
  image: ControlImage;
  index: number;
  isActive: boolean;
  onPick: () => void;
  onUpload?: () => void; // 可选：仅控制图槽位有上传功能
}

function ThumbnailItem({ image, index, isActive, onPick, onUpload }: ThumbnailItemProps) {
  const hasContent = image.url && image.url.trim() !== '';

  // 激活状态样式
  const activeClasses = isActive
    ? "ring-2 ring-blue-500 ring-offset-1"
    : "ring-1 ring-gray-200";

  // 悬浮效果
  const hoverClasses = "hover:ring-2 hover:ring-blue-300 hover:scale-105";

  if (!hasContent && onUpload) {
    // 空控制图槽位 - 显示上传按钮
    return (
      <div className="flex-1 min-h-0 relative">
        <Button
          size="sm"
          variant="bordered"
          className={`w-full h-full p-0 rounded-lg ${activeClasses} ${hoverClasses} transition-all duration-200`}
          onPress={onUpload}
        >
          <div className="flex flex-col items-center justify-center text-xs text-gray-500">
            <div className="text-base">+</div>
            <div className="text-xs">上传</div>
          </div>
        </Button>
      </div>
    );
  }

  if (!hasContent) {
    // 原图槽位但无内容（不应该发生）
    return (
      <div className={`flex-1 min-h-0 rounded-lg bg-gray-100 flex items-center justify-center ${activeClasses}`}>
        <div className="text-gray-400 text-xs">无图</div>
      </div>
    );
  }

  // 有内容的缩略图
  return (
    <div className="flex-1 min-h-0 relative">
      <button
        className={`w-full h-full rounded-lg overflow-hidden bg-gray-100 ${activeClasses} ${hoverClasses} transition-all duration-200`}
        onClick={onPick}
      >
        <img
          src={image.url}
          alt={image.filename || `图片 ${index}`}
          className="w-full h-full object-cover"
          loading="lazy"
          onError={(e) => {
            console.error(`控制图加载失败: ${image.url}`, e);
            const target = e.target as HTMLImageElement;
            target.style.display = 'none';
          }}
        />

        {/* 索引标签 */}
        <div className="absolute bottom-1 right-1 bg-black/60 text-white text-xs px-1 py-0.5 rounded">
          {index === 0 ? '原' : index}
        </div>

        {/* 激活指示器 */}
        {isActive && (
          <div className="absolute top-1 right-1 w-3 h-3 bg-blue-500 rounded-full flex items-center justify-center">
            <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
          </div>
        )}
      </button>
    </div>
  );
}

export function ControlStrip({ images, activeIndex, onPick, onUpload, controlType }: ControlStripProps) {
  // 根据控制图类型确定可用的控制图槽位数量
  const maxControlSlots = controlType === 'single_control_image' ? 1 : 3;

  return (
    <div className="flex flex-row gap-2 p-2 h-16 bg-black/20 backdrop-blur-sm rounded-lg">
      {images.map((image, index) => {
        // 原图(index=0)始终显示，控制图根据类型限制显示数量
        const shouldShow = index === 0 || index <= maxControlSlots;

        if (!shouldShow) {
          return null; // 不显示超出限制的控制图槽位
        }

        return (
          <ThumbnailItem
            key={index}
            image={image}
            index={index}
            isActive={activeIndex === index}
            onPick={() => onPick(index)}
            onUpload={index >= 1 && index <= maxControlSlots ? () => onUpload(index) : undefined}
          />
        );
      })}
    </div>
  );
}