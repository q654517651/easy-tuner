import React, { useState } from 'react';
import { Button, Textarea } from '@heroui/react';
import { CardShell } from './CardShell';
import { ControlStrip } from './ControlStrip';
import { useAutosaveText } from '../hooks/useAutosaveText';
import type { ControlCardProps, ControlImage } from '../types/media-cards';

export function ControlImageCard({
  url,
  filename,
  caption,
  selected,
  labeling,
  onSelectChange,
  onDelete,
  onCaptionSave,
  onUploadControl,
  controls,
  autosaveDelay = 1800
}: ControlCardProps) {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);

  const { text, setText, bindTextareaHandlers } = useAutosaveText({
    initial: caption,
    autosaveDelay,
    onSave: onCaptionSave || (() => {})
  });

  // 构建图片列表：原图 + 控制图（固定4个位置）
  const imageList: [ControlImage, ControlImage, ControlImage, ControlImage] = [
    { url, filename }, // 原图
    controls[0] || {}, // 控制图1
    controls[1] || {}, // 控制图2
    controls[2] || {}  // 控制图3
  ];

  const currentImage = imageList[currentImageIndex];

  // 操作按钮
  const actions = (
    <>
      {onDelete && (
        <Button
          size="sm"
          color="danger"
          variant="flat"
          onPress={onDelete}
          className="bg-white/80 backdrop-blur-sm"
        >
          删除
        </Button>
      )}
    </>
  );

  // 媒体区域 - 控制图模式
  const media = (
    <div className="relative w-full h-52 sm:h-60 md:h-64 overflow-hidden">
      {/* 主图区域 */}
      <div className="flex h-full">
        <div className="flex-1 relative">
          {currentImage.url ? (
            <>
              {/* 背景模糊图 */}
              <img
                src={currentImage.url}
                alt=""
                className="absolute inset-0 w-full h-full object-cover scale-110 blur-xl brightness-[0.6]"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-black/20 to-black/25" />

              {/* 前景主图 */}
              <img
                src={currentImage.url}
                alt={currentImage.filename || filename}
                className="relative z-10 w-full h-full object-contain"
                loading="lazy"
              />
            </>
          ) : (
            <div className="w-full h-full bg-gray-200 flex items-center justify-center">
              <div className="text-gray-400 text-center">
                <div className="text-lg mb-2">📷</div>
                <div className="text-sm">等待上传控制图</div>
              </div>
            </div>
          )}

          {/* 图片标识 */}
          {currentImageIndex > 0 && currentImage.url && (
            <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded">
              控制图 {currentImageIndex}
            </div>
          )}
        </div>
      </div>

      {/* 右侧控制图条 */}
      <ControlStrip
        images={imageList}
        activeIndex={currentImageIndex}
        onPick={setCurrentImageIndex}
        onUpload={(index) => {
          if (onUploadControl && index >= 1 && index <= 3) {
            onUploadControl(index as 1 | 2 | 3);
          }
        }}
        controlType="multi_control_image"
      />
    </div>
  );

  // 底部区域
  const footer = (
    <div className="p-4">
      <div className="text-sm font-medium text-gray-700 mb-2 truncate">
        {filename}
        {currentImageIndex > 0 && (
          <span className="ml-2 text-xs text-gray-500">
            (控制图 {currentImageIndex})
          </span>
        )}
      </div>
      <Textarea
        value={text}
        onValueChange={setText}
        placeholder="添加标签..."
        minRows={2}
        maxRows={4}
        variant="bordered"
        size="sm"
        className="w-full"
        {...bindTextareaHandlers}
      />
    </div>
  );

  return (
    <CardShell
      selected={selected}
      labeling={labeling}
      onSelectChange={onSelectChange}
      onDelete={onDelete}
      actions={actions}
      children={{ media, footer }}
    />
  );
}