/// <reference types="vite/client" />

declare global {
  interface Window {
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
      // 打开文件夹
      openFolder(taskId: string, kind: "sample" | "output"): Promise<{ ok: boolean; error?: string }>;
    };
  }
}

export {};