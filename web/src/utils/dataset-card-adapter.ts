// 适配器：将现有的 MediaItem 转换为新的 DatasetCardProps
import type { DatasetCardProps } from '../types/dataset-card';

interface MediaItem {
  id: string;
  filename: string;
  url: string;
  caption: string;
  control_images?: {
    url: string;
    filename: string;
  }[];
}

interface Dataset {
  type: string;
}

// 判断文件类型
const IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"];
const VIDEO_EXTS = [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm", ".m4v"];

function isImageFile(filename: string): boolean {
  const lower = filename.toLowerCase();
  return IMAGE_EXTS.some(ext => lower.endsWith(ext));
}

function isVideoFile(filename: string): boolean {
  const lower = filename.toLowerCase();
  return VIDEO_EXTS.some(ext => lower.endsWith(ext));
}

export function convertToDatasetCardProps(
  item: MediaItem,
  dataset: Dataset | null,
  selectedItems: Set<string>,
  labelingItems: Set<string>,
  handlers: {
    handleSelect: (id: string, selected: boolean) => void;
    handleDelete: (id: string) => void;
    handleAutoLabel: (id: string) => void;
    handleSave: (id: string, caption: string) => void;
    handleUploadControl: (filename: string, index: number) => void;
    handleDeleteControl: (filename: string, index: number) => void;
  }
): DatasetCardProps {
  const {
    handleSelect,
    handleDelete,
    handleAutoLabel,
    handleSave,
    handleUploadControl,
    handleDeleteControl
  } = handlers;

  const baseProps = {
    url: item.url,
    filename: item.filename,
    caption: item.caption,
    selected: selectedItems.has(item.id),
    labeling: labelingItems.has(item.id),
    onSelect: (selected: boolean) => handleSelect(item.id, selected),
    onDelete: () => handleDelete(item.id),
    onCaptionSave: (caption: string) => handleSave(item.id, caption),
    autosaveDelay: 1500
  };

  // 根据数据集类型和文件类型决定卡片类型
  if (dataset?.type === 'single_control_image') {
    return {
      ...baseProps,
      mediaType: 'single_control_image' as const,
      controlImages: item.control_images || [],
      onUploadControl: (index: 1) => handleUploadControl(item.filename, index - 1),
      onDeleteControl: (index: 1) => handleDeleteControl(item.filename, index - 1)
    };
  } else if (dataset?.type === 'multi_control_image') {
    return {
      ...baseProps,
      mediaType: 'multi_control_image' as const,
      controlImages: item.control_images || [],
      onUploadControl: (index: 1 | 2 | 3) => handleUploadControl(item.filename, index - 1),
      onDeleteControl: (index: 1 | 2 | 3) => handleDeleteControl(item.filename, index - 1)
    };
  } else if (dataset?.type === 'video' || isVideoFile(item.filename)) {
    return {
      ...baseProps,
      mediaType: 'video' as const
    };
  } else {
    return {
      ...baseProps,
      mediaType: 'image' as const,
      onAutoLabel: () => handleAutoLabel(item.id)
    };
  }
}