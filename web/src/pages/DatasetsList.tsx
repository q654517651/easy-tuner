import { addToast, Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, useDisclosure, Input } from "@heroui/react";
import { Link } from "react-router-dom";
import HeaderBar from "../ui/HeaderBar";
import CreateDatasetDialog from "../ui/CreateDatasetDialog";
import { useEffect, useState, useRef } from "react";
import { datasetApi } from "../services/api";
import EmptyState from "../ui/EmptyState";
import EmptyImg from "../assets/img/EmptyDataset.png?inline";
import DatasetImageIcon from "../assets/icon/dataset_image_icon.svg?react";
import DatasetVideoIcon from "../assets/icon/dataset_video_icon.svg?react";
import DatasetControlImageIcon from "../assets/icon/dataset_control_image_icon.svg?react";
import MoreIcon from "@/assets/icon/more.svg?react";

interface Dataset {
  id: string;
  name: string;
  type: string;
  total_count: number;
  labeled_count: number;
  created_at: string;
  updated_at: string;
}


// 这些函数需要移到组件内部，因为它们需要访问 setDatasets



function Row(
  props: Dataset & {
    onRename: (id: string, currentName: string) => void;
    onDelete: (id: string) => void;
  }
) {
  const { id, name, type, total_count, labeled_count, onRename, onDelete } = props;

  const getTypeName = (type: string) => {
    switch (type) {
      case "image":
        return "图片";
      case "video":
        return "视频";
      case "image_control":
        return "控制图";
      default:
        return type;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "image":
        return <DatasetImageIcon className="w-full h-full" />;
      case "video":
        return <DatasetVideoIcon className="w-full h-full" />;
      case "image_control":
        return <DatasetControlImageIcon className="w-full h-full" />;
      default:
        return <DatasetImageIcon className="w-full h-full" />;
    }
  };

  const [isDeleting, setIsDeleting] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const { isOpen: isDeleteOpen, onOpen: onDeleteOpen, onClose: onDeleteClose } = useDisclosure();
  const { isOpen: isRenameOpen, onOpen: onRenameOpen, onClose: onRenameClose } = useDisclosure();
  const rowRef = useRef<HTMLAnchorElement>(null);

  const handleDropdownAction = (key: React.Key) => {
    if (key === "rename") {
      setNewName(name); // 设置当前名称为默认值
      onRenameOpen();
    } else if (key === "delete") {
      onDeleteOpen();
    }
  };

  const handleRenameSubmit = async () => {
    if (!newName.trim() || newName === name) {
      onRenameClose();
      return;
    }

    try {
      setIsRenaming(true);
      await onRename(id, newName.trim());
      onRenameClose();
      addToast({
        title: "重命名成功",
        description: `数据集已重命名为"${newName.trim()}"`,
        color: "success",
        timeout: 3000
      });
    } catch (error) {
      addToast({
        title: "重命名失败",
        description: `重命名数据集失败: ${error}`,
        color: "danger",
        timeout: 3000
      });
    } finally {
      setIsRenaming(false);
    }
  };

  const handleConfirmDelete = async () => {
    try {
      setIsDeleting(true);
      await onDelete(id);
      onDeleteClose();
      addToast({
        title: "删除成功",
        description: `数据集"${name}"已删除`,
        color: "success",
        timeout: 3000
      });
    } catch (error) {
      addToast({
        title: "删除失败",
        description: `删除数据集失败: ${error}`,
        color: "danger",
        timeout: 3000
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Link
      to={`/datasets/${id}`}
      className="relative flex items-center gap-3 p-6 bg-neutral-100/80 dark:bg-white/10 rounded-2xl hover:bg-neutral-100 dark:hover:bg-white/15 transition-colors"
    >
      <div className="w-12 h-12 rounded-xl bg-white/10 border border-black/5 dark:border-white/10 grid place-items-center">
        {getTypeIcon(type)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{name}</div>
        <div className="text-xs opacity-60 mt-1">
          数据集类型：{getTypeName(type)}　　数据数量：{total_count}　　已标注：{labeled_count}
        </div>
      </div>

      {/* 更多按钮 */}
      <div
        className="absolute top-3 right-3"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onMouseDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
      >
        <Dropdown placement="bottom-end">
          <DropdownTrigger>
            <Button
              isIconOnly
              variant="light"
              size="sm"
              className="w-8 h-8"
              onPress={(e) => {
                e?.stopPropagation?.();
              }}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
            >
              <span className="flex items-center justify-center w-6 h-6 [&>svg]:w-6 [&>svg]:h-6 [&_path]:fill-current text-gray-900 dark:text-gray-100">
                <MoreIcon />
              </span>
            </Button>
          </DropdownTrigger>
          <DropdownMenu
            aria-label="数据集操作"
            onAction={handleDropdownAction}
          >
            <DropdownItem
              key="rename"
              startContent="✏️"
            >
              重命名
            </DropdownItem>
            <DropdownItem
              key="delete"
              className="text-danger"
              color="danger"
              startContent="🗑️"
            >
              删除
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </div>

      {/* 重命名Modal */}
      <Modal isOpen={isRenameOpen} onClose={onRenameClose} placement="center">
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            重命名数据集
          </ModalHeader>
          <ModalBody>
            <p className="text-sm text-gray-600 mb-4">
              为数据集 <strong>"{name}"</strong> 输入新的名称：
            </p>
            <Input
              label="数据集名称"
              placeholder="请输入新的数据集名称"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isRenaming) {
                  handleRenameSubmit();
                }
              }}
              disabled={isRenaming}
              autoFocus
            />
          </ModalBody>
          <ModalFooter>
            <Button
              variant="light"
              onPress={onRenameClose}
              disabled={isRenaming}
            >
              取消
            </Button>
            <Button
              color="primary"
              onPress={handleRenameSubmit}
              disabled={isRenaming || !newName.trim() || newName === name}
              isLoading={isRenaming}
            >
              {isRenaming ? "重命名中..." : "确认重命名"}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* 删除确认Modal */}
      <Modal isOpen={isDeleteOpen} onClose={onDeleteClose} placement="center">
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            确认删除
          </ModalHeader>
          <ModalBody>
            <p>确定要删除数据集 <strong>"{name}"</strong> 吗？</p>
            <p className="text-sm text-gray-500">此操作不可撤销，数据集中的所有图像、标签和相关数据都将被永久删除。</p>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="light"
              onPress={onDeleteClose}
              disabled={isDeleting}
            >
              取消
            </Button>
            <Button
              color="danger"
              onPress={handleConfirmDelete}
              disabled={isDeleting}
              isLoading={isDeleting}
            >
              {isDeleting ? "删除中..." : "确认删除"}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Link>
  );
}


