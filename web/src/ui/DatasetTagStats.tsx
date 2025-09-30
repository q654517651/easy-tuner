import { useState, useMemo } from "react";
import { Input } from "@heroui/react";
import ScrollArea from "./ScrollArea";

interface TagStat {
  tag: string;
  count: number;
  images: string[]; // 包含此标签的图片ID列表
}

interface DatasetTagStatsProps {
  tagStats: TagStat[];
  onTagClick?: (tag: string) => void;
  onAddToCurrentImage?: (tag: string) => void;
  selectedImageId?: string;
  isLoading?: boolean;
}

interface TagStatItemProps {
  tagStat: TagStat;
  onTagClick: (tag: string) => void;
  onAddToCurrentImage: (tag: string) => void;
  canAddToCurrentImage: boolean;
}

function TagStatItem({ tagStat, onTagClick, onAddToCurrentImage, canAddToCurrentImage }: TagStatItemProps) {
  const [showActions, setShowActions] = useState(false);

  return (
    <div
      className="group flex items-center justify-between p-2 rounded-lg hover:bg-content2 transition-colors"
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      <div
        className="flex-1 cursor-pointer"
        onClick={() => onTagClick(tagStat.tag)}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm font-medium text-gray-900 dark:text-white break-words flex-1">
            {tagStat.tag}
          </span>
          <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
            {tagStat.count}
          </span>
        </div>
      </div>

      {/* 悬浮操作按钮 */}
      {showActions && canAddToCurrentImage && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAddToCurrentImage(tagStat.tag);
          }}
          className="ml-2 p-1 text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 opacity-0 group-hover:opacity-100 transition-opacity"
          title="添加到当前图片"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default function DatasetTagStats({
  tagStats,
  onTagClick = () => {},
  onAddToCurrentImage = () => {},
  selectedImageId,
  isLoading = false
}: DatasetTagStatsProps) {
  const [searchTerm, setSearchTerm] = useState("");

  // 过滤和排序标签 - 默认按使用次数降序
  const filteredAndSortedTags = useMemo(() => {
    let filtered = tagStats.filter(stat => {
      const matchesSearch = stat.tag.toLowerCase().includes(searchTerm.toLowerCase());
      const hasCount = stat.count > 0; // 只显示已使用的标签
      return matchesSearch && hasCount;
    });

    return filtered.sort((a, b) => b.count - a.count); // 按使用次数降序
  }, [tagStats, searchTerm]);

  // 统计信息
  const totalTags = tagStats.length;
  const totalUsedTags = tagStats.filter(stat => stat.count > 0).length;
  const totalOccurrences = tagStats.reduce((sum, stat) => sum + stat.count, 0);

  if (isLoading) {
    return (
      <div className="flex flex-col h-full bg-transparent">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-sm text-gray-500 dark:text-gray-400">加载标签统计中...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* 头部 */}
      <div className="p-4">

        {/* 统计信息 */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="text-center p-2 bg-content1 rounded-lg">
            <div className="text-lg font-semibold text-gray-900 dark:text-white">{totalUsedTags}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">已使用</div>
          </div>
          <div className="text-center p-2 bg-content1 rounded-lg">
            <div className="text-lg font-semibold text-gray-900 dark:text-white">{totalOccurrences}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">总次数</div>
          </div>
          <div className="text-center p-2 bg-content1 rounded-lg">
            <div className="text-lg font-semibold text-gray-900 dark:text-white">
              {totalOccurrences > 0 ? Math.round(totalOccurrences / totalUsedTags * 10) / 10 : 0}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">平均</div>
          </div>
        </div>

        {/* 搜索框 */}
        <Input
          placeholder="搜索标签..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          size="sm"
          startContent={
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          }
          endContent={
            filteredAndSortedTags.length !== totalTags && (
              <span className="text-xs text-gray-500">
                {filteredAndSortedTags.length}/{totalTags}
              </span>
            )
          }
        />

      </div>

      {/* 标签列表 */}
      <div className="flex-1 min-h-0">
        <ScrollArea className="h-full">
          <div className="p-4">
        {filteredAndSortedTags.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
            <svg className="w-12 h-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 7h.01M7 3h5c1.1 0 2 .9 2 2v1M9 21h6c1.1 0 2-.9 2-2V7.5l-2.5-2.5H9c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2z" />
            </svg>
            <p className="text-sm">
              {searchTerm ? "没有找到匹配的标签" : "暂无标签数据"}
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {filteredAndSortedTags.map((tagStat) => (
              <TagStatItem
                key={tagStat.tag}
                tagStat={tagStat}
                onTagClick={onTagClick}
                onAddToCurrentImage={onAddToCurrentImage}
                canAddToCurrentImage={!!selectedImageId}
              />
            ))}
          </div>
        )}
          </div>
        </ScrollArea>
      </div>

      {/* 底部操作提示 */}
      <div className="p-3 bg-content1">
        <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
          <p>💡 点击标签查看包含该标签的图片</p>
          {selectedImageId && <p>➕ 鼠标悬浮可快速添加标签到当前图片</p>}
        </div>
      </div>
    </div>
  );
}