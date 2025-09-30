import React from 'react';
import { Checkbox, Button } from '@heroui/react';
import { cn } from '../../utils/cn';
import type { CardFrameProps } from '../../types/dataset-card';

// 角落控制组件
interface CornerControlsProps {
  selected?: boolean;
  onSelectChange?: (selected: boolean) => void;
  actions?: React.ReactNode;
}

function CornerControls({ selected, onSelectChange, actions }: CornerControlsProps) {
  return (
    <>
      {/* 左上角选择框 */}
      {onSelectChange && (
        <div
          className="absolute top-2 left-2 z-20"
          onClick={(e) => e.stopPropagation()}
        >
          <Checkbox
            isSelected={selected}
            onValueChange={onSelectChange}
            size="lg"
            classNames={{
              base: "pointer-events-auto",
              wrapper: "before:border-white/50 after:bg-blue-500 after:text-white bg-black/30 backdrop-blur-sm",
            }}
          />
        </div>
      )}

      {/* 右上角操作区 */}
      {actions && (
        <div
          className="absolute top-2 right-2 z-20 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => e.stopPropagation()}
        >
          {actions}
        </div>
      )}
    </>
  );
}

export function CardFrame({
  selected = false,
  labeling = false,
  onSelectChange,
  actions,
  children
}: CardFrameProps) {
  return (
    <div
      className={cn(
        "group relative rounded-2xl bg-[#F4F4F6] dark:bg-white/[0.04] shadow-none transition-all duration-200 overflow-hidden",
        // 选中状态：蓝色边框
        selected ? "ring-2 ring-blue-500" : ""
      )}
    >
      {/* 角落控制 */}
      <CornerControls
        selected={selected}
        onSelectChange={onSelectChange}
        actions={actions}
      />

      {/* 主体内容 */}
      {children}

      {/* 标注中指示器 */}
      {labeling && (
        <div className="absolute inset-0 z-40 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center rounded-2xl">
          <div className="text-white text-sm font-medium mb-2">正在打标中...</div>
          <div className="w-8 h-8 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
        </div>
      )}
    </div>
  );
}