import { useState, useRef } from "react";
import { Link } from "react-router-dom";
import { addToast, Button, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem, Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Input, useDisclosure } from "@heroui/react";
import { AppButton } from "./primitives/Button";
import DatasetImageIcon from "../assets/icon/dataset_image_icon.svg?react";
import DatasetVideoIcon from "../assets/icon/dataset_video_icon.svg?react";
import DatasetControlImageIcon from "../assets/icon/dataset_control_image_icon.svg?react";
import MoreIcon from "@/assets/icon/more.svg?react";

export interface DatasetRowProps {
  id: string;
  name: string;
  type: string;
  total_count: number;
  labeled_count: number;
  onRename: (id: string, newName: string) => void;
  onDelete: (id: string) => void;
}

export default function DatasetRow(props: DatasetRowProps) {
  const { id, name, type, total_count, labeled_count, onRename, onDelete } = props;

  const getTypeName = (type: string) => {
    switch (type) {
      case "image":
        return "图片";
      case "video":
        return "视频";
      case "single_control_image":
        return "单图控制";
      case "multi_control_image":
        return "多图控制";
      default:
        return type;
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "image":
        return <DatasetImageIcon className="w-7 h-7" />;
      case "video":
        return <DatasetVideoIcon className="w-7 h-7" />;
      case "single_control_image":
      case "multi_control_image":
        return <DatasetControlImageIcon className="w-7 h-7" />;
      default:
        return <DatasetImageIcon className="w-7 h-7" />;
    }
  };

  const getIconBgClass = (type: string) => {
    switch (type) {
      case "image":
        return "bg-yellow-500/15"; // 黄色背景
      case "video":
        return "bg-blue-500/15"; // 蓝色背景
      case "single_control_image":
      case "multi_control_image":
        return "bg-green-500/15"; // 绿色背景
      default:
        return "bg-yellow-500/15";
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
      setNewName(name);
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
      ref={rowRef}
      to={`/datasets/${id}`}
      className="relative flex items-center gap-3 p-5 rounded-2xl hover:bg-neutral-100 dark:hover:bg-white/15 transition-colors"
      style={{ backgroundColor: 'var(--bg2)' }}
    >
      <div className={`w-12 h-12 rounded-xl ${getIconBgClass(type)} grid place-items-center shrink-0`}>
        {getTypeIcon(type)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold truncate">{name}</div>
        <div className="text-xs opacity-60 mt-1">
          数据集类型：{getTypeName(type)}　　数据数量：{total_count}　　已标注：{labeled_count}
        </div>
      </div>

      {/* 更多按钮 */}
      <div
        className="absolute top-2 right-2"
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
            <AppButton
              isIconOnly
              kind="filled"
              size="sm"
              color="default"
              className="w-8 h-8 min-w-0 bg-transparent"
              onPress={(e) => {
                e?.stopPropagation?.();
              }}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
            >
              <span className="flex items-center justify-center w-6 h-6 [&>svg]:w-6 [&>svg]:h-6 [&_path]:fill-current text-gray-700 dark:text-gray-300">
                <MoreIcon />
              </span>
            </AppButton>
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