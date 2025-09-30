import { useState, useEffect, useRef } from "react";
import ScrollArea from "./ScrollArea";

// 判断文件类型的工具函数
const isVideoFile = (filename: string): boolean => {
  const videoExts = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.webm', '.m4v'];
  const ext = filename.toLowerCase().slice(filename.lastIndexOf('.'));
  return videoExts.includes(ext);
};


interface MediaItem {
  id: string;
  filename: string;
  url: string;
  caption: string;
}

interface ImageTagEditorProps {
  image: MediaItem | null;
  onTagsChange: (imageId: string, tags: string) => Promise<void>;
  allTags?: string[]; // 数据集中所有标签，用于自动补全
}

interface TagChipProps {
  tag: string;
  index: number;
  isEditing: boolean;
  onRemove: () => void;
  onEdit: (newTag: string) => void;
  onEnterEdit: () => void;
  onRequestClose: () => void;
  onDragStart: (index: number) => void;
  onDragOver: (index: number) => void;
  onDrop: (index: number) => void;
  isDragging: boolean;
  isDragOver: boolean;
}

function TagChip({
  tag,
  index,
  isEditing,
  onRemove,
  onEdit,
  onEnterEdit,
  onRequestClose,
  onDragStart,
  onDragOver,
  onDrop,
  isDragging,
  isDragOver,
}: TagChipProps) {
  const [editValue, setEditValue] = useState(tag);
  const inputRef = useRef<HTMLInputElement>(null);

  // tag 变化时同步本地值
  useEffect(() => {
    setEditValue(tag);
  }, [tag]);

  // 进入编辑态后自动聚焦
  useEffect(() => {
    if (isEditing && inputRef.current) {
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    }
  }, [isEditing]);

  const handleSave = () => {
    const next = editValue.trim();
    if (next && next !== tag) onEdit(next);
    onRequestClose();
    setEditValue(tag); // 显示态回到最新 tag
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSave();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onRequestClose();
      setEditValue(tag);
    }
  };

  // —— 编辑态 —— //
  if (isEditing) {
    return (
      <div
        className={`block w-full px-3 py-1.5 rounded-md text-sm leading-5 ring-2 ring-blue-500 bg-transparent text-gray-900 dark:text-white transition-colors ${
          isDragging ? "opacity-50" : ""
        }`}
        draggable={false}
        title="编辑标签，回车保存，Esc 取消"
        onPointerDown={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          className="w-full bg-transparent outline-none text-sm leading-5 font-medium"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          autoFocus
        />
      </div>
    );
  }

  // —— 查看态 —— //
  return (
    <div
      className={`block w-full px-3 py-1.5 rounded-md text-sm leading-5 ring-2 ring-transparent bg-content2 text-gray-700 dark:text-gray-300 group hover:bg-content3 transition-colors cursor-pointer ${
        isDragging ? "opacity-50 scale-95 rotate-3" : ""
      } ${isDragOver ? "ring-blue-400 bg-blue-50 dark:bg-blue-900/20" : ""}`}
      draggable={!isEditing}
      onDragStart={(e) => {
        // 仅处理标签排序，避免触发页面级"文件导入"
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("application/tag-sort", index.toString());
        e.stopPropagation();
        onDragStart(index);
      }}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes("application/tag-sort")) return;
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "move";
        onDragOver(index);
      }}
      onDrop={(e) => {
        if (!e.dataTransfer.types.includes("application/tag-sort")) return;
        e.preventDefault();
        e.stopPropagation();
        onDrop(index);
      }}
      title="点击编辑，拖拽排序"
      onClick={(e) => {
        e.stopPropagation();
        onEnterEdit();
      }}
    >
      <div className="flex items-start gap-1">
        {/* 拖拽图标 */}
        <svg
          className="w-3 h-3 mt-0.5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 16a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" />
        </svg>

        {/* 文本内容 */}
        <span
          className="flex-1 select-none font-medium"
          style={{
            wordBreak: "break-all",
            whiteSpace: "pre-wrap",
            lineHeight: "1.25rem",
          }}
        >
          {tag}
        </span>

        {/* 删除按钮 */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-0.5"
          title="删除标签"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}


