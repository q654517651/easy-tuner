// Electron API 类型定义

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

interface ElectronUpdater {
  checkForUpdates: () => Promise<any>;
  downloadUpdate: () => Promise<any>;
  quitAndInstall: () => void;
}

interface ElectronAPI {
  // 文件夹操作
  openFolder: (folderPath: string) => Promise<{ ok: boolean; error?: string }>;
  selectWorkspace: () => Promise<{ canceled: boolean; path: string }>;
  
  // 更新相关
  updater: ElectronUpdater;
  
  // 事件监听
  on: (channel: string, callback: (...args: any[]) => void) => void;
  removeAllListeners: (channel: string) => void;
}

interface WindowAPI {
  getVersion: () => Promise<{
    version: string;
    electron: string;
    node: string;
  }>;
  getPaths: () => Promise<{
    userData: string;
    documents: string;
    downloads: string;
  }>;
}

interface WinCtrlAPI {
  minimize: () => void;
  maximizeToggle: () => void;
  close: () => void;
  isMaximized: () => Promise<boolean>;
  isFocused: () => Promise<boolean>;
  onMaximizeChanged: (cb: (maxed: boolean) => void) => () => void;
}

interface ElectronAPICommon {
  invoke: (channel: string, ...args: any[]) => Promise<any>;
  checkBackendHealth: () => Promise<{ ready: boolean; port: number }>;
}

declare global {
  interface Window {
    api: WindowAPI;
    winCtrl: WinCtrlAPI;
    electron: ElectronAPI;
    electronAPI: ElectronAPICommon;
  }
}

export {};
