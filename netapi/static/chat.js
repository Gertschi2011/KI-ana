  // Global debug overlay status helper (safe in all scopes)
  var setDebugStatus = (typeof setDebugStatus === 'function') ? setDebugStatus : function(msg, ok){
    try{
      var o = document.getElementById('debug-overlay');
      var s = document.getElementById('debug-status');
      if(!o || !s) return;
      o.style.display = 'block';
      s.textContent = String(msg||'');
      s.style.color = (ok===false)? 'red' : 'lime';
    }catch{}
  };

  // Build default follow-up suggestions when backend doesn't provide any
  function buildFollowUps(userText, aiReply){
    try{
      const u = String(userText||'');
      const r = String(aiReply||'');
      const pri = (lastTopic||'').trim();
      const topicBase = pri || u;
      const topic = (topicBase.length > 80 ? (topicBase.slice(0,77)+'…') : topicBase) || 'dem Thema';
      const lcu = u.toLowerCase();
      const lcr = r.toLowerCase();

      // Category heuristics
      const isHealth = /(gesund|medizin|symptom|diagnos|behandl|krank|arzt|therapie)/.test(lcu+lcr);
      const isTech   = /(code|api|programm|entwickl|bug|fehler|best practice|javascript|python|server|backend|frontend)/.test(lcu+lcr);
      const isFinance= /(preis|kosten|budget|rechnung|steuer|finanz|invest|rendite|kostenlos)/.test(lcu+lcr);
      const isTravel = /(reise|flug|hotel|route|visum|ticket|bahn|urlaub)/.test(lcu+lcr);
      const isHistory= /(geschichte|histor|jahr|krieg|epoche|antik|mittelalter)/.test(lcu+lcr);
      const isHowTo  = /(wie|anleitung|schritt|setup|install|konfig)/.test(lcu+lcr);

      let base = [];
      const persona = (typeof window !== 'undefined' && window.kianaPersona) ? String(window.kianaPersona) : '';
      if (isHealth){
        base = ['Symptome', 'Ursachen', 'Behandlung'];
      } else if (isTech){
        base = ['Codebeispiel', 'Best Practices', 'Häufige Fehler'];
      } else if (isFinance){
        base = ['Kostenaufschlüsselung', 'Alternativen vergleichen', 'Risiken & Hinweise'];
      } else if (isTravel){
        base = ['Route & Dauer', 'Beste Reisezeit', 'Budget & Tipps'];
      } else if (isHistory){
        base = ['Zeitleiste', 'Schlüsselpersonen', 'Kontext & Folgen'];
      } else if (isHowTo){
        base = ['Schritt‑für‑Schritt', 'Voraussetzungen', 'Fehlersuche'];
      } else {
        if (persona === 'kids'){
          base = ['Erzähl mir mehr', 'Einfach erklären', 'Ein Beispiel zeigen'];
        } else {
          base = [`Beispiele zu ${topic}`, 'Schritt‑für‑Schritt erklärt', 'Wichtigste Details vertiefen'];
        }

  // ---- Username helpers (for greeting/fallback) ----
  async function initUserIdentity(){
    try{
      const r = await fetch('/api/me', { credentials: 'include' });
      const data = await r.json().catch(()=>({}));
      if (data && data.auth && data.user){
        cachedUserName = data.user.username || data.user.email || null;
        try{ localStorage.setItem('kiana_username', cachedUserName || ''); }catch{}
        // store plan if provided
        try{ if (data.user.plan){ localStorage.setItem('kiana_plan', String(data.user.plan)); } }catch{}
        if (data.user.created_at){
          try{ localStorage.setItem('kiana_last_seen', String(data.user.created_at)); }catch{}
        }
      } else {
        cachedUserName = null;
        try{ localStorage.removeItem('kiana_username'); }catch{}
        try{ localStorage.removeItem('kiana_plan'); }catch{}
      }
    }catch{
      cachedUserName = null;
    }
  }

  function getGreetingByTime(name){
    try{
      const hour = new Date().getHours();
      if (hour < 12) return name ? `Guten Morgen ${name} ☀️` : 'Guten Morgen ☀️';
      if (hour < 18) return name ? `Hallo ${name} 👋 Wie läuft dein Tag bisher?` : 'Hallo 👋 Wie läuft dein Tag bisher?';
      return name ? `Schönen Abend, ${name} 🌙` : 'Schönen Abend 🌙';
    }catch{ return name ? `Hallo ${name} 👋` : 'Hallo 👋'; }
  }

  function showWelcomeMessage(){
    try{
      const chat = document.getElementById('chat');
      if (!chat) return;
      const name = (localStorage.getItem('kiana_username')||'').trim() || null;
      const plan = (localStorage.getItem('kiana_plan')||'').trim();
      let text = getGreetingByTime(name);
      if (plan) text += ` (Du nutzt aktuell den ${plan}-Plan 💜)`;
      text += ' Was interessiert dich heute?';
      const el = appendMsg('ai', text);
      try{ el?.classList?.add('welcome-msg'); el?.querySelector('.bubble')?.classList?.add('welcome-msg'); }catch{}
    }catch{}
  }

  // Debug overlay status helper
  function setDebugStatus(msg, ok=true){
    try{
      const o=document.getElementById('debug-overlay');
      const s=document.getElementById('debug-status');
      if(!o||!s) return;
      o.style.display='block';
      s.textContent=String(msg||'');
      s.style.color = ok ? 'lime' : 'red';
    }catch{}
  }

  // New: generic clickable toast
  function showToast(msg, link){
    try{
      const n = document.createElement('div');
      n.className = 'toast';
      if (link){ n.innerHTML = `<a href="${link}" target="_blank" style="color:#fff;text-decoration:none">${msg}</a>`; }
      else { n.textContent = msg; }
      document.body.appendChild(n);
      requestAnimationFrame(()=> n.classList.add('show'));
      setTimeout(()=>{ n.classList.remove('show'); setTimeout(()=> n.remove(), 250); }, 4000);
    }catch{}
  }

  // ---- Delta Viewer (Comparison UI) ----------------------------------------
  function parseComparisonSections(text){
    const res = { neu: [], diff: [], contra: [] };
    try{
      const t = String(text||'');
      // Split by known headers
      const parts = t.split(/\n(?=Neu:|Unterschiedlich:|Widersprüchlich:)/g);
      let current = null;
      for (let p of parts){
        const header = (p.match(/^(Neu|Unterschiedlich|Widersprüchlich):/)||[])[1];
        const body = p.replace(/^(Neu|Unterschiedlich|Widersprüchlich):\s*/,'');
        const items = body.split(/\n-\s+/g).map(x=>x.trim()).filter(Boolean);
        if (header === 'Neu') current = 'neu';
        else if (header === 'Unterschiedlich') current = 'diff';
        else if (header === 'Widersprüchlich') current = 'contra';
        if (!current) continue;
        // If first element still contains header label, clean it
        const clean = items.map(s => s.replace(/^Neu:\s*|^Unterschiedlich:\s*|^Widersprüchlich:\s*/,'')).filter(Boolean);
        res[current].push(...clean);
      }
    }catch{}
    return res;
  }

  function renderDeltaViewerIfComparison(meta, fullText){
    try{
      if (!meta || !meta.comparison) return;
      const chat = document.getElementById('chat');
      if (!chat) return;
      const wrap = chat.lastElementChild;
      if (!wrap || !wrap.classList.contains('msg') || !wrap.classList.contains('ai')) return;
      if (wrap.querySelector('.delta-viewer')) return; // already rendered
      const sections = parseComparisonSections(fullText);
      const hasAny = (sections.neu.length + sections.diff.length + sections.contra.length) > 0;
      if (!hasAny) return;
      const dv = document.createElement('div');
      dv.className = 'delta-viewer';
      function mkSec(title, cls, items){
        if (!items || !items.length) return null;
        const s = document.createElement('div');
        s.className = 'dv-sec ' + cls;
        const h = document.createElement('div'); h.className = 'dv-title'; h.textContent = title; s.appendChild(h);
        const ul = document.createElement('ul');
        for (const it of items){ const li = document.createElement('li'); li.textContent = it; ul.appendChild(li); }
        s.appendChild(ul);
        return s;
      }
      const secNeu = mkSec('Neu', 'neu', sections.neu);
      const secDiff = mkSec('Unterschiedlich', 'diff', sections.diff);
      const secContra = mkSec('Widersprüchlich', 'contra', sections.contra);
      for (const s of [secNeu, secDiff, secContra]){ if (s) dv.appendChild(s); }
      wrap.appendChild(dv);
    }catch{}
  }

  // ---- Meta badges (Fallback/Origin/Delta) ----
  function addMetaBadgesToLastAI(meta){
    try{
      if (!chatEl) return;
      const wrap = chatEl.lastElementChild;
      if (!wrap || !wrap.classList.contains('msg') || !wrap.classList.contains('ai')) return;
      // badges row
      let row = wrap.querySelector('.meta.badges');
      if (!row){
        row = document.createElement('div');
        row.className = 'meta badges';
        wrap.appendChild(row);
      }
      // Fallback badge
      if (meta && meta.safety_valve){
        const b = document.createElement('span'); b.className = 'badge fallback'; b.textContent = 'Fallback'; row.appendChild(b);
      }
      // Origin badge
      const origin = (meta && meta.origin) ? String(meta.origin) : '';
      if (origin){
        const b = document.createElement('span');
        if (origin === 'web'){ b.className = 'badge origin-web'; b.textContent = '🌐 Web'; b.title = 'Quelle: Web'; }
        else if (origin === 'memory'){ b.className = 'badge origin-memory'; b.textContent = '📚 Memory'; b.title = 'Quelle: Memory'; }
        else { b.className = 'badge origin-mixed'; b.textContent = '🔀 Mixed'; b.title = 'Quelle: Web + Memory'; }
        // Neu: explizite Tooltips setzen (CSS zeigt diese per :hover an)
        try{ b.classList.add('source-badge'); }catch{}
        try{
          if (origin === 'memory') { b.dataset.tooltip = '🧠 Memory – gelernt aus Wissen'; }
          if (origin === 'web') { b.dataset.tooltip = '🌐 Web – externe Quelle'; }
          if (origin === 'mixed') { b.dataset.tooltip = '🔀 Memory + Web kombiniert'; }
          if (origin === 'unknown') { b.dataset.tooltip = '❓ Unbekannte Quelle'; }
        }catch{}
        row.appendChild(b);
      }
      // Delta note (under badges)
      const delta = (meta && meta.delta_note) ? String(meta.delta_note) : '';
      if (delta){
        const d = document.createElement('div'); d.className = 'meta delta-note'; d.textContent = delta; wrap.appendChild(d);
      }
    }catch{}
  }

  // ---- Natural formatter for AI answers (plain text + optional details button) ----
  function applyNaturalFormat(meta, fullText){
    try{
      const wrap = document.getElementById('chat')?.lastElementChild || null;
      if (!wrap || !wrap.classList || !wrap.classList.contains('msg') || !wrap.classList.contains('ai')) return;
      const contentEl = wrap.querySelector('.content') || wrap;
      if (!contentEl) return;

      // Clean technical noise (repeat aggressively)
      let cleaned = String(fullText||'');
      // Normalize bullets (remove common bullet prefixes entirely)
      cleaned = cleaned.replace(/(^|\n)\s*[•\-\u2022\*]\s*/g, '$1');
      // Remove "Kernpunkte:" headings and their immediate lines
      cleaned = cleaned.replace(/(^|\n)\s*Kernpunkte:?[^\n]*\n?/gi, '$1');
      // Remove any Wissensblock IDs or mentions
      cleaned = cleaned.replace(/(^|\n)\s*Wissensblock[^\n]*\n?/gi, '$1');
      // Remove repeated scaffolding like "Hier ist, was ich zu ... weiß"
      cleaned = cleaned.replace(/Hier\s+ist,\s*was\s+ich\s+zu\s+[^\n]*?\s+weiß:?/gi, '');
      cleaned = cleaned.replace(/(^|\n)\s*Hier\s+ist,\s*was\s+ich\s+zu\s+[^\n]*\n?/gi, '$1');
      // Remove echoed question lines like "Was weißt du über ...?"
      cleaned = cleaned.replace(/(^|\n)\s*Was\s+weißt\s+du\s+über[^\n]*\?\s*/gi, '$1');
      // Collapse multiple blank lines and whitespace
      cleaned = cleaned.replace(/[\t ]+/g, ' ');
      cleaned = cleaned.replace(/\n{2,}/g, '\n');
      cleaned = cleaned.trim();

      if (!cleaned){ cleaned = String(fullText||'').trim(); }
      if (!cleaned){ cleaned = '…'; }

      // Style switch: natural (default), formal, concise
      try{
        const style = (localStorage.getItem('kiana_style')||'natural').toLowerCase();
        if (style === 'concise'){
          // Intelligent short summary: pick 1–2 best sentences
          const sentences = cleaned.replace(/\s+/g,' ').split(/(?<=[.!?])\s+/).filter(Boolean);
          let pick = sentences.slice(0,2).join(' ').trim();
          if (pick.length > 280) { pick = sentences[0]; }
          if (pick && !/[.!?]$/.test(pick)) pick += '.';
          cleaned = pick || cleaned;
        } else if (style === 'formal'){
          // Light structure: optional headings + max 3 sentences per paragraph
          const sentences = cleaned.replace(/\s+/g,' ').split(/(?<=[.!?])\s+/).filter(Boolean);
          if (sentences.length > 5){
            const bg = sentences.slice(0, Math.min(3, sentences.length));
            const rem = sentences.slice(bg.length);
            const det = rem.slice(0, Math.min(3, rem.length));
            const sum = rem.slice(det.length).slice(-2); // last 0-2
            const blocks = [];
            if (bg.length) blocks.push({ title:'Hintergrund', text: bg.join(' ') });
            if (det.length) blocks.push({ title:'Details', text: det.join(' ') });
            if (sum.length) blocks.push({ title:'Zusammenfassung', text: sum.join(' ') });
            contentEl.innerHTML = blocks.map(b=>`<h4 style=\"margin:.4em 0 .2em\">${escapeHTML(b.title)}</h4><p>${escapeHTML(b.text)}</p>`).join('');
          } else {
            // Up to 3 sentences per paragraph
            const paras = [];
            for (let i=0; i<sentences.length; i+=3){ paras.push(sentences.slice(i,i+3).join(' ')); }
            contentEl.innerHTML = paras.map(p=>`<p>${escapeHTML(p)}</p>`).join('');
          }
        } else {
          // natural (default)
          contentEl.textContent = cleaned;
        }
      }catch{ contentEl.textContent = cleaned; }

      // Optional details button
      try{
        const memIds = Array.isArray(meta?.memory_ids) ? meta.memory_ids : [];
        if (memIds.length){
          const div = document.createElement('div');
          div.style.marginTop = '6px';
          const a = document.createElement('a');
          a.className = 'details-button';
          a.href = '/static/viewer.html?highlight=' + encodeURIComponent(String(memIds[0]));
          a.target = '_blank'; a.rel = 'noopener';
          a.textContent = 'ℹ️ Details im Wissen';
          div.appendChild(a);
          // append into message container after content
          wrap.appendChild(div);
        }
      }catch{}

      // Speak if enabled
      try{ speakText(cleaned); }catch{}
    }catch{}
  }

  // ---- Browser error telemetry (rate-limited) ----
  (function initTelemetry(){
    try{
      const sent = new Map(); // key -> lastTs
      const RATE_WINDOW_MS = 60 * 1000; // 1 min per key
      function keyOf(msg, url){
        try{ return (String(msg||'').slice(0,160)+'|'+String(url||'').slice(0,120)); }catch{ return String(Date.now()); }
      }
      async function send(payload){
        try{
          await fetch('/api/telemetry/error', { method:'POST', credentials:'include', headers: { 'Content-Type':'application/json' }, body: JSON.stringify(payload) });
        }catch{}
      }
      window.addEventListener('error', (ev)=>{
        try{
          const msg = (ev && ev.message) || 'Script error';
          const src = (ev && ev.filename) || location.pathname;
          const k = keyOf(msg, src);
          const now = Date.now();
          if (sent.has(k) && (now - (sent.get(k)||0) < RATE_WINDOW_MS)) return;
          sent.set(k, now);
          send({ message: String(msg).slice(0,500), url: String(src).slice(0,400), stack: (ev && ev.error && String(ev.error.stack||'').slice(0,4000)) || '' });
        }catch{}
      });
      window.addEventListener('unhandledrejection', (ev)=>{
        try{
          const reason = ev && ev.reason ? (ev.reason.message || ev.reason) : 'unhandledrejection';
          const msg = String(reason).slice(0,500);
          const src = location.pathname;
          const k = keyOf(msg, src);
          const now = Date.now();
          if (sent.has(k) && (now - (sent.get(k)||0) < RATE_WINDOW_MS)) return;
          sent.set(k, now);
          const stack = (ev && ev.reason && ev.reason.stack) ? String(ev.reason.stack).slice(0,4000) : '';
          send({ message: msg, url: src, stack });
        }catch{}
      });
    }catch{}
  })();

  // Load dynamic config (e.g., upgrade URL)
  async function loadSystemConfig(){
    try{
      const r = await fetch('/api/system/config', { credentials:'include' });
      const j = await r.json().catch(()=>({}));
      if (r.ok && j && j.upgrade_url){ upgradeUrl = String(j.upgrade_url); }
    }catch{}
  }
      }

  function renderTtsPrompt(text){
    try{
      if (!text || !text.trim()) return;
      const el = appendMsg('system', 'Vorlesen? <button class="btn" id="ttsPlay">▶️</button> <button class="btn" id="ttsStop">⏹</button>');
      if (el){
        const c = el.querySelector('.content');
        if (c){ c.innerHTML = 'Vorlesen? <button class="btn" id="ttsPlay">▶️</button> <button class="btn" id="ttsStop">⏹</button>'; }
        el.querySelector('#ttsPlay')?.addEventListener('click', ()=>{
          try{ window.parent && window.parent.postMessage({ type:'tts', action:'play', text }, '*'); }catch{}
        });
        el.querySelector('#ttsStop')?.addEventListener('click', ()=>{
          try{ window.parent && window.parent.postMessage({ type:'tts', action:'stop' }, '*'); }catch{}
        });
      }
    }catch{}
  }

  // ---- Electron postMessage integration ----
  function dataURLtoBlob(dataURL){
    try{
      const parts = dataURL.split(',');
      const meta = parts[0];
      const b64 = parts[1];
      const mime = (meta.match(/data:(.*?);base64/)||[])[1] || 'application/octet-stream';
      const bin = atob(b64);
      const len = bin.length;
      const bytes = new Uint8Array(len);
      for (let i=0;i<len;i++){ bytes[i] = bin.charCodeAt(i); }
      return new Blob([bytes], { type: mime });
    }catch{ return null; }
  }

  async function uploadAnalyzeImage(name, dataURL){
    try{
      const blob = dataURLtoBlob(dataURL);
      if (!blob){ appendMsg('system', `Bild ${name}: ungültiges Format`); return; }
      const fd = new FormData();
      const file = new File([blob], name || 'image', { type: blob.type });
      fd.append('file', file);
      const r = await fetch('/api/media/image/analyze', { method:'POST', body: fd, credentials:'include' });
      const js = await r.json().catch(()=>({ ok:false }));
      if (!r.ok || !js || js.ok===false){ appendMsg('system', `Analyse fehlgeschlagen für ${name}`); return; }
      const avg = js.avg_color ? `[#${js.avg_color.map(x=>('0'+x.toString(16)).slice(-2)).join('')}]` : '';
      const info = `Bild: ${name}\nFormat: ${js.format||'?'} ${js.width||'?'}×${js.height||'?'} ${avg}`;
      const el = appendMsg('system', `${info}\n\n<img alt="thumb" style="max-width:200px;border:1px solid #eee;border-radius:6px" />`);
      try{ if (el){ const c = el.querySelector('.content'); if (c){ c.innerHTML = `${info.replace(/\n/g,'<br>')}<br><br><img alt="thumb" style="max-width:200px;border:1px solid #eee;border-radius:6px" src="${dataURL}">`; } } }catch{}
    }catch{ appendMsg('system', `Analyse fehlgeschlagen für ${name}`); }
  }

  window.addEventListener('message', (ev)=>{
    try{
      const data = ev.data || {};
      if (data && data.type === 'openFile' && Array.isArray(data.files)){
        appendMsg('system', `📷 ${data.files.length} Bild(er) empfangen – starte Analyse…`);
        data.files.forEach(f=>{
          if (!f || !f.dataURL) return;
          uploadAnalyzeImage(f.name||'Bild', f.dataURL);
        });
      }
    }catch{}
  });

  // Bind mic button if present
  window.addEventListener('DOMContentLoaded', ()=>{
    try{
      const mic = document.getElementById('micBtn') || document.getElementById('mic-btn');
      if (mic){
        mic.addEventListener('click', startVoiceInput);
        // If STT available, show mic button
        try{ if (typeof recognizer !== 'undefined' && recognizer){ mic.style.display = 'inline-block'; } }catch{}
      }
    }catch{}
  });

  async function sendFeedback(status){
    try{
      const tools = Array.isArray(window.__last_tools_used) ? window.__last_tools_used : [];
      await fetch('/api/chat/feedback', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: '', status, tools })
      });
      appendMsg('system', status === 'up' ? 'Danke für dein Feedback 👍' : 'Danke für dein Feedback 👎');
    }catch{}
  }

  function renderFeedbackPrompt(){
    try{
      const el = appendMsg('system', 'War das hilfreich? <button class="btn" id="fbUp">👍</button> <button class="btn" id="fbDown">👎</button>');
      if (el){
        const c = el.querySelector('.content');
        if (c){ c.innerHTML = 'War das hilfreich? <button class="btn" id="fbUp">👍</button> <button class="btn" id="fbDown">👎</button>'; }
        el.querySelector('#fbUp')?.addEventListener('click', ()=> sendFeedback('up'));
        el.querySelector('#fbDown')?.addEventListener('click', ()=> sendFeedback('down'));
      }
    }catch{}
  }

  // ---- STT (Mic) ----
  async function startRecording(){
    try{
      if (isRecording) return;
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRec = new MediaRecorder(mediaStream);
      chunks = [];
      mediaRec.ondataavailable = (e)=>{ if (e.data && e.data.size>0) chunks.push(e.data); };
      mediaRec.onstop = async ()=>{
        try{
          const blob = new Blob(chunks, { type: 'audio/webm' });
          const fd = new FormData();
          const langSel = document.querySelector('#language');
          const lang = (langSel && langSel.value) ? langSel.value : 'de-DE';
          fd.append('audio', new File([blob], 'speech.webm', { type: 'audio/webm' }));
          const res = await fetch('/api/stt/recognize', { method: 'POST', body: fd, credentials: 'include' });
          const data = await res.json().catch(()=>({}));
          if (res.ok && data && data.ok && data.text){
            if (msgEl) {
              const sep = msgEl.value && !msgEl.value.endsWith(' ')? ' ' : '';
              msgEl.value = (msgEl.value || '') + sep + data.text;
              msgEl.focus();
            }
          } else {
            appendMsg('system', 'Spracherkennung nicht verfügbar oder fehlgeschlagen.');
          }
        }catch{
          appendMsg('system', 'Spracherkennung fehlgeschlagen.');
        } finally {
          try{ mediaStream.getTracks().forEach(t=>t.stop()); }catch{}
          mediaStream = null; mediaRec = null; chunks = []; isRecording = false;
          const micBtn = document.querySelector('#micBtn'); if (micBtn) micBtn.textContent = '🎤';
        }
      };
      mediaRec.start(); isRecording = true;
      const micBtn = document.querySelector('#micBtn'); if (micBtn) { micBtn.textContent = '⏺️'; micBtn.title='Aufnahme läuft – zum Stoppen klicken'; }
    }catch{
      appendMsg('system', 'Kein Mikrofonzugriff. Bitte Berechtigungen prüfen.');
    }
  }

  function stopRecording(){
    try{ if (mediaRec && isRecording) mediaRec.stop(); }catch{}
  }

  // ---- TTS ----
  async function maybeSpeak(text){
    try{
      const ttsToggle = document.querySelector('#ttsToggle');
      const voiceSel = document.querySelector('#voice');
      const langSel = document.querySelector('#language');
      const on = !!(ttsToggle && ttsToggle.checked);
      const voice = (voiceSel && voiceSel.value) ? voiceSel.value : 'auto';
      const lang = (langSel && langSel.value) ? langSel.value : 'de-DE';
      if (!on) return;
      const preview = String(text||'').slice(0, 650);
      if (voice === 'elevenlabs'){
        const url = `/api/elevenlabs/speak?text=${encodeURIComponent(preview)}&lang=${encodeURIComponent(lang)}`;
        const aud = new Audio(url);
        ttsAudio = aud;
        isSpeaking = true;
        aud.onended = ()=>{ isSpeaking=false; };
        aud.play().catch(()=>{ isSpeaking=false; });
      } else if ('speechSynthesis' in window) {
        const u = new SpeechSynthesisUtterance(preview);
        u.lang = lang;
        window.speechSynthesis.cancel();
        isSpeaking = true;
        u.onend = ()=>{ isSpeaking=false; };
        window.speechSynthesis.speak(u);
      }
    }catch{}
  }

  function stopSpeaking(){
    try{ if (ttsAudio){ ttsAudio.pause(); ttsAudio.currentTime=0; } }catch{}
    try{ if ('speechSynthesis' in window){ window.speechSynthesis.cancel(); } }catch{}
    isSpeaking = false;
  }

  function extractTopicClient(txt){
    try{
      const s = String(txt||'');
      const rx = /\b(?:über|zu|von)\s+([a-z0-9äöüß +\-_/]{3,})$|^(?:was ist|erkläre|erklärung|thema|lerne[nr]?|kannst du).*?\b([a-z0-9äöüß +\-_/]{3,})/i;
      const m = s.match(rx);
      let cand = (m && (m[1]||m[2])||'').trim();
      cand = cand.replace(/[^a-z0-9äöüß +\-_/]/ig,' ').replace(/\s{2,}/g,' ').trim();
      if (cand.length>80) cand = cand.slice(0,80).replace(/\s+\S*$/,'');
      return cand;
    }catch{ return ''; }
  }

  function addFeedbackControls(msgWrap){
    try{
      if (!msgWrap || !msgWrap.classList || !msgWrap.classList.contains('msg')) return;
      if (msgWrap.querySelector('.fb-row')) return; // once
      const row = document.createElement('div');
      row.className = 'fb-row';
      row.style.cssText = 'display:flex;gap:8px;align-items:center;margin-top:6px;opacity:.8;font-size:12px;';
      const lab = document.createElement('span'); lab.textContent = 'War das hilfreich?';
      const up = document.createElement('button'); up.type='button'; up.textContent='👍'; up.className='fb-btn';
      const dn = document.createElement('button'); dn.type='button'; dn.textContent='👎'; dn.className='fb-btn';
      const disable = ()=>{ up.disabled = true; dn.disabled = true; up.style.opacity=dn.style.opacity='0.6'; };
      async function sendFeedback(status){
        try{
          const txt = (msgWrap.querySelector('.bubble')?.textContent||'').trim().slice(0,2000);
          await fetch('/api/chat/feedback', {
            method: 'POST', credentials: 'include', headers: { 'Content-Type':'application/json' },
            body: JSON.stringify({ message: txt, status })
          });
        }catch{}
      // store last AI text for TTS
      try{ if (data.reply) window.__last_ai_text = String(data.reply); }catch{}
      }
      async function rateMemory(score){
        try{
          const raw = msgWrap.dataset.memoryIds ? JSON.parse(msgWrap.dataset.memoryIds) : [];
          const ids = Array.isArray(raw) ? raw.slice(0,5) : [];
          await Promise.all(ids.map(id => fetch('/api/memory/rate', { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ id, score, comment: '' }) }))); 
        }catch{}
      }
      up.addEventListener('click', async ()=>{ disable(); await sendFeedback('ok'); await rateMemory(1.0); try{ toast('Danke!'); }catch{} });
      dn.addEventListener('click', async ()=>{ disable(); await sendFeedback('wrong'); await rateMemory(0.0); try{ toast('Danke für dein Feedback!'); }catch{} });
      row.appendChild(lab); row.appendChild(up); row.appendChild(dn);
      msgWrap.appendChild(row);
    }catch{}
  }

      // ensure uniqueness and trim
      return Array.from(new Set(base.map(s => String(s).trim()))).slice(0,3);
    }catch{ return ['Beispiele zeigen','Schritt‑für‑Schritt','Details vertiefen']; }
  }

  // Quick reply click handler (used by generated follow-ups)
  function onQuickReplyClick(text){
    try{
      if (!text) return;
      const input = document.getElementById('msg');
      if (input){ input.value = text; }
      const send = document.getElementById('send');
      if (send) send.click();
    }catch{}
  }

  // Render Quick Reply buttons (⚖️ Vergleiche, 📑 Details) if follow-up question detected
  function renderQuickRepliesIfNeeded(meta){
    try{
      const askCompare = !!(meta && meta.ask_compare);
      const askDetails = !!(meta && meta.ask_details);
      if (!askCompare && !askDetails) return;
      if (!chatEl) return;
      const wrap = chatEl.lastElementChild;
      if (!wrap || !wrap.classList.contains('msg') || !wrap.classList.contains('ai')) return;
      if (wrap.querySelector('.qr-row')) return; // already shown
      const row = document.createElement('div');
      row.className = 'qr-row';
      row.style.cssText = 'display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap;';
      const lab = document.createElement('span'); lab.textContent = 'Schnellantworten:'; lab.style.opacity='.8'; lab.style.fontSize='12px';
      row.appendChild(lab);
      function mkBtn(title, text){
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn';
        b.textContent = title;
        b.addEventListener('click', ()=>{ try{ row.remove(); }catch{}; onQuickReplyClick(text); });
        return b;
      }
      if (askCompare){ row.appendChild(mkBtn('⚖️ Vergleiche', 'ja, vergleiche')); }
      if (askDetails){ row.appendChild(mkBtn('🔍 Mehr Infos', 'zeige details')); }
      wrap.appendChild(row);
    }catch{}
  }
  (() => {
  // ---------- DOM ----------
  const $ = (sel, p = document) => p.querySelector(sel);
  const chatEl = $('#chat');
  const typingEl = $('#typing');
  const msgEl = $('#msg');
  const sendBtn = $('#send');
  const ttsToggle = $('#ttsToggle');
  const webAllowToggle = $('#webAllowToggle');
  const chainToggle = $('#chainToggle');
  const agentToggle = $('#agentToggle');
  const factToggle = $('#factToggle');
  const counterToggle = $('#counterToggle');
  const delibToggle = $('#delibToggle');
  const critiqueToggle = $('#critiqueToggle');
  const micBtn = $('#micBtn');
  const attachBtn = $('#attachBtn');
  const attachInput = $('#attachInput');
  const attachmentsInfo = $('#attachmentsInfo');
  const tabsContainer = $('#tabs');
  const chatTab = $('#chatTab');
  const addressBookTab = $('#addressBookTab');
  const addressBookContent = $('#addressBookContent');
  const addressBookSearch = $('#addressBookSearch');
  const addressBookList = $('#addressBookList');
  const jumpBottomBtn = $('#jumpBottom');
  let pendingFiles = [];
  let currentConvId = null; // Track current conversation ID
  // Sidebar & conversations
  const convListEl = $('#convList');
  const newConvBtn = $('#newConv');
  const selectAllConvsBtn = $('#selectAllConvs');
  const deleteSelectedConvsBtn = $('#deleteSelectedConvs');
  const toggleSidebarBtn = $('#toggleSidebar');
  const closeSidebarBtn = $('#closeSidebar');
  const sidebarBackdrop = $('#sidebarBackdrop');

  // Settings modal + controls
  const openSettingsBtn = $('#openSettings');
  const settingsModal = $('#settingsModal');
  const closeSettingsBtn = $('#closeSettings');
  const cancelSettingsBtn = $('#cancelSettings');
  const settingsForm = $('#settingsForm');
  const llmStatusEl = $('#llmStatus');
  const personaSel = $('#persona');
  const languageSel = $('#language');
  const voiceSel = $('#voice');
  const streamingChk = $('#streaming');
  const userColorInp = $('#userColor');
  const aiColorInp = $('#aiColor');
  const answerStyleSel = $('#answerStyle');
  const bulletCountInp = $('#bulletCount');
  const answerLogicSel = $('#answerLogic');
  const answerFormatSel = $('#answerFormat');
  const autonomySel = $('#autonomy');
  const ethicsSel = $('#ethicsFilter');
  const allowNetChk = $('#allowNet');
  const activeSubkisSel = $('#activeSubkis');

  // ---------- State ----------
  const STORAGE_KEY = 'kiana.settings.v4';
  const STYLE_PRESET_KEY = 'kiana.style.preset.v1';
  const CONVS_KEY = 'kiana.convs.v1';
  const ACTIVE_KEY = 'kiana.activeConv.v1';
  const CONV_PREFIX = 'kiana.conv.';
  const PREF_PREFIX = 'kiana.conv.prefs.'; // pro‑Unterhaltung‑Voreinstellungen
  let settings = loadSettings();
  let recognition = null;
  let speakingUtterance = null;
  let currentES = null;          // aktive EventSource-Instanz
  let previewEl = null;          // laufende KI-Bubble beim Stream
  let bootedGreeting = false;
  let sendWatch = null;          // watchdog timer for stalled requests
  let convs = loadConvs();
  let activeConv = loadActiveConv();
  let isAuth = false;
  let sending = false;           // Doppel-Send verhindern
  let selectedConvs = new Set(); // IDs der markierten Unterhaltungen
  let quickReplies = [];         // Current quick replies to show
  let addressBookData = [];      // Cached address book data
  let lastCid = null;            // Correlation ID from SSE stream
  let autoScroll = true;         // keep view pinned to bottom unless user scrolls up
  let scrollHintShown = false;   // show toast once when user scrolls up
  let lastTopic = '';
  let mediaRec = null;
  let mediaStream = null;
  let chunks = [];
  let isRecording = false;
  let ttsAudio = null;
  let isSpeaking = false;
  let upgradeUrl = '/static/upgrade.html';
  let cachedUserName = null; // personalized greetings

  // ---- Voice: STT (SpeechRecognition) & TTS (SpeechSynthesis) ----
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  try{
    if (SpeechRecognition) {
      recognizer = new SpeechRecognition();
      // Map stored lang to BCP-47
      const st = (localStorage.getItem('kiana_lang')||'de').toLowerCase();
      const lang = st === 'en' ? 'en-US' : st === 'de' ? 'de-DE' : st === 'ro' ? 'ro-RO' : (st.includes('-')? st : 'de-DE');
      recognizer.lang = lang;
      recognizer.interimResults = false;
      recognizer.maxAlternatives = 1;
    }
  }catch{}

  function startVoiceInput(){
    try{
      if (!recognizer){ appendMsg('system', '🎤 Sprachaufnahme wird nicht unterstützt.'); return; }
      recognizer.start();
      let listenEl = null;
      try{ listenEl = appendMsg('system', '🎤 … hört zu'); }catch{}
      recognizer.onresult = (e)=>{
        try{
          const text = e && e.results && e.results[0] && e.results[0][0] && e.results[0][0].transcript ? String(e.results[0][0].transcript) : '';
          const input = document.getElementById('msg');
          if (input){ input.value = text; }
          try{ onSend && onSend(); }catch{}
        }catch{}
        try{ if (listenEl && listenEl.remove) listenEl.remove(); }catch{}
      };
      recognizer.onerror = (e)=>{ try{ appendMsg('system', '⚠️ Sprachfehler: ' + (e && e.error ? e.error : 'unbekannt')); }catch{} try{ if (listenEl && listenEl.remove) listenEl.remove(); }catch{} };
      recognizer.onend = ()=>{ try{ if (listenEl && listenEl.remove) listenEl.remove(); }catch{} };
    }catch{ appendMsg('system', '⚠️ Sprachaufnahme fehlgeschlagen.'); }
  }

  function speakText(text){
    try{
      if (!('speechSynthesis' in window)) return;
      if (localStorage.getItem('kiana_tts') !== 'on') return;
      const utter = new SpeechSynthesisUtterance(String(text||''));
      const st = (localStorage.getItem('kiana_lang')||'de').toLowerCase();
      utter.lang = st === 'en' ? 'en-US' : st === 'de' ? 'de-DE' : st === 'ro' ? 'ro-RO' : (st.includes('-')? st : 'de-DE');
      try{
        const pref = localStorage.getItem('kiana_tts_voice') || '';
        const voices = window.speechSynthesis.getVoices() || [];
        const match = voices.find(v => v.name === pref || v.voiceURI === pref || v.lang === pref);
        if (match) utter.voice = match;
      }catch{}
      utter.pitch = 1; utter.rate = 1; utter.volume = 1;
      window.speechSynthesis.speak(utter);
    }catch{}
  }

  // ---- Kids preset helpers ----
  function _computeAge(b){
    try{
      if (!b) return null;
      const t = String(b).trim().replaceAll('/', '-');
      const [y,m,d] = t.split('-').map(x=>parseInt(x,10));
      if (!y||!m||!d) return null;
      const bd = new Date(y, Math.max(0,Math.min(11,(m-1))), Math.max(1,Math.min(31,d)));
      const today = new Date();
      let age = today.getFullYear() - bd.getFullYear();
      const mDiff = today.getMonth() - bd.getMonth();
      if (mDiff < 0 || (mDiff===0 && today.getDate() < bd.getDate())) age--;
      return age;
    }catch{ return null; }
  }

  function lockKidsSettings(){
    try{
      const sel = document.getElementById('persona');
      if (sel){
        try{ sel.value = 'kids'; }catch{}
        try{ Array.from(sel.options||[]).forEach(o=>{ if (o && o.value && o.value !== 'kids') o.disabled = true; }); }catch{}
        sel.disabled = true;
      }
    }catch{}
  }

  async function maybeApplyKidsPreset(){
    try{
      // Don't override if user explicitly selected persona
      const alreadyKids = (settings.persona||'') === 'kids';
      // If UI toggle present, we may need to hide it for kids
      const hideWebToggle = ()=>{ try{ if (webAllowToggle){ webAllowToggle.closest('label')?.classList.add('hidden'); webAllowToggle.checked=false; } }catch{} };

      // Fetch /api/me and inspect
      const r = await fetch('/api/me', { credentials:'include' });
      const j = await r.json().catch(()=>({}));
      if (!r.ok || !j) return;
      // accept multiple shapes: {is_kid:true} or {user:{birthdate:'YYYY-MM-DD'}}
      const isKidFlag = !!(j.is_kid || (j.user && j.user.is_kid));
      const bdate = (j.birthdate || (j.user && j.user.birthdate)) || '';
      const age = _computeAge(bdate);
      const isKid = isKidFlag || (typeof age==='number' && age < 14);
      if (!isKid) return;
      // Apply preset if not already set
      if (!alreadyKids){ settings.persona = 'kids'; saveSettings(); try{ window.kianaPersona = 'kids'; }catch{} }
      // Lock down web search for kids
      hideWebToggle();
      // Show Kids badge in header
      try{ const kb = document.getElementById('kidsBadge'); if (kb) kb.style.display = ''; }catch{}
      // Lock persona to kids in settings
      lockKidsSettings();
    }catch{}
  }

  async function hydrateLastTopicFromServer(){
    try{
      const sid = typeof getServerConvId === 'function' ? getServerConvId(activeConv) : null;
      if (!sid) return;
      const res = await fetch(`/api/chat/conv_state?conv_id=${encodeURIComponent(String(sid))}`, { credentials:'include' });
      const data = await res.json();
      if (res.ok && data && data.ok && data.last_topic){
        lastTopic = String(data.last_topic||'').trim();
      }
    }catch{}
  }

  // ---- Scroll helpers ----
  function scrollToBottom(smooth=false){
    try{
      if (!chatEl) return;
      if ('scrollTo' in chatEl){ 
        chatEl.scrollTo({ top: chatEl.scrollHeight, behavior: smooth ? 'smooth' : 'auto' }); 
      }
      else { 
        chatEl.scrollTop = chatEl.scrollHeight; 
      }
    }catch{}
  }
  function isNearBottom(){
    if (!chatEl) return true;
    try{
      const delta = chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight;
      return delta < 60;
    }catch{ return true; }
  }
  function applyScrollUI(){
    try{
      // bottom shadow hint when not at end
      if (chatEl) {
        chatEl.classList.toggle('not-at-bottom', !autoScroll);
        // dynamic shade intensity based on distance
        try{
          const delta = Math.max(0, chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight);
          // Clamp 0..360px -> 0.00..0.12
          const shade = Math.max(0.02, Math.min(0.12, (delta / 360) * 0.12));
          chatEl.style.setProperty('--bottomShade', shade.toFixed(3));
        }catch{}
      }
      // jump button visible when not at end
      if (jumpBottomBtn){
        if (!autoScroll) jumpBottomBtn.classList.add('show'); else jumpBottomBtn.classList.remove('show');
      }
      // one-time toast hint
      if (!autoScroll && !scrollHintShown){
        scrollHintShown = true;
        try { toast('Du liest ältere Nachrichten. Klick auf ⬇ oder den Button, um zum Ende zu springen.'); } catch {}
      }
    }catch{}
  }

  // Helper: include CID in error messages when present
  function withCid(txt){
    try{ return lastCid ? `${txt} (cid: ${lastCid})` : txt; }catch{ return txt; }
  }

  // ---------- i18n helper ----------
  const I18N = {
    de: {
      error_generic: 'Ein Fehler ist aufgetreten.',
      unauthorized: '⚠️ Nicht eingeloggt.',
      forbidden: '⚠️ Keine Berechtigung für diese Aktion.',
      logs_view: 'Logs ansehen',
      logs_details: 'Weitere Details in den Logs ansehen',
      model_loading: '⏳ Modell lädt…',
      model_ready: '✅ KI bereit',
      model_not_ready: 'KI noch nicht bereit.',
      settings_saved: 'Einstellungen gespeichert.',
      conv_delete_confirm: 'Ausgewählte Unterhaltungen löschen?',
      stt_not_supported: 'Dein Browser unterstützt keine Spracheingabe.',
      mic_error: 'Mikrofon-Fehler.',
      agent_problem: '⚠️ Leider gab es ein Problem beim Agenten.',
      agent_network_error: '⚠️ Netzwerkfehler (Agent).',
      stream_start_fail: '⚠️ Konnte Streaming nicht starten.',
      stream_error_fallback: '⚠️ Streamingfehler: Verbindung konnte nicht aufgebaut werden.',
      network_error: '⚠️ Netzwerkfehler.',
      ai_answering: 'KI_ana antwortet...'
    },
    en: {
      error_generic: 'An error occurred.',
      unauthorized: '⚠️ Not signed in.',
      forbidden: '⚠️ You are not allowed to perform this action.',
      logs_view: 'View logs',
      logs_details: 'See more details in logs',
      model_loading: '⏳ Model loading…',
      model_ready: '✅ AI ready',
      model_not_ready: 'AI not ready yet.',
      settings_saved: 'Settings saved.',
      conv_delete_confirm: 'Delete selected conversations?',
      stt_not_supported: 'Your browser does not support speech input.',
      mic_error: 'Microphone error.',
      agent_problem: '⚠️ There was a problem with the agent.',
      agent_network_error: '⚠️ Network error (Agent).',
      stream_start_fail: '⚠️ Could not start streaming.',
      stream_error_fallback: '⚠️ Streaming error: connection could not be established.',
      network_error: '⚠️ Network error.',
      ai_answering: 'KI_ana is responding...'
    },
    fr: {
      error_generic: 'Une erreur est survenue.',
      unauthorized: '⚠️ Non connecté.',
      forbidden: "⚠️ Vous n'êtes pas autorisé à effectuer cette action.",
      logs_view: 'Voir les journaux',
      logs_details: 'Voir plus de détails dans les journaux',
      model_loading: '⏳ Chargement du modèle…',
      model_ready: '✅ IA prête',
      model_not_ready: "L'IA n'est pas encore prête.",
      settings_saved: 'Paramètres enregistrés.',
      conv_delete_confirm: 'Supprimer les conversations sélectionnées ?',
      stt_not_supported: 'Votre navigateur ne prend pas en charge la saisie vocale.',
      mic_error: 'Erreur de microphone.',
      agent_problem: ":warning: Un problème est survenu avec l'agent.",
      agent_network_error: ":warning: Erreur réseau (Agent).",
      stream_start_fail: ":warning: Impossible de démarrer le streaming.",
      stream_error_fallback: ":warning: Erreur de streaming : connexion impossible.",
      network_error: ":warning: Erreur réseau.",
      ai_answering: "KI_ana répond..."
    },
    es: {
      error_generic: 'Ocurrió un error.',
      unauthorized: '⚠️ No has iniciado sesión.',
      forbidden: '⚠️ No tienes permiso para realizar esta acción.',
      logs_view: 'Ver registros',
      logs_details: 'Ver más detalles en los registros',
      model_loading: '⏳ Cargando modelo…',
      model_ready: '✅ IA lista',
      model_not_ready: 'La IA aún no está lista.',
      settings_saved: 'Configuraciones guardadas.',
      conv_delete_confirm: '¿Eliminar conversaciones seleccionadas?',
      stt_not_supported: 'Tu navegador no admite entrada de voz.',
      mic_error: 'Error de micrófono.',
      agent_problem: '⚠️ Hubo un problema con el agente.',
      agent_network_error: '⚠️ Error de red (Agente).',
      stream_start_fail: '⚠️ No se pudo iniciar el streaming.',
      stream_error_fallback: '⚠️ Error de streaming: no se pudo establecer la conexión.',
      network_error: '⚠️ Error de red.',
      ai_answering: 'KI_ana está respondiendo...'
    }
  };
  function currentLang(){
    try{ return (settings.lang || navigator.language || 'de-DE').slice(0,2).toLowerCase(); }catch{ return 'de'; }
  }
  function t(key){
    const lc = currentLang();
    const dict = I18N[lc] || I18N.de;
    return (dict && dict[key]) || (I18N.de[key]) || key;
  }

  // Prefer external JSON i18n if available (netapi/static/i18n/*.json)
  function tExt(key, fallback){
    try{ if (window.i18n && typeof window.i18n.t === 'function') return window.i18n.t(key, fallback); }catch{}
    return fallback;
  }

  // ---------- Init ----------
  applySettingsToUI();
  // Pull server defaults if available
  try { syncSettingsFromServer(); } catch {}
  hydrateVoicesList();
  autoresizeSetup();
  // Conversations init: immer mit neuer Unterhaltung starten
  const freshId = createConversation();
  setActiveConversation(freshId);
  // Auth + sync server conversations
  bootstrapAuthAndSync();
  // Live LLM Status
  startLLMStatusPolling();
  // Background events (Sub‑KI callbacks etc.)
  startEventBus();
  
  // Initialize tabs if they exist
  if (tabsContainer) {
    initTabs();
  }

  // Begrüßung beim Start (einmalig) – robust gegen frühe Inserts
  window.addEventListener('DOMContentLoaded', ()=>{
    try{
      if (!chatEl) return;
      if (chatEl.dataset.booted === '1') return;
      const hasAIMsg = !!chatEl.querySelector('.msg.ai');
      if (hasAIMsg) { chatEl.dataset.booted = '1'; return; }
      initUserIdentity().then(()=>{
        showWelcomeMessage();
        chatEl.dataset.booted = '1';
        bootedGreeting = true;
      }).catch(()=>{
        showWelcomeMessage();
        chatEl.dataset.booted = '1';
        bootedGreeting = true;
      });
    }catch{}
  });

  // Fallback: Wenn nach kurzer Zeit noch keine AI-Nachricht existiert, Begrüßung nachreichen
  window.addEventListener('DOMContentLoaded', ()=>{
    try{
      setTimeout(()=>{
        try{
          const chat = document.getElementById('chat');
          const hasAIMsg = !!(chat && chat.querySelector('.msg.ai'));
          if (chat && !hasAIMsg){
            showWelcomeMessage();
          }
        }catch{}
      }, 600);
    }catch{}
  });

  // ---------- Error Banner (non-blocking) ----------
  let errorBannerEl = null;
  function rootPrefix(){
    try{
      const p = window.location.pathname || '/';
      const i = p.indexOf('/static/');
      if (i >= 0) return p.slice(0, i);
      return '';
    }catch{ return ''; }
  }
  function ensureErrorBanner(){
    if (errorBannerEl) return errorBannerEl;
    const el = document.createElement('div');
    el.id = 'errorBanner';
    el.style.position = 'fixed';
    el.style.left = '50%';
    el.style.transform = 'translateX(-50%)';
    el.style.bottom = '16px';
    el.style.zIndex = '1000';
    el.style.background = '#3a0f14';
    el.style.border = '1px solid #69242c';
    el.style.color = '#ffdfe3';
    el.style.padding = '10px 12px';
    el.style.borderRadius = '10px';
    el.style.boxShadow = '0 6px 20px rgba(0,0,0,.35)';
    el.style.maxWidth = '92vw';
    el.style.display = 'none';
    el.innerHTML = '<span id="errMsg"></span> <a id="errLink" href="#" style="color:#ffe4e7; text-decoration:underline; margin-left:.5em;">'+t('logs_view')+'</a> <button id="errClose" style="margin-left:.75em; background:transparent; border:1px solid #8a3a43; color:#ffdfe3; padding:2px 8px; border-radius:8px; cursor:pointer;">OK</button>';
    document.body.appendChild(el);
    el.querySelector('#errClose').addEventListener('click', ()=> hideErrorBanner());
    el.querySelector('#errLink').addEventListener('click', (e)=>{
      e.preventDefault();
      try{
        const cidPart = (typeof lastCid !== 'undefined' && lastCid) ? ('?cid=' + encodeURIComponent(String(lastCid))) : '';
        const url = rootPrefix() + '/static/admin.html#logs' + cidPart;
        window.open(url, '_blank', 'noopener');
      }catch{}
    });
    errorBannerEl = el; return el;
  }
  function showErrorBanner(msg, linkText){
    const el = ensureErrorBanner();
    try{
      el.querySelector('#errMsg').textContent = String(msg||t('error_generic'));
      const a = el.querySelector('#errLink');
      if (a) a.textContent = String(linkText || t('logs_view'));
      el.style.display = 'block';
    }catch{}
  }
  function hideErrorBanner(){ try{ if (errorBannerEl) errorBannerEl.style.display = 'none'; }catch{} }

  function startLLMStatusPolling(){
    const apply = (state) => {
      if (!llmStatusEl) return;
      try{
        const o = state?.info || {};
        if (state.ok) {
          if (o.available === false || o.model_present === false) {
            llmStatusEl.textContent = t('model_loading');
            llmStatusEl.style.opacity = '0.7';
            // don't spam banner here; just update label
          } else {
            llmStatusEl.textContent = t('model_ready');
            llmStatusEl.style.opacity = '1';
            hideErrorBanner();
          }
        } else {
          llmStatusEl.textContent = t('model_loading');
          llmStatusEl.style.opacity = '0.7';
          // If it's a soft network fail from preflight, avoid noisy banner
          if (!(state.info && state.info.softFail)){
            showErrorBanner(t('model_not_ready'), t('logs_view'));
          }
        }
      }catch{}
    };
    const tick = async () => {
      try { const res = await preflightLLM(); apply(res); } catch {}
    };
    tick();
    setInterval(tick, 5000);
  }

  function startEventBus(){
    try{
      let es = null;
      let tries = 0;
      const maxTries = 5;
      const base = 800;
      const connect = () => {
        try{ es?.close(); }catch{}
        es = new EventSource('/events', { withCredentials: true });
        es.onmessage = (ev) => {
          try{
            const evt = JSON.parse(ev.data);
            if (!evt || !evt.type) return;
            if (evt.type === 'submind_result'){
              const sid = evt.submind || 'submind';
              const t = evt.task_id ? ` (Task ${evt.task_id})` : '';
              const txt = evt.preview ? `: ${String(evt.preview).slice(0,140)}` : '';
              toast(`📦 Sub‑KI ${sid}${t} → ${evt.status || 'done'}${txt}`);
            } else if (evt.type === 'submind_status'){
              const sid = evt.submind || 'submind';
              const prog = (typeof evt.progress === 'number') ? ` – ${(evt.progress*100).toFixed(0)}%` : '';
              toast(`🛰️ Sub‑KI ${sid} Status: ${evt.status || ''}${prog}`);
            }
          }catch{}
        };
        es.onerror = () => {
          try{ es.close(); }catch{}
          if (tries < maxTries){
            const delay = Math.min(8000, base * Math.pow(2, tries++));
            setTimeout(connect, delay);
          }
        };
      };
      connect();
    }catch{}
  }

  // ---------- Events ----------
  if (sendBtn) sendBtn.addEventListener('click', onSend);
  newConvBtn?.addEventListener('click', () => {
    const id = createConversation();
    setActiveConversation(id);
  });
  selectAllConvsBtn?.addEventListener('click', () => {
    try{
      if (selectedConvs.size < convs.length) {
        selectedConvs = new Set(convs.map(c => c.id));
      } else {
        selectedConvs.clear();
      }
      renderConversationList();
    }catch{}
  });
  deleteSelectedConvsBtn?.addEventListener('click', () => {
    try{
      const ids = Array.from(selectedConvs);
      if (!ids.length) return;
      if (!confirm(t('conv_delete_confirm'))) return;
      ids.forEach(id => { try { deleteConversation(id); } catch {} });
      selectedConvs.clear();
      renderConversationList();
    }catch{}
  });
  toggleSidebarBtn?.addEventListener('click', () => {
    document.body.classList.toggle('show-sidebar');
  });
  closeSidebarBtn?.addEventListener('click', () => { document.body.classList.remove('show-sidebar'); });
  sidebarBackdrop?.addEventListener('click', () => { document.body.classList.remove('show-sidebar'); });

  if (msgEl) {
    // Enter = senden, Shift+Enter = Zeilenumbruch
    msgEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        onSend();
      }
    });
    // Entfernt globalen Fallback, um Doppel-Send zu verhindern
    msgEl.addEventListener('input', autoresize);
  }

  if (ttsToggle) {
    ttsToggle.addEventListener('change', () => {
      settings.tts = !!ttsToggle.checked;
      saveSettings();
    });
  }

  if (webAllowToggle) {
    webAllowToggle.addEventListener('change', () => {
      if (webAllowToggle.checked) {
        const until = Date.now() + 10*60*1000;
        try { localStorage.setItem('kiana.web.allow.until', String(until)); } catch {}
      } else {
        try { localStorage.removeItem('kiana.web.allow.until'); } catch {}
      }
    });
    try { const u = parseInt(localStorage.getItem('kiana.web.allow.until')||'0',10)||0; webAllowToggle.checked = (Date.now()<u); } catch {}
  }

  openSettingsBtn?.addEventListener('click', openSettings);
  closeSettingsBtn?.addEventListener('click', closeSettings);
  cancelSettingsBtn?.addEventListener('click', closeSettings);
  settingsForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    settings.persona = personaSel?.value || 'friendly';
    settings.lang = languageSel?.value || 'de-DE';
    settings.voice = voiceSel?.value || 'auto';
    settings.streaming = !!(streamingChk?.checked ?? true);
    settings.userColor = userColorInp?.value || settings.userColor;
    settings.aiColor = aiColorInp?.value || settings.aiColor;
    settings.style = answerStyleSel?.value || 'balanced';
    settings.bullets = Math.max(1, Math.min(8, parseInt(bulletCountInp?.value||'5', 10) || 5));
    settings.logic = answerLogicSel?.value || 'balanced';
    settings.format = answerFormatSel?.value || 'structured';
    settings.autonomy = parseInt(autonomySel?.value||'0',10) || 0;
    settings.ethics = ethicsSel?.value || 'default';
    settings.allowNet = !!(allowNetChk?.checked);
    try{ settings.activeSubkis = Array.from(activeSubkisSel?.selectedOptions || []).map(o => o.value); }catch{ settings.activeSubkis = []; }
    try{ const remember = document.querySelector('#rememberStyle'); settings.rememberStyle = !!(remember && remember.checked); }catch{}
    saveSettings();
    // Optional: persist style preset for future chats
    try{
      if (settings.rememberStyle){
        const preset = { persona: settings.persona, lang: settings.lang, style: settings.style, bullets: settings.bullets, logic: settings.logic, format: settings.format };
        localStorage.setItem(STYLE_PRESET_KEY, JSON.stringify(preset));
      } else {
        localStorage.removeItem(STYLE_PRESET_KEY);
      }
    }catch{}
    // Push subset to server (admin-only on server side)
    try{
      fetch('/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({ language: settings.lang, ethics_filter: settings.ethics, active_subkis: (settings.activeSubkis||[]), allow_net: !!settings.allowNet })
      }).catch(()=>{});
    }catch{}
    // Pro‑Unterhaltung Voreinstellungen sichern
    try{ saveConvPrefs(activeConv, { style: settings.style, bullets: settings.bullets, persona: settings.persona, logic: settings.logic, format: settings.format }); }catch{}
    closeSettings();
    toast(t('settings_saved'));
  });

  // Modal schließen bei Klick außerhalb & ESC
  settingsModal?.addEventListener('click', (e) => {
    const t = e.target;
    if (t === settingsModal || (t && t.classList && t.classList.contains('modal-backdrop'))) closeSettings();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape'){
      if (!settingsModal?.hasAttribute('hidden')) closeSettings();
      document.body.classList.remove('show-sidebar');
    }
  });

  micBtn?.addEventListener('click', toggleMic);

  // ---------- Attachments (upload helper) ----------
  attachBtn?.addEventListener('click', ()=> attachInput?.click());
  attachInput?.addEventListener('change', ()=>{
    pendingFiles = Array.from(attachInput.files || []);
    if (attachmentsInfo) {
      attachmentsInfo.textContent = pendingFiles.length ? (pendingFiles.length + ' Datei(en) bereit') : '';
    }
  });

  async function uploadAttachments(){
    if (!pendingFiles.length) return [];
    const fd = new FormData();
    pendingFiles.forEach(f => fd.append('files', f));
    const res = await fetch('/api/media/upload', { method:'POST', credentials:'include', headers: { 'X-Lang': settings.lang || 'de-DE' }, body: fd });
    const j = await res.json().catch(()=>({}));
    if (!res.ok || !j || j.ok !== true) throw new Error('Upload fehlgeschlagen');
    // clear after success
    pendingFiles = [];
    if (attachmentsInfo) attachmentsInfo.textContent = '';
    if (attachInput) attachInput.value = '';
    const items = (j.items || []).map(it => ({ name: it.name, url: it.url, type: it.content_type, block_id: it.block_id, jobs: it.jobs || null }));
    try {
      // Show a small toast with queued jobs (keeps chat clean)
      items.forEach(it => {
        const jobs = it.jobs || {};
        const keys = Object.keys(jobs);
        if (keys.length){
          const list = keys.map(k => `${k}#${jobs[k]}`).join(', ');
          toast(`⏳ Verarbeite ${it.name}: ${list}`);
        }
      });
      // Optional: single consolidated system note if many jobs
      const totalJobs = items.reduce((a,it)=> a + (it.jobs? Object.keys(it.jobs).length : 0), 0);
      if (totalJobs >= 3){
        appendMsg('system', `⏳ ${totalJobs} Medien‑Jobs eingereiht. Details im Papa‑Bereich → Job‑Queue.`);
      }
    } catch {}
    return items;
  }

  function isWebAllowedNow(){
    try { const u = parseInt(localStorage.getItem('kiana.web.allow.until')||'0',10)||0; return Date.now()<u; } catch { return false; }
  }

  // ---------- Chat-Funktionen ----------
  function appendMsg(role, text, quickReplies = []) {
    if (!chatEl) return null;
    const div = document.createElement('div');
    div.className = `msg ${role==='user' ? 'me' : role}`;
    
    // Format AI messages with markdown-like formatting
    const formattedText = (role === 'ai' || role === 'assistant') ? formatMessage(text) : escapeHTML(text);
    div.innerHTML = `<div class="content">${formattedText}</div>`;
    chatEl.appendChild(div);

    // Add quick replies if any
    if (role === 'ai' && quickReplies && quickReplies.length > 0) {
      const qrContainer = document.createElement('div');
      qrContainer.className = 'quick-replies';
      quickReplies.forEach(reply => {
        const btn = document.createElement('button');
        btn.className = 'quick-reply-btn';
        btn.textContent = reply;
        btn.onclick = () => onQuickReplyClick(reply);
        qrContainer.appendChild(btn);
      });
      div.appendChild(qrContainer);
    }
    
    if (autoScroll){ scrollToBottom(false); }
    applyScrollUI();
    return div;
  }

  function escapeHTML(s){
    try { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c])); } catch { return String(s||''); }
  }

  function formatMessage(text) {
    if (!text) return '';
    let html = escapeHTML(text);
    
    // Code blocks (```code```) - must be done before inline code
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="code-block">$1</pre>');
    
    // Inline code (`code`)
    html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    
    // Bold text (**text** or __text__)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    
    // Italic text (*text* or _text_) - nur wenn nicht Teil von **
    html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
    html = html.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>');
    
    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="chat-link">$1</a>');
    
    // Auto-detect URLs
    html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener" class="chat-link">$1</a>');
    
    // Split into paragraphs (double newline)
    const paragraphs = html.split(/\n\n+/);
    
    html = paragraphs.map(para => {
      para = para.trim();
      if (!para) return '';
      
      const lines = para.split('\n');
      
      // Check for mixed content (lists + text)
      const listLines = [];
      const otherLines = [];
      
      lines.forEach(line => {
        const trimmed = line.trim();
        if (/^\d+\.\s/.test(trimmed) || /^[•\-*+]\s/.test(trimmed)) {
          listLines.push(line);
        } else if (trimmed) {
          otherLines.push(line);
        }
      });
      
      // If we have list items, format them
      if (listLines.length > 0) {
        const isNumbered = /^\d+\.\s/.test(listLines[0].trim());
        const items = listLines.map(line => {
          const match = isNumbered 
            ? line.match(/^\d+\.\s*(.*)/)
            : line.match(/^[•\-*+]\s*(.*)/);
          return match ? `<li>${match[1]}</li>` : '';
        }).filter(Boolean).join('');
        
        const listHtml = isNumbered 
          ? `<ol class="chat-list">${items}</ol>`
          : `<ul class="chat-list">${items}</ul>`;
        
        // If we also have other lines, wrap them in paragraphs
        if (otherLines.length > 0) {
          const otherHtml = otherLines.map(l => `<p class="chat-paragraph">${l}</p>`).join('');
          return listHtml + otherHtml;
        }
        return listHtml;
      }
      
      // Headers (# Header)
      if (/^#{1,3}\s/.test(para)) {
        const level = para.match(/^(#{1,3})/)[1].length;
        const text = para.replace(/^#{1,3}\s*/, '');
        return `<h${level + 2} class="chat-heading">${text}</h${level + 2}>`;
      }
      
      // Quote (> text)
      if (/^>\s/.test(para)) {
        const text = para.replace(/^>\s*/, '');
        return `<blockquote class="chat-quote">${text}</blockquote>`;
      }
      
      // Regular paragraph - but break on single newlines too for better readability
      const subParas = para.split('\n').filter(l => l.trim());
      if (subParas.length > 1) {
        return subParas.map(sp => `<p class="chat-paragraph">${sp}</p>`).join('');
      }
      
      return `<p class="chat-paragraph">${para}</p>`;
    }).join('');
    
    return html;
  }

  function appendMsgHTML(role, html, plainText) {
    if (!chatEl) return;
    const wrap = document.createElement('div');
    wrap.className = `msg ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.innerHTML = html;
    wrap.appendChild(bubble);
    chatEl.appendChild(wrap);
    try{ if (role==='ai') addFeedbackControls(wrap); }catch{}
    if (autoScroll && chatEl){ chatEl.scrollTop = chatEl.scrollHeight; }
    try{
      const msgs = loadMessages(activeConv);
      const txt = plainText || bubble.textContent || '';
      msgs.push({ role, text: txt, ts: Date.now() });
      saveMessages(activeConv, msgs);
      touchConversation(activeConv);
      autoTitle(activeConv, role, txt);
      renderConversationList();
    }catch{}
  }

  function appendDeliberation(plan, critic){
    try{
      if (!plan && !critic) return;
      const p = plan ? `<div><strong>Plan:</strong> ${escapeHTML(plan)}</div>` : '';
      const c = critic ? `<div><strong>Kritik:</strong> ${escapeHTML(critic)}</div>` : '';
      const html = `<details class="deliberation"><summary>🔍 Deliberation</summary>${p}${c}</details>`;
      const plain = `Deliberation – ${plan?('Plan: '+plan):''}${critic? (plan?' | ':'')+('Kritik: '+critic):''}`;
      appendMsgHTML('system', html, plain);
    }catch{}
  }

  function startTyping() {
    typingEl && (typingEl.style.display = 'block');
    if (autoScroll){ scrollToBottom(false); }
    applyScrollUI();
  }
  function stopTyping() {
    typingEl && (typingEl.style.display = 'none');
  }

  function resetPreview() {
    previewEl = null;
  }

  function updatePreview(txt) {
    if (!chatEl) return;
    if (!previewEl) {
      previewEl = document.createElement('div');
      previewEl.className = 'msg ai';
      const c = document.createElement('div');
      c.className = 'content';
      previewEl.appendChild(c);
      // meta line holder (for cid and small info)
      const meta = document.createElement('div');
      meta.className = 'meta';
      previewEl.appendChild(meta);
      chatEl.appendChild(previewEl);
    }
    // annotate bubble with CID if available
    try{
      if (lastCid && previewEl){
        previewEl.setAttribute('data-cid', String(lastCid));
        const cnt = previewEl.querySelector('.content');
        if (cnt) cnt.setAttribute('title', `cid: ${lastCid}`);
        const meta = previewEl.querySelector('.meta');
        if (meta) {
          meta.innerHTML = `cid: ${escapeHTML(String(lastCid))} <button class="copy-btn" type="button" aria-label="CID kopieren">📋 Kopieren</button>`;
          try {
            const btn = meta.querySelector('.copy-btn');
            btn?.addEventListener('click', async (e) => {
              e.preventDefault();
              try {
                await navigator.clipboard.writeText(String(lastCid));
                btn.textContent = 'Kopiert';
                setTimeout(()=>{ btn.textContent = '📋 Kopieren'; }, 1200);
              } catch {}
            }, { once: true });
          } catch {}
        }
      }
    }catch{}
    const cnt = previewEl.querySelector('.content');
    if (cnt) cnt.innerHTML = formatMessage(txt);
    if (autoScroll){ scrollToBottom(false); }
    applyScrollUI();
  }

  function finalizePreview(txt) {
    if (!chatEl) return;
    if (!previewEl) {
      const el = appendMsg('ai', txt);
      try{ if (el) addFeedbackControls(el); }catch{}
    } else {
      // turn preview into a normal ai message structure (.content only) and drop meta line
      try{
        const meta = previewEl.querySelector('.meta');
        if (meta) meta.remove();
      }catch{}
      let cnt = previewEl.querySelector('.content');
      if (!cnt){
        cnt = document.createElement('div');
        cnt.className = 'content';
        previewEl.appendChild(cnt);
      }
      cnt.innerHTML = formatMessage(txt);
    }
  }
  

  function abortStream() {
    try { currentES?.close(); } catch {}
    currentES = null;
    stopTyping();
  }

  function armSendWatch(label='chat', ms=15000){
    try{ if (sendWatch) { clearTimeout(sendWatch); sendWatch = null; } }catch{}
    try{
      sendWatch = setTimeout(()=>{
        try{ abortStream(); }catch{}
        sending = false;
        stopTyping();
        showErrorBanner(withCid('⚠️ Verbindung scheint zu hängen – ich habe zurückgesetzt.'), t('logs_view'));
      }, Math.max(3000, ms|0));
    }catch{}
  }
  function clearSendWatch(){ try{ if (sendWatch){ clearTimeout(sendWatch); sendWatch = null; } }catch{} }

  async function preflightLLM(){
    // Quick readiness probe for local LLM (Ollama)
    try{
      const ctl = new AbortController();
      const t = setTimeout(()=>ctl.abort(), 2000);
      const res = await fetch(rootPrefix() + '/api/metrics', { credentials:'include', signal: ctl.signal });
      clearTimeout(t);
      const data = await res.json().catch(()=>({}));
      const o = (data && data.ollama) || {};
      // available is primary; also consider model presence if reported
      if (o.available === false) return { ok:false, reason:'not_available', info:o };
      if (o.model_present === false) return { ok:false, reason:'model_missing', info:o };
      return { ok:true, info:o };
    }catch(e){
      // Network errors -> do not hard-block, but signal soft-fail
      return { ok:false, reason:'network', info:{ softFail:true } };
    }
  }

  async function onSend() {
    if (sending) return;
    // Setze sofort auf true, um Doppel-Trigger durch schnelle Events zu verhindern
    sending = true;
    const text = (msgEl?.value || '').trim();
    if (!text) { sending = false; return; }
    try{ const t = extractTopicClient(text); if (t) lastTopic = t; }catch{}

    // Preflight: verify local LLM readiness (non-blocking on soft failures)
    const probe = await preflightLLM();
    if (!probe.ok) {
      const o = probe.info || {};
      const host = o.host ? ` bei ${o.host}` : '';
      const model = o.model ? ` (Modell: ${o.model})` : '';
      // Only inform; do not block sending. Backend will handle cold starts.
      let msg = 'KI ist noch nicht bereit'+host+'.';
      if (probe.reason === 'model_missing') msg = `KI‑Modell${model} ist noch nicht geladen${host}.`;
      if (probe.reason === 'network') {
        // silent on transient network issues during metrics probe
      } else {
        showErrorBanner(msg, 'Logs anzeigen');
      }
      // continue without returning; sending proceeds
    }

    // Ensure server conversation exists if logged in
    let serverConvId = null;
    if (await isLoggedIn()) {
      try { serverConvId = await ensureServerConversation(); } catch {}
    }

    appendMsg('user', text);
    autoScroll = true; // after sending, pin to bottom again
    scrollToBottom(true);
    if (msgEl) {
      msgEl.value = '';
      autoresize();
    }
    stopSpeaking();

    // alten Stream sauber schließen, falls vorhanden
    abortStream();

    if (settings.streaming) {
      await sendStream(text, serverConvId);
    } else {
      await sendOnce(text, '', serverConvId);
    }
    // sendStream/Once setzen sending am Ende zurück (in finally)
  }

  async function sendOnceAgent(text, serverConvId = null) {
    try {
      startTyping();
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: text, persona: settings.persona, lang: settings.lang })
      });
      const data = await res.json().catch(() => ({}));
      stopTyping();
      clearSendWatch();

      if (!res.ok || !data || data.ok === false) {
        const msg = res.status === 401 ? t('unauthorized') : (res.status === 403 ? t('forbidden') : t('agent_problem'));
        finalizePreview(msg);
        console.error('agent error', data);
        return;
      }
      const reply = data.reply ?? data.text ?? String(data);
      finalizePreview(reply);
    } catch (e) {
      stopTyping();
      finalizePreview(t('agent_network_error'));
      console.error(e);
    } finally {
      setTimeout(()=>{ sending = false; }, 50);
    }
  }

  async function sendStreamAgent(text, serverConvId = null) {
    let acc = '';
    let done = false;
    startTyping();
    try {
      const params = new URLSearchParams({
        message: text,
        persona: settings.persona || '',
        lang: settings.lang || ''
      });
      currentES = new EventSource(`/api/agent/stream?${params.toString()}`, { withCredentials: true });
      currentES.onmessage = (ev) => {
        try {
          const payload = JSON.parse(ev.data);
          if (payload && payload.cid){ lastCid = payload.cid; console.debug('SSE cid (agent):', lastCid); }
          if (payload.delta !== undefined) {
            acc += payload.delta;
            updatePreview(acc);
          } else if (payload.text !== undefined) {
            acc = payload.text;
            updatePreview(acc, true);
          }
          if (payload.done) {
            done = true;
            currentES?.close();
            stopTyping();
            finalizePreview(acc);
            setTimeout(()=>{ sending = false; }, 50);
          }
        } catch { acc += ev.data; updatePreview(acc); }
      };
      currentES.onerror = async (err) => {
        if (done) return;
        currentES?.close();
        stopTyping();
        try { await sendOnce(text, '', serverConvId); } catch {}
        setTimeout(()=>{ sending = false; }, 50);
      };
    } catch (e) {
      stopTyping();
      finalizePreview('⚠️ Konnte Agent-Streaming nicht starten.');
      console.error(e);
    }
  };

  // ---- NEU: passt auf /api/chat (statt /api/talk)
  async function sendOnce(text, prefill = '', serverConvId = null) {
    try {
      startTyping();
      armSendWatch('sendOnce', 15000);
      let attachments = [];
      try { attachments = await uploadAttachments(); } catch (e) { console.error(e); }
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          message: text,
          persona: settings.persona,
          lang: settings.lang,
          attachments,
          conv_id: serverConvId || getServerConvId(activeConv) || null,
          style: settings.style || 'balanced',
          bullets: settings.bullets || 5,
          logic: settings.logic || 'balanced',
          format: settings.format || 'structured',
          web_ok: isWebAllowedNow(),
          autonomy: (settings.autonomy||0)
        })
      });
      const data = await res.json().catch(() => ({}));
      stopTyping();

      if (!res.ok || !data || data.ok === false) {
        const msg = res.status === 401 ? t('unauthorized') : (res.status === 403 ? (data && (data.detail||'')==='kids_restricted' ? 'Für Kinderkonten ist diese Funktion deaktiviert.' : t('forbidden')) : (res.status===429 && data && data.error==='quota_exceeded' ? ('Tageslimit erreicht – <a href="'+upgradeUrl+'" target="_blank" rel="noopener">Upgrade auf Papa</a>') : t('error_generic')));
        finalizePreview(prefill || msg);
        console.error('chat error', data);
        return;
      }
      const reply = data.reply ?? data.text ?? String(data);
      finalizePreview(prefill ? (prefill + reply) : reply);
      try{ addMetaBadgesToLastAI(data || {}); }catch{}
      try{
        // Attach memory ids to last AI bubble for rating
        const ids = Array.isArray(data.memory_ids) ? data.memory_ids : [];
        if (ids && ids.length && chatEl && chatEl.lastElementChild){
          chatEl.lastElementChild.dataset.memoryIds = JSON.stringify(ids);
        }
      }catch{}
      try{
        if (data.role_used && chatEl && chatEl.lastElementChild){
          chatEl.lastElementChild.dataset.roleUsed = String(data.role_used);
          // add small meta line if not present
          const meta = document.createElement('div');
          meta.className = 'meta';
          meta.textContent = `Rolle: ${String(data.role_used)}`;
          chatEl.lastElementChild.appendChild(meta);
        }
      }catch{}
      // Update client topic from server
      try{ if (data.topic && String(data.topic).trim()) lastTopic = String(data.topic).trim(); }catch{}
      // Follow-ups (prefer backend quick_replies)
      try{
        const qrs = Array.isArray(data.quick_replies) && data.quick_replies.length ? data.quick_replies : (buildFollowUps(text, reply) || []);
        if (qrs && qrs.length){
          const t = (data.topic && String(data.topic).trim()) || lastTopic || '';
          const persona = (typeof window !== 'undefined' && window.kianaPersona) ? String(window.kianaPersona) : '';
          const prompt = t ? (persona==='kids' ? `Thema: ${t}\nWillst du mehr darüber wissen?` : `Thema: ${t}\nMöchtest du zu etwas Spezifischem mehr wissen?`) : (persona==='kids' ? 'Willst du mehr darüber wissen?' : 'Möchtest du zu etwas Spezifischem mehr wissen?');
          appendMsg('ai', prompt, qrs);
        }
      }catch{}
      // Risk indicator and reflective prompt
      try{
        if (data.risk_flag){
          const qrs = [
            { title: 'Sicher prüfen', text: 'Bitte prüfe das sicher und achte auf Risiken.' },
            { title: 'Alternativen vorschlagen', text: 'Schlag sichere Alternativen vor.' },
          ];
          appendMsg('system', '⚠️ riskant: Das wirkt riskant – soll ich das vorsichtshalber prüfen oder lieber nach sicheren Alternativen suchen?', qrs);
        }
      }catch{}
      // Show tools used if provided
      try{
        if (Array.isArray(data.tools_used) && data.tools_used.length){
          const chips = data.tools_used.map(t=>{
            const name = t.tool || '';
            const reason = (t.meta && t.meta.reason) ? String(t.meta.reason) : '';
            const ok = (t.ok ? 'ok' : 'fail');
            const title = reason ? `${name}: ${reason} (${ok})` : `${name} (${ok})`;
            return `<span class="pill" title="${escapeHTML(title)}">${escapeHTML(name)}</span>`;
          }).join(' ');
          if (chips){
            const el = appendMsg('system', `🔧 Verwendete Tools: ${chips}`);
            // allow HTML inside content
            if (el){ const c = el.querySelector('.content'); if (c){ c.innerHTML = `🔧 Verwendete Tools: ${chips}`; } }
            // store last tools for feedback hooks
            window.__last_tools_used = data.tools_used.map(t=>t.tool).filter(Boolean);
          }
        }
      }catch{}
      // store server conv id returned by backend (first message)
      if (data.conv_id) { try { setServerConvId(activeConv, data.conv_id); hydrateLastTopicFromServer(); } catch {} }
      // Deliberation (Plan/Kritik) is now backend-only; do not render in UI
      // Show auto-activated modes, if any
      try{
        if (Array.isArray(data.auto_modes) && data.auto_modes.length){
          const modes = data.auto_modes.join(', ');
          appendMsg('system', `⚙️ Auto‑Modi: ${modes}`);
        }
      }catch{}
      // Follow-up quick replies (server-provided or client-generated)
      // Suppress extra follow-up AI prompts for a cleaner, human chat
      try{/* no-op */}catch{}
      // Try refresh title from server (no await in non-async context)
      try { isLoggedIn().then(auth => { if (auth) refreshServerConvTitle(activeConv); }).catch(() => {}); } catch {}
    } catch (e) {
      stopTyping();
      finalizePreview(prefill || t('network_error'));
      console.error(e);
    } finally {
      // leichte Entprellung
      clearSendWatch();
      setTimeout(()=>{ sending = false; }, 50);
    }
  }

  // ---- NEU: passt auf /api/chat/stream (statt /api/talk/stream)
  async function sendStream(text, serverConvId = null) {
    let acc = '';
    let done = false;
    startTyping();
    armSendWatch('sendStream', 15000);

    try {
      const params = new URLSearchParams({
        message: text,
        persona: settings.persona || '',
        lang: settings.lang || '',
        style: settings.style || 'balanced',
        bullets: String(settings.bullets || 5),
        logic: settings.logic || 'balanced',
        format: settings.format || 'structured',
        web_ok: (function(){ try{const u=parseInt(localStorage.getItem('kiana.web.allow.until')||'0',10)||0; return Date.now()<u;}catch{return false;} })() ? '1':'0',
        autonomy: String(settings.autonomy || 0)
      });
      const sid = serverConvId || getServerConvId(activeConv);
      if (sid) params.set('conv_id', String(sid));

      const url = `/api/chat/stream?${params.toString()}`;
      let retries = 0;
      const maxRetries = 3;
      const baseDelay = 800;

      // Minimal SSE-over-fetch fallback for browsers/proxies that kill EventSource
      async function fetchSSEFallback(url, onChunk, onEnd){
        try{
          const res = await fetch(url, { credentials:'include', headers: { 'Accept': 'text/event-stream' } });
          if (!res.ok || !res.body){ throw new Error('sse_fetch_failed'); }
          const reader = res.body.getReader();
          const dec = new TextDecoder('utf-8');
          let buf = '';
          while(true){
            const { value, done: rDone } = await reader.read();
            if (rDone){ break; }
            buf += dec.decode(value, { stream: true });
            let idx;
            while((idx = buf.indexOf('\n\n')) >= 0){
              const rawEvt = buf.slice(0, idx);
              buf = buf.slice(idx+2);
              // parse SSE event: collect data: lines
              const lines = rawEvt.split('\n');
              let dataLines = [];
              for (const ln of lines){
                if (ln.startsWith('data:')) dataLines.push(ln.slice(5).trimStart());
              }
              if (!dataLines.length) continue;
              const dataStr = dataLines.join('\n');
              try{
                const payload = JSON.parse(dataStr);
                onChunk(payload);
                if (payload && payload.done){ onEnd(); return; }
              }catch{
                // treat as raw delta
                onChunk({ delta: dataStr });
              }
            }
          }
          onEnd();
        }catch(e){
          console.warn('SSE fetch fallback failed', e);
          onEnd();
        }
      }

      setDebugStatus('⏳ Verbinde…', true);
      const connect = () => {
        currentES = new EventSource(url, { withCredentials: true });
        let finalized = false;
        const finalizeOnce = (payload) => {
          if (finalized) return; finalized = true;
          try {
            const chat = document.getElementById('chat');
            const wrap = chat ? chat.lastElementChild : null;
            if (wrap && wrap.classList.contains('msg') && wrap.classList.contains('ai')){
              wrap.classList.add('finalized');
            }
          } catch {}
          try { stopTyping(); } catch {}
          try { finalizePreview(acc, payload || {}); } catch {}
          // Apply natural formatting (plain text + optional details button)
          try { applyNaturalFormat(payload || {}, String(acc||'')); } catch {}
          // Fallback if content is empty/meaningless
          try{
            const wrap2 = document.getElementById('chat')?.lastElementChild || null;
            if (wrap2 && wrap2.classList.contains('msg') && wrap2.classList.contains('ai')){
              const bubble = wrap2.querySelector('.bubble') || wrap2;
              const textNow = (bubble.textContent || '').trim();
              // Heuristik: sehr kurz oder nur Wiederholungsfloskeln
              const bad = (!textNow || textNow.length < 20);
              if (bad){
                let name = null; try{ name = localStorage.getItem('kiana_username') || null; }catch{}
                const fallback = name && name.trim()
                  ? `Hm, das weiß ich gerade nicht genau 🤔 – magst du die Frage anders stellen, ${name.trim()}?`
                  : 'Hm, das weiß ich gerade nicht genau 🤔 – magst du die Frage anders stellen?';
                bubble.textContent = fallback;
              }
            }
          }catch{}
          // Add source/tool badges with tooltips
          try { addMetaBadgesToLastAI(payload || {}); } catch {}
          // Suppress quick replies and technical comparison UI for a clean, human response
          // try { renderQuickRepliesIfNeeded(payload || {}); } catch {}
          // try { if (payload && payload.comparison) renderDeltaViewerIfComparison(payload, String(acc||'')); } catch {}
          // After formatting: store memory IDs for later (feedback, etc.)
          try {
            const wrap = document.getElementById('chat')?.lastElementChild || null;
            if (wrap && wrap.classList && wrap.classList.contains('msg') && wrap.classList.contains('ai')){
              const memIds = Array.isArray(payload?.memory_ids) ? payload.memory_ids : [];
              const bubble = wrap.querySelector('.bubble') || wrap;
              // Only ensure we store memory IDs for later (feedback, etc.). Link already rendered by applyNaturalFormat.
              try{ if (memIds && memIds.length){ wrap.dataset.memoryIds = JSON.stringify(memIds.slice(0,5)); } }catch{}
            }
          } catch {}
          try { currentES?.close(); } catch {}
          try { setDebugStatus('✅ Antwort fertig', true); } catch {}
          try { clearSendWatch(); } catch {}
          sending = false;
        };

        currentES.onopen = () => { retries = 0; try { setDebugStatus('🔌 Verbunden mit KI_ana', true); } catch {} };

        currentES.onmessage = (ev) => {
          try {
            const payload = JSON.parse(ev.data);
            if (payload && payload.cid){ lastCid = payload.cid; }
            if (payload.delta !== undefined) {
              acc += payload.delta;
              try { updatePreview(acc); } catch {}
            } else if (payload.text !== undefined) {
              acc = String(payload.text || '');
              try { updatePreview(acc, true); } catch {}
            }
            if (payload.done === true) {
              done = true;
              finalizeOnce(payload);
              // enrich UI extras after finalize
              try{ if (Array.isArray(payload.tools_used)){ window.__last_tools_used = payload.tools_used.map(t=>t.tool).filter(Boolean); } }catch{}
              try { isLoggedIn().then(auth => { if (auth) refreshServerConvTitle(activeConv); }).catch(() => {}); } catch {}
              if (!payload.no_prompts){
                renderFeedbackPrompt();
                try{ window.__last_ai_text = String(acc||''); }catch{}
                renderTtsPrompt(window.__last_ai_text||'');
              }
            } else if (payload.error) {
              // show banner but do not finalize here
              try{
                const code = String((payload.error||payload.code||'')).toLowerCase();
                const mapKey = code ? `chat.error.${code}` : '';
                let msg = mapKey ? tExt(mapKey, null) : null;
                if (!msg || msg === mapKey) msg = (code==='kids_restricted') ? 'Für Kinderkonten ist diese Funktion deaktiviert.' : t('stream_error_fallback');
                if ((!msg || msg === t('stream_error_fallback')) && payload.detail){ msg = String(payload.detail); }
                showErrorBanner(withCid(msg), t('logs_view'));
              }catch{}
            }
          } catch {
            // Plain text chunk; append and update. Only finalize on explicit done markers
            const raw = String(ev.data||'');
            if (/\"done\"\s*:\s*true/.test(raw) || raw.trim()==='[DONE]' || raw.trim()==='done'){
              done = true; finalizeOnce({}); return;
            }
            acc += raw; try { updatePreview(acc); } catch {}
          }
        };

        currentES.onerror = async (err) => {
          try { setDebugStatus('❌ Verbindung fehlgeschlagen', false); } catch {}
          if (done) return;
          try { currentES?.close(); } catch {}
          console.warn('SSE error; retrying…', err);
          if (retries < maxRetries) {
            const jitter = Math.floor(Math.random() * 250);
            const delay = baseDelay * Math.pow(2, retries) + jitter;
            retries += 1;
            setTimeout(connect, delay);
            return;
          }
          // Fallback after retries: switch to fetch-based SSE
          try { stopTyping(); } catch {}
          await fetchSSEFallback(url, (payload)=>{
            try{
              if (payload && payload.cid){ lastCid = payload.cid; }
              if (payload && payload.error){
                showErrorBanner(withCid(String(payload.detail||t('stream_error_fallback'))), t('logs_view'));
                return;
              }
              if (payload && payload.delta !== undefined){ acc += payload.delta; updatePreview(acc); return; }
              if (payload && payload.text !== undefined){ acc = String(payload.text||''); updatePreview(acc, true); return; }
              if (typeof payload === 'string'){ acc += payload; updatePreview(acc); }
            }catch{}
          }, ()=>{
            finalizeOnce({});
          });
        };
      };

      connect();
    } catch (e) {
      stopTyping();
      finalizePreview(t('stream_start_fail'));
      console.error(e);
      clearSendWatch();
      setTimeout(()=>{ sending = false; }, 50);
    }
  }

  // ---------- Settings ----------
  function loadSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch {}
    return { persona: 'friendly', lang: 'de-DE', voice: 'auto', streaming: true, tts: false, rememberStyle: false, userColor:'#e6f7ff', aiColor:'#efeaff', style:'balanced', bullets:5, logic:'balanced', format:'structured', autonomy: 0, ethics:'default', allowNet:true, activeSubkis:[] };
  }
  function saveSettings() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(settings)); } catch {}
    applySettingsToUI();
  }
  function applySettingsToUI() {
    if (personaSel) personaSel.value = settings.persona || 'friendly';
    if (languageSel) languageSel.value = settings.lang || 'de-DE';
    if (voiceSel) voiceSel.value = settings.voice || 'auto';
    if (streamingChk) streamingChk.checked = !!settings.streaming;
    if (ttsToggle) ttsToggle.checked = !!settings.tts;
    try{ const remember = document.querySelector('#rememberStyle'); if (remember) remember.checked = !!settings.rememberStyle; }catch{}
    if (userColorInp) userColorInp.value = settings.userColor || '#e6f7ff';
    if (aiColorInp) aiColorInp.value = settings.aiColor || '#efeaff';
    if (answerStyleSel) answerStyleSel.value = settings.style || 'balanced';
    if (bulletCountInp) bulletCountInp.value = String(settings.bullets || 5);
    if (answerLogicSel) answerLogicSel.value = settings.logic || 'balanced';
    if (answerFormatSel) answerFormatSel.value = settings.format || 'structured';
    if (autonomySel) autonomySel.value = String(settings.autonomy || 0);
    if (ethicsSel) ethicsSel.value = settings.ethics || 'default';
    if (allowNetChk) allowNetChk.checked = !!settings.allowNet;
    applyTheme();
    try{ window.kianaPersona = settings.persona || 'friendly'; }catch{}
    // If kids mode active, lock settings
    try{ if ((settings.persona||'') === 'kids') lockKidsSettings(); }catch{}
  }
  // Load preset on boot if user opted-in previously
  try{
    const presetRaw = localStorage.getItem(STYLE_PRESET_KEY);
    if (presetRaw){
      const preset = JSON.parse(presetRaw);
      if (preset && typeof preset === 'object'){
        settings.persona = preset.persona || settings.persona;
        settings.lang = preset.lang || settings.lang;
        settings.style = preset.style || settings.style;
        settings.bullets = typeof preset.bullets === 'number' ? preset.bullets : settings.bullets;
        settings.logic = preset.logic || settings.logic;
        settings.format = preset.format || settings.format;
        saveSettings();
      }
    }
  }catch{}

  // Apply kids preset based on /api/me (if logged in)
  try{ isLoggedIn().then(ok => { if (ok) maybeApplyKidsPreset().catch(()=>{}); }).catch(()=>{}); }catch{}
  // Load system config at boot (upgrade URL etc.)
  try{ loadSystemConfig().catch(()=>{}); }catch{}

  function applyTheme(){
    try{
      const root = document.documentElement;
      root.style.setProperty('--bubble-user-bg', settings.userColor || '#e6f7ff');
      root.style.setProperty('--bubble-ai-bg', settings.aiColor || '#efeaff');
    }catch{}
  }

  // ---------- Settings sync with server ----------
  async function syncSettingsFromServer(){
    try{
      const res = await fetch('/api/settings', { credentials: 'include' });
      const data = await res.json();
      if (res.ok && data && data.settings){
        const s = data.settings;
        // adopt server default language if set (does not override explicit user choice)
        if (!settings.lang && s.language){ settings.lang = s.language; saveSettings(); }
        // adopt ethics and allow_net defaults
        if (!settings.ethics && s.ethics_filter){ settings.ethics = s.ethics_filter; }
        if (typeof s.allow_net === 'boolean'){ settings.allowNet = !!s.allow_net; }
        // populate subki list
        const list = Array.isArray(data.available_subkis) ? data.available_subkis : [];
        if (activeSubkisSel){
          activeSubkisSel.innerHTML = list.map(id => `<option value="${id}">${id}</option>`).join('');
          const active = Array.isArray(s.active_subkis) ? s.active_subkis : [];
          Array.from(activeSubkisSel.options).forEach(o => { o.selected = active.includes(o.value); });
        }
        applySettingsToUI();
      }
    }catch{}
  }

  function openSettings() {
    if (!settingsModal) return;
    settingsModal.removeAttribute('hidden');
    settingsModal.classList.add('open');
  }
  function closeSettings() {
    if (!settingsModal) return;
    settingsModal.classList.remove('open');
    settingsModal.setAttribute('hidden', '');
  }

  function toast(msg) {
    try {
      const n = document.createElement('div');
      n.className = 'toast';
      n.textContent = msg;
      document.body.appendChild(n);
      requestAnimationFrame(() => n.classList.add('show'));
      setTimeout(() => {
        n.classList.remove('show');
        setTimeout(() => n.remove(), 250);
      }, 2000);
    } catch {}
  }

  // ---------- TTS ----------
  function hydrateVoicesList() {
    if (!('speechSynthesis' in window)) return disableTTS();
    const fill = () => {
      const voices = window.speechSynthesis.getVoices();
      if (!voiceSel) return;
      const current = settings.voice || 'auto';
      voiceSel.innerHTML = '<option value="auto">Automatisch</option>';
      voices
        .filter(v => !settings.lang || v.lang.toLowerCase().startsWith((settings.lang || '').slice(0,2).toLowerCase()))
        .forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.name;
          opt.textContent = `${v.name} (${v.lang})`;
          voiceSel.appendChild(opt);
        });
      voiceSel.value = current;
    };
    fill();
    window.speechSynthesis.onvoiceschanged = fill;
  }

  function disableTTS() {
    if (ttsToggle) {
      ttsToggle.checked = false;
      ttsToggle.disabled = true;
    }
  }

  function speak(text) {
    stopSpeaking();
    if (settings.voice === 'elevenlabs') {
      const audio = new Audio();
      audio.src = `/api/elevenlabs/speak?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(settings.lang || 'de-DE')}`;
      audio.play().catch(err => console.error('TTS playback error', err));
      speakingUtterance = audio;
    } else if ('speechSynthesis' in window) {
      const u = new SpeechSynthesisUtterance(text);
      u.lang = settings.lang || 'de-DE';
      const voices = speechSynthesis.getVoices();
      if (settings.voice && settings.voice !== 'auto') {
        const v = voices.find(v => v.name === settings.voice);
        if (v) u.voice = v;
      } else {
        const v = voices.find(v => v.lang.toLowerCase().startsWith((settings.lang || 'de-DE').slice(0,2).toLowerCase()));
        if (v) u.voice = v;
      }
      speakingUtterance = u;
      speechSynthesis.speak(u);
    }
  }
  function stopSpeaking() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    if (speakingUtterance instanceof HTMLAudioElement) {
      speakingUtterance.pause();
      speakingUtterance = null;
    }
  }

  // ---------- Speech-to-Text ----------
  function toggleMic() {
    if (recognition) {
      recognition.stop();
      recognition = null;
      micBtn?.classList.remove('active');
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      toast(t('stt_not_supported'));
      return;
    }
    recognition = new SR();
    recognition.lang = settings.lang || 'de-DE';
    recognition.interimResults = true;
    recognition.continuous = false;

    let final = '';
    recognition.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const tr = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += tr + ' ';
        else interim += tr;
      }
      if (msgEl) msgEl.value = (final + interim).trim();
      autoresize();
    };
    recognition.onend = () => {
      micBtn?.classList.remove('active');
      recognition = null;
    };
    recognition.onerror = () => {
      micBtn?.classList.remove('active');
      recognition = null;
      toast(t('mic_error'));
    };
    micBtn?.classList.add('active');
    recognition.start();
  }

  // ---------- Autoresize für Textarea ----------
  function autoresizeSetup() {
    autoresize(); // initial
    window.addEventListener('resize', autoresize);
  }
  function autoresize() {
    if (!msgEl) return;
    msgEl.style.height = 'auto';
    const max = 160; // max 6-8 Zeilen
    msgEl.style.height = Math.min(msgEl.scrollHeight, max) + 'px';
  }

  // ---------- Conversations (localStorage) ----------
  function loadConvs(){
    try{ const raw = localStorage.getItem(CONVS_KEY); if(raw) return JSON.parse(raw); }catch{}
    return [];
  }
  function saveConvs(){ try{ localStorage.setItem(CONVS_KEY, JSON.stringify(convs)); }catch{} }
  function loadActiveConv(){ try{ return localStorage.getItem(ACTIVE_KEY) || ''; }catch{ return ''; } }
  function saveActiveConv(){ try{ localStorage.setItem(ACTIVE_KEY, activeConv); }catch{} }
  function loadMessages(id){ try{ const raw = localStorage.getItem(CONV_PREFIX+id); return raw? JSON.parse(raw): []; }catch{ return []; } }
  function saveMessages(id, msgs){ try{ localStorage.setItem(CONV_PREFIX+id, JSON.stringify(msgs)); }catch{} }
  function loadConvPrefs(id){ try{ const raw = localStorage.getItem(PREF_PREFIX+id); return raw? JSON.parse(raw): null; }catch{ return null; } }
  function saveConvPrefs(id, prefs){ try{ localStorage.setItem(PREF_PREFIX+id, JSON.stringify(prefs||{})); }catch{} }
  function createConversation(title){
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2,7);
    const t = (title || 'Neue Unterhaltung');
    convs.unshift({ id, title: t, createdAt: Date.now(), updatedAt: Date.now() });
    saveConvs(); saveMessages(id, []);
    return id;
  }
  async function deleteConversation(id){
    // If this conversation is linked to a server-side conversation, delete there too
    try{
      const sid = getServerConvId(id);
      if (sid){
        try{ await fetch(`/api/chat/conversations/${sid}`, { method:'DELETE', credentials:'include' }); }catch{}
        try{ localStorage.removeItem('kiana.conv.server.'+id); }catch{}
      }
    }catch{}
    const idx = convs.findIndex(c => c.id === id);
    if (idx >= 0){ convs.splice(idx,1); saveConvs(); }
    try{ localStorage.removeItem(CONV_PREFIX+id); }catch{}
    if (activeConv === id){ activeConv = convs[0]?.id || createConversation(); saveActiveConv(); renderActiveConversation(); }
    renderConversationList();
  }
  function renameConversation(id, title){
    const c = convs.find(c => c.id === id); if (!c) return;
    c.title = title || c.title; c.updatedAt = Date.now(); saveConvs(); renderConversationList();
  }
  function setActiveConversation(id){ activeConv = id; saveActiveConv(); renderConversationList(); renderActiveConversation(); document.body.classList.remove('show-sidebar');
    // Wende per‑Unterhaltung Voreinstellungen an (Style/Bullets)
    try{
      const p = loadConvPrefs(activeConv);
      if (p){
        if (p.style) settings.style = p.style;
        if (typeof p.bullets === 'number') settings.bullets = p.bullets;
        if (p.persona) settings.persona = p.persona;
        saveSettings(); // persist merged settings
      }
    }catch{}
  }
  function touchConversation(id){ const c = convs.find(c => c.id === id); if (c){ c.updatedAt = Date.now(); convs.sort((a,b)=>b.updatedAt - a.updatedAt); saveConvs(); } }
  function autoTitle(id, role, text){
    const c = convs.find(c => c.id === id); if (!c) return;
    if ((!c.title || c.title === 'Neue Unterhaltung') && role === 'user'){
      const base = text.replace(/\s+/g,' ').trim().slice(0,60);
      c.title = base || 'Unterhaltung'; c.updatedAt = Date.now(); saveConvs();
    }
  }
  function renderConversationList(){
    if (!convListEl) return;
    convListEl.innerHTML = '';
    convs.forEach(c => {
      const li = document.createElement('li'); li.className = 'conv-item' + (c.id===activeConv?' active':''); li.dataset.id = c.id;
      const sel = document.createElement('input'); sel.type='checkbox'; sel.className='conv-select'; sel.title='Auswählen'; sel.checked = selectedConvs.has(c.id);
      const icon = document.createElement('div'); icon.className='icon'; icon.textContent='💬';
      const name = document.createElement('div'); name.className='name'; name.textContent = c.title || 'Unterhaltung';
      const actions = document.createElement('div'); actions.className='actions';
      const btnEdit = document.createElement('button'); btnEdit.type='button'; btnEdit.className='icon'; btnEdit.title='Umbenennen'; btnEdit.textContent='✏️';
      const btnDel = document.createElement('button'); btnDel.type='button'; btnDel.className='icon'; btnDel.title='Löschen'; btnDel.textContent='🗑️';
      actions.append(btnEdit, btnDel);
      li.append(sel, icon, name, actions);
      convListEl.appendChild(li);
      li.addEventListener('click', (e)=>{ if (e.target===btnEdit || e.target===btnDel || e.target===sel) return; setActiveConversation(c.id); });
      sel.addEventListener('click', (e)=> e.stopPropagation());
      sel.addEventListener('change', (e)=>{
        if (sel.checked) selectedConvs.add(c.id); else selectedConvs.delete(c.id);
      });
      btnEdit.addEventListener('click', (e)=>{ e.stopPropagation(); const t = prompt('Neuer Titel:', c.title) || c.title; renameConversation(c.id, t); });
      btnDel.addEventListener('click', (e)=>{ e.stopPropagation(); if (confirm('Unterhaltung löschen?')) deleteConversation(c.id); });
    });
  }
  function renderActiveConversation(){
    if (!chatEl) return;
    chatEl.innerHTML = '';
    const msgs = loadMessages(activeConv);
    msgs.forEach(m => { 
      const wrap = document.createElement('div'); 
      wrap.className = `msg ${m.role==='user'?'me':(m.role==='system'?'system':'ai')}`; 
      const b = document.createElement('div'); 
      b.className='bubble'; 
      // Format AI messages, escape user messages
      if (m.role === 'ai' || m.role === 'assistant') {
        b.innerHTML = formatMessage(m.text);
      } else {
        b.textContent = m.text;
      }
      wrap.appendChild(b); 
      chatEl.appendChild(wrap); 
    });
    chatEl.scrollTop = chatEl.scrollHeight;
    // Lazy-load from server if logged in and no local msgs
    try{
      if (msgs.length === 0 && getServerConvId(activeConv)) {
        fetchServerMessagesInto(activeConv);
      }
    }catch{}
  }

  // ---------- Server sync helpers ----------
  function getServerConvId(localId){ try{ return localStorage.getItem('kiana.conv.server.'+localId) || null; }catch{ return null; } }
  function setServerConvId(localId, serverId){ try{ localStorage.setItem('kiana.conv.server.'+localId, String(serverId)); }catch{} }
  async function isLoggedIn(){
    if (isAuth) return true;
    try{ const r = await fetch('/api/me', {credentials:'include'}); const j = await r.json(); isAuth = !!(j && j.auth); return isAuth; }catch{ return false; }
  }
  async function bootstrapAuthAndSync(){
    if (!(await isLoggedIn())) return;
    try{
      const r = await fetch('/api/chat/conversations', {credentials:'include'});
      if (!r.ok) return; const j = await r.json();
      if (!j || !j.items) return;
      j.items.forEach(c => {
        const lid = 'srv-'+c.id;
        if (!convs.find(x => x.id === lid)){
          convs.push({ id: lid, title: c.title || 'Unterhaltung', createdAt: c.created_at || Date.now(), updatedAt: c.updated_at || Date.now() });
          saveConvs();
        }
        setServerConvId(lid, c.id);
      });
      renderConversationList();
    }catch{}
  }
  async function ensureServerConversation(){
    let sid = getServerConvId(activeConv);
    if (sid) return sid;
    try{
      const title = (convs.find(c => c.id===activeConv)?.title) || 'Neue Unterhaltung';
      const r = await fetch('/api/chat/conversations', { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({title}) });
      const j = await r.json(); if (r.ok && j && j.id){ setServerConvId(activeConv, j.id); return j.id; }
    }catch{}
    return null;
  }
  async function fetchServerMessagesInto(localId){
    const sid = getServerConvId(localId); if (!sid) return;
    try{
      const r = await fetch(`/api/chat/conversations/${sid}/messages`, {credentials:'include'});
      const j = await r.json();
      if (r.ok && j && Array.isArray(j.items)){
        const msgs = j.items.map(m => ({ role: (m.role==='ai'?'ai':(m.role==='system'?'system':'user')), text: m.text, ts: m.created_at||Date.now() }));
        saveMessages(localId, msgs);
        if (localId === activeConv) renderActiveConversation();
      }
    }catch{}
  }

  async function refreshServerConvTitle(localId){
    const sid = getServerConvId(localId); if (!sid) return;
    try{
      const r = await fetch(`/api/chat/conversations/${sid}`, {credentials:'include'});
      const j = await r.json();
      if (r.ok && j && j.conversation){
        const c = convs.find(x => x.id === localId);
        if (c && j.conversation.title && j.conversation.title !== c.title){
          c.title = j.conversation.title; c.updatedAt = Date.now(); saveConvs(); renderConversationList();
        }
      }
    }catch{}
  }

  // ---------- Cleanup ----------
  window.addEventListener('beforeunload', () => {
    abortStream();
    stopSpeaking();
  });

  // ---------- Memory-Funktionen (neu ans Backend angepasst) ----------
  async function saveMemoryManually() {
    const text = (msgEl?.value || '').trim();
    if (!text) {
      toast('Kein Text zum Speichern.');
      return;
    }
    try {
      const res = await fetch('/api/memory/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          title: 'Notiz aus Chat',
          content: text,
          tags: ['chat']
        })
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        toast('Erinnerung gespeichert.');
      } else {
        toast('⚠️ Konnte Erinnerung nicht speichern.');
        console.error(data);
      }
    } catch (e) {
      toast('⚠️ Netzwerkfehler beim Speichern.');
      console.error(e);
    }
  }

  async function searchMemory() {
    const term = prompt('Wonach möchtest du im Gedächtnis suchen?');
    if (!term) return;
    try {
      const res = await fetch(`/api/memory/search?q=${encodeURIComponent(term)}`, {
        credentials: 'include'
      });
      const data = await res.json();
      if (res.ok && data && data.ok && Array.isArray(data.results)) {
        if (data.results.length === 0) {
          appendMsg('ai', '🔍 Nichts im Gedächtnis gefunden.');
        } else {
          const formatted = data.results.map(d => `• ${d.title || 'Ohne Titel'} – ${d.snippet || ''}`).join('\n');
          appendMsg('ai', `🔍 Gefundene Erinnerungen:\n\n${formatted}`);
        }
      } else {
        appendMsg('ai', '⚠️ Fehler bei der Gedächtnisabfrage.');
        console.error(data);
      }
    } catch (e) {
      appendMsg('ai', '⚠️ Netzwerkfehler bei der Gedächtnisabfrage.');
      console.error(e);
    }
  }

  // listMemory() war in der neuen API nicht mehr vorhanden → optional über /search('*') selbst bauen
  
  // ---------- Tabs + Address Book (Papa‑Modus) ----------
  function initTabs(){
    tabsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.tab');
      if (!btn) return;
      const tab = btn.dataset.tab;
      setActiveTab(tab);
      if (tab === 'addressbook') {
        if (!addressBookData || addressBookData.length === 0) {
          loadAddressBook();
        }
      }
    });
    if (addressBookSearch) {
      addressBookSearch.placeholder = 'Suche nach Thema, Pfad, Quelle…';
      addressBookSearch.addEventListener('input', debounce(() => {
        loadAddressBook(addressBookSearch.value.trim());
      }, 250));
    }
  }

  function setActiveTab(name){
    const tabs = Array.from(tabsContainer.querySelectorAll('.tab'));
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    if (name === 'chat'){
      document.querySelector('#chat').style.display = 'block';
      addressBookContent.style.display = 'none';
    } else if (name === 'addressbook'){
      document.querySelector('#chat').style.display = 'none';
      addressBookContent.style.display = 'block';
    }
  }

  async function loadAddressBook(q = ''){
    try {
      const url = q ? `/api/chat/addressbook?q=${encodeURIComponent(q)}` : '/api/chat/addressbook';
      addressBookList.innerHTML = '<p>Lade Adressbuch…</p>';
      const res = await fetch(url, { credentials: 'include' });
      const data = await res.json();
      if (!res.ok || !data || data.ok === false) {
        addressBookList.innerHTML = '<p>⚠️ Konnte Adressbuch nicht laden.</p>';
        return;
      }
      addressBookData = Array.isArray(data.blocks) ? data.blocks : [];
      renderAddressBook(addressBookData);
    } catch (e) {
      console.error(e);
      addressBookList.innerHTML = '<p>⚠️ Netzwerkfehler beim Laden.</p>';
    }
  }

  function renderAddressBook(items){
    if (!items || items.length === 0){
      addressBookList.innerHTML = '<p>Keine Einträge.</p>';
      return;
    }
    const rows = items.map(b => {
      const topic = escapeHtml(String(b.topic||''));
      const bid = escapeHtml(String(b.block_id||''));
      const path = escapeHtml(String(b.path||''));
      const source = escapeHtml(String(b.source||''));
      const tsRaw = b.timestamp;
      let ts = '';
      try {
        if (typeof tsRaw === 'number') ts = new Date(tsRaw*1000).toLocaleString();
        else if (typeof tsRaw === 'string') ts = new Date(tsRaw).toLocaleString();
      } catch {}
      const rating = (typeof b.rating === 'number') ? b.rating.toFixed(2) : '';
      const byIdHref = bid ? `/viewer/api/block/by-id/${encodeURIComponent(bid)}` : '';
      const dlHref = path ? `/viewer/api/block/download?file=${encodeURIComponent(path)}` : '';
      return `<tr>
        <td>${topic}</td>
        <td>${bid ? `<a href="${byIdHref}" target="_blank" rel="noopener">${bid}</a>` : ''}</td>
        <td>${path ? `<a href="${dlHref}" target="_blank" rel="noopener">${path.split('/').slice(-2).join('/')}</a>` : ''}</td>
        <td>${source ? `<a href="${escapeAttr(source)}" target="_blank" rel="noopener">Quelle</a>` : ''}</td>
        <td>${escapeHtml(ts)}</td>
        <td>${escapeHtml(String(rating))}</td>
      </tr>`;
    }).join('');
    const html = `
      <table class="address-table">
        <thead><tr>
          <th>Thema</th>
          <th>Block‑ID</th>
          <th>Pfad</th>
          <th>Quelle</th>
          <th>Zeit</th>
          <th>Rating</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
    addressBookList.innerHTML = html;
  }

  function debounce(fn, ms){
    let t = null; return (...args) => { clearTimeout(t); t = setTimeout(() => fn.apply(null, args), ms); };
  }
  function escapeHtml(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c])); }
  function escapeAttr(s){ try{ return String(s).replace(/"/g, '%22'); }catch{return s;} }

  // ========== SERVER-FIRST STORAGE ==========
  // New: Server-first approach with localStorage as backup
  
  let syncInProgress = false;
  let syncQueue = [];

  // Check if user is logged in
  function isLoggedIn() {
    try {
      const token = localStorage.getItem('ki_token');
      return !!token;
    } catch {
      return false;
    }
  }

  // Save messages: Server-first, localStorage as backup
  async function saveMessagesToServer(convId, messages) {
    if (!isLoggedIn()) return false;
    
    try {
      const serverConvId = getServerConvId(convId);
      if (!serverConvId) return false;

      // Save each message to server
      for (const msg of messages) {
        if (msg._synced) continue; // Already synced
        
        await fetch(`/api/conversations/${serverConvId}/messages`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + (localStorage.getItem('ki_token') || '')
          },
          credentials: 'include',
          body: JSON.stringify({
            role: msg.role,
            text: msg.text,
            created_at: msg.ts || Date.now()
          })
        });
        
        msg._synced = true;
      }
      
      return true;
    } catch (e) {
      console.warn('Server save failed:', e);
      return false;
    }
  }

  // Load messages: Server-first, localStorage as fallback
  async function loadMessagesFromServer(convId) {
    if (!isLoggedIn()) return null;
    
    try {
      const serverConvId = getServerConvId(convId);
      if (!serverConvId) return null;

      const r = await fetch(`/api/conversations/${serverConvId}/messages`, {
        headers: {
          'Authorization': 'Bearer ' + (localStorage.getItem('ki_token') || '')
        },
        credentials: 'include'
      });
      
      if (r.ok) {
        const data = await r.json();
        if (data.ok && Array.isArray(data.items)) {
          return data.items.map(m => ({
            role: m.role,
            text: m.text,
            ts: m.created_at || Date.now(),
            _synced: true
          }));
        }
      }
    } catch (e) {
      console.warn('Server load failed:', e);
    }
    
    return null;
  }

  // Enhanced saveMessages: Try server first, always save to localStorage
  const originalSaveMessages = saveMessages;
  saveMessages = async function(id, msgs) {
    // Always save to localStorage immediately
    originalSaveMessages(id, msgs);
    
    // Try to sync to server in background
    if (isLoggedIn() && !syncInProgress) {
      syncInProgress = true;
      try {
        await saveMessagesToServer(id, msgs);
      } catch (e) {
        console.warn('Background sync failed:', e);
      } finally {
        syncInProgress = false;
      }
    }
  };

  // Enhanced loadMessages: Try server first, fallback to localStorage
  const originalLoadMessages = loadMessages;
  loadMessages = async function(id) {
    // Try server first
    if (isLoggedIn()) {
      const serverMsgs = await loadMessagesFromServer(id);
      if (serverMsgs && serverMsgs.length > 0) {
        // Update localStorage with server data
        originalSaveMessages(id, serverMsgs);
        return serverMsgs;
      }
    }
    
    // Fallback to localStorage
    return originalLoadMessages(id);
  };

  // ========== FOLDER SUPPORT ==========
  
  let folders = [];
  let currentFolder = null;

  async function loadFolders() {
    if (!isLoggedIn()) return;
    
    try {
      const r = await fetch('/api/folders', {
        headers: {
          'Authorization': 'Bearer ' + (localStorage.getItem('ki_token') || '')
        },
        credentials: 'include'
      });
      
      if (r.ok) {
        const data = await r.json();
        if (data.ok && Array.isArray(data.folders)) {
          folders = data.folders;
          renderFolders();
        }
      }
    } catch (e) {
      console.warn('Failed to load folders:', e);
    }
  }

  async function createFolder(name, icon = '📁', color = '#667eea') {
    if (!isLoggedIn()) return null;
    
    try {
      const r = await fetch('/api/folders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + (localStorage.getItem('ki_token') || '')
        },
        credentials: 'include',
        body: JSON.stringify({ name, icon, color })
      });
      
      if (r.ok) {
        const data = await r.json();
        if (data.ok) {
          await loadFolders();
          return data.folder;
        }
      }
    } catch (e) {
      console.warn('Failed to create folder:', e);
    }
    
    return null;
  }

  async function moveConversationToFolder(convId, folderId) {
    if (!isLoggedIn()) return false;
    
    try {
      const serverConvId = getServerConvId(convId);
      if (!serverConvId) return false;

      const r = await fetch(`/api/folders/${folderId}/conversations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + (localStorage.getItem('ki_token') || '')
        },
        credentials: 'include',
        body: JSON.stringify({ conversation_ids: [serverConvId] })
      });
      
      return r.ok;
    } catch (e) {
      console.warn('Failed to move conversation:', e);
      return false;
    }
  }

  function renderFolders() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar || folders.length === 0) return;
    
    // Check if folders section already exists
    let foldersSection = sidebar.querySelector('.folders-section');
    if (!foldersSection) {
      foldersSection = document.createElement('div');
      foldersSection.className = 'folders-section';
      sidebar.insertBefore(foldersSection, sidebar.querySelector('.conversations-section'));
    }
    
    const foldersHTML = folders.map(f => `
      <div class="folder-item" data-folder-id="${f.id}">
        <span class="folder-icon">${f.icon}</span>
        <span class="folder-name">${escapeHtml(f.name)}</span>
        <span class="folder-count">${f.conversation_count || 0}</span>
      </div>
    `).join('');
    
    foldersSection.innerHTML = `
      <div class="folders-header">
        <h3>Ordner</h3>
        <button class="btn-icon" onclick="createFolderDialog()" title="Neuer Ordner">+</button>
      </div>
      <div class="folders-list">${foldersHTML}</div>
    `;
    
    // Add click handlers
    foldersSection.querySelectorAll('.folder-item').forEach(item => {
      item.addEventListener('click', () => {
        const folderId = parseInt(item.dataset.folderId);
        filterByFolder(folderId);
      });
    });
  }

  function filterByFolder(folderId) {
    currentFolder = folderId;
    renderConversationList();
  }

  function createFolderDialog() {
    const name = prompt('Ordner-Name:');
    if (!name) return;
    
    const icon = prompt('Icon (Emoji):', '📁') || '📁';
    const color = prompt('Farbe (Hex):', '#667eea') || '#667eea';
    
    createFolder(name, icon, color);
  }

  // Initialize folders on login
  if (isLoggedIn()) {
    loadFolders();
  }
})();
