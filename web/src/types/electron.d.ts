/// <reference types="vite/client" />

declare global {
  interface Window {
    // Electron 注入的后端端口（动态）
    __BACKEND_PORT__?: number;
    // 自定义 API 基址（可选）
    __API_BASE__?: string;

    api: {
      // 获取应用版本信息
      getVersion(): Promise<{
        version: string;
        electron: string;
        node: string;
      }>;

      // 获取应用路径信息
      getPaths(): Promise<{
        userData: string;
        documents: string;
        downloads: string;
      }>;

      // 可以根据需要添加更多API声明，比如：
      // openFile(): Promise<string>;
      // saveFile(data: any): Promise<boolean>;
    };

    winCtrl?: {
      minimize(): void;
      maximizeToggle(): void;
      close(): void;
      isMaximized(): Promise<boolean>;
      isFocused(): Promise<boolean>;
      onMaximizeChanged(cb: (maxed: boolean) => void): () => void;
    };

    electron?: {
      // 打开文件夹（接收绝对路径）
      openFolder(folderPath: string): Promise<{ ok: boolean; error?: string }>;
      // 选择工作区目录
      selectWorkspace(): Promise<{ canceled: boolean; path: string }>;
    };

    electronAPI?: {
      // 通用 IPC invoke
      invoke(channel: string, ...args: any[]): Promise<any>;
      // 后端健康检查
      checkBackendHealth(): Promise<{ ready: boolean; port: number }>;
    };
  }
}

export {};