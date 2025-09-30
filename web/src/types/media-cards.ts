// 基础媒体卡片接口
export interface BaseMediaCard {
  url: string;
  filename: string;
  caption: string;
  selected?: boolean;
  labeling?: boolean;
  onSelectChange?: (selected: boolean) => void;
  onDelete?: () => void;
  onCaptionSave?: (caption: string) => Promise<void> | void;
  autosaveDelay?: number;
}

// 控制图信息
export interface ControlImage {
  url?: string;
  filename?: string;
}

// 图像数据集卡片
export interface ImageCardProps extends BaseMediaCard {
  type: 'image';
  onAutoLabel?: () => Promise<void> | void;
}

// 视频数据集卡片
export interface VideoCardProps extends BaseMediaCard {
  type: 'video';
  // 视频特有的props可以在这里添加
}

// 控制图数据集卡片
export interface ControlCardProps extends BaseMediaCard {
  type: 'image_control';
  controls: [ControlImage, ControlImage, ControlImage]; // 固定3个控制图位置
  onUploadControl?: (slotIndex: 1 | 2 | 3) => void; // 控制图索引 1-3
}

// 联合类型，用于类型安全的组件选择
export type AnyCardProps = ImageCardProps | VideoCardProps | ControlCardProps;

// 媒体类型枚举
export enum MediaType {
  IMAGE = 'image',
  VIDEO = 'video',
  IMAGE_CONTROL = 'image_control'
}

// 工厂函数类型守护
export function isImageCard(props: AnyCardProps): props is ImageCardProps {
  return props.type === 'image';
}

export function isVideoCard(props: AnyCardProps): props is VideoCardProps {
  return props.type === 'video';
}

export function isControlCard(props: AnyCardProps): props is ControlCardProps {
  return props.type === 'image_control';
}