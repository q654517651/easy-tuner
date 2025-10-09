import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Tabs, Tab, CircularProgress, addToast, Skeleton, Input } from "@heroui/react";
import HeaderBar from "../ui/HeaderBar";
import { DatasetCard } from "../ui/dataset-card";
import { CropCard } from "../ui/dataset-card/CropCard";
import { AppButton } from "../ui/primitives/Button";
import { convertToDatasetCardProps } from "../utils/dataset-card-adapter";
import TagManager from "../components/TagManager";
import { datasetApi, labelingApi, joinApiUrl, API_BASE_URL } from "../services/api";
import EmptyState from "../ui/EmptyState";
import EmptyImg from "../assets/img/EmptyDataset.png?inline";
import { PageLayout } from "../layouts/PageLayout";

interface MediaItem {
  id: string;
  filename: string;
  url: string;
  caption: string;
  control_images?: {
    url: string;
    filename: string;
  }[];
}

interface Dataset {
  id: string;
  name: string;
  type: string;
  description: string;
  total_count: number;
  labeled_count: number;
  media_items: MediaItem[];
}


export default function DatasetDetail() {
  const { id } = useParams();

  const [selectedTab, setSelectedTab] = useState("labeling");
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [dragDepth, setDragDepth] = useState(0);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [batchLabeling, setBatchLabeling] = useState(false);
  const [labelingItems, setLabelingItems] = useState<Set<string>>(new Set());
  const [labelingProgress, setLabelingProgress] = useState(0);

  // 裁剪相关状态
  const [cropWidth, setCropWidth] = useState(1024);
  const [cropHeight, setCropHeight] = useState(1024);
  const [cropping, setCropping] = useState(false);

  // 当ID变化时立即重置状态（同步操作，确保骨架屏立即显示）
  useEffect(() => {
    setLoading(true);
    setDataset(null);
    setItems([]);
    setError(null);
    setSelectedItems(new Set());
  }, [id]);

  // 获取数据集详情
  useEffect(() => {
    const fetchDataset = async () => {
      if (!id) return;

      try {
        const data = await datasetApi.getDataset(id);
        if (data) {
          setDataset(data);
          // 转换媒体文件格式
          const mediaItems = (data.media_items ?? []).map((item: any) => ({
            id: item.id,
            filename: item.filename,
            url: joinApiUrl(item.url),
            caption: item.caption ?? "",
            control_images: (item.control_images ?? []).map((ctrl: any) => ({
              ...ctrl,
              url: joinApiUrl(ctrl.url)
            }))
          }));
          setItems(mediaItems);
        }
        setError(null);
      } catch (err) {
        console.error('获取数据集详情失败:', err);
        setError('获取数据集详情失败');
      } finally {
        setLoading(false);
      }
    };

    fetchDataset();
  }, [id]);

  const handleDelete = async (rid: string) => {
    const item = items.find(x => x.id === rid);
    if (!item || !id) return;

    try {
      // 调用后端删除API
      await datasetApi.deleteMediaFile(id, item.filename);

      // 从前端列表中移除
      setItems((prev) => prev.filter((x) => x.id !== rid));

      // 更新数据集统计
      if (dataset) {
        setDataset({
          ...dataset,
          total_count: dataset.total_count - 1,
          labeled_count: item.caption ? dataset.labeled_count - 1 : dataset.labeled_count
        });
      }

      // 静默：成功删除日志
    } catch (error) {
      console.error('删除文件失败:', error);
      addToast({
        title: "删除失败",
        description: `无法删除文件 ${item.filename}`,
        color: "danger",
        timeout: 3000,
      });
    }
  };

  const handleSave = async (rid: string, next: string) => {
    const item = items.find(x => x.id === rid);
    if (!item || !id) return;

    try {
      // 调用后端更新标注API
      await datasetApi.updateMediaCaption(id, item.filename, next);

      // 更新前端显示
      setItems((prev) => prev.map((x) => (x.id === rid ? { ...x, caption: next } : x)));

      // 更新数据集统计（如果从无标签变为有标签）
      if (dataset && !item.caption && next.trim()) {
        setDataset({
          ...dataset,
          labeled_count: dataset.labeled_count + 1
        });
      } else if (dataset && item.caption && !next.trim()) {
        // 如果从有标签变为无标签
        setDataset({
          ...dataset,
          labeled_count: dataset.labeled_count - 1
        });
      }

      // 静默：成功标注日志
    } catch (error) {
      console.error('更新标注失败:', error);
      addToast({
        title: "保存失败",
        description: `无法保存标注内容`,
        color: "danger",
        timeout: 3000,
      });
    }
  };

  const handleAutoLabel = async (rid: string) => {
    const item = items.find(x => x.id === rid);
    if (!item || !id) return;

    // 开始打标 - 设置labeling状态
    setLabelingItems(prev => new Set([...prev, rid]));

    try {
      const result = await labelingApi.labelSingle(id, item.filename);
      // 从响应数据中提取caption
      const caption = result.data?.caption || result.caption || "";

      // 更新items中的caption
      setItems((prev) => prev.map((x) => (x.id === rid ? { ...x, caption } : x)));

      // 更新labeled_count
      if (dataset && !item.caption && caption.trim()) {
        setDataset({ ...dataset, labeled_count: dataset.labeled_count + 1 });
      }

      // 显示成功提示
      addToast({
        title: "打标完成",
        description: `已为 ${item.filename} 生成标注`,
        color: "success",
        timeout: 3000,
      });
    } catch (error) {
      console.error('单张打标失败:', error);
      addToast({
        title: "打标失败",
        description: `无法为 ${item.filename} 生成标注`,
        color: "danger",
        timeout: 3000,
      });
    } finally {
      // 完成打标 - 清除labeling状态
      setLabelingItems(prev => {
        const newSet = new Set(prev);
        newSet.delete(rid);
        return newSet;
      });
    }
  };

  // 处理选中状态
  const handleSelect = (itemId: string, selected: boolean) => {
    // 批量打标进行中时禁用选择
    if (batchLabeling) return;

    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(itemId);
      } else {
        newSet.delete(itemId);
      }
      return newSet;
    });
  };

  // 处理控制图上传
  const handleUploadControl = async (originalFilename: string, controlIndex: number) => {
    if (!id) return;

    // 创建文件选择器
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = false;

    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;

      try {
        // 构建FormData
        const formData = new FormData();
        formData.append('original_filename', originalFilename);
        formData.append('control_index', controlIndex.toString());
        formData.append('control_file', file);

        // 调用上传API
        const response = await fetch(`${API_BASE_URL}/datasets/${id}/control-images`, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          let errorMessage = `HTTP ${response.status}`;
          try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorMessage;
          } catch {
            // JSON解析失败时使用默认消息
          }
          throw new Error(errorMessage);
        }

        const result = await response.json();

        // 上传成功，重新获取数据集详情以刷新数据
        const updatedDataset = await datasetApi.getDataset(id);
        if (updatedDataset) {
          setDataset(updatedDataset);
          // 更新媒体文件列表
          const mediaItems = updatedDataset.media_items.map(item => ({
            id: item.id,
            filename: item.filename,
            url: joinApiUrl(item.url),
            caption: item.caption || "",
            control_images: item.control_images
          }));
          setItems(mediaItems);
        }

        addToast({
          title: "上传成功",
          description: `成功上传控制图 ${result.data.control_filename}`,
          color: "success",
          timeout: 3000
        });

      } catch (error: any) {
        console.error('上传控制图失败:', error);
        addToast({
          title: "上传失败",
          description: error?.message || "上传控制图时发生错误",
          color: "danger",
          timeout: 3000
        });
      }
    };

    // 触发文件选择器
    input.click();
  };

  // 批量打标逻辑
  const handleBatchLabeling = async () => {
    if (selectedItems.size === 0 || batchLabeling) return;

    setBatchLabeling(true);
    setLabelingItems(new Set(selectedItems));
    setLabelingProgress(0);

    const selectedItemsList = Array.from(selectedItems);
    let completedCount = 0;
    let successCount = 0;

    try {
      for (const itemId of selectedItemsList) {
        const item = items.find(x => x.id === itemId);
        if (!item) {
          completedCount++;
          setLabelingProgress((completedCount / selectedItemsList.length) * 100);
          continue;
        }

        try {
          // 调用单张打标API
          const result = await labelingApi.labelSingle(id!, item.filename);
          const caption = result.caption || "";

          // 更新item的标签
          setItems(prev => prev.map(x =>
            x.id === itemId ? { ...x, caption } : x
          ));

          // 更新数据集统计
          if (dataset && !item.caption && caption.trim()) {
            setDataset(prev => prev ? { ...prev, labeled_count: prev.labeled_count + 1 } : null);
          }

          // 从正在打标的集合中移除
          setLabelingItems(prev => {
            const newSet = new Set(prev);
            newSet.delete(itemId);
            return newSet;
          });

          successCount++;
          completedCount++;
          setLabelingProgress((completedCount / selectedItemsList.length) * 100);

        } catch (error) {
          console.error(`打标失败 ${item.filename}:`, error);

          // 即使失败也要从正在打标的集合中移除
          setLabelingItems(prev => {
            const newSet = new Set(prev);
            newSet.delete(itemId);
            return newSet;
          });

          completedCount++;
          setLabelingProgress((completedCount / selectedItemsList.length) * 100);
        }
      }
    } finally {
      // 批量打标完成，清理状态
      setBatchLabeling(false);
      setLabelingItems(new Set());
      setSelectedItems(new Set());
      setLabelingProgress(0);

      // 显示完成通知，根据成功数量判断结果
      const totalCount = selectedItemsList.length;
      const failedCount = totalCount - successCount;

      if (successCount === 0) {
        // 全部失败
        addToast({
          title: "打标失败",
          description: `全部 ${totalCount} 张图片打标失败`,
          color: "danger",
          timeout: 3000,
        });
      } else if (failedCount === 0) {
        // 全部成功
        addToast({
          title: "打标完成",
          description: `成功打标 ${successCount} 张图片`,
          color: "success",
          timeout: 3000,
        });
      } else {
        // 部分成功
        addToast({
          title: "打标完成",
          description: `成功 ${successCount} 张，失败 ${failedCount} 张`,
          color: "warning",
          timeout: 3000,
        });
      }
    }
  };

  // 检测是否为文件拖拽
  const isFileDrag = (e: React.DragEvent) => {
    // 优先检查 dataTransfer.items
    if (e.dataTransfer.items) {
      return Array.from(e.dataTransfer.items).some(item => item.kind === 'file');
    }
    // 降级检查 dataTransfer.types
    return e.dataTransfer.types.includes('Files');
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    // 只处理文件拖拽，忽略内部标签拖拽
    if (!isFileDrag(e)) return;

    e.preventDefault();
    setDragDepth(0);
    setDragging(false);

    const fileList = Array.from(e.dataTransfer.files);
    if (fileList.length === 0 || !id) return;

    try {
      // 上传文件到后端
      const result = await datasetApi.uploadMediaFiles(id, fileList);

      // 静默：上传结果日志

      // 上传成功后重新获取数据集详情
      if (result.success_count > 0) {
        const updatedDataset = await datasetApi.getDataset(id);
        if (updatedDataset) {
          setDataset(updatedDataset);
          // 更新媒体文件列表
          const mediaItems = updatedDataset.media_items.map(item => ({
            id: item.id,
            filename: item.filename,
            url: joinApiUrl(item.url),
            caption: item.caption || "",
            control_images: item.control_images
          }));
          setItems(mediaItems);
        }
      }

      // 显示上传结果
      if (result.success_count > 0) {
        addToast({
          title: "上传成功",
          description: `成功上传 ${result.success_count} 个文件`,
          color: "success",
          timeout: 3000,
        });
      }

      if (result.errors.length > 0) {
        console.warn('部分文件上传失败:', result.errors);
        addToast({
          title: "部分上传失败",
          description: `${result.errors.length} 个文件上传失败`,
          color: "warning",
          timeout: 5000,
        });
      }

    } catch (error) {
      console.error('文件上传失败:', error);
      addToast({
        title: "上传失败",
        description: "文件上传过程中发生错误",
        color: "danger",
        timeout: 3000,
      });
    }
  };

  return (
    <div
      className="flex flex-col h-full relative"
      onDragEnter={(e) => {
        // 只处理文件拖拽，忽略内部标签拖拽
        if (!isFileDrag(e)) return;

        e.preventDefault();
        setDragDepth((d) => {
          const nd = d + 1;
          if (nd === 1) setDragging(true);
          return nd;
        });
      }}
      onDragOver={(e) => {
        // 只处理文件拖拽，忽略内部标签拖拽
        if (!isFileDrag(e)) return;

        e.preventDefault();
      }}
      onDragLeave={(e) => {
        // 只处理文件拖拽，忽略内部标签拖拽
        if (!isFileDrag(e)) return;

        e.preventDefault();
        setDragDepth((d) => {
          const nd = Math.max(0, d - 1);
          if (nd === 0) setDragging(false);
          return nd;
        });
      }}
      onDrop={handleDrop}
    >
      <HeaderBar
        crumbs={[
          { label: "数据集", path: "/datasets" },
          { label: loading ? "加载中..." : (dataset?.name || `数据集 ${id}`) },
        ]}
      />

      <div className="h-[72px] shrink-0 bg-white/40 dark:bg-black/10 backdrop-blur px-4 flex items-center justify-between">
        <Tabs
          selectedKey={selectedTab}
          onSelectionChange={(key) => setSelectedTab(key as string)}
          variant="solid"
        >
          <Tab key="labeling" title="打标" />
          <Tab key="editing" title="标签管理" />
          <Tab key="cropping" title="图片裁剪" />
        </Tabs>

        {selectedTab === "labeling" && dataset?.type === "image" && (
          <div className="flex items-center gap-2">
            {items.length > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg2)] rounded-lg border border-black/10 dark:border-white/10">
                <span className="text-sm text-foreground">已选择 {selectedItems.size} 项</span>
                <button
                  onClick={() => setSelectedItems(new Set(items.map(item => item.id)))}
                  className="text-xs text-primary hover:text-primary-600 dark:hover:text-primary-400"
                  disabled={batchLabeling}
                >
                  全选
                </button>
                <button
                  onClick={() => setSelectedItems(new Set())}
                  className="text-xs text-primary hover:text-primary-600 dark:hover:text-primary-400"
                  disabled={batchLabeling}
                >
                  清除
                </button>
              </div>
            )}
            <AppButton
              kind="outlined"
              size="sm"
              onPress={() => {
                // TODO: 打标设置逻辑
                // 静默：调试日志
              }}
            >
              打标设置
            </AppButton>
            <AppButton
              kind="filled"
              size="sm"
              color="primary"
              isDisabled={selectedItems.size === 0 || batchLabeling}
              isLoading={batchLabeling}
              onPress={handleBatchLabeling}
              startIcon={
                batchLabeling ? (
                  <CircularProgress
                    size="sm"
                    value={labelingProgress}
                    color="default"
                    aria-label={`打标进度 ${Math.round(labelingProgress)}%`}
                    classNames={{
                      svg: "w-4 h-4",
                      indicator: "stroke-white",
                      track: "stroke-white/30",
                    }}
                  />
                ) : null
              }
            >
              {batchLabeling ? '正在打标...' : '批量打标'}
            </AppButton>
          </div>
        )}

        {selectedTab === "cropping" && dataset?.type === "image" && (
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm text-default-600">目标尺寸：</span>
              <Input
                type="number"
                value={String(cropWidth)}
                onChange={(e) => setCropWidth(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-24"
                size="sm"
                placeholder="宽度"
                min={1}
              />
              <span className="text-sm text-default-400">×</span>
              <Input
                type="number"
                value={String(cropHeight)}
                onChange={(e) => setCropHeight(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-24"
                size="sm"
                placeholder="高度"
                min={1}
              />
            </div>
            <AppButton
              kind="filled"
              color="primary"
              size="sm"
              isDisabled={cropping}
              isLoading={cropping}
              onPress={() => {
                // TODO: 批量裁剪逻辑
                addToast({
                  title: "裁剪功能开发中",
                  description: "后端接口待完善",
                  color: "warning",
                  timeout: 2000,
                });
              }}
            >
              {cropping ? '正在裁剪...' : '确认裁剪'}
            </AppButton>
          </div>
        )}
      </div>


      {/* 主内容区域 */}
      <div className="flex-1 min-h-0 relative">
        {/* 骨架屏层 - 绝对定位覆盖 */}
        {loading && (
          <div className="absolute inset-0 px-6 py-6 space-y-5">
            {/* Tab内容区域的骨架屏 */}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-5">
              {Array.from({ length: 12 }).map((_, index) => (
                <div key={index} className="bg-content1 rounded-xl ring-1 ring-black/5 dark:ring-white/10 overflow-hidden">
                  {/* 图片骨架 */}
                  <div className="w-full h-48 bg-default-100 animate-pulse" />
                  {/* 内容骨架 */}
                  <div className="p-4 space-y-3">
                    <div className="h-4 w-3/4 bg-default-100 rounded-lg animate-pulse" />
                    <div className="h-16 w-full bg-default-100 rounded-lg animate-pulse" />
                    <div className="flex gap-2">
                      <div className="h-8 w-20 bg-default-100 rounded-lg animate-pulse" />
                      <div className="h-8 w-20 bg-default-100 rounded-lg animate-pulse" />
                      <div className="h-8 w-8 bg-default-100 rounded-lg animate-pulse" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 错误状态 */}
        {error && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-red-500">{error}</div>
          </div>
        )}

        {/* 实际内容层 */}
        <div className={`h-full transition-opacity duration-300 ease-out ${loading ? 'opacity-0' : 'opacity-100'}`}>
          {!loading && !error && (
            items.length === 0 ? (
              <div className="flex-1 flex items-center justify-center h-full">
                <EmptyState image={EmptyImg} message="这个数据集还没有图片，拖拽或上传一些吧" />
              </div>
            ) : (
              <div className="h-full">
                {/* 标签管理页面 - 使用 display 控制显示/隐藏，避免重新挂载 */}
                <div className={`h-full ${selectedTab === "editing" ? "block" : "hidden"}`}>
                  <TagManager
                    datasetId={id!}
                    mediaItems={items}
                    onTagsUpdated={() => {
                      // 标签更新后重新获取数据集信息，刷新统计数据
                      const fetchDataset = async () => {
                        try {
                          const data = await datasetApi.getDataset(id!);
                          if (data) {
                            setDataset(data);
                            const mediaItems = data.media_items.map(item => ({
                              id: item.id,
                              filename: item.filename,
                              url: joinApiUrl(item.url),
                              caption: item.caption || "",
                              control_images: item.control_images
                            }));
                            setItems(mediaItems);
                          }
                        } catch (err) {
                          console.error('刷新数据集失败:', err);
                        }
                      };
                      fetchDataset();
                    }}
                  />
                </div>

                {/* 打标页面 - 使用 display 控制显示/隐藏 */}
                <div className={`h-full ${selectedTab === "labeling" ? "block" : "hidden"}`}>
                  <div className="h-full overflow-y-auto">
                    <div className="px-6 py-6">
                      <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-5">
                        {items.map((item) => {
                          const cardProps = convertToDatasetCardProps(
                            item,
                            dataset,
                            selectedItems,
                            labelingItems,
                            {
                              handleSelect,
                              handleDelete,
                              handleAutoLabel,
                              handleSave,
                              handleUploadControl
                            }
                          );
                          return (
                            <DatasetCard
                              key={item.id}
                              {...cardProps}
                            />
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>

                {/* 图片裁剪页面 */}
                <div className={`h-full ${selectedTab === "cropping" ? "block" : "hidden"}`}>
                  <div className="h-full overflow-y-auto">
                    <div className="px-6 py-6">
                      <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-5">
                        {items.map((item) => (
                          <CropCard
                            key={item.id}
                            url={item.url}
                            filename={item.filename}
                            targetWidth={cropWidth}
                            targetHeight={cropHeight}
                            onCropChange={(params) => {
                              console.log(`[${item.filename}] 裁剪参数:`, params);
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {dragging && (
        <div className="absolute inset-0 bg-black/40 backdrop-blur-md flex flex-col items-center justify-center z-50 border-4 border-sky-400 rounded-xl pointer-events-none">
          <div className="text-white text-lg font-medium">将文件拖到这里进行添加</div>
        </div>
      )}
    </div>
  );
}
