import { contextBridge, ipcRenderer } from "electron";

// 安全的API暴露到渲染进程
contextBridge.exposeInMainWorld("api", {
  // 获取应用版本信息
  getVersion: () => ipcRenderer.invoke("app:getVersion"),

  // 获取应用路径信息
  getPaths: () => ipcRenderer.invoke("app:getPaths"),

  // 可以根据需要添加更多API，比如：
  // openFile: () => ipcRenderer.invoke("dialog:openFile"),
  // saveFile: (data: any) => ipcRenderer.invoke("dialog:saveFile", data),
});

// 窗口控制API
contextBridge.exposeInMainWorld("winCtrl", {
  minimize: () => ipcRenderer.send("win:minimize"),
  maximizeToggle: () => ipcRenderer.send("win:maxToggle"),
  close: () => ipcRenderer.send("win:close"),

  isMaximized: () => ipcRenderer.invoke("win:isMaximized") as Promise<boolean>,
  isFocused: () => ipcRenderer.invoke("win:isFocused") as Promise<boolean>,

  onMaximizeChanged: (cb: (maxed: boolean) => void) => {
    const handler = (_: unknown, maxed: boolean) => cb(maxed);
    ipcRenderer.on("win:maximize-changed", handler);
    return () => ipcRenderer.removeListener("win:maximize-changed", handler);
  }
});

// Electron专用API
contextBridge.exposeInMainWorld("electron", {
  // 打开文件夹（接收绝对路径）
  openFolder: (folderPath: string) =>
    ipcRenderer.invoke("open-folder", { folderPath }) as Promise<{ ok: boolean; error?: string }>,
  // 选择工作区目录
  selectWorkspace: () => ipcRenderer.invoke('system:selectWorkspaceDialog') as Promise<{ canceled: boolean; path: string }>,
  
  // 更新相关 API
  updater: {
    checkForUpdates: () => ipcRenderer.invoke('updater:check-for-updates'),
    downloadUpdate: () => ipcRenderer.invoke('updater:download-update'),
    quitAndInstall: () => ipcRenderer.invoke('updater:quit-and-install'),
  },
  
  // 更新事件监听
  on: (channel: string, callback: (...args: any[]) => void) => {
    const validChannels = [
      'updater:checking-for-update',
      'updater:update-available',
      'updater:update-not-available',
      'updater:download-progress',
      'updater:update-downloaded',
      'updater:error',
      'backend:ready',
      'win:maximize-changed'
    ];
    if (validChannels.includes(channel)) {
      ipcRenderer.on(channel, (_event, ...args) => callback(...args));
    }
  },
  
  removeAllListeners: (channel: string) => {
    ipcRenderer.removeAllListeners(channel);
  }
});

// ElectronAPI（统一接口，供前端使用）
contextBridge.exposeInMainWorld("electronAPI", {
  // 通用 IPC invoke 方法
  invoke: (channel: string, ...args: any[]) => ipcRenderer.invoke(channel, ...args),

  // 后端健康检查
  checkBackendHealth: () => ipcRenderer.invoke("backend:checkHealth") as Promise<{ ready: boolean; port: number }>,
});
