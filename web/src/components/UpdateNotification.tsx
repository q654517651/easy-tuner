import { useState, useEffect } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, Progress } from '@heroui/react';

interface UpdateInfo {
  version: string;
  releaseNotes?: string;
  releaseDate?: string;
}

interface DownloadProgress {
  percent: number;
  bytesPerSecond: number;
  transferred: number;
  total: number;
}

export function UpdateNotification() {
  const [isUpdateAvailable, setIsUpdateAvailable] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const [isReadyToInstall, setIsReadyToInstall] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 监听更新事件
    const handleUpdateAvailable = (info: UpdateInfo) => {
      setUpdateInfo(info);
      setIsUpdateAvailable(true);
    };

    const handleDownloadProgress = (progress: DownloadProgress) => {
      setDownloadProgress(progress);
    };

    const handleUpdateDownloaded = () => {
      setIsDownloading(false);
      setIsReadyToInstall(true);
    };

    const handleError = (err: { message: string }) => {
      setError(err.message);
      setIsDownloading(false);
    };

    // 注册监听器
    if (window.electron?.on) {
      window.electron.on('updater:update-available', handleUpdateAvailable);
      window.electron.on('updater:download-progress', handleDownloadProgress);
      window.electron.on('updater:update-downloaded', handleUpdateDownloaded);
      window.electron.on('updater:error', handleError);
    }

    return () => {
      // 清理监听器
      if (window.electron?.removeAllListeners) {
        window.electron.removeAllListeners('updater:update-available');
        window.electron.removeAllListeners('updater:download-progress');
        window.electron.removeAllListeners('updater:update-downloaded');
        window.electron.removeAllListeners('updater:error');
      }
    };
  }, []);

  const handleDownload = async () => {
    setIsDownloading(true);
    setError(null);
    await window.electron?.updater?.downloadUpdate();
  };

  const handleInstall = () => {
    window.electron?.updater?.quitAndInstall();
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatSpeed = (bytesPerSecond: number) => {
    return formatBytes(bytesPerSecond) + '/s';
  };

  // 发现新版本弹窗
  if (isUpdateAvailable && !isReadyToInstall) {
    return (
      <Modal 
        isOpen={true} 
        onClose={() => setIsUpdateAvailable(false)}
        isDismissable={!isDownloading}
        hideCloseButton={isDownloading}
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
            
            {isDownloading && downloadProgress && (
              <div className="space-y-2">
                <Progress 
                  value={downloadProgress.percent} 
                  className="max-w-full"
                  color="primary"
                  showValueLabel={true}
                />
                <div className="flex justify-between text-xs text-default-500">
                  <span>{formatBytes(downloadProgress.transferred)} / {formatBytes(downloadProgress.total)}</span>
                  <span>{formatSpeed(downloadProgress.bytesPerSecond)}</span>
                </div>
              </div>
            )}

            {error && (
              <div className="text-sm text-danger">
                下载失败：{error}
              </div>
            )}
          </ModalBody>
          <ModalFooter>
            {!isDownloading && (
              <>
                <Button variant="light" onPress={() => setIsUpdateAvailable(false)}>
                  稍后提醒
                </Button>
                <Button color="primary" onPress={handleDownload}>
                  立即下载
                </Button>
              </>
            )}
            {isDownloading && (
              <Button isDisabled color="primary">
                下载中...
              </Button>
            )}
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  }

  // 准备安装弹窗
  if (isReadyToInstall) {
    return (
      <Modal isOpen={true} isDismissable={false} hideCloseButton>
        <ModalContent>
          <ModalHeader>✅ 更新已就绪</ModalHeader>
          <ModalBody>
            <p>新版本 v{updateInfo?.version} 已下载完成。</p>
            <p className="text-sm text-default-600 mt-2">
              点击"立即安装"将退出应用并安装更新。
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="light" onPress={() => setIsReadyToInstall(false)}>
              稍后安装
            </Button>
            <Button color="primary" onPress={handleInstall}>
              立即安装
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    );
  }

  return null;
}

