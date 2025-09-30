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
  // 打开文件夹
  openFolder: (taskId: string, kind: "sample" | "output") =>
    ipcRenderer.invoke("open-folder", { taskId, kind }) as Promise<{ ok: boolean; error?: string }>,
  // 选择工作区目录
  selectWorkspace: () => ipcRenderer.invoke('system:selectWorkspaceDialog') as Promise<{ canceled: boolean; path: string }>,
  // 安装运行时（占位）
  runtimeInstall: () => ipcRenderer.invoke('runtime:install') as Promise<{ ok: boolean; message?: string }>,
});
