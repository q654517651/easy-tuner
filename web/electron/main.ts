import { app, BrowserWindow, ipcMain, Menu, nativeTheme, shell, nativeImage, dialog} from "electron";
import { spawn, exec } from "node:child_process";
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

// stopBackend 幂等控制
let isStoppingBackend = false;

// ---- 全局异常处理（确保任何未捕获的异常都能清理后端） ----
process.on('uncaughtException', async (error) => {
  console.error('[electron] Uncaught exception:', error);
  await stopBackend(true, 1500);
  app.exit(1);
});

process.on('unhandledRejection', async (reason) => {
  console.error('[electron] Unhandled rejection:', reason);
  await stopBackend(true, 1500);
  app.exit(1);
});

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
  win.on("close", async (event) => {
    // 阻止默认关闭行为，先停止后端
    if (backendProc) {
      event.preventDefault();
      console.log('[electron] Window closing, stopping backend...');
      await stopBackend(true, 2000);
      console.log('[electron] Backend stopped, closing window');
      // 后端停止后，真正关闭窗口
      win?.destroy();
    }
  });

  win.on("closed", () => {
    win = null;
  });
}

// 应用生命周期事件
app.whenReady().then(async () => {
  // 先创建窗口，让用户看到界面
  await createWindow();

  // 仅在打包后启动后端 EXE；开发态默认不启动（可通过环境变量开启）
  console.log(`[electron] isProd=${isProd}, app.isPackaged=${app.isPackaged}, ELECTRON_START_BACKEND=${process.env.ELECTRON_START_BACKEND}`);
  if (isProd || process.env.ELECTRON_START_BACKEND === '1') {
    console.log('[electron] Starting backend...');
    // 异步启动后端，不阻塞窗口显示
    startBackend().catch(err => {
      console.error('[electron] startBackend failed:', err);
      // 使用 dialog.showErrorBox（主进程 API）
      dialog.showErrorBox(
        'Backend Startup Failed',
        `Failed to start backend:\n${err.message}\n\nCheck console for details.`
      );
    });
  } else {
    console.log('[electron] Backend not started (development mode)');
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
ipcMain.handle("open-folder", async (_evt, { folderPath }: { folderPath: string }) => {
  try {
    // 直接使用前端传递的绝对路径
    const target = path.resolve(folderPath);

    // 检查目录是否存在
    if (!fs.existsSync(target)) {
      return { ok: false, error: `目录不存在: ${target}` };
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
 * 检查端口是否处于 LISTEN 状态（仅 Windows）
 */
async function isPortInUse(port: number): Promise<boolean> {
  if (process.platform !== 'win32') {
    // 非 Windows 系统使用原有的 socket 探测方式
    return new Promise((resolve) => {
      const server = http.createServer();
      server.once('error', () => resolve(true)); // 端口被占用
      server.once('listening', () => {
        server.close();
        resolve(false); // 端口可用
      });
      server.listen(port, '127.0.0.1');
    });
  }

  // Windows 使用 netstat 精确检查 LISTEN 状态
  return new Promise((resolve) => {
    exec(`netstat -ano -p TCP | findstr ":${port} " | findstr "LISTENING"`, (err: any, stdout: string) => {
      resolve(stdout.trim().length > 0);
    });
  });
}

/**
 * 探测可用端口（从 startPort 开始）
 */
async function findAvailablePort(startPort: number): Promise<number> {
  for (let port = startPort; port < startPort + 10; port++) {
    const inUse = await isPortInUse(port);
    if (!inUse) {
      console.log(`[electron] Port ${port} is available`);
      return port;
    } else {
      console.log(`[electron] Port ${port} is in use, trying next...`);
    }
  }
  throw new Error(`No available port found from ${startPort} to ${startPort + 9}`);
}

/**
 * 等待端口释放（使用 netstat 精确检查 LISTEN 状态）
 */
async function waitPortRelease(port: number): Promise<void> {
  const { pollInterval, maxWaitTime } = PORT_RELEASE_CONFIG;
  const deadline = Date.now() + maxWaitTime;

  while (Date.now() < deadline) {
    const inUse = await isPortInUse(port);

    if (!inUse) {
      console.log(`[electron] Port ${port} released`);
      return;
    }

    await new Promise(r => setTimeout(r, pollInterval));
  }

  console.warn(`[electron] Port ${port} still occupied after ${maxWaitTime}ms`);
}

async function startBackend() {
  console.log('[electron] ========================================');
  console.log('[electron] startBackend() called');
  console.log('[electron] ========================================');

  // 1. 探测可用端口
  console.log('[electron] [1/5] Finding available port...');
  try {
    BACKEND_PORT = await findAvailablePort(8000);
    console.log(`[electron]   ✓ Port: ${BACKEND_PORT}`);
  } catch (e) {
    const errMsg = `Failed to find available port: ${e}`;
    console.error(`[electron]   ✗ ${errMsg}`);
    throw new Error(errMsg);
  }

  // 2. 准备目录和路径
  console.log('[electron] [2/5] Preparing paths...');
  const exeDir = resourcesBackendDir();
  const resourcesDir = path.dirname(exeDir);
  const exePath = path.join(exeDir, 'EasyTunerBackend.exe');

  console.log(`[electron]   process.resourcesPath: ${process.resourcesPath}`);
  console.log(`[electron]   exeDir: ${exeDir}`);
  console.log(`[electron]   resourcesDir: ${resourcesDir}`);
  console.log(`[electron]   exePath: ${exePath}`);

  // 3. 检查 EXE 是否存在
  console.log('[electron] [3/5] Checking backend executable...');
  const exeExists = fs.existsSync(exePath);
  console.log(`[electron]   exists: ${exeExists}`);

  if (!exeExists) {
    // 列出 backend 目录内容，帮助调试
    try {
      if (fs.existsSync(exeDir)) {
        const files = fs.readdirSync(exeDir);
        console.log(`[electron]   Files in ${exeDir}:`, files);
      } else {
        console.log(`[electron]   Directory does not exist: ${exeDir}`);
      }
    } catch (listErr) {
      console.error(`[electron]   Failed to list directory:`, listErr);
    }

    const errMsg = `Backend executable not found: ${exePath}`;
    console.error(`[electron]   ✗ ${errMsg}`);
    throw new Error(errMsg);
  }

  // 4. Spawn 后端进程
  console.log('[electron] [4/5] Spawning backend process...');
  try {
    // 设置默认 workspace 路径（用户数据目录）
    const defaultWorkspace = path.join(app.getPath('userData'), 'workspace');
    
    backendProc = spawn(exePath, [], {
      cwd: resourcesDir,  // 工作目录设为 resources/
      stdio: 'pipe',      // 捕获标准输入输出（调试用）
      detached: false,    // 不创建独立进程组，确保父进程退出时子进程能被清理
      windowsHide: true,  // Windows 下隐藏控制台窗口
      windowsVerbatimArguments: true,  // Windows 命令行参数原样传递
      env: {
        ...process.env,
        BACKEND_PORT: String(BACKEND_PORT),
        TAGTRAGGER_ROOT: resourcesDir,  // 明确指定项目根
        DEFAULT_WORKSPACE: defaultWorkspace,  // 传递默认 workspace 路径（打包环境使用）
        ELECTRON_PPID: String(process.pid),  // 传递父进程 PID（用于后端自杀检测）
        ELECTRON_START_TIME: String(Date.now()),  // 传递启动时间戳
      }
    });

    if (!backendProc.pid) {
      throw new Error('Spawn succeeded but PID is undefined');
    }

    console.log(`[electron]   ✓ Spawned successfully`);
    console.log(`[electron]   PID: ${backendProc.pid}`);
    console.log(`[electron]   killed: ${backendProc.killed}`);

    // 监听进程事件
    backendProc.on('error', (err) => {
      console.error('[electron] [backend] Process error event:', err);
      console.error(`[electron]   error.code: ${(err as any).code}`);
      console.error(`[electron]   error.message: ${err.message}`);
    });

    backendProc.on('exit', (code, signal) => {
      console.log(`[electron] [backend] Process exited: code=${code}, signal=${signal}`);
      backendProc = null;
    });

    backendProc.stdout?.on('data', d => {
      const text = d.toString().trim();
      console.log(`[backend stdout] ${text}`);
    });

    backendProc.stderr?.on('data', d => {
      const text = d.toString().trim();
      console.error(`[backend stderr] ${text}`);
    });

    // 5. 等待后端就绪
    console.log('[electron] [5/5] Waiting for backend to be ready...');
    await waitBackendReady();
    console.log('[electron]   ✓ Backend is ready!');

    // 6. 通知前端
    await win?.webContents.executeJavaScript(`window.__BACKEND_PORT__ = ${BACKEND_PORT};`);
    win?.webContents.send('backend:ready', { port: BACKEND_PORT });
    console.log('[electron] ========================================');
    console.log('[electron] Backend startup completed successfully');
    console.log('[electron] ========================================');

  } catch (spawnErr) {
    const errMsg = `Spawn failed: ${spawnErr}`;
    console.error(`[electron]   ✗ ${errMsg}`);
    throw new Error(errMsg);
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
 * 幂等设计：支持多次调用，防止重入
 */
async function stopBackend(graceful = true, timeoutMs = 2000) {
  // 幂等检查：如果正在停止或已无进程，直接返回
  if (isStoppingBackend) {
    console.log('[electron] stopBackend already in progress, skipping...');
    return;
  }

  const p = backendProc;
  if (!p || !p.pid) {
    console.log('[electron] No backend process to stop');
    return;
  }

  // 标记正在停止
  isStoppingBackend = true;
  const pid = p.pid;
  const oldPort = BACKEND_PORT;

  try {
    console.log(`[electron] Stopping backend (PID: ${pid}, graceful: ${graceful})`);

    // 1. 尝试优雅关闭
    if (graceful) {
      try {
        await new Promise<void>((resolve, reject) => {
          const req = http.request({
            hostname: '127.0.0.1',
            port: BACKEND_PORT,
            path: '/__internal__/shutdown',
            method: 'POST',
            timeout: 1000
          }, () => {
            console.log('[electron] Graceful shutdown request sent');
            resolve();
          });
          req.on('error', (err) => {
            console.log('[electron] Graceful shutdown request failed:', err.message);
            resolve(); // 失败也继续
          });
          req.setTimeout(1000, () => {
            req.destroy();
            resolve();
          });
          req.end();
        });
      } catch (err) {
        console.log('[electron] Graceful shutdown error:', err);
      }
    }

    // 2. 等待进程退出
    const done = new Promise<void>((resolve) => {
      p.once('exit', (code) => {
        console.log(`[electron] Backend process exited (code: ${code})`);
        resolve();
      });
    });

    const timer = setTimeout(() => {
      // 3. 超时后使用 tree-kill 强制清理进程树
      console.log(`[electron] Timeout (${timeoutMs}ms), force killing process tree (PID: ${pid})`);
      treeKill(pid, 'SIGKILL', (err) => {
        if (err) {
          console.error('[electron] tree-kill failed:', err);
        } else {
          console.log('[electron] Process tree killed successfully');
        }
      });
    }, timeoutMs);

    await done.catch(() => {});
    clearTimeout(timer);

    // 4. 等待端口释放
    console.log(`[electron] Waiting for port ${oldPort} to be released...`);
    await waitPortRelease(oldPort);
    console.log(`[electron] Port ${oldPort} released successfully`);
  } finally {
    // 5. 清理句柄（finally 确保必定执行）
    backendProc = null;
    isStoppingBackend = false;
    console.log('[electron] Backend cleanup complete');
  }
}

// ---- 应用退出路径统一处理 ----

// 优雅关闭标记（防止重复处理）
let isQuitting = false;

app.on('will-quit', async (event) => {
  if (isQuitting) return;

  event.preventDefault();
  isQuitting = true;

  console.log('[electron] Application quitting, stopping backend...');
  await stopBackend(true, 2000);
  console.log('[electron] Backend stopped, exiting application');

  app.exit(0);
});

// process.on('exit') 是同步的，不能使用 async/await
// 作为最后的兜底，尝试强制 kill（可能不会生效，因为 stopBackend 已经清理了）
process.on('exit', () => {
  if (backendProc?.pid) {
    console.log('[electron] process.exit hook: force killing backend');
    try {
      // Windows 不支持 SIGKILL，使用无参数的 kill() 强制终止
      if (process.platform === 'win32') {
        backendProc.kill();
      } else {
        backendProc.kill('SIGKILL');
      }
    } catch (e) {
      console.error('[electron] Failed to kill backend in exit hook:', e);
    }
  }
});

// SIGINT/SIGTERM 统一走 app.quit() 触发 will-quit
process.on('SIGINT', () => {
  console.log('[electron] Received SIGINT, quitting...');
  if (!isQuitting) {
    app.quit();
  }
});

process.on('SIGTERM', () => {
  console.log('[electron] Received SIGTERM, quitting...');
  if (!isQuitting) {
    app.quit();
  }
});

// ---------- 选择工作区对话框 ----------
ipcMain.handle('system:selectWorkspaceDialog', async () => {
  const res = await dialog.showOpenDialog({ properties: ['openDirectory', 'createDirectory'] });
  return { canceled: res.canceled, path: res.filePaths?.[0] || '' };
});
