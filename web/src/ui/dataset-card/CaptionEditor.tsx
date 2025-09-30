import React from 'react';
import { Textarea } from '@heroui/react';
import type { CaptionEditorProps } from '../../types/dataset-card';

export function CaptionEditor({
  filename,
  value,
  onChange,
  bindKeys
}: CaptionEditorProps) {
  return (
    <div className="p-4">
      {/* 文件名标题 */}
      <div className="text-sm font-bold text-black dark:text-white mb-2 truncate" title={filename}>
        {filename}
      </div>

      {/* 标签输入框 */}
      <Textarea
        value={value}
        onValueChange={onChange}
        placeholder="添加标签..."
        variant="flat"
        size="sm"
        className="w-full shadow-none"
        classNames={{
          input: "min-h-[80px] max-h-[80px] resize-none",
          base: "shadow-none",
          inputWrapper: "shadow-none bg-black/[0.04] dark:bg-white/[0.04] data-[hover=true]:bg-black/[0.06] dark:data-[hover=true]:bg-white/[0.06] group-data-[focus=true]:bg-black/[0.04] dark:group-data-[focus=true]:bg-white/[0.04]"
        }}
        {...bindKeys}
      />
    </div>
  );
}