export default function DatasetsList() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  useEffect(() => {
    const fetchDatasets = async () => {
      try {
        setLoading(true);
        const { data } = await datasetApi.listDatasets();
        setDatasets(data);
        setError(null);
      } catch (err) {
        console.error('获取数据集列表失败:', err);
        setError('获取数据集列表失败');
      } finally {
        setLoading(false);
      }
    };

    fetchDatasets();
  }, []);

  const handleCreateDataset = async (data: { name: string; type: string; description: string }) => {
    try {
      const newDataset = await datasetApi.createDataset(data);
      if (newDataset) {
        // 刷新数据集列表
        const { data: updatedDatasets } = await datasetApi.listDatasets();
        setDatasets(updatedDatasets);

        // 显示成功通知
        addToast({
          title: "创建成功",
          description: `数据集"${data.name}"已创建完成`,
          color: "success",
          timeout: 3000
        });
      }
    } catch (error) {
      console.error('创建数据集失败:', error);

      // 显示失败通知
      const errorMessage = error instanceof Error ? error.message : '创建失败';
      addToast({
        title: "创建失败",
        description: errorMessage,
        color: "danger",
        timeout: 3000
      });

      throw error;
    }
  };

  const refreshDatasets = async () => {
    const { data: updated } = await datasetApi.listDatasets();
    setDatasets(updated);
  };

  const handleRename = async (id: string, newName: string) => {
    try {
      await datasetApi.renameDataset(id, { name: newName });
      await refreshDatasets();
    } catch (err) {
      console.error("重命名失败:", err);
      throw err; // 让Row组件的handleRenameSubmit处理错误显示
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await datasetApi.deleteDataset(id);
      await refreshDatasets();
    } catch (err) {
      console.error("删除失败:", err);
      throw err; // 让Row组件的handleConfirmDelete处理错误显示
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar
          crumbs={[
            { label: "数据集" },
          ]}
          actions={
            <Button
              onClick={() => setShowCreateDialog(true)}
              variant="bordered"
              size="sm"
              startContent="✨"
            >
              创建数据集
            </Button>
          }
        />
        <div className="p-6">加载中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <HeaderBar
          crumbs={[
            { label: "数据集" },
          ]}
          actions={
            <Button
              onClick={() => setShowCreateDialog(true)}
              variant="bordered"
              size="sm"
              startContent="✨"
            >
              创建数据集
            </Button>
          }
        />
        <div className="p-6 text-red-500">错误: {error}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <HeaderBar
        crumbs={[
          { label: "数据集" },
        ]}
        actions={
          <Button
            onClick={() => setShowCreateDialog(true)}
            variant="bordered"
            size="sm"
            startContent="✨"
          >
            创建数据集
          </Button>
        }
      />

      <div className="p-6 space-y-4 flex-1 min-h-0">
        {datasets.length === 0 ? (
          <EmptyState image={EmptyImg} message="暂无数据集，先去创建一个吧" />
        ) : (
          datasets.map((dataset) => (
            <Row key={dataset.id} {...dataset} onRename={handleRename} onDelete={handleDelete} />
          ))
        )}
      </div>

      {/* 创建数据集对话框 */}
      <CreateDatasetDialog
        isOpen={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onSubmit={handleCreateDataset}
      />
    </div>
  );
}
