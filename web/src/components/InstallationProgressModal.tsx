import { useState, useEffect, useRef, useCallback } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button, addToast } from '@heroui/react';
import { useReadiness } from '../contexts/ReadinessContext';
import { readinessApi, getApiBaseUrl, postJson } from '../services/api';

interface InstallationProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  installationId: string;
  onSuccess?: () => void;
  onRetry?: () => void; // 新增：重试回调
}

type InstallationState = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export default function InstallationProgressModal({
  isOpen,
  onClose,
  installationId,
  onSuccess,
  onRetry
}: InstallationProgressModalProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [state, setState] = useState<InstallationState>('pending');
  const [cancelling, setCancelling] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const { setRuntimeReady } = useReadiness();

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [logs, scrollToBottom]);

  // WebSocket 连接
  useEffect(() => {
    if (!isOpen || !installationId) return;

    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const isDev = (import.meta as any)?.env?.DEV;
    const isNonBackendPort = typeof location !== 'undefined' && location.port && location.port !== '8000';
    const baseHost = isDev && isNonBackendPort ? '127.0.0.1:8000' : (location.host || '127.0.0.1:8000');
    const wsUrl = `${wsProtocol}//${baseHost}/ws/installation/${installationId}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[安装 WS] 连接成功');
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'log') {
          const line = message.payload?.line || '';
          if (line) {
            setLogs(prev => [...prev, line]);
          }
        } else if (message.type === 'state') {
          const newState = message.payload?.state as InstallationState;
          if (newState) {
            setState(newState);

            // 终态处理
            if (newState === 'completed') {
              handleInstallationCompleted();
            } else if (newState === 'failed' || newState === 'cancelled') {
              // 失败/取消状态保留日志，等待用户操作
            }
          }
        }
      } catch (error) {
        console.error('[安装 WS] 消息解析失败:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('[安装 WS] 错误:', error);
    };

    ws.onclose = () => {
      console.log('[安装 WS] 连接关闭');
    };

    return () => {
      // 总是关闭 WebSocket，无论状态（CONNECTING/OPEN 都能正常关闭）
      ws?.close();
      wsRef.current = null;
    };
  }, [isOpen, installationId]);

  // 安装完成处理
  const handleInstallationCompleted = async () => {
    try {
      // 验证运行时状态
      const rtStatus = await readinessApi.getRuntimeStatus();
      const rtOk = rtStatus.data?.reason === 'OK';

      if (rtOk) {
        setRuntimeReady(true);
        addToast({
          title: '安装成功',
          description: 'Python 运行时已成功安装',
          color: 'success',
          timeout: 3000
        });
        onClose();
        onSuccess?.();
      } else {
        addToast({
          title: '安装异常',
          description: `安装脚本完成但运行时状态不正常: ${rtStatus.data?.reason}`,
          color: 'warning',
          timeout: 5000
        });
      }
    } catch (e) {
      console.error('验证运行时状态失败:', e);
      addToast({
        title: '验证失败',
        description: '无法验证运行时状态，请手动检查',
        color: 'warning',
        timeout: 5000
      });
    }
  };

  // 处理关闭按钮点击
  const handleCloseClick = () => {
    const isRunning = state === 'pending' || state === 'running';
    if (isRunning) {
      // 运行中，显示二次确认
      setShowCloseConfirm(true);
    } else {
      // 终态，直接关闭
      onClose();
    }
  };

  // 确认关闭并取消安装
  const handleConfirmClose = async () => {
    try {
      setCancelling(true);

      // 调用后端取消安装
      await postJson(`/installation/${installationId}/cancel`, {});

      addToast({
        title: '安装已取消',
        color: 'warning',
        timeout: 2000
      });
    } catch (e) {
      addToast({
        title: '取消失败',
        description: e instanceof Error ? e.message : String(e),
        color: 'danger',
        timeout: 3000
      });
    } finally {
      setCancelling(false);

      // 关闭 WebSocket
      wsRef.current?.close();
      wsRef.current = null;

      // 关闭二次确认弹窗
      setShowCloseConfirm(false);

      // 关闭主弹窗
      onClose();
    }
  };

  // 取消二次确认，继续安装
  const handleCancelClose = () => {
    setShowCloseConfirm(false);
  };

  // 重试安装
  const handleRetry = () => {
    onClose(); // 关闭当前进度弹窗
    onRetry?.(); // 触发父组件的 doInstallRuntime()
  };

  // 复制日志
  const handleCopyLogs = () => {
    const logText = logs.join('\n');
    navigator.clipboard.writeText(logText).then(() => {
      addToast({
        title: '日志已复制',
        color: 'success',
        timeout: 1500
      });
    }).catch(err => {
      console.error('复制失败:', err);
      addToast({
        title: '复制失败',
        color: 'danger',
        timeout: 1500
      });
    });
  };

  const isTerminal = state === 'completed' || state === 'failed' || state === 'cancelled';
  const isFailed = state === 'failed' || state === 'cancelled';

  return (
    <>
      {/* 二次确认对话框 */}
      <Modal
        isOpen={showCloseConfirm}
        onClose={handleCancelClose}
        placement="center"
        size="sm"
      >
        <ModalContent>
          <ModalHeader>确认关闭</ModalHeader>
          <ModalBody>
            <p>安装正在进行中，关闭将强制终止安装进程。确定要关闭吗？</p>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="light"
              onPress={handleCancelClose}
              isDisabled={cancelling}
            >
              继续安装
            </Button>
            <Button
              color="danger"
              onPress={handleConfirmClose}
              isLoading={cancelling}
            >
              仍要关闭并取消
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* 主安装进度弹窗 */}
      <Modal
        isOpen={isOpen}
        onClose={handleCloseClick}
        placement="center"
        size="3xl"
        isDismissable={!showCloseConfirm}
      >
      <ModalContent>
        <ModalHeader className="flex items-center gap-2">
          <span>安装 Python 运行时</span>
          {state === 'running' && (
            <span className="text-sm font-normal text-primary">安装中...</span>
          )}
          {state === 'completed' && (
            <span className="text-sm font-normal text-success">✅ 安装成功</span>
          )}
          {state === 'failed' && (
            <span className="text-sm font-normal text-danger">❌ 安装失败</span>
          )}
          {state === 'cancelled' && (
            <span className="text-sm font-normal text-warning">⚠️ 已取消</span>
          )}
        </ModalHeader>
        <ModalBody>
          <div
            ref={logContainerRef}
            className="bg-black/90 text-green-400 font-mono text-xs p-4 rounded-lg overflow-y-auto"
            style={{ height: '400px', maxHeight: '60vh' }}
          >
            {logs.length === 0 ? (
              <div className="text-gray-500">等待安装日志...</div>
            ) : (
              logs.map((line, index) => (
                <div key={index} className="whitespace-pre-wrap break-all">
                  {line}
                </div>
              ))
            )}
          </div>

          {/* 失败时的友好提示 */}
          {state === 'failed' && (
            <div className="mt-4 p-3 bg-danger-50 dark:bg-danger-900/20 rounded-lg">
              <div className="text-sm text-danger">
                <div className="font-semibold mb-1">安装失败</div>
                <div className="text-xs text-danger-700 dark:text-danger-300">
                  {logs.some(log => log.includes('不存在') || log.includes('not exist')) ? (
                    <>安装脚本缺失，请检查 runtime/setup_portable_uv.ps1 是否存在</>
                  ) : logs.some(log => log.includes('权限') || log.includes('permission') || log.includes('denied')) ? (
                    <>权限不足，请以管理员身份运行或检查目录权限</>
                  ) : (
                    <>请查看日志了解详细错误信息，或前往设置页面手动配置</>
                  )}
                </div>
              </div>
            </div>
          )}
        </ModalBody>
        <ModalFooter>
          {isFailed && (
            <>
              <Button
                variant="light"
                onPress={handleCopyLogs}
                isDisabled={logs.length === 0}
              >
                复制日志
              </Button>
              <Button
                color="primary"
                onPress={handleRetry}
              >
                重试安装
              </Button>
            </>
          )}

          {state === 'completed' && (
            <Button
              color="success"
              onPress={onClose}
            >
              完成
            </Button>
          )}

          {!isTerminal && (
            <div className="text-sm text-default-500">
              点击右上角 ✕ 可取消安装
            </div>
          )}
        </ModalFooter>
      </ModalContent>
    </Modal>
    </>
  );
}
