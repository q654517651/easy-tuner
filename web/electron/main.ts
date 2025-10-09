import { app, BrowserWindow, ipcMain, Menu, nativeTheme, shell, nativeImage, dialog} from "electron";
import { spawn } from "node:child_process";
import http from "node:http";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import treeKill from "tree-kill";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isProd = app.isPackaged;
let backendProc: ReturnType<typeof spawn> | null = null;
// 动态后端端口：优先环境变量，其次从后端 stdout 解析，默认 8000
let BACKEND_PORT = Number(process.env.BACKEND_PORT || '8000');
let win: BrowserWindow | null = null;

// 健康检查配置（统一配置）
const HEALTH_CHECK_CONFIG = {
  timeout: 1500,           // 单次超时（ms）
  initialRetryDelay: 500,  // 初始重试延迟（ms）
  maxRetryDelay: 4000,     // 最大重试延迟（ms）
  maxWaitTime: 60000,      // 总等待时间（ms）
};

// 端口释放等待配置
const PORT_RELEASE_CONFIG = {
  pollInterval: 150,       // 轮询间隔（ms）
  maxWaitTime: 8000,       // 最大等待时间（ms）
};

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
    // 打包后也支持开发者工具（通过环境变量或快捷键 F12 打开）
    if (process.env.ENABLE_DEVTOOLS === '1') {
      win.webContents.openDevTools({ mode: "detach" });
    }
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

  // F12 快捷键切换开发者工具（生产环境也支持）
  win.webContents.on("before-input-event", (event, input) => {
    if (input.key === "F12") {
      if (win?.webContents.isDevToolsOpened()) {
        win.webContents.closeDevTools();
      } else {
        win?.webContents.openDevTools({ mode: "detach" });
      }
      event.preventDefault();
    }
  });

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
  // 先创建窗口，让用户看到界面
  await createWindow();

  // 仅在打包后启动后端 EXE；开发态默认不启动（可通过环境变量开启）
  if (isProd || process.env.ELECTRON_START_BACKEND === '1') {
    // 异步启动后端，不阻塞窗口显示
    startBackend();
  }
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

// ---- IPC：后端健康检查 ----
ipcMain.handle("backend:checkHealth", async () => {
  const { timeout } = HEALTH_CHECK_CONFIG;
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/healthz`, res => {
      res.resume(); // 消费响应体，避免 socket 泄漏
      resolve({ ready: res.statusCode === 200, port: BACKEND_PORT, statusCode: res.statusCode });
    });
    req.on('error', (err: NodeJS.ErrnoException) => resolve({ ready: false, port: BACKEND_PORT, error: err.code }));
    req.setTimeout(timeout, () => {
      try { req.destroy(); } catch {}
      resolve({ ready: false, port: BACKEND_PORT, error: 'TIMEOUT' });
    });
  });
});

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
    // 构建目录路径（打包后使用 resources/workspace）
    const baseWorkspace = isProd
      ? path.resolve(process.resourcesPath, "workspace")
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

/**
 * 探测可用端口（从 startPort 开始）
 */
async function findAvailablePort(startPort: number): Promise<number> {
  const checkPort = (port: number): Promise<boolean> => {
    return new Promise((resolve) => {
      const server = http.createServer();
      server.once('error', () => resolve(false));
      server.once('listening', () => {
        server.close();
        resolve(true);
      });
      server.listen(port, '127.0.0.1');
    });
  };

  for (let port = startPort; port < startPort + 10; port++) {
    if (await checkPort(port)) {
      return port;
    }
  }
  throw new Error(`No available port found from ${startPort} to ${startPort + 9}`);
}

/**
 * 等待端口释放
 */
async function waitPortRelease(port: number): Promise<void> {
  const { pollInterval, maxWaitTime } = PORT_RELEASE_CONFIG;
  const deadline = Date.now() + maxWaitTime;

  while (Date.now() < deadline) {
    const isPortOpen = await new Promise<boolean>((resolve) => {
      const req = http.get(`http://127.0.0.1:${port}/healthz`, (res) => {
        res.resume(); // 消费响应体，避免 socket 泄漏
        resolve(true);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(500, () => {
        try { req.destroy(); } catch {}
        resolve(false);
      });
    });

    if (!isPortOpen) {
      console.log(`[electron] Port ${port} released`);
      return;
    }

    await new Promise(r => setTimeout(r, pollInterval));
  }

  console.warn(`[electron] Port ${port} still occupied after ${maxWaitTime}ms`);
}

