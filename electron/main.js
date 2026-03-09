/**
 * Open Interface — Electron main process.
 *
 * Spawns the Python/Gradio backend as a child process, waits for the
 * server to become ready, then opens it in a BrowserWindow.
 */

const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const SERVER_PORT = 7860;
const SERVER_URL = `http://127.0.0.1:${SERVER_PORT}`;
const POLL_INTERVAL_MS = 500;
const MAX_WAIT_MS = 30000;

let mainWindow = null;
let serverProcess = null;

/**
 * Resolve the path to the bundled Python server executable.
 *
 * In development the executable lives at ``../dist/open-interface-server/``.
 * In a packaged Electron app it is placed under ``resources/server/``.
 */
function getServerPath() {
  const isPacked = app.isPackaged;
  if (isPacked) {
    return path.join(process.resourcesPath, 'server', getServerBinary());
  }
  // Development fallback
  return path.join(__dirname, '..', 'dist', 'open-interface-server', getServerBinary());
}

function getServerBinary() {
  return process.platform === 'win32'
    ? 'Open Interface.exe'
    : 'Open Interface';
}

function startServer() {
  const serverPath = getServerPath();
  console.log(`Starting server: ${serverPath}`);

  serverProcess = spawn(serverPath, [], {
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env },
  });

  serverProcess.stdout.on('data', (data) => {
    console.log(`[server] ${data}`);
  });

  serverProcess.stderr.on('data', (data) => {
    console.error(`[server] ${data}`);
  });

  serverProcess.on('close', (code) => {
    console.log(`Server exited with code ${code}`);
    serverProcess = null;
  });
}

/**
 * Poll the Gradio server until it responds or timeout is reached.
 */
function waitForServer() {
  return new Promise((resolve, reject) => {
    const start = Date.now();

    function poll() {
      const req = http.get(SERVER_URL, (res) => {
        resolve();
        res.resume();
      });

      req.on('error', () => {
        if (Date.now() - start > MAX_WAIT_MS) {
          reject(new Error('Server did not start in time'));
        } else {
          setTimeout(poll, POLL_INTERVAL_MS);
        }
      });

      req.end();
    }

    poll();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    title: 'Open Interface',
    icon: path.join(__dirname, '..', 'app', 'resources', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadURL(SERVER_URL);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  startServer();

  try {
    await waitForServer();
  } catch (err) {
    console.error(err.message);
    app.quit();
    return;
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
  }
});
