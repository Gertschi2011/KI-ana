const { app, BrowserWindow, ipcMain, shell, dialog, Notification } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Load local shell (tabs). Provide base URL via query param
  const base = process.env.KI_DESKTOP_BASE || 'https://localhost:8000';
  const indexPath = path.join(__dirname, 'index.html');
  win.loadFile(indexPath, { query: { base } });

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

app.whenReady().then(() => {
  createWindow();
  ipcMain.handle('kiana:openFile', async (event, opts) => {
    const res = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: opts && opts.filters ? opts.filters : [ { name: 'Images', extensions: ['png','jpg','jpeg','webp'] } ]
    });
    if (res.canceled) return { canceled: true };
    return { canceled: false, filePaths: res.filePaths };
  });
  ipcMain.handle('kiana:notify', async (event, payload) => {
    try{ new Notification({ title: payload.title||'Kiana', body: payload.body||'' }).show(); }catch{}
    return { ok: true };
  });
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
