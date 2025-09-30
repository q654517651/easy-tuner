import { createRoot } from "react-dom/client";
import { createBrowserRouter, createHashRouter, RouterProvider, Navigate, Link } from "react-router-dom";
import { lazy, Suspense } from "react";
import { ThemeProvider } from "./contexts/ThemeContext";
import { Providers } from "./providers";
import { I18nProvider } from "./i18n/I18nProvider";
import AppShell from "./shell/AppShell";
import { Skeleton } from "@heroui/react";
import "./index.css";

// 懒加载页面组件
const DatasetsList = lazy(() => import("./pages/DatasetsList"));
const DatasetDetail = lazy(() => import("./pages/DatasetDetail"));
const TasksList = lazy(() => import("./pages/TasksList"));
const CreateTask = lazy(() => import("./pages/CreateTask"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const TaskDetail = lazy(() => import("./pages/TaskDetail"));
const EmptyStatePage = lazy(() => import("./pages/EmptyState"));
function ErrorFallback() {
  return (
    <div className="h-full flex items-center justify-center p-10">
      <div className="text-center">
        <div className="text-5xl mb-3">😕</div>
        <div className="text-lg font-semibold mb-2">页面未找到或加载失败</div>
        <div className="text-sm opacity-70">请返回首页或重启应用</div>
        <Link to="/" className="mt-4 inline-block text-primary underline">返回首页</Link>
      </div>
    </div>
  );
}

// 简单的页面加载指示器
const PageLoadingFallback = () => (
  <div className="h-full flex items-center justify-center">
    <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
  </div>
);

// 在应用启动时初始化主题
const initializeTheme = () => {
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
};

// 在应用启动时初始化语言（用于Electron环境）
const initializeLanguage = () => {
  // 这个函数会在I18nProvider初始化时被调用
  // 主要作用是在Electron环境中可能需要额外的系统语言检测
  try {
    const isElectron = window.electronAPI !== undefined;
    if (isElectron) {
    // 静默
    } else {
    // 静默
    }
  } catch (error) {
    console.warn('[Language] 语言初始化失败:', error);
  }
};

// 立即初始化主题和语言，避免闪烁
initializeTheme();
initializeLanguage();

// 优先通过 process.versions.electron 检测是否为 Electron 渲染进程，必要时回退
const isElectron = (() => {
  try {
    const anyProcess: any = typeof process !== 'undefined' ? (process as any) : undefined;
    if (anyProcess?.versions?.electron) return true; // 最可靠：Electron 注入的版本信息
    // 其次：预加载脚本暴露的桥接对象（本项目已使用）
    if ((window as any).electronAPI) return true;
    // 最后回退：开发态部分环境中的 UA 识别
    return navigator.userAgent.includes('Electron');
  } catch {
    return false;
  }
})();
const routes = [
  {
    path: "/",
    element: <AppShell />,
    errorElement: <ErrorFallback />,
    children: [
      { index: true, element: <Navigate to="/datasets" replace /> },
      {
        path: "/datasets",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <DatasetsList />
          </Suspense>
        )
      },
      {
        path: "/datasets/:id",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <DatasetDetail />
          </Suspense>
        )
      },
      {
        path: "/tasks",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <TasksList />
          </Suspense>
        )
      },
      {
        path: "/train/create",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <CreateTask />
          </Suspense>
        )
      },
      {
        path: "/settings",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <SettingsPage />
          </Suspense>
        )
      },
      {
        path: "/tasks/:id",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <TaskDetail />
          </Suspense>
        )
      },
      {
        path: "/empty/:kind?",
        element: (
          <Suspense fallback={<PageLoadingFallback />}>
            <EmptyStatePage />
          </Suspense>
        )
      },
      { path: "*", element: <ErrorFallback /> },
    ],
  },
];

const router = (isElectron ? createHashRouter : createBrowserRouter)(routes);

createRoot(document.getElementById("root")!).render(
  <I18nProvider>
    <ThemeProvider>
      <Providers>
        <Suspense fallback={<PageLoadingFallback />}>
          <RouterProvider router={router} />
        </Suspense>
      </Providers>
    </ThemeProvider>
  </I18nProvider>
);
