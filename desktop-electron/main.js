// KI_ana OS - Electron Main Process

const { app, BrowserWindow, Tray, Menu, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const Store = require('electron-store');
const { autoUpdater } = require('electron-updater');

// Configuration store
const store = new Store();

// Global references
let mainWindow = null;
let tray = null;
let backendProcess = null;

// Backend configuration
const BACKEND_PORT = store.get('backend_port', 8000);
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

// Create main window
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        icon: path.join(__dirname, 'assets/icon.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        },
        backgroundColor: '#1a1a2e',
        show: false
    });

    // Load dashboard
    mainWindow.loadURL(`${BACKEND_URL}/dashboard.html`);

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        
        // Check for updates
        if (!app.isPackaged) {
            console.log('Development mode - skipping auto-update');
        } else {
            autoUpdater.checkForUpdatesAndNotify();
        }
    });

    // Handle window close
    mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
        return false;
    });

    // Open external links in browser
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });
}

// Create system tray
function createTray() {
    tray = new Tray(path.join(__dirname, 'assets/tray-icon.png'));
    
    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'KI_ana OS',
            enabled: false
        },
        { type: 'separator' },
        {
            label: 'Show',
            click: () => {
                mainWindow.show();
            }
        },
        {
            label: 'Hide',
            click: () => {
                mainWindow.hide();
            }
        },
        { type: 'separator' },
        {
            label: 'Dashboard',
            click: () => {
                mainWindow.show();
                mainWindow.loadURL(`${BACKEND_URL}/dashboard.html`);
            }
        },
        {
            label: 'Settings',
            click: () => {
                mainWindow.show();
                mainWindow.loadURL(`${BACKEND_URL}/settings.html`);
            }
        },
        { type: 'separator' },
        {
            label: 'Restart Backend',
            click: () => {
                restartBackend();
            }
        },
        {
            label: 'Check for Updates',
            click: () => {
                autoUpdater.checkForUpdatesAndNotify();
            }
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                app.isQuitting = true;
                app.quit();
            }
        }
    ]);

    tray.setContextMenu(contextMenu);
    tray.setToolTip('KI_ana OS');

    // Show window on tray click
    tray.on('click', () => {
        mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    });
}

// Start backend server
function startBackend() {
    console.log('Starting KI_ana backend...');
    
    const backendPath = path.join(__dirname, '..', '.venv', 'bin', 'python');
    const appPath = path.join(__dirname, '..', 'netapi', 'app.py');
    
    backendProcess = spawn(backendPath, [
        '-m', 'uvicorn',
        'netapi.app:app',
        '--host', '0.0.0.0',
        '--port', BACKEND_PORT.toString()
    ], {
        cwd: path.join(__dirname, '..'),
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    backendProcess.stdout.on('data', (data) => {
        console.log(`Backend: ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`Backend Error: ${data}`);
    });

    backendProcess.on('close', (code) => {
        console.log(`Backend exited with code ${code}`);
        if (code !== 0 && !app.isQuitting) {
            // Auto-restart on crash
            setTimeout(() => {
                startBackend();
            }, 3000);
        }
    });
}

// Restart backend
function restartBackend() {
    if (backendProcess) {
        backendProcess.kill();
    }
    setTimeout(() => {
        startBackend();
    }, 1000);
}

// Stop backend
function stopBackend() {
    if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
    }
}

// Auto-updater events
autoUpdater.on('update-available', () => {
    mainWindow.webContents.send('update-available');
});

autoUpdater.on('update-downloaded', () => {
    mainWindow.webContents.send('update-downloaded');
});

// IPC handlers
ipcMain.handle('get-backend-url', () => {
    return BACKEND_URL;
});

ipcMain.handle('restart-backend', () => {
    restartBackend();
    return { success: true };
});

ipcMain.handle('get-app-version', () => {
    return app.getVersion();
});

ipcMain.handle('install-update', () => {
    autoUpdater.quitAndInstall();
});

// App lifecycle
app.whenReady().then(() => {
    // Start backend
    startBackend();
    
    // Wait for backend to start
    setTimeout(() => {
        createWindow();
        createTray();
    }, 3000);

    // macOS: Re-create window when dock icon is clicked
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// Quit when all windows are closed (except macOS)
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Cleanup on quit
app.on('before-quit', () => {
    app.isQuitting = true;
    stopBackend();
});

app.on('will-quit', () => {
    stopBackend();
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
});

console.log('KI_ana OS starting...');
console.log('Version:', app.getVersion());
console.log('Backend URL:', BACKEND_URL);
