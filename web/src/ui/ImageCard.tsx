import React from 'react';
import { Button, Textarea } from '@heroui/react';
import { CardShell } from './CardShell';
import { useAutosaveText } from '../hooks/useAutosaveText';
import type { ImageCardProps } from '../types/media-cards';

export function ImageCard({
  url,
  filename,
  caption,
  selected,
  labeling,
  onSelectChange,
  onDelete,
  onCaptionSave,
  onAutoLabel,
  autosaveDelay = 1800
}: ImageCardProps) {
  const { text, setText, bindTextareaHandlers } = useAutosaveText({
    initial: caption,
    autosaveDelay,
    onSave: onCaptionSave || (() => {})
  });

  // 操作按钮
  const actions = (
    <>
      {onAutoLabel && (
        <Button
          size="sm"
          color="primary"
          variant="flat"
          onPress={onAutoLabel}
          isLoading={labeling}
          className="bg-white/80 backdrop-blur-sm"
        >
          AI标注
        </Button>
      )}
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
    <div className="relative w-full h-52 sm:h-60 md:h-64 overflow-hidden">
      <img
        src={url}
        alt={filename}
        className="w-full h-full object-cover"
        loading="lazy"
      />
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