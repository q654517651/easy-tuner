import { Outlet } from "react-router-dom";
import { useState } from "react";
import { useIsElectron } from "../utils/platform";
import Sidebar from "../ui/Sidebar";
import TitleBarControls from "../components/TitleBarControls";
import StartupGuard from "../components/StartupGuard";
import BackendLoader from "../components/BackendLoader";

export default function AppShell() {
  const isElectron = useIsElectron();
  const [backendReady, setBackendReady] = useState(false);

  // 如果后端未就绪，显示加载界面
  if (!backendReady) {
    return (
      <div className="h-dvh w-dvw flex flex-col bg-gray-50 text-neutral-900 dark:bg-black dark:text-neutral-50">
        <TitleBarControls />
        <BackendLoader onReady={() => setBackendReady(true)} />
      </div>
    );
  }

  return (
    <div className="h-dvh w-dvw flex flex-col bg-gray-50 text-neutral-900 selection:bg-sky-200/60 dark:bg-black dark:text-neutral-50">
      {/* Electron自定义标题栏 */}
      <TitleBarControls />

      {/* 主体区域：侧边栏 + 内容 */}
      <div className="flex-1 flex min-h-0">
        {/* 左侧竖向导航 */}
        <aside className="w-64 shrink-0">
          <Sidebar />
        </aside>

        {/* 右侧内容区：Header + Topbar + Content */}
        <main className={`flex-1 min-w-0 min-h-0 bg-white dark:bg-zinc-900 border-l border-gray-200 dark:border-zinc-700 overflow-hidden ${
          isElectron ? 'rounded-tl-2xl border-t' : ''
        }`}>
          <StartupGuard />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