export default function ImageTagEditor({image, onTagsChange, allTags = []}: ImageTagEditorProps) {
  const [tags, setTags] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const saveTimerRef = useRef<number | null>(null);

  // 拖拽状态
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // 编辑状态 - 统一管理哪个标签正在编辑
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  // 视频相关状态
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isVideo, setIsVideo] = useState(false);
  const [isHovering, setIsHovering] = useState(false);

  // 当选中的图片改变时，更新标签
  useEffect(() => {
    if (image) {
      const imageTags = image.caption
        ? image.caption.split(/[,，]/).map(tag => tag.trim()).filter(tag => tag)
        : [];
      setTags(imageTags);
      setIsVideo(isVideoFile(image.filename));
    } else {
      setTags([]);
      setIsVideo(false);
    }
    // 重置拖拽状态和编辑状态
    resetDragState();
    setEditingIndex(null);
    setIsHovering(false);
  }, [image]);

  // 视频播放控制
  useEffect(() => {
    if (!isVideo || !videoRef.current) return;

    const video = videoRef.current;

    if (isHovering) {
      // 鼠标悬浮时播放
      video.currentTime = 0; // 重新播放
      video.play().catch(() => {
        // 忽略播放失败
      });
    } else {
      // 鼠标移出时暂停
      video.pause();
    }
  }, [isHovering, isVideo]);

  // 自动保存（防抖）
  const saveTagsDebounced = (newTags: string[]) => {
    if (!image) return;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = window.setTimeout(() => {
      const tagsString = newTags.join(', ');
      onTagsChange(image.id, tagsString);
    }, 1000);
  };

  // 更新标签并触发保存
  const updateTags = (newTags: string[]) => {
    setTags(newTags);
    saveTagsDebounced(newTags);
  };

  // 输入建议过滤
  useEffect(() => {
    if (inputValue.trim() && allTags.length > 0) {
      const filtered = allTags
        .filter(tag =>
          tag.toLowerCase().includes(inputValue.toLowerCase()) &&
          !tags.includes(tag)
        )
        .slice(0, 5);
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
      setSelectedSuggestionIndex(-1);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [inputValue, allTags, tags]);

  // 添加标签
  const addTag = (tag: string) => {
    const trimmedTag = tag.trim();
    if (trimmedTag && !tags.includes(trimmedTag)) {
      updateTags([...tags, trimmedTag]);
    }
    setInputValue("");
    setShowSuggestions(false);
  };

  // 删除标签
  const removeTag = (index: number) => {
    updateTags(tags.filter((_, i) => i !== index));
  };

  // 编辑标签
  const editTag = (index: number, newTag: string) => {
    if (!tags.includes(newTag)) {
      updateTags(tags.map((tag, i) => i === index ? newTag : tag));
    }
  };

  // 拖拽排序相关函数
  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
    setDragOverIndex(null);
  };

  const handleDragOver = (index: number) => {
    if (draggedIndex !== null && draggedIndex !== index) {
      setDragOverIndex(index);
    }
  };

  const handleDrop = (dropIndex: number) => {
    if (draggedIndex !== null && draggedIndex !== dropIndex) {
      const newTags = [...tags];
      const draggedItem = newTags[draggedIndex];

      // 移除被拖拽的项目
      newTags.splice(draggedIndex, 1);

      // 在新位置插入项目
      newTags.splice(dropIndex, 0, draggedItem);

      updateTags(newTags);
    }

    // 重置拖拽状态
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const resetDragState = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  // 键盘事件处理
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedSuggestionIndex >= 0 && suggestions[selectedSuggestionIndex]) {
        addTag(suggestions[selectedSuggestionIndex]);
      } else if (inputValue.trim()) {
        addTag(inputValue);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (suggestions.length > 0) {
        setSelectedSuggestionIndex(prev =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedSuggestionIndex(prev => prev > 0 ? prev - 1 : -1);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setSelectedSuggestionIndex(-1);
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      // 退格删除最后一个标签
      removeTag(tags.length - 1);
    }
  };

  if (!image) {
    return (
      <div className="flex flex-col h-full bg-transparent">
        <div className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400">
          <div className="text-center">
            <svg className="w-12 h-12 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M7 7h.01M7 3h5c1.1 0 2 .9 2 2v1M9 21h6c1.1 0 2-.9 2-2V7.5l-2.5-2.5H9c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2z" />
            </svg>
            <p className="text-sm">请选择一张图片进行标签编辑</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-transparent">
      {/* 媒体预览 - 限制最大高度为40% */}
      <div className="p-4" style={{ maxHeight: '40%' }}>
        <div
          className="w-full h-full bg-content2 rounded-lg overflow-hidden relative cursor-pointer"
          onMouseEnter={() => setIsHovering(true)}
          onMouseLeave={() => setIsHovering(false)}
        >
          {/* 背景模糊图/视频 */}
          {isVideo ? (
            <video
              src={image.url}
              className="absolute inset-0 w-full h-full object-cover scale-110 blur-sm brightness-50"
              muted
              playsInline
            />
          ) : (
            <img
              src={image.url}
              alt=""
              className="absolute inset-0 w-full h-full object-cover scale-110 blur-sm brightness-50"
            />
          )}

          {/* 前景清晰图/视频 */}
          {isVideo ? (
            <video
              ref={videoRef}
              src={image.url}
              className="relative z-10 w-full h-full object-contain"
              muted
              playsInline
              loop
              preload="metadata"
            />
          ) : (
            <img
              src={image.url}
              alt={image.filename}
              className="relative z-10 w-full h-full object-contain"
            />
          )}

          {/* 视频悬浮提示 */}
          {isVideo && !isHovering && (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/20">
              <div className="bg-black/50 rounded-full p-3">
                <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M8 5v10l7-5z" />
                </svg>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 标签编辑区域 */}
      <div className="flex-1 min-h-0 flex flex-col">
        {/* 标题和操作按钮 */}
        <div className="px-4 pb-0">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              当前标签 ({tags.length})
            </label>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {/* TODO: 添加标签逻辑 */}}
                className="text-xs text-blue-500 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                添加标签
              </button>
              <button
                onClick={() => updateTags([])}
                className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                disabled={tags.length === 0}
              >
                清空所有
              </button>
            </div>
          </div>
        </div>

        {/* 标签容器 - 充满剩余空间 */}
        <div className="flex-1 min-h-0 p-4 pt-0">
          <div className="h-full border border-black/5 dark:border-white/10 rounded-lg">
            {tags.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-gray-500 dark:text-gray-400 text-sm">暂无标签</p>
              </div>
            ) : (
              <ScrollArea className="h-full">
                <div className="p-3">
                  <div
                    className="flex flex-wrap gap-2"
                    onPointerDownCapture={() => setEditingIndex(null)}
                    onDragOver={(e) => {
                      // 只处理标签排序拖拽，阻止文件导入
                      if (e.dataTransfer.types.includes('application/tag-sort')) {
                        e.preventDefault();
                        e.stopPropagation();
                      }
                    }}
                    onDrop={(e) => {
                      // 只处理标签排序拖拽，阻止文件导入
                      if (e.dataTransfer.types.includes('application/tag-sort')) {
                        e.preventDefault();
                        e.stopPropagation();
                      }
                    }}
                    onDragLeave={(e) => {
                      // 只有当拖拽离开整个容器时才重置状态
                      if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                        resetDragState();
                      }
                    }}
                  >
                    {tags.map((tag, index) => (
                      <TagChip
                        key={`${tag}-${index}`}
                        tag={tag}
                        index={index}
                        isEditing={editingIndex === index}
                        onRemove={() => removeTag(index)}
                        onEdit={(newTag) => editTag(index, newTag)}
                        onEnterEdit={() => setEditingIndex(index)}
                        onRequestClose={() => setEditingIndex(null)}
                        onDragStart={handleDragStart}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        isDragging={draggedIndex === index}
                        isDragOver={dragOverIndex === index}
                      />
                    ))}
                  </div>
                </div>
              </ScrollArea>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}