async function startBackend() {
  // 1. 探测可用端口
  try {
    BACKEND_PORT = await findAvailablePort(8000);
    console.log(`[electron] Using port: ${BACKEND_PORT}`);
  } catch (e) {
    console.error('[electron] Failed to find available port:', e);
    return;
  }

  // 2. 打包后：准备工作目录
  const exeDir = resourcesBackendDir();  // resources/backend
  const resourcesDir = path.dirname(exeDir);  // resources
  // workspace 由用户选择，不在此处创建

  // 3. 启动后端进程（工作目录设为 resources/，通过环境变量传递配置）
  const exePath = path.join(exeDir, 'EasyTunerBackend.exe');
  try {
    backendProc = spawn(exePath, [], {
      cwd: resourcesDir,  // ✅ 修改：工作目录设为 resources/
      stdio: 'pipe',
      env: {
        ...process.env,
        BACKEND_PORT: String(BACKEND_PORT),
        TAGTRAGGER_ROOT: resourcesDir,  // 明确指定项目根
        // 注意：workspace 路径会在后端首次启动时通过 API 设置，暂不在此处指定
      }
    });

    backendProc.stdout?.on('data', d => {
      const text = d.toString();
      console.log('[backend]', text);
    });
    backendProc.stderr?.on('data', d => console.error('[backend-err]', d.toString()));
    backendProc.on('exit', code => {
      console.log('[backend] exit', code);
      backendProc = null;
    });

    // 4. 等待后端就绪（指数退避重试）
    await waitBackendReady();
    console.log('[electron] Backend is ready!');

    // 5. 注入全局变量并通知前端后端已就绪
    await win?.webContents.executeJavaScript(`window.__BACKEND_PORT__ = ${BACKEND_PORT};`);
    win?.webContents.send('backend:ready', { port: BACKEND_PORT });
  } catch (e) {
    console.error('[backend] spawn failed:', e);
  }
}

/**
 * 等待后端就绪（指数退避重试）
 */
function waitBackendReady(): Promise<void> {
  const { timeout, initialRetryDelay, maxRetryDelay, maxWaitTime } = HEALTH_CHECK_CONFIG;
  const deadline = Date.now() + maxWaitTime;
  let retryDelay = initialRetryDelay;

  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/healthz`, res => {
        res.resume(); // 消费响应体，避免 socket 泄漏
        if (res.statusCode === 200) {
          console.log(`[electron] Health check passed (${res.statusCode})`);
          resolve();
        } else {
          console.log(`[electron] Health check failed (${res.statusCode}), retrying in ${retryDelay}ms`);
          retry();
        }
      });

      req.on('error', (err: NodeJS.ErrnoException) => {
        console.log(`[electron] Health check error (${err.code || 'UNKNOWN'}), retrying in ${retryDelay}ms`);
        retry();
      });
      req.setTimeout(timeout, () => {
        try { req.destroy(); } catch {}
        console.log(`[electron] Health check timeout, retrying in ${retryDelay}ms`);
        retry();
      });

      function retry() {
        if (Date.now() > deadline) {
          reject(new Error(`Backend health check timeout after ${maxWaitTime}ms`));
        } else {
          // 指数退避：每次重试延迟翻倍，上限为 maxRetryDelay
          setTimeout(tryOnce, retryDelay);
          retryDelay = Math.min(retryDelay * 2, maxRetryDelay);
        }
      }
    };
    tryOnce();
  });
}

/**
 * 停止后端（优雅关闭 + tree-kill 兜底）
 */
async function stopBackend(graceful = true, timeoutMs = 2000) {
  const p = backendProc;
  if (!p || !p.pid) return;

  const oldPort = BACKEND_PORT;

  // 1. 尝试优雅关闭
  if (graceful) {
    try {
      await new Promise<void>((resolve) => {
        const req = http.request({
          hostname: '127.0.0.1',
          port: BACKEND_PORT,
          path: '/__internal__/shutdown',
          method: 'POST',
          timeout: 1000
        }, () => resolve());
        req.on('error', () => resolve());
        req.end();
      });
    } catch {}
  }

  // 2. 等待进程退出
  const done = new Promise<void>((resolve) => {
    p.once('exit', () => resolve());
  });

  const timer = setTimeout(() => {
    // 3. 超时后使用 tree-kill 强制清理进程树
    const pid = p.pid;
    if (pid) {
      console.log(`[electron] Timeout, killing backend process tree (PID: ${pid})`);
      treeKill(pid, 'SIGKILL', (err) => {
        if (err) console.error('[electron] tree-kill failed:', err);
      });
    }
  }, timeoutMs);

  await done.catch(() => {});
  clearTimeout(timer);
  backendProc = null;

  // 4. 等待端口释放
  await waitPortRelease(oldPort);
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
