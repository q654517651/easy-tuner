import { useState } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, Input, addToast } from '@heroui/react';
import { readinessApi } from '../services/api';
import { useReadiness } from '../contexts/ReadinessContext';

interface WorkspaceSelectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function WorkspaceSelectModal({ isOpen, onClose, onSuccess }: WorkspaceSelectModalProps) {
  const [selectedPath, setSelectedPath] = useState('');
  const [selecting, setSelecting] = useState(false);
  const [applying, setApplying] = useState(false);
  const { setWorkspaceReady } = useReadiness();

  const pickWorkspace = async () => {
    try {
      setSelecting(true);
      const res = await window.electron?.selectWorkspace?.();
      if (!res || res.canceled || !res.path) return;
      setSelectedPath(res.path);
    } catch (e) {
      console.error(e);
    } finally {
      setSelecting(false);
    }
  };

  const applyWorkspace = async () => {
    if (!selectedPath) return;
    try {
      setApplying(true);
      await readinessApi.selectWorkspace(selectedPath);
      addToast({ title: '工作区设置成功', color: 'success', timeout: 1500 });
      setWorkspaceReady(true);
      setSelectedPath('');
      onClose();
      onSuccess?.();
    } catch (e) {
      addToast({ title: '设置失败', description: String(e), color: 'danger' });
    } finally {
      setApplying(false);
    }
  };

  const handleClose = () => {
    if (!applying) {
      setSelectedPath('');
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      placement="center"
      isDismissable={!applying}
    >
      <ModalContent>
        <ModalHeader>选择工作区</ModalHeader>
        <ModalBody>
          <p>创建数据集前需要先指定工作区目录，用于存放数据集与日志。</p>
          <div className="flex items-center gap-2 mt-4">
            <Input
              readOnly
              value={selectedPath}
              placeholder="未选择"
              className="flex-1"
            />
            <Button
              onPress={pickWorkspace}
              isLoading={selecting}
              variant="bordered"
            >
              浏览…
            </Button>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button
            variant="light"
            onPress={handleClose}
            isDisabled={applying}
          >
            取消
          </Button>
          <Button
            color="primary"
            isDisabled={!selectedPath || applying}
            isLoading={applying}
            onPress={applyWorkspace}
          >
            确定
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
