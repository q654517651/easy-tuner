import { useState, useEffect } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button } from '@heroui/react';

interface UpdateInfo {
  version: string;
  releaseNotes?: string;
  releaseDate?: string;
}

const GITHUB_RELEASES_URL = 'https://github.com/q654517651/easy-tuner/releases';

export function UpdateNotification() {
  const [isUpdateAvailable, setIsUpdateAvailable] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);

  useEffect(() => {
    // 监听更新事件
    const handleUpdateAvailable = (info: UpdateInfo) => {
      setUpdateInfo(info);
      setIsUpdateAvailable(true);
    };

    // 注册监听器
    if (window.electron?.on) {
      window.electron.on('updater:update-available', handleUpdateAvailable);
    }

    return () => {
      // 清理监听器
      if (window.electron?.removeAllListeners) {
        window.electron.removeAllListeners('updater:update-available');
      }
    };
  }, []);

  const handleOpenReleases = () => {
    // 打开浏览器到 GitHub releases 页面
    if (window.electron?.openExternal) {
      // 桌面版：使用系统默认浏览器
      window.electron.openExternal(GITHUB_RELEASES_URL);
    } else {
      // Web 版本：使用普通打开方式
      window.open(GITHUB_RELEASES_URL, '_blank');
    }
    setIsUpdateAvailable(false);
  };

  const handleClose = () => {
    setIsUpdateAvailable(false);
  };

  // 发现新版本弹窗
  if (isUpdateAvailable) {
    return (
      <Modal 
        isOpen={true} 
        onClose={handleClose}
        isDismissable={true}
      >
        <ModalContent>
          <ModalHeader className="flex flex-col gap-1">
            🎉 发现新版本 v{updateInfo?.version}
          </ModalHeader>
          <ModalBody>
            {updateInfo?.releaseNotes && (
              <div className="mb-4">
                <p className="text-sm font-semibold mb-2">更新内容：</p>
                <div className="text-sm text-default-600 whitespace-pre-wrap max-h-60 overflow-y-auto">
                  {updateInfo.releaseNotes}
                </div>
              </div>
            )}
            
            <p className="text-sm text-default-600">
              点击"前往下载"将在浏览器中打开 GitHub Releases 页面，您可以手动下载最新版本。
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="light" onPress={handleClose}>
              稍后提醒
            </Button>
            <Button color="primary" onPress={handleOpenReleases}>
              前往下载
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  }

  return null;
}

