import { useEffect, useMemo, useState } from 'react';
import { Modal, ModalBody, ModalContent, ModalFooter, ModalHeader, Button, Input } from '@heroui/react';
import { readinessApi } from '../services/api';
import { useReadiness } from '../contexts/ReadinessContext';
import { addToast } from '@heroui/toast';

export default function StartupGuard() {
  const { workspaceReady, runtimeReady, setWorkspaceReady, setRuntimeReady, loading, setLoading } = useReadiness();
  const [wsModalOpen, setWsModalOpen] = useState(false);
  const [rtModalOpen, setRtModalOpen] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selectedPath, setSelectedPath] = useState('');
  const [installing, setInstalling] = useState(false);
  const needGuard = useMemo(() => !workspaceReady || !runtimeReady, [workspaceReady, runtimeReady]);

  useEffect(() => {
    // 首屏拉取状态
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        const ws = await readinessApi.getWorkspaceStatus();
        if (!mounted) return;
        const wsOk = !!(ws.data?.exists && ws.data?.writable);
        setWorkspaceReady(wsOk);
        if (!wsOk) {
          setWsModalOpen(true);
          return;
        }
        const rt = await readinessApi.getRuntimeStatus();
        if (!mounted) return;
        const rtOk = !!(rt.data?.python_present);
        setRuntimeReady(rtOk);
        if (!rtOk) setRtModalOpen(true);
      } catch (e) {
        console.error('就绪状态检查失败', e);
        // 保守默认不就绪，要求用户选择工作区
        setWorkspaceReady(false);
        setRuntimeReady(false);
        setWsModalOpen(true);
      } finally {
        setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [setLoading, setWorkspaceReady, setRuntimeReady]);

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
      setLoading(true);
      await readinessApi.selectWorkspace(selectedPath);
      addToast({ title: '工作区设置成功', color: 'success', timeout: 1500 });
      setWsModalOpen(false);
      setWorkspaceReady(true);
      // 继续检查 runtime
      const rt = await readinessApi.getRuntimeStatus();
      const rtOk = !!(rt.data?.python_present);
      setRuntimeReady(rtOk);
      if (!rtOk) setRtModalOpen(true);
    } catch (e) {
      addToast({ title: '设置失败', description: String(e), color: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const doInstallRuntime = async () => {
    try {
      setInstalling(true);
      const res = await window.electron?.runtimeInstall?.();
      if (res && res.ok) {
        addToast({ title: '运行时安装成功', color: 'success', timeout: 1500 });
        setRuntimeReady(true);
        setRtModalOpen(false);
      } else {
        addToast({ title: '运行时安装失败', description: res?.message || '未实现', color: 'danger' });
      }
    } catch (e) {
      addToast({ title: '运行时安装异常', description: String(e), color: 'danger' });
    } finally {
      setInstalling(false);
    }
  };

  if (!needGuard) return null;

  return (
    <>
      {/* 工作区选择（阻断式，不可关闭） */}
      <Modal isOpen={wsModalOpen} onClose={() => {}} hideCloseButton placement="center">
        <ModalContent>
          <ModalHeader>选择工作区</ModalHeader>
          <ModalBody>
            <p>首次使用需指定工作区目录，用于存放任务、数据集与日志。</p>
            <div className="flex items-center gap-2">
              <Input readOnly value={selectedPath} placeholder="未选择" className="flex-1" />
              <Button onPress={pickWorkspace} isLoading={selecting}>浏览…</Button>
            </div>
          </ModalBody>
          <ModalFooter>
            <Button color="primary" isDisabled={!selectedPath || loading} isLoading={loading} onPress={applyWorkspace}>确定</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* 运行时安装（阻断式，可跳过） */}
      <Modal isOpen={rtModalOpen} onClose={() => {}} hideCloseButton placement="center">
        <ModalContent>
          <ModalHeader>安装运行时</ModalHeader>
          <ModalBody>
            <p>缺少嵌入式 Python 运行时，安装后才能训练。你也可以跳过，仅浏览与管理任务/数据集。</p>
          </ModalBody>
          <ModalFooter>
            <Button variant="light" isDisabled={installing} onPress={() => { setRtModalOpen(false); addToast({ title: '已跳过运行时安装', color: 'warning'}); }}>跳过</Button>
            <Button color="primary" isLoading={installing} onPress={doInstallRuntime}>安装</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
}

