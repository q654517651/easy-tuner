import { useEffect } from 'react';
import { addToast } from '@heroui/react';
import { readinessApi } from '../services/api';
import { useReadiness } from '../contexts/ReadinessContext';

function getWorkspaceMessage(reason?: string) {
  switch (reason) {
    case "NOT_SET": return "工作区未设置，创建数据集前请先选择目录";
    case "NOT_FOUND": return "工作区目录不存在，请重新选择";
    case "NOT_WRITABLE": return "工作区目录无写入权限，请更换目录";
    default: return "工作区状态异常，请在设置里检查";
  }
}

function getRuntimeMessage(reason?: string) {
  switch (reason) {
    case "PYTHON_MISSING": return "缺少 Python 环境，开始训练前需要安装";
    case "MUSUBI_MISSING": return "缺少 Musubi 引擎（子仓库），请先安装/修复";
    case "ENGINES_MISSING": return "缺少训练引擎，开始训练前需要安装/修复";
    default: return "训练环境状态异常，请在设置里检查";
  }
}

export default function StartupGuard() {
  const { setWorkspaceReady, setRuntimeReady, setLoading } = useReadiness();

  useEffect(() => {
    // 首屏拉取状态
    let mounted = true;
    (async () => {
      try {
        setLoading(true);
        const ws = await readinessApi.getWorkspaceStatus();
        if (!mounted) return;

        const wsOk = ws.data?.reason === "OK";
        setWorkspaceReady(wsOk);

        if (!wsOk) {
          // 轻量提示，不阻断
          addToast({
            title: "提示",
            description: getWorkspaceMessage(ws.data?.reason),
            color: "warning",
            timeout: 5000
          });
        }

        const rt = await readinessApi.getRuntimeStatus();
        if (!mounted) return;

        const rtOk = rt.data?.reason === "OK";
        setRuntimeReady(rtOk);

        if (!rtOk) {
          addToast({
            title: "提示",
            description: getRuntimeMessage(rt.data?.reason),
            color: "warning",
            timeout: 5000
          });
        }
      } catch (e) {
        console.error('就绪状态检查失败', e);
        // 失败时默认为未就绪，但不阻断
        setWorkspaceReady(false);
        setRuntimeReady(false);
      } finally {
        setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [setLoading, setWorkspaceReady, setRuntimeReady]);

  return null;
}


