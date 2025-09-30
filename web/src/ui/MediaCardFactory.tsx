import React from 'react';
import { ImageCard } from './ImageCard';
import { VideoCard } from './VideoCard';
import { ControlImageCard } from './ControlImageCard';
import type { AnyCardProps } from '../types/media-cards';

/**
 * 媒体卡片工厂函数
 * 根据卡片类型返回对应的专门组件
 * 使用 TypeScript 的可辨识联合类型确保类型安全
 */
export function MediaCardFactory(props: AnyCardProps) {
  switch (props.type) {
    case 'image':
      return <ImageCard {...props} />;

    case 'video':
      return <VideoCard {...props} />;

    case 'image_control':
      return <ControlImageCard {...props} />;

    default:
      // TypeScript 会确保这里永远不会执行到
      // 如果新增了类型但忘记处理，编译时会报错
      const _exhaustive: never = props;
      throw new Error(`Unknown card type: ${JSON.stringify(_exhaustive)}`);
  }
}

/**
 * 便捷的类型检查工具函数
 * 可以在使用前进行类型判断
 */
export function getCardType(props: AnyCardProps): string {
  return props.type;
}

/**
 * 渲染媒体卡片的便捷函数
 * 用于替换原有的条件渲染逻辑
 */
export function renderMediaCard(props: AnyCardProps) {
  return <MediaCardFactory {...props} />;
}