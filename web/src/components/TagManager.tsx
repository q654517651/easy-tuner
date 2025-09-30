import { useState, useEffect, useMemo } from "react";
import { addToast } from "@heroui/react";
import ImageThumbnailList from "../ui/ImageThumbnailList";
import ImageTagEditor from "../ui/ImageTagEditor";
import DatasetTagStats from "../ui/DatasetTagStats";
import { datasetApi } from "../services/api";

interface MediaItem {
  id: string;
  filename: string;
  url: string;
  caption: string;
}

interface TagStat {
  tag: string;
  count: number;
  images: string[];
}

interface TagManagerProps {
  datasetId: string;
  mediaItems: MediaItem[];
  onTagsUpdated?: () => void; // 标签更新后的回调，用于刷新父组件数据
}

export default function TagManager({ datasetId, mediaItems, onTagsUpdated }: TagManagerProps) {
  const [selectedImageId, setSelectedImageId] = useState<string>("");
  const [tagStats, setTagStats] = useState<TagStat[]>([]);
  const [loadingTagStats, setLoadingTagStats] = useState(false);
  const [items, setItems] = useState<MediaItem[]>(mediaItems);

  // 获取当前选中的图片
  const selectedImage = useMemo(() => {
    return items.find(item => item.id === selectedImageId) || null;
  }, [items, selectedImageId]);

  // 获取所有标签列表（用于自动补全）
  const allTags = useMemo(() => {
    const tagSet = new Set<string>();
    items.forEach(item => {
      if (item.caption) {
        const tags = item.caption.split(/[,，]/).map(tag => tag.trim()).filter(tag => tag);
        tags.forEach(tag => tagSet.add(tag));
      }
    });
    return Array.from(tagSet).sort();
  }, [items]);

  // 更新媒体项目列表
  useEffect(() => {
    setItems(mediaItems);
  }, [mediaItems]);

  // 获取标签统计
  const fetchTagStats = async () => {
    if (!datasetId) return;

    try {
      setLoadingTagStats(true);
      const stats = await datasetApi.getDatasetTagStats(datasetId);
      setTagStats(stats);
    } catch (error) {
      console.error('获取标签统计失败:', error);
      addToast({
        title: "获取标签统计失败",
        description: "无法加载数据集标签统计信息",
        color: "danger",
        timeout: 3000,
      });
    } finally {
      setLoadingTagStats(false);
    }
  };

  // 初始化获取标签统计
  useEffect(() => {
    fetchTagStats();
  }, [datasetId]);

  // 处理图片选择
  const handleImageSelect = (imageId: string) => {
    setSelectedImageId(imageId);
  };

  // 处理标签编辑
  const handleTagsChange = async (imageId: string, newTags: string) => {
    const image = items.find(item => item.id === imageId);
    if (!image) return;

    try {
      // 更新后端标注
      await datasetApi.updateMediaCaption(datasetId, image.filename, newTags);

      // 更新前端状态
      setItems(prev => prev.map(item =>
        item.id === imageId ? { ...item, caption: newTags } : item
      ));

      // 重新获取标签统计
      fetchTagStats();

      // 通知父组件数据已更新
      onTagsUpdated?.();

      // 静默：成功日志
    } catch (error) {
      console.error('更新标签失败:', error);
      addToast({
        title: "保存失败",
        description: `无法保存图片 ${image.filename} 的标签`,
        color: "danger",
        timeout: 3000,
      });
    }
  };

  // 处理标签统计点击（显示包含该标签的图片）
  const handleTagClick = (tag: string) => {
    // 找到包含该标签的第一张图片并选中
    const imageWithTag = items.find(item => {
      if (!item.caption) return false;
      const tags = item.caption.split(/[,，]/).map(t => t.trim());
      return tags.includes(tag);
    });

    if (imageWithTag) {
      setSelectedImageId(imageWithTag.id);
      addToast({
        title: "标签筛选",
        description: `已定位到包含标签"${tag}"的图片`,
        color: "success",
        timeout: 2000,
      });
    }
  };

  // 处理将标签添加到当前图片
  const handleAddToCurrentImage = async (tag: string) => {
    if (!selectedImage) return;

    // 检查是否已经包含该标签
    const currentTags = selectedImage.caption
      ? selectedImage.caption.split(/[,，]/).map(t => t.trim()).filter(t => t)
      : [];

    if (currentTags.includes(tag)) {
      addToast({
        title: "标签已存在",
        description: `图片已包含标签"${tag}"`,
        color: "warning",
        timeout: 2000,
      });
      return;
    }

    // 添加新标签
    const newTags = [...currentTags, tag].join(', ');
    await handleTagsChange(selectedImage.id, newTags);

    addToast({
      title: "标签添加成功",
      description: `已将标签"${tag}"添加到当前图片`,
      color: "success",
      timeout: 2000,
    });
  };

  return (
    <div className="flex h-full min-h-0 px-4 pt-1 pb-4">
      <div className="flex w-full h-full rounded-2xl ring-1 ring-black/5 dark:ring-white/10 overflow-hidden">
        {/* 左侧：图片列表 - 20% */}
        <div className="w-[20%] min-h-0">
          <ImageThumbnailList
            images={items}
            selectedImageId={selectedImageId}
            onImageSelect={handleImageSelect}
          />
        </div>

        {/* 分割线 1 */}
        <div className="w-px bg-black/5 dark:bg-white/10"></div>

        {/* 中间：标签编辑器 - 50% */}
        <div className="w-[50%] min-h-0">
          <ImageTagEditor
            image={selectedImage}
            onTagsChange={handleTagsChange}
            allTags={allTags}
          />
        </div>

        {/* 分割线 2 */}
        <div className="w-px bg-black/5 dark:bg-white/10"></div>

        {/* 右侧：标签统计 - 30% */}
        <div className="w-[30%] min-h-0">
          <DatasetTagStats
            tagStats={tagStats}
            onTagClick={handleTagClick}
            onAddToCurrentImage={handleAddToCurrentImage}
            selectedImageId={selectedImageId}
            isLoading={loadingTagStats}
          />
        </div>
      </div>
    </div>
  );
}
