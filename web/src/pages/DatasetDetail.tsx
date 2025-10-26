import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Tabs, Tab, CircularProgress, addToast, Input } from "@heroui/react";
import HeaderBar from "../ui/HeaderBar";
import { DatasetCard } from "../ui/dataset-card";
import { CropCard } from "../ui/dataset-card/CropCard";
import { AppButton } from "../ui/primitives/Button";
import { AppModal } from "../ui/primitives/Modal";
import { convertToDatasetCardProps } from "../utils/dataset-card-adapter";
import TagManager from "../components/TagManager";
import { datasetApi, labelingApi, imagesApi, joinApiUrl, API_BASE_URL } from "../services/api";
import EmptyState from "../ui/EmptyState";
import EmptyImg from "../assets/img/EmptyDataset.png?inline";

interface MediaItem {
  id: string;
  filename: string;
  file_path: string;
  url: string;
  caption: string;
  control_images?: {
    url: string;
    filename: string;
  }[];
}

// 统一的归一化函数：将后端数据转换为 MediaItem
const toMediaItem = (item: any): MediaItem => ({
  id: item.id ?? crypto.randomUUID(),
  filename: item.filename ?? '',
  file_path: item.file_path ?? item.url ?? '',
  url: joinApiUrl(item.url ?? ''),
  caption: item.caption ?? '',
  control_images: (item.control_images ?? []).map((ctrl: any) => ({
    ...ctrl,
    url: joinApiUrl(ctrl.url ?? ''),
  })),
});

interface Dataset {
  id: string;
  name: string;
  type: string;
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
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [batchLabeling, setBatchLabeling] = useState(false);
  const [labelingItems, setLabelingItems] = useState<Set<string>>(new Set());
  const [labelingProgress, setLabelingProgress] = useState(0);

