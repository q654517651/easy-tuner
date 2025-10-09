import React from "react";
import {
  Modal as HModal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
} from "@heroui/react";
import AppButton from "./Button";

export interface AppModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl" | "5xl" | "full";
  hideCloseButton?: boolean;
  isDismissable?: boolean;
  className?: string;
}

/**
 * 统一模态框封装（基于 HeroUI Modal）：
 * - 支持自定义标题、内容、底部按钮
 * - 提供便捷的确认/取消按钮配置
 */
export const AppModal: React.FC<AppModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = "md",
  hideCloseButton = false,
  isDismissable = true,
  className,
}) => {
  return (
    <HModal
      isOpen={isOpen}
      onClose={onClose}
      size={size}
      hideCloseButton={hideCloseButton}
      isDismissable={isDismissable}
      className={className}
    >
      <ModalContent>
        {title && <ModalHeader className="text-lg font-semibold">{title}</ModalHeader>}
        <ModalBody>{children}</ModalBody>
        {footer && <ModalFooter>{footer}</ModalFooter>}
      </ModalContent>
    </HModal>
  );
};

/**
 * 确认对话框（带确认/取消按钮）
 */
export interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  children: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: "primary" | "success" | "danger" | "default";
  isLoading?: boolean;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  children,
  confirmText = "确认",
  cancelText = "取消",
  confirmColor = "primary",
  isLoading = false,
}) => {
  return (
    <AppModal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      footer={
        <div className="flex gap-2">
          <AppButton kind="outlined" color="default" onClick={onClose} disabled={isLoading}>
            {cancelText}
          </AppButton>
          <AppButton color={confirmColor} onClick={onConfirm} disabled={isLoading}>
            {isLoading ? "处理中..." : confirmText}
          </AppButton>
        </div>
      }
    >
      {children}
    </AppModal>
  );
};

export default AppModal;