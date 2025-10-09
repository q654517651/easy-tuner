import React from 'react';
import { Button } from '@heroui/react';
import type { ControlImage } from '../../types/dataset-card';

interface ControlStripProps {
  images: [ControlImage, ControlImage, ControlImage, ControlImage]; // 固定4个位置：原图 + 3个控制图
  activeIndex: number;
  onPick: (index: number) => void;
  onUpload: (index: number) => void; // 1-3，语义清晰（控制图索引）
  onDelete?: (index: number) => void; // 删除控制图
  controlType: 'single_control_image' | 'multi_control_image'; // 控制图类型
}

// 单个缩略图项组件
interface ThumbnailItemProps {
  image: ControlImage;
  index: number;
  isActive: boolean;
  onPick: () => void;
  onUpload?: () => void; // 可选：仅控制图槽位有上传功能
  onDelete?: () => void; // 可选：删除功能
}

function ThumbnailItem({ image, index, isActive, onPick, onUpload, onDelete }: ThumbnailItemProps) {
  const hasContent = image.url && image.url.trim() !== '';

  // 统一的 ring 样式：选中时蓝色，未选中时白色半透明；悬浮时加粗
  const ringClasses = isActive
    ? "ring-2 ring-blue-500 hover:ring-[3px]"
    : "ring-1 ring-white/20 hover:ring-2 hover:ring-white/40";

  // 悬浮缩放效果
  const hoverScaleClasses = "hover:scale-105";

  if (!hasContent && onUpload) {
    // 空控制图槽位 - 显示上传按钮
    return (
      <button
        className={`w-12 h-12 shrink-0 rounded-lg bg-black/40 backdrop-blur ${ringClasses} ${hoverScaleClasses} transition-all duration-200 flex items-center justify-center`}
        onClick={onUpload}
      >
        <div className="flex flex-col items-center justify-center text-white/80">
          <div className="text-lg leading-none">+</div>
        </div>
      </button>
    );
  }

  if (!hasContent) {
    // 原图槽位但无内容（不应该发生）
    return (
      <div className={`w-12 h-12 shrink-0 rounded-lg bg-black/40 backdrop-blur flex items-center justify-center ${ringClasses}`}>
        <div className="text-white/60 text-xs">无图</div>
      </div>
    );
  }

  // 有内容的缩略图
  return (
    <div className="relative w-12 h-12 shrink-0 group/ctrl-thumb">
      <button
        type="button"
        className={`w-full h-full rounded-lg overflow-hidden bg-black/40 backdrop-blur ${ringClasses} ${hoverScaleClasses} transition-all duration-200 relative`}
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
        <div className="absolute bottom-0.5 right-0.5 bg-black/70 text-white text-[10px] px-1 py-0.5 rounded leading-none">
          {index === 0 ? '原' : index}
        </div>
      </button>

      {/* 删除按钮 - 仅控制图显示，在外层 div 中不会被裁切 */}
      {onDelete && index > 0 && (
        <button
          type="button"
          aria-label="删除控制图"
          className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover/ctrl-thumb:opacity-100 transition-opacity duration-200 hover:bg-red-600 z-10"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <span className="text-white text-xs leading-none">×</span>
        </button>
      )}
    </div>
  );
}

export function ControlStrip({ images, activeIndex, onPick, onUpload, onDelete, controlType }: ControlStripProps) {
  // 根据控制图类型确定可用的控制图槽位数量
  const maxControlSlots = controlType === 'single_control_image' ? 1 : 3;

  return (
    <div className="flex flex-row gap-2">
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
            onDelete={index >= 1 && onDelete ? () => onDelete(index) : undefined}
          />
        );
      })}
    </div>
  );
}