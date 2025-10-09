import { useState } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, addToast } from '@heroui/react';
import { postJson } from '../services/api';
import InstallationProgressModal from './InstallationProgressModal';

interface RuntimeInstallModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function RuntimeInstallModal({ isOpen, onClose, onSuccess }: RuntimeInstallModalProps) {
  const [starting, setStarting] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  const [installationId, setInstallationId] = useState<string>('');

  const doInstallRuntime = async () => {
    try {
      setStarting(true);

      // 获取当前语言设置
      const locale = navigator.language || 'en-US';

      // 调用后端 API 启动安装任务
      const result = await postJson<any>('/installation/start', { locale });

      if (result.success && result.data?.installation_id) {
        const id = result.data.installation_id;
        setInstallationId(id);

        // 关闭当前 Modal，打开进度 Modal
        onClose();
        setShowProgress(true);
      } else {
        throw new Error(result.message || '启动安装失败');
      }
    } catch (e) {
      addToast({
        title: '启动安装失败',
        description: e instanceof Error ? e.message : String(e),
        color: 'danger',
        timeout: 5000
      });
    } finally {
      setStarting(false);
    }
  };

  const handleSkip = () => {
    addToast({ title: '已跳过训练环境安装', color: 'warning', timeout: 2000 });
    onClose();
  };

  const handleProgressClose = () => {
    setShowProgress(false);
    setInstallationId('');
  };

  const handleProgressSuccess = () => {
    setShowProgress(false);
    setInstallationId('');
    onSuccess?.();
  };

  const handleRetryInstallation = () => {
    // 重试：关闭进度弹窗，重新启动安装
    setShowProgress(false);
    setInstallationId('');
    // 自动重新启动安装
    doInstallRuntime();
  };

  return (
    <>
      <Modal
        isOpen={isOpen && !showProgress}
        onClose={() => !starting && onClose()}
        placement="center"
        isDismissable={!starting}
      >
        <ModalContent>
          <ModalHeader>安装/修复训练环境</ModalHeader>
          <ModalBody>
            <p>缺少嵌入式 Python 环境，安装后才能开始训练。你也可以跳过，稍后在设置页面安装。</p>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="light"
              onPress={handleSkip}
              isDisabled={starting}
            >
              跳过
            </Button>
            <Button
              color="primary"
              isLoading={starting}
              onPress={doInstallRuntime}
            >
              安装
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* 安装进度 Modal */}
      {showProgress && installationId && (
        <InstallationProgressModal
          isOpen={showProgress}
          onClose={handleProgressClose}
          installationId={installationId}
          onSuccess={handleProgressSuccess}
          onRetry={handleRetryInstallation}
        />
      )}
    </>
  );
}
