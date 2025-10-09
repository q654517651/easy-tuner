import React, { useCallback } from 'react';
import { CardFrame } from './CardFrame';
import { MediaDisplay } from './MediaDisplay';
import { CaptionEditor } from './CaptionEditor';
import { useAutosaveText } from '../../hooks/useAutosaveText';
import type { DatasetCardProps, MediaDisplayProps } from '../../types/dataset-card';
import { isImageCard, isControlCard } from '../../types/dataset-card';

// props 转接层：提取 MediaDisplay 需要的最小集合
function pickMediaProps(props: DatasetCardProps, onSelect?: (selected: boolean) => void): MediaDisplayProps {
  const baseProps: MediaDisplayProps = {
    mediaType: props.mediaType,
    url: props.url,
    filename: props.filename,
    selected: props.selected,
    labeling: props.labeling,
    onSelect: onSelect
  };

  if (isControlCard(props)) {
    return {
      ...baseProps,
      controlImages: props.controlImages,
      onUploadControl: props.onUploadControl,
      onDeleteControl: props.onDeleteControl
    };
  }

  return baseProps;
}

// props 转接层：根据类型生成操作按钮
function pickActionsByType(props: DatasetCardProps): React.ReactNode {
  const deleteButton = props.onDelete && (
    <button
      key="delete"
      aria-label="删除"
      onClick={(e) => {
        e.stopPropagation();
        props.onDelete?.();
      }}
      className="w-9 h-9 rounded-lg bg-black/40 text-white/90 backdrop-blur grid place-items-center hover:bg-black/50 cursor-pointer"
      title="删除"
    >
      🗑️
    </button>
  );

  if (isImageCard(props) && props.onAutoLabel) {
    return (
      <>
        <button
          key="auto-label"
          aria-label="打标"
          onClick={(e) => {
            e.stopPropagation();
            props.onAutoLabel?.();
          }}
          className="w-9 h-9 rounded-lg bg-black/40 text-white/90 backdrop-blur grid place-items-center hover:bg-black/50 cursor-pointer"
          title="打标"
        >
          🏷️
        </button>
        {deleteButton}
      </>
    );
  }

  return deleteButton;
}

export function DatasetCard(props: DatasetCardProps) {
  const {
    caption,
    selected,
    labeling,
    onSelect,
    onCaptionSave,
    filename,
    autosaveDelay = 1800
  } = props;

  // 使用 useAutosaveText hook 处理自动保存逻辑
  const { text, setText, bindTextareaHandlers } = useAutosaveText({
    initial: caption,
    autosaveDelay,
    onSave: onCaptionSave || (() => {})
  });

  // 优化 callbacks
  const handleSelectChange = useCallback((selected: boolean) => {
    onSelect?.(selected);
  }, [onSelect]);

  return (
    <CardFrame
      selected={selected}
      labeling={labeling}
      onSelectChange={handleSelectChange}
      actions={pickActionsByType(props)}
    >
      {/* 上半部分：媒体展示区域 */}
      <MediaDisplay {...pickMediaProps(props, handleSelectChange)} />

      {/* 下半部分：标注编辑区域 */}
      <CaptionEditor
        filename={filename}
        value={text}
        onChange={setText}
        bindKeys={bindTextareaHandlers}
      />
    </CardFrame>
  );
}