  // 裁剪相关状态
  const [cropWidth, setCropWidth] = useState(1024);
  const [cropHeight, setCropHeight] = useState(1024);
  // 防抖后的目标尺寸（用于渲染与提交），避免输入过程中频繁刷新
  const [debouncedCrop, setDebouncedCrop] = useState<{ w: number; h: number }>({ w: 1024, h: 1024 });
  useEffect(() => {
    const t = window.setTimeout(() => {
      setDebouncedCrop({ w: Math.max(1, cropWidth), h: Math.max(1, cropHeight) });
    }, 400);
    return () => window.clearTimeout(t);
  }, [cropWidth, cropHeight]);
  const [cropping, setCropping] = useState(false);
  const [showCropConfirm, setShowCropConfirm] = useState(false);
  const [flushCounter, setFlushCounter] = useState(0);
  const [cropTransforms, setCropTransforms] = useState<Record<string, { scale: number; positionX: number; positionY: number }>>({});

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
          const mediaItems = (data.media_items ?? []).map(toMediaItem);
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
      const caption = result.caption ?? "";

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
    } catch (error: any) {
      console.error('单张打标失败:', error);

      // 尝试解析后端返回的详细错误
      let errorMessage = `无法为 ${item.filename} 生成标注`;
      if (error?.message) {
        try {
          // 尝试从 JSON 格式的错误信息中提取 detail
          const errorData = JSON.parse(error.message);
          errorMessage = errorData.detail || errorData.error || error.message;
        } catch {
          // 如果不是 JSON，直接使用 error.message
          errorMessage = error.message;
        }
      }

      addToast({
        title: "打标失败",
        description: errorMessage,
        color: "danger",
        timeout: 5000,  // 延长显示时间，方便查看详细错误
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

  // 执行裁剪：在确认后调用
  const performCrop = async () => {
    if (!items.length) {
      setShowCropConfirm(false);
      return;
    }
    try {
      setShowCropConfirm(false);
      setCropping(true);

      // 1) 先强制子组件flush一次transform
      setFlushCounter((x) => x + 1);
      await new Promise((resolve) => setTimeout(resolve, 100));

      // 2) 组装images，确保每项都带有source_path（file_path缺失则从URL回退解析）
      const getSourcePathFromUrl = (u: string) => {
        try {
          const urlObj = new URL(u);
          const pathname = decodeURIComponent(urlObj.pathname || '');
          const marker = '/workspace/';
          const idx = pathname.indexOf(marker);
          if (idx >= 0) return pathname.substring(idx + marker.length).replace(/^\/+/, '');
          return pathname.replace(/^\/+/, '');
        } catch {
          // 相对路径兜底
          return String(u || '').replace(/^https?:\/\/[^/]+\//, '').replace(/^\/+/, '');
        }
      };

      const images = items.map((it) => {
        const t: any = cropTransforms[it.id] || {};
        const src = it.file_path && it.file_path.length > 0 ? it.file_path : getSourcePathFromUrl(it.url);
        const hasPx = t.pixelRect && typeof t.pixelRect.x === 'number';
        return hasPx ? (
          {
            id: it.id,
            source_path: src,
            transform: null,
            source_rect: {
              x: Math.max(0, Math.round(t.pixelRect.x)),
              y: Math.max(0, Math.round(t.pixelRect.y)),
              width: Math.max(1, Math.round(t.pixelRect.width)),
              height: Math.max(1, Math.round(t.pixelRect.height)),
            }
          }
        ) : (
          {
            id: it.id,
            source_path: src,
            transform: t ? { scale: t.scale, offset_x: t.positionX, offset_y: t.positionY } : null,
          }
        ) as any;
      });

      // 3) 请求裁剪
      const resp = await imagesApi.cropBatch({
        target_width: debouncedCrop.w,
        target_height: debouncedCrop.h,
        images,
      });

      let ok = 0, ko = 0;
      const itemsRes = (resp as any)?.data?.items || [];
      ok = itemsRes.filter((x: any) => x.success).length;
      ko = itemsRes.length - ok;
      addToast({
        title: ko === 0 ? '裁剪完成' : '部分失败',
        description: `成功 ${ok} 张，失败 ${ko} 张`,
        color: ko === 0 ? 'success' : 'warning',
        timeout: 3000,
      });

      // 4) 刷新数据集并强制刷新图片显示
      if (id) {
        try {
          const data = await datasetApi.getDataset(id);
          if (data) {
            setDataset(data as any);
            const v = Date.now();
            const mediaItems = (data.media_items ?? []).map((item: any) => ({
              ...toMediaItem(item),
              url: `${joinApiUrl(item.url)}?v=${v}`,
              control_images: (item.control_images ?? []).map((ctrl: any) => ({
                ...ctrl,
                url: `${joinApiUrl(ctrl.url)}?v=${v}`,
              }))
            }));
            setItems(mediaItems);
          }
        } catch (e) {
          console.error('刷新裁剪后数据集失败:', e);
        }
      }
    } catch (e: any) {
      console.error('裁剪失败:', e);
      addToast({
        title: '裁剪失败',
        description: e?.message || String(e),
        color: 'danger',
      });
    } finally {
      setCropping(false);
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
          setItems(updatedDataset.media_items.map(toMediaItem));
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

  // 处理控制图删除
  const handleDeleteControl = async (originalFilename: string, controlIndex: number) => {
    if (!id) return;

    try {
      // 调用删除API
      await imagesApi.deleteControlImage(id, originalFilename, controlIndex);

      // 删除成功，重新获取数据集详情以刷新数据
      const updatedDataset = await datasetApi.getDataset(id);
      if (updatedDataset) {
        setDataset(updatedDataset);
        // 更新媒体文件列表
        setItems(updatedDataset.media_items.map(toMediaItem));
      }

      addToast({
        title: "删除成功",
        description: "控制图已删除",
        color: "success",
        timeout: 2000
      });

    } catch (error: any) {
      console.error('删除控制图失败:', error);
      addToast({
        title: "删除失败",
        description: error?.message || "删除控制图时发生错误",
        color: "danger",
        timeout: 3000
      });
    }
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
    const dt = e.dataTransfer as DataTransfer;
    const types = Array.from(dt.types || []);
    
    // 🔧 修复：不区分大小写检查（兼容 Electron 和浏览器）
    // Electron 返回 'Files'（大写），浏览器返回 'files'（小写）
    const hasFilesType = types.some(type => 
      type.toLowerCase() === 'files'
    );
    
    // 只检查类型，不检查 files.length（在 dragOver/dragEnter 时为空，受浏览器安全限制）
    return hasFilesType;
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    // 只处理文件拖拽，忽略内部标签拖拽
    if (!isFileDrag(e)) return;

    e.preventDefault();
    setDragging(false);

    const fileList = Array.from(e.dataTransfer.files);
    if (fileList.length === 0 || !id) return;

    try {
      const isControlDataset = dataset?.type === 'single_control_image' || dataset?.type === 'multi_control_image';

      if (isControlDataset) {
        // 控制图数据集：智能分类文件
        const normalFiles: File[] = [];
        const controlFiles: { file: File; basename: string; index: number }[] = [];

        for (const file of fileList) {
          // 匹配控制图命名模式：basename_数字.扩展名
          const match = file.name.match(/^(.+?)_(\d+)\.(jpg|jpeg|png|webp|bmp)$/i);

          if (match) {
            // 是控制图格式
            const basename = match[1];
            const index = parseInt(match[2]);
            controlFiles.push({ file, basename, index });
          } else {
            // 普通图片
            normalFiles.push(file);
          }
        }

        let totalSuccess = 0;
        let totalFailed = 0;
        const errors: string[] = [];

        // 1. 上传普通图片
        if (normalFiles.length > 0) {
          const result = await datasetApi.uploadMediaFiles(id, normalFiles);
          totalSuccess += result.success_count;
          totalFailed += result.failed_count;
          errors.push(...result.errors);
        }

        // 2. 上传控制图
        if (controlFiles.length > 0) {
          // 需要先刷新数据集以获取最新的图片列表
          const updatedDataset = await datasetApi.getDataset(id);
          const currentItems = updatedDataset?.media_items || [];

          for (const { file, basename, index } of controlFiles) {
            try {
              // 查找对应的原图（支持不同扩展名）
              const originalItem = currentItems.find(item => {
                const itemBasename = item.filename.replace(/\.(jpg|jpeg|png|webp|bmp)$/i, '');
                return itemBasename === basename;
              });

              if (!originalItem) {
                errors.push(`控制图 ${file.name} 没有找到对应的原图 ${basename}.*`);
                totalFailed++;
                continue;
              }

              // 构建FormData上传控制图
              const formData = new FormData();
              formData.append('original_filename', originalItem.filename);
              formData.append('control_index', index.toString());
              formData.append('control_file', file);

              const response = await fetch(`${API_BASE_URL}/datasets/${id}/control-images`, {
                method: 'POST',
                body: formData
              });

              if (response.ok) {
                totalSuccess++;
              } else {
                const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
                errors.push(`控制图 ${file.name} 上传失败: ${errorData.detail}`);
                totalFailed++;
              }

            } catch (error: any) {
              errors.push(`控制图 ${file.name} 上传失败: ${error.message}`);
              totalFailed++;
            }
          }
        }

        // 刷新数据集
        const updatedDataset = await datasetApi.getDataset(id);
        if (updatedDataset) {
          setDataset(updatedDataset);
          setItems(updatedDataset.media_items.map(toMediaItem));
        }

        // 显示上传结果
        if (totalSuccess > 0 && totalFailed === 0) {
          // 全部成功
          addToast({
            title: "上传成功",
            description: `成功上传 ${totalSuccess} 个文件${controlFiles.length > 0 ? '（含控制图）' : ''}`,
            color: "success",
            timeout: 3000,
          });
        } else if (totalSuccess > 0 && totalFailed > 0) {
          // 部分成功
          const missingOriginalCount = errors.filter(e => e.includes('没有找到对应的原图')).length;
          const otherErrorCount = totalFailed - missingOriginalCount;
          
          let description = `成功 ${totalSuccess} 个，失败 ${totalFailed} 个`;
          if (missingOriginalCount > 0) {
            description += `\n其中 ${missingOriginalCount} 个控制图找不到对应的原图`;
          }
          if (otherErrorCount > 0) {
            description += `\n其他错误 ${otherErrorCount} 个`;
          }
          
          addToast({
            title: "部分文件上传失败",
            description: description,
            color: "warning",
            timeout: 6000,
          });
        } else if (totalFailed > 0) {
          // 全部失败
          const missingOriginalCount = errors.filter(e => e.includes('没有找到对应的原图')).length;
          
          if (missingOriginalCount === totalFailed) {
            // 全部是因为找不到原图
            addToast({
              title: "上传失败",
              description: `${totalFailed} 个控制图找不到对应的原图\n请先上传原图，或将原图与控制图一起拖入`,
              color: "danger",
              timeout: 6000,
            });
          } else if (missingOriginalCount > 0) {
            // 部分是找不到原图
            addToast({
              title: "上传失败",
              description: `${totalFailed} 个文件上传失败\n其中 ${missingOriginalCount} 个控制图找不到对应的原图`,
              color: "danger",
              timeout: 6000,
            });
          } else {
            // 其他原因
            addToast({
              title: "上传失败",
              description: `${totalFailed} 个文件上传失败\n${errors[0] || '请查看控制台了解详情'}`,
              color: "danger",
              timeout: 6000,
            });
          }
        }

      } else {
        // 非控制图数据集：所有文件都作为普通图片上传
        const result = await datasetApi.uploadMediaFiles(id, fileList);

        // 上传成功后重新获取数据集详情
        if (result.success_count > 0) {
          const updatedDataset = await datasetApi.getDataset(id);
          if (updatedDataset) {
            setDataset(updatedDataset);
            setItems(updatedDataset.media_items.map(toMediaItem));
          }
        }

        // 显示上传结果
        if (result.success_count > 0 && result.failed_count === 0) {
          // 全部成功
          addToast({
            title: "上传成功",
            description: `成功上传 ${result.success_count} 个文件`,
            color: "success",
            timeout: 3000,
          });
        } else if (result.success_count > 0 && result.failed_count > 0) {
          // 部分成功
          console.warn('部分文件上传失败:', result.errors);
          addToast({
            title: "部分文件上传成功",
            description: `成功 ${result.success_count} 个，失败 ${result.failed_count} 个\n${result.errors[0] || '查看控制台了解详情'}`,
            color: "warning",
            timeout: 5000,
          });
        } else if (result.failed_count > 0) {
          // 全部失败
          console.error('所有文件上传失败:', result.errors);
          addToast({
            title: "上传失败",
            description: `${result.failed_count} 个文件全部上传失败\n${result.errors[0] || '请查看控制台了解详情'}`,
            color: "danger",
            timeout: 5000,
          });
        }
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
        setDragging(true);
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
        setDragging(false);
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
          {dataset?.type === "image" && <Tab key="cropping" title="图片裁剪" />}
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
              onPress={() => setShowCropConfirm(true)}
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
                            setItems(data.media_items.map(toMediaItem));
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
                              handleUploadControl,
                              handleDeleteControl
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
                            targetWidth={debouncedCrop.w}
                            targetHeight={debouncedCrop.h}
                            autosaveDelay={300}
                            flushSignal={flushCounter}
                            onCropChange={(params) => {
                              const anyParams = params as any;
                              setCropTransforms(prev => ({
                                ...prev,
                                [item.id]: {
                                  scale: params.zoom,
                                  positionX: anyParams.positionX ?? 0,
                                  positionY: anyParams.positionY ?? 0,
                                  pixelRect: anyParams.pixelRect ?? null,
                                  imageSize: anyParams.imageSize ?? null,
                                }
                              }));
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

      {/* 二次确认弹窗：覆盖原图不可撤销 */}
      <AppModal
        isOpen={showCropConfirm}
        onClose={() => setShowCropConfirm(false)}
        title="确认裁剪"
        footer={
          <div className="flex gap-2">
            <AppButton kind="outlined" onPress={() => setShowCropConfirm(false)}>取消</AppButton>
            <AppButton kind="filled" color="primary" onPress={performCrop}>确认覆盖</AppButton>
          </div>
        }
      >
        <div className="space-y-2 text-sm">
          <div>本操作将按当前视图覆盖原图，且不可撤销。</div>
          <div>将处理 {items.length} 张图片，目标尺寸：{debouncedCrop.w}×{debouncedCrop.h}。</div>
          <div>建议确认视图已停止操作（已稳定），以确保裁剪使用最新定位。</div>
        </div>
      </AppModal>
    </div>
  );
}

// 确认裁剪弹窗与执行逻辑（追加在组件内部末尾附近）
