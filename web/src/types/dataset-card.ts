// 基础类型定义
export interface ControlImage {
  url?: string;
  filename?: string;
}

// 基础 props（所有类型共享）
type BaseCardProps = {
  url: string;
  filename: string;
  caption: string;
  selected?: boolean;
  labeling?: boolean;
  onSelect?: (selected: boolean) => void;
  onDelete?: () => void;
  onCaptionSave?: (caption: string) => void | Promise<void>;
  autosaveDelay?: number;
};

// 图像卡片 props
export type ImageCardProps = BaseCardProps & {
  mediaType: 'image';
  onAutoLabel?: () => void;
};

// 视频卡片 props
export type VideoCardProps = BaseCardProps & {
  mediaType: 'video';
};

// 单图控制卡片 props
export type SingleControlCardProps = BaseCardProps & {
  mediaType: 'single_control_image';
  controlImages: Array<ControlImage>; // 长度 ≤ 1
  onUploadControl?: (slotIndex: 1) => void;
  onDeleteControl?: (slotIndex: 1) => void;
};

// 多图控制卡片 props
export type MultiControlCardProps = BaseCardProps & {
  mediaType: 'multi_control_image';
  controlImages: Array<ControlImage>; // 长度 ≤ 3
  onUploadControl?: (slotIndex: 1 | 2 | 3) => void;
  onDeleteControl?: (slotIndex: 1 | 2 | 3) => void;
};

// 可辨识联合类型
export type DatasetCardProps = ImageCardProps | VideoCardProps | SingleControlCardProps | MultiControlCardProps;

// MediaDisplay 需要的 props
export interface MediaDisplayProps {
  mediaType: 'image' | 'video' | 'single_control_image' | 'multi_control_image';
  url: string;
  filename: string;
  controlImages?: Array<ControlImage>;
  onUploadControl?: (slotIndex: 1 | 2 | 3) => void;
  onDeleteControl?: (slotIndex: 1 | 2 | 3) => void;
  // 选中相关
  selected?: boolean;
  labeling?: boolean;
  onSelect?: (selected: boolean) => void;
}

// CardFrame 需要的 props
export interface CardFrameProps {
  selected?: boolean;
  labeling?: boolean;
  onSelectChange?: (selected: boolean) => void;
  actions?: React.ReactNode;
  children: React.ReactNode;
}

// CaptionEditor 需要的 props
export interface CaptionEditorProps {
  filename: string;
  value: string;
  onChange: (value: string) => void;
  bindKeys: {
    onKeyDown: (e: React.KeyboardEvent) => void;
  };
}

// 类型守护函数
export function isImageCard(props: DatasetCardProps): props is ImageCardProps {
  return props.mediaType === 'image';
}

export function isVideoCard(props: DatasetCardProps): props is VideoCardProps {
  return props.mediaType === 'video';
}

export function isSingleControlCard(props: DatasetCardProps): props is SingleControlCardProps {
  return props.mediaType === 'single_control_image';
}

export function isMultiControlCard(props: DatasetCardProps): props is MultiControlCardProps {
  return props.mediaType === 'multi_control_image';
}

export function isControlCard(props: DatasetCardProps): props is SingleControlCardProps | MultiControlCardProps {
  return props.mediaType === 'single_control_image' || props.mediaType === 'multi_control_image';
}