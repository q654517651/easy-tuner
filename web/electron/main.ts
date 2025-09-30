import { app, BrowserWindow, ipcMain, Menu, nativeTheme, shell, nativeImage, dialog} from "electron";
import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isProd = app.isPackaged;
let backendProc: ReturnType<typeof spawn> | null = null;
// 动态后端端口：优先环境变量，其次从后端 stdout 解析，默认 8000
let BACKEND_PORT = Number(process.env.BACKEND_PORT || '8000');
let win: BrowserWindow | null = null;

function getAppIconPath() {
  const isWin = process.platform === "win32";
  const isMac = process.platform === "darwin";
  const filename = isWin ? "app.ico" : isMac ? "app.icns" : "app.png";

  const candidates = [
    // dev 下常用
    path.resolve(process.cwd(), "public", "icons", filename),
    path.resolve(process.cwd(), "src", "assets", "app_icon", `AppIcon.${isWin ? "ico" : isMac ? "icns" : "png"}`),
    // 打包后常见位置（__dirname 指向 dist-electron 或 resources）
    path.resolve(__dirname, "../public/icons", filename),
    path.resolve(__dirname, "./icons", filename),
  ];

  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return ""; // 找不到就交给系统默认
}

async function createWindow() {
  // 清空默认菜单，移除 File / Edit / View
  Menu.setApplicationMenu(null);

  // 构建图标路径，确保开发和生产环境都能正确找到
  const iconPath = getAppIconPath();


  win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
    title: "EasyTuner",
    icon: iconPath ? nativeImage.createFromPath(iconPath) : undefined,
    frame: false,              // 自绘标题栏
    titleBarStyle: "hidden",
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#171717" : "#ffffff",
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });

  if (isProd) {
    // 生产模式：加载构建后的前端文件
    const indexHtml = path.join(__dirname, "../dist/index.html");
    await win.loadFile(indexHtml);
  } else {
    // 开发模式：连接Vite开发服务器（支持动态端口检测）
    const devServerURL = process.env.VITE_DEV_SERVER_URL || "http://localhost:5173";
    await win.loadURL(devServerURL);
    win.webContents.openDevTools({ mode: "detach" });
  }

  // 将窗口最大化状态变化广播给渲染层
  const emitMaxState = () => {
    win?.webContents.send("win:maximize-changed", win?.isMaximized() ?? false);
  };

  win.on("maximize", emitMaxState);
  win.on("unmaximize", emitMaxState);
  win.on("focus", emitMaxState);
  win.on("blur", emitMaxState);

  // 兜底监听：渲染进程异常或无响应时，尝试优雅停止后端
  win.webContents.on('render-process-gone', (_e, details) => {
    console.warn('[electron] render-process-gone:', details);
    void stopBackend(true, 1500);
  });
  win.on('unresponsive', () => {
    console.warn('[electron] window unresponsive');
    void stopBackend(true, 1500);
  });

  // 处理窗口关闭
  win.on("closed", () => {
    win = null;
  });
}

