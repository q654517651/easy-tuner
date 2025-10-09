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
  return (
    <div
      className="flex items-center justify-between p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 transition-colors cursor-pointer"
      onClick={() => onTagClick(tagStat.tag)}
    >
      <div className="flex items-center justify-between gap-2 flex-1 min-w-0">
        <span className="text-sm font-medium text-gray-900 dark:text-white truncate flex-1">
          {tagStat.tag}
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">
          {tagStat.count}
        </span>
      </div>
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
          <div className="px-4 pb-4">
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
    </div>
  );
}