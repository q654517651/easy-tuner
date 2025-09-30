import React from "react";

// 分组卡片：仅描边、圆角、padding=24，标题 14 加粗（去除背景）
const GroupCard: React.FC<React.PropsWithChildren<{
  title: string;
  anchorId?: string;
  headerContent?: React.ReactNode;
}>> = ({
  title,
  anchorId,
  headerContent,
  children,
}) => (
  <div id={anchorId} className="rounded-2xl p-6 bg-[#F9F9FA] dark:bg-white/4 overflow-hidden">
    <div className="flex items-center justify-between mb-4">
      <div className="text-[14px] font-semibold">{title}</div>
      {headerContent && <div>{headerContent}</div>}
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
  </div>
);

export default GroupCard;
