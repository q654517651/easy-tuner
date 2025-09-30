import React from 'react';
import { Button, Textarea } from '@heroui/react';
import { CardShell } from './CardShell';
import { useAutosaveText } from '../hooks/useAutosaveText';
import { useHoverVideo } from '../hooks/useHoverVideo';
import type { VideoCardProps } from '../types/media-cards';

export function VideoCard({
  url,
  filename,
  caption,
  selected,
  labeling,
  onSelectChange,
  onDelete,
  onCaptionSave,
  autosaveDelay = 1800
}: VideoCardProps) {
  const { text, setText, bindTextareaHandlers } = useAutosaveText({
    initial: caption,
    autosaveDelay,
    onSave: onCaptionSave || (() => {})
  });

  const { videoRef, isHovering, hoverBind } = useHoverVideo();

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

  // 媒体区域
  const media = (
    <div
      className="relative w-full h-52 sm:h-60 md:h-64 overflow-hidden cursor-pointer"
      {...hoverBind}
    >
      <video
        ref={videoRef}
        src={url}
        className="w-full h-full object-cover"
        muted
        loop
        preload="metadata"
      />

      {/* 播放状态指示器 */}
      <div className="absolute inset-0 flex items-center justify-center">
        {!isHovering && (
          <div className="bg-black/50 rounded-full p-3">
            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        )}
      </div>

      {/* 视频标识 */}
      <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded">
        VIDEO
      </div>
    </div>
  );

  // 底部区域
  const footer = (
    <div className="p-4">
      <div className="text-sm font-medium text-gray-700 mb-2 truncate">
        {filename}
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