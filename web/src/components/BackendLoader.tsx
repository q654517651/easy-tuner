import { useEffect, useState } from "react";
import { Spinner } from "@heroui/react";

interface BackendLoaderProps {
  onReady: () => void;
}

// 健康检查配置（与 Electron 主进程保持一致）
const HEALTH_CHECK_CONFIG = {
  timeout: 2000,           // 单次超时（ms）
  initialRetryDelay: 500,  // 初始重试延迟（ms）
  maxRetryDelay: 4000,     // 最大重试延迟（ms）
  maxWaitTime: 60000,      // 总等待时间（ms）
};

export default function BackendLoader({ onReady }: BackendLoaderProps) {
  const [status, setStatus] = useState<"checking" | "ready" | "error">("checking");
  const [debugInfo, setDebugInfo] = useState<string[]>([]);
  const [retryDelay, setRetryDelay] = useState(HEALTH_CHECK_CONFIG.initialRetryDelay);
  const [elapsedTime, setElapsedTime] = useState(0);

  const addDebug = (msg: string) => {
    setDebugInfo(prev => [...prev.slice(-5), `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  useEffect(() => {
    const startTime = Date.now();

    const checkBackend = async () => {
      const currentElapsed = Date.now() - startTime;
      setElapsedTime(currentElapsed);

      // 超时检查
      if (currentElapsed > HEALTH_CHECK_CONFIG.maxWaitTime) {
        addDebug('Max wait time exceeded, giving up');
        setStatus("error");
        return;
      }

      try {
        const { isElectron: checkIsElectron } = await import('../utils/platform');
        const isElectron = checkIsElectron();
        if (currentElapsed === 0) {
          addDebug(`Environment: ${isElectron ? 'Electron' : 'Web'}`);
        }

        if (isElectron) {
          // Electron 环境：通过 IPC 检查后端
          const result = await window.electronAPI.invoke("backend:checkHealth");

          if (result.ready) {
            addDebug(`✓ Ready (port=${result.port}, status=${result.statusCode})`);
            setStatus("ready");
            setTimeout(onReady, 100);
            return;
          } else {
            addDebug(`✗ Failed (port=${result.port}, error=${result.error || result.statusCode || 'unknown'})`);
          }
        } else {
          // Web 开发模式：使用相对路径（通过 Vite 代理）
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), HEALTH_CHECK_CONFIG.timeout);

          try {
            const response = await fetch("/healthz", {
              method: "GET",
              signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (response.ok) {
              addDebug(`✓ Ready (status=${response.status})`);
              setStatus("ready");
              setTimeout(onReady, 100);
              return;
            } else {
              addDebug(`✗ Failed (status=${response.status})`);
            }
          } catch (fetchError: any) {
            clearTimeout(timeoutId);
            addDebug(`✗ Error (${fetchError?.name || 'Unknown'})`);
          }
        }

        // 后端未就绪，指数退避重试
        addDebug(`⏳ Retry in ${retryDelay}ms (elapsed: ${Math.round(currentElapsed/1000)}s)`);
        setTimeout(checkBackend, retryDelay);
        setRetryDelay(prev => Math.min(prev * 2, HEALTH_CHECK_CONFIG.maxRetryDelay));

      } catch (error) {
        addDebug(`Error: ${error instanceof Error ? error.message : String(error)}`);
        setTimeout(checkBackend, retryDelay);
        setRetryDelay(prev => Math.min(prev * 2, HEALTH_CHECK_CONFIG.maxRetryDelay));
      }
    };

    checkBackend();
  }, [onReady]);

  if (status === "ready") {
    return null;
  }

  if (status === "error") {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-background z-50">
        <div className="text-center">
          <div className="text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold mb-2">后端启动失败</h2>
          <p className="text-default-500 mb-4">
            无法连接到后端服务，请检查后端是否正常运行
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90"
          >
            重新加载
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-background z-50">
      <div className="text-center max-w-2xl px-4">
        <Spinner size="lg" className="mb-4" />
        <h2 className="text-2xl font-bold mb-2">正在启动</h2>
        <p className="text-default-500 mb-4">
          正在启动后端服务，请稍候... ({Math.round(elapsedTime/1000)}s / {HEALTH_CHECK_CONFIG.maxWaitTime/1000}s)
        </p>

        {/* 调试信息 */}
        <div className="mt-6 p-4 bg-default-100 rounded-lg text-left text-xs font-mono">
          <div className="text-default-600 mb-2">Debug Info:</div>
          {debugInfo.map((info, i) => (
            <div key={i} className="text-default-500">{info}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
