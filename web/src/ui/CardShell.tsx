import React from 'react';
import { Checkbox } from '@heroui/react';

interface CardShellProps {
  selected?: boolean;
  labeling?: boolean;
  onSelectChange?: (selected: boolean) => void;
  onDelete?: () => void;
  actions?: React.ReactNode;
  children: {
    media: React.ReactNode;
    footer: React.ReactNode;
  };
  className?: string;
}

export function CardShell({
  selected = false,
  labeling = false,
  onSelectChange,
  onDelete,
  actions,
  children,
  className = ''
}: CardShellProps) {
  return (
    <div className={`
      relative bg-white rounded-2xl shadow-lg transition-all duration-200 overflow-hidden
      ${selected ? 'ring-2 ring-blue-500 shadow-xl scale-[1.02]' : 'hover:shadow-xl hover:scale-[1.01]'}
      ${labeling ? 'ring-2 ring-orange-500' : ''}
      ${className}
    `}>
      {/* 选择checkbox */}
      {onSelectChange && (
        <div className="absolute top-3 left-3 z-20">
          <div className="bg-white/80 backdrop-blur-sm rounded-lg p-1">
            <Checkbox
              isSelected={selected}
              onValueChange={onSelectChange}
              size="sm"
            />
          </div>
        </div>
      )}

      {/* 操作按钮区域 */}
      {actions && (
        <div className="absolute top-3 right-3 z-20">
          <div className="flex gap-2">
            {actions}
          </div>
        </div>
      )}

      {/* 主体内容 */}
      {children.media}
      {children.footer}

      {/* 标注中蒙层 */}
      {labeling && (
        <div className="absolute inset-0 bg-orange-500/20 rounded-2xl flex items-center justify-center z-30">
          <div className="bg-white px-4 py-2 rounded-lg shadow-lg border border-orange-200">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-orange-600 font-medium">标注中...</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}