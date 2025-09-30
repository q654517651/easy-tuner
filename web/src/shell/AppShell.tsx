import { Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import Sidebar from "../ui/Sidebar";
import TitleBarControls from "../components/TitleBarControls";
import StartupGuard from "../components/StartupGuard";

export default function AppShell() {
  const [isElectron, setIsElectron] = useState(false);

  useEffect(() => {
    // 检测是否在Electron环境中
    setIsElectron(window.navigator.userAgent.includes('Electron'));
  }, []);

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
        <main className={`flex-1 min-w-0 bg-white dark:bg-zinc-900 border-l border-gray-200 dark:border-zinc-700 overflow-hidden ${
          isElectron ? 'rounded-tl-2xl border-t' : ''
        }`}>
          <StartupGuard />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