// 应用生命周期事件
app.whenReady().then(async () => {
  // 仅在打包后启动后端 EXE；开发态默认不启动（可通过环境变量开启）
  if (isProd || process.env.ELECTRON_START_BACKEND === '1') {
    try {
      await startBackendAndWait();
    } catch (e) {
      console.error('[backend] failed to start:', e);
    }
  }
  await createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// ---- IPC：窗口控制 ----
ipcMain.on("win:minimize", () => win?.minimize());
ipcMain.on("win:close", () => win?.close());
ipcMain.on("win:maxToggle", () => {
  if (!win) return;
  win.isMaximized() ? win.unmaximize() : win.maximize();
});

// ---- IPC：状态查询 ----
ipcMain.handle("win:isMaximized", () => win?.isMaximized() ?? false);
ipcMain.handle("win:isFocused", () => win?.isFocused() ?? false);

// 示例 IPC：供渲染进程获取版本信息
ipcMain.handle("app:getVersion", () => {
  return {
    version: app.getVersion(),
    electron: process.versions.electron,
    node: process.versions.node,
  };
});

// 示例 IPC：获取应用路径信息
ipcMain.handle("app:getPaths", () => {
  return {
    userData: app.getPath("userData"),
    documents: app.getPath("documents"),
    downloads: app.getPath("downloads"),
  };
});

// ---- IPC：文件夹打开功能 ----
ipcMain.handle("open-folder", async (_evt, { taskId, kind }: { taskId: string; kind: "sample" | "output" }) => {
  try {
    // 构建目录路径（打包后使用 userData/backend/workspace）
    const baseWorkspace = isProd
      ? path.resolve(app.getPath('userData'), "backend", "workspace")
      : path.resolve(process.cwd(), "workspace");
    const base = path.resolve(baseWorkspace, "tasks", taskId, "output");
    const target = path.resolve(base, kind === "sample" ? "sample" : ".");

    // 安全检查：确保目标路径在基础路径内
    if (!target.startsWith(base)) {
      return { ok: false, error: "禁止访问该路径" };
    }

    // 检查目录是否存在
    if (!fs.existsSync(target)) {
      return { ok: false, error: "目录不存在" };
    }

    // 尝试打开目录
    const result = await shell.openPath(target);

    // shell.openPath 返回空字符串表示成功，否则返回错误信息
    if (result) {
      return { ok: false, error: result };
    } else {
      return { ok: true };
    }
  } catch (error) {
    return { ok: false, error: `打开目录失败: ${error}` };
  }
});

// ---------- 后端启动/健康检查 ----------
function resourcesBackendDir() {
  return path.join(process.resourcesPath, 'backend');
}
function userDataBackendDir() {
  return path.join(app.getPath('userData'), 'backend');
}
function ensureDir(p: string) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}
function copyDirSync(src: string, dest: string) {
  if (!fs.existsSync(src)) return;
  ensureDir(dest);
  for (const entry of fs.readdirSync(src)) {
    const s = path.join(src, entry);
    const d = path.join(dest, entry);
    const stat = fs.statSync(s);
    if (stat.isDirectory()) copyDirSync(s, d);
    else if (!fs.existsSync(d)) fs.copyFileSync(s, d);
  }
}

function startBackend() {
  // 打包后：将 runtime 复制到用户数据目录，工作目录设置到 userData/backend
  const exeDir = resourcesBackendDir();
  const runDir = userDataBackendDir();
  ensureDir(runDir);
  // 确保 workspace 目录存在（runtime 不再随应用打包，由用户自行提供或按配置路径使用）
  ensureDir(path.join(runDir, 'workspace'));

  const exePath = path.join(exeDir, 'EasyTunerBackend.exe');
  try {
    backendProc = spawn(exePath, [], { cwd: runDir, stdio: 'pipe' });
    backendProc.stdout?.on('data', d => {
      const text = d.toString();
      console.log('[backend]', text);
      // 尝试从 Uvicorn 启动行解析端口
      try {
        const m = text.match(/Uvicorn running on\s+https?:\/\/[^:]+:(\d+)/i);
        if (m && m[1]) {
          const port = Number(m[1]);
          if (!Number.isNaN(port) && port > 0) {
            BACKEND_PORT = port;
            console.log('[backend] detected port:', BACKEND_PORT);
          }
        }
      } catch {}
    });
    backendProc.stderr?.on('data', d => console.error('[backend-err]', d.toString()));
    backendProc.on('exit', code => console.log('[backend] exit', code));
  } catch (e) {
    console.error('[backend] spawn failed:', e);
  }
}

function waitBackendReady(timeoutMs = 20000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, res => {
        if (res.statusCode === 200) resolve();
        else retry();
      });
      req.on('error', retry);
      req.setTimeout(1500, () => { try { req.destroy(); } catch {} ; retry(); });
      function retry() {
        if (Date.now() > deadline) reject(new Error('backend health timeout'));
        else setTimeout(tryOnce, 500);
      }
    };
    tryOnce();
  });
}

async function startBackendAndWait() {
  startBackend();
  await waitBackendReady(20000);
}

async function stopBackend(graceful = true, timeoutMs = 2000) {
  const p = backendProc;
  if (!p) return;
  if (graceful) {
    try {
      await new Promise<void>((resolve) => {
        const req = http.request({ hostname: '127.0.0.1', port: BACKEND_PORT, path: '/__internal__/shutdown', method: 'POST', timeout: 1000 }, () => resolve());
        req.on('error', () => resolve());
        req.end();
      });
    } catch {}
  }
  const done = new Promise<void>((resolve) => {
    p.once('exit', () => resolve());
  });
  const timer = setTimeout(() => {
    // 强制杀死（包含子进程树）
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/PID', String(p.pid), '/F', '/T']);
      } else {
        try { p.kill('SIGKILL'); } catch {}
      }
    } catch {}
  }, timeoutMs);
  await done.catch(() => {});
  clearTimeout(timer);
  backendProc = null;
}

app.on('will-quit', async (event) => {
  try {
    event.preventDefault();
  } catch {}
  await stopBackend(true, 1500);
  app.exit(0);
});
process.on('exit', () => { try { backendProc?.kill(); } catch {} });
process.on('SIGINT', async () => { await stopBackend(); process.exit(0); });
process.on('SIGTERM', async () => { await stopBackend(); process.exit(0); });

// ---------- 选择工作区对话框 & 运行时安装（占位） ----------
ipcMain.handle('system:selectWorkspaceDialog', async () => {
  const res = await dialog.showOpenDialog({ properties: ['openDirectory', 'createDirectory'] });
  return { canceled: res.canceled, path: res.filePaths?.[0] || '' };
});

ipcMain.handle('runtime:install', async () => {
  // TODO: 在这里实现实际安装逻辑（打开终端窗口执行安装脚本，并返回进度/结果）
  // 目前先返回未实现，前端可按占位流程展示
  return { ok: false, message: 'Runtime installer not implemented yet' } as any;
});
