const { contextBridge, ipcRenderer } = require('electron');
const fs = require('fs');

async function readAsDataURL(path){
  try{
    const buf = fs.readFileSync(path);
    const b64 = buf.toString('base64');
    // best-effort mime
    const ext = path.split('.').pop().toLowerCase();
    const mime = (ext === 'png') ? 'image/png' : (ext === 'webp') ? 'image/webp' : 'image/jpeg';
    return `data:${mime};base64,${b64}`;
  }catch{ return null; }
}

contextBridge.exposeInMainWorld('kianaDesktop', {
  version: '0.1.0',
  async openFile(opts){
    const res = await ipcRenderer.invoke('kiana:openFile', opts||{});
    if (!res || res.canceled || !Array.isArray(res.filePaths)) return { canceled: true };
    const paths = res.filePaths;
    const dataURLs = [];
    for (const p of paths){
      const d = await readAsDataURL(p);
      if (d) dataURLs.push({ name: p.split(/[\\/]/).pop(), dataURL: d });
    }
    return { canceled: false, files: dataURLs };
  },
  async notify(payload){
    return await ipcRenderer.invoke('kiana:notify', payload||{});
  },
  async ttsPlay(text){
    try{
      const u = new SpeechSynthesisUtterance(String(text||''));
      window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);
      return { ok: true };
    }catch{ return { ok:false } }
  },
  async ttsStop(){ try{ window.speechSynthesis.cancel(); return { ok:true } }catch{ return { ok:false } } }
});
