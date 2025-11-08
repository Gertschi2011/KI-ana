// KI_ana OS - Preload Script (Bridge between Renderer and Main)

const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to renderer process
contextBridge.exposeInMainWorld('kianaOS', {
    // Backend
    getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
    restartBackend: () => ipcRenderer.invoke('restart-backend'),
    
    // App info
    getAppVersion: () => ipcRenderer.invoke('get-app-version'),
    
    // Updates
    onUpdateAvailable: (callback) => {
        ipcRenderer.on('update-available', callback);
    },
    onUpdateDownloaded: (callback) => {
        ipcRenderer.on('update-downloaded', callback);
    },
    installUpdate: () => ipcRenderer.invoke('install-update'),
    
    // Platform info
    platform: process.platform,
    arch: process.arch
});

console.log('KI_ana OS Preload loaded');
