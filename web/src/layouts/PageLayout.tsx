import { ReactNode } from 'react';
import HeaderBar from '../ui/HeaderBar';
import ScrollArea from '../ui/ScrollArea';
import type { ActionDesc } from '../ui/ActionButton';

/**
 * 页面面包屑导航项
 */
export type Crumb = {
  /** 显示的标签 */
  label: string;
  /** 路径（可选），有路径表示可点击 */
  path?: string;
};

export interface PageLayoutProps {
  /** 面包屑导航 */
  crumbs: Crumb[];
  /** 顶部右侧操作按钮 */
  actions?: ReactNode | ActionDesc[];
  /** 页面内容 */
  children: ReactNode;
  /** 是否禁用滚动区域（默认 false） */
  disableScroll?: boolean;
  /** 自定义内容区域类名 */
  contentClassName?: string;
}

/**
 * 通用页面布局组件
 *
 * 提供统一的页面结构：HeaderBar + ScrollArea
 *
 * @example
 * // 基础用法
 * <PageLayout crumbs={[{ label: "数据集" }]}>
 *   <div className="p-6">页面内容</div>
 * </PageLayout>
 *
 * @example
 * // 带操作按钮
 * <PageLayout
 *   crumbs={[{ label: "数据集" }]}
 *   actions={
 *     <Button onClick={handleCreate}>创建</Button>
 *   }
 * >
 *   <div className="p-6">页面内容</div>
 * </PageLayout>
 *
 * @example
 * // 使用动作数组（统一样式）
 * <PageLayout
 *   crumbs={[{ label: "数据集", path: "/datasets" }, { label: "详情" }]}
 *   actions={[
 *     { label: "编辑", icon: "✏️", onClick: handleEdit },
 *     { label: "删除", icon: "🗑️", onClick: handleDelete, danger: true }
 *   ]}
 * >
 *   <div className="p-6">页面内容</div>
 * </PageLayout>
 *
 * @example
 * // 禁用滚动（用于自定义布局）
 * <PageLayout
 *   crumbs={[{ label: "任务详情" }]}
 *   disableScroll
 * >
 *   <div className="flex h-full">
 *     <div className="flex-1">左侧</div>
 *     <div className="flex-1">右侧</div>
 *   </div>
 * </PageLayout>
 */
export function PageLayout({
  crumbs,
  actions,
  children,
  disableScroll = false,
  contentClassName = '',
}: PageLayoutProps) {
  return (
    <div className="flex flex-col h-full min-h-0">
      <HeaderBar crumbs={crumbs} actions={actions} />
      {disableScroll ? (
        <div className={`flex-1 min-h-0 ${contentClassName}`}>
          {children}
        </div>
      ) : (
        <ScrollArea className={`flex-1 min-h-0 ${contentClassName}`}>
          {children}
        </ScrollArea>
      )}
    </div>
  );
}
