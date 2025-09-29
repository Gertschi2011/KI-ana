// nav.js – lädt /static/nav.html in #nav, blendet Links je nach Login/Rolle/Submind ein,
// markiert aktiven Link und steuert das Hamburger-Menü.

(async function initNav() {
  async function ensureI18n(){
    if (window.i18n && typeof window.i18n.apply === 'function') return;
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = '/static/i18n.js';
      s.onload = resolve;
      s.onerror = () => reject(new Error('i18n load failed'));
      document.head.appendChild(s);
    }).catch(() => {});
  }

  const host = document.getElementById('nav');
  if (!host) return;

  // 1) Fragment laden
  const src = host.getAttribute('data-src') || '/static/nav.html';
  async function loadNav(url){
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error(`${r.status}`);
    const html = await r.text();
    host.innerHTML = html;
  }
  try {
    try { await loadNav(src); }
    catch { await loadNav('/nav'); }
  } catch (e) {
    console.warn('nav load failed', e);
    return;
  }

  // Load/apply i18n after nav is injected
  await ensureI18n();
  try { await (window.i18n?._ready || Promise.resolve());  } catch {}

  try { window.i18n && window.i18n.apply(host); } catch {}

  // 2) Loginstatus & User ermitteln
  let me = null;
  let caps = null;
  try {
    const r = await fetch('/api/me', { credentials: 'include' });
    if (r.ok) {
      const j = await r.json();
      if (j && (j.auth || j.logged_in)) {
        me = j.user || j.me || null;
        try{ caps = me && me.caps ? me.caps : null; }catch{}
      }
    }
  } catch (e) { /* ignore */ }

  // Inject 'Upgrade' link for free users only (now that `me` is available)
  try{
    const plan = (me && (me.plan || me.tier)) ? String(me.plan || me.tier).toLowerCase() : null;
    if (plan === 'free'){
      const nav = host.querySelector('.nav-links');
      if (nav && !nav.querySelector('#navUpgrade')){
        const up = document.createElement('a');
        up.id = 'navUpgrade';
        up.href = '/static/upgrade.html';
        up.textContent = 'Upgrade';
        up.setAttribute('title','Upgrade auf Papa/Creator');
        const logout = nav.querySelector('a[href="/logout"]');
        if (logout && logout.parentNode){ logout.parentNode.insertBefore(up, logout); }
        else { nav.appendChild(up); }
      }
    }
  }catch{}

  // 2a) Minimal browser error telemetry (rate-limited)
  (function initBrowserTelemetry(){
    try{
      const KEY_TS = 'tele.last';
      const KEY_CNT = 'tele.count';
      const LIMIT_PER_MIN = 8;
      function allowed(){
        try{
          const now = Date.now();
          const last = parseInt(localStorage.getItem(KEY_TS)||'0',10)||0;
          let cnt = parseInt(localStorage.getItem(KEY_CNT)||'0',10)||0;
          if (!last || now-last > 60*1000){ localStorage.setItem(KEY_TS, String(now)); localStorage.setItem(KEY_CNT, '0'); cnt = 0; }
          if (cnt >= LIMIT_PER_MIN) return false;
          localStorage.setItem(KEY_CNT, String(cnt+1));
          return true;
        }catch{ return false; }
      }
      async function send(evt){
        try{
          if (!allowed()) return;
          const payload = {
            level: 'error',
            kind: 'browser_error',
            message: String(evt.message || evt.reason || 'error'),
            url: String((evt.filename||evt.source||location.href)||''),
            line: evt.lineno||null,
            col: evt.colno||null,
            stack: evt.error && evt.error.stack ? String(evt.error.stack).slice(0,2000) : (evt.reason && evt.reason.stack ? String(evt.reason.stack).slice(0,2000) : null),
            user_agent: navigator.userAgent || '',
          };
          await fetch('/api/telemetry/error', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload), credentials:'include' }).catch(()=>{});
        }catch{}
      }
      window.addEventListener('error', (e)=>{ try{ send(e); }catch{} }, true);
      window.addEventListener('unhandledrejection', (e)=>{ try{ send(e); }catch{} });
    }catch{}
  })();

  // Replace 'Admin' label with username in the top nav if logged in
  try{
    const adminSum = host.querySelector('details.dropdown > summary[data-i18n="nav.admin"]');
    if (adminSum){
      const uname = (me && (me.name || me.username)) ? String(me.name || me.username) : null;
      if (uname){
        const short = uname.length > 24 ? (uname.slice(0, 22) + '…') : uname;
        adminSum.textContent = short;
        adminSum.setAttribute('title', uname);
        adminSum.removeAttribute('data-i18n');
      }
    }
  }catch{}

  // ---- Helpers --------------------------------------------------------------
  const toSet = (v) => {
    // akzeptiert: string | string[] | undefined | null | boolean-Flags -> Set<string>
    const s = new Set();
    if (!v && v !== 0) return s;
    if (typeof v === 'string') {
      v.split(',').map(x => x.trim().toLowerCase()).filter(Boolean).forEach(x => s.add(x));
    } else if (Array.isArray(v)) {
      v.map(x => (typeof x === 'string' ? x : (x && x.name) ? x.name : x))
       .map(String).map(x => x.trim().toLowerCase()).filter(Boolean).forEach(x => s.add(x));
    } else if (typeof v === 'boolean') {
      if (v) s.add('true');
    } else {
      s.add(String(v).trim().toLowerCase());
    }
    return s;
  };

  const normalizeUser = (u) => {
    const roles = new Set();

    // klassische Felder
    if (u?.role) roles.add(String(u.role).toLowerCase());
    toSet(u?.roles).forEach(x => roles.add(x));
    toSet(u?.permissions).forEach(x => roles.add(x));
    // häufige alternativen
    toSet(u?.groups).forEach(x => roles.add(x));
    toSet(u?.group).forEach(x => roles.add(x));
    toSet(u?.claims).forEach(x => roles.add(x));
    toSet(u?.scopes).forEach(x => roles.add(x));
    toSet(u?.authorities).forEach(x => roles.add(x));

    // bool flags → Rollen ergänzen
    if (u?.is_creator || u?.creator === true || u?.isCreator === true) roles.add('creator');
    if (u?.is_admin || u?.admin === true || u?.isAdmin === true || u?.is_owner || u?.owner === true) roles.add('admin');
    if (u?.is_papa || u?.papa === true || u?.isPapa === true) roles.add('papa');
    // Alias: 'worker' gilt im UI wie 'creator'
    if (roles.has('worker')) roles.add('creator');

    // "user" als Basisrolle für eingeloggte Accounts
    if (u) roles.add('user');

    // Subminds erfassen (IDs oder Objekte erlaubt)
    const submindIds = new Set();
    const submindsRaw = Array.isArray(u?.subminds) ? u.subminds : [];
    submindsRaw.forEach(item => {
      if (!item) return;
      if (typeof item === 'string') submindIds.add(item.toLowerCase());
      else if (typeof item === 'object' && item.id) submindIds.add(String(item.id).toLowerCase());
    });

    // Creator hat implizit alle Subminds (falls du das so möchtest)
    return { roles, submindIds };
  };

  const userCaps = normalizeUser(me);

  const hasAnyRole = (neededCSV) => {
    if (!neededCSV) return true; // kein Filter gesetzt
    const needed = toSet(neededCSV);
    if (!me) return false;
    for (const r of needed) if (userCaps.roles.has(r)) return true;
    return false;
  };

  const lacksNoRole = (blockedCSV) => {
    if (!blockedCSV) return true;
    const blocked = toSet(blockedCSV);
    for (const r of blocked) if (userCaps.roles.has(r)) return false;
    return true;
  };

  const hasSubmind = (id) => {
    if (!me) return false;
    if (!id) return userCaps.submindIds.size > 0; // nur "hat mind. 1 Submind?"
    return userCaps.submindIds.has(String(id).toLowerCase());
  };

  // ---------------------------------------------------------------------------
  // Worker lamp (admin/creator/worker)
  (function initWorkerLamp(){
    try{
      const lamp = host.querySelector('#workerLamp');
      if (!lamp) return;
      const hasAdmin = (() => {
        const r = userCaps.roles; return r.has('admin') || r.has('creator') || r.has('worker');
      })();

  // ---------------------------------------------------------------------------
  // Global System status pill (Ollama / Emergency)
  (function initSystemLamp(){
    try{
      const pill = host.querySelector('#sysLamp');
      const selfAmp = host.querySelector('#selfHealthAmpel');
      const llmLamp = host.querySelector('#llmLamp');
      if (!pill) return;
      async function poll(){
        try{
          const r = await fetch('/api/system/status', { credentials: 'include' });
          const j = await r.json();
          const m = j?.metrics || {};
          const ok = !!(m?.ollama?.available);
          const emergency = !!m?.emergency_active;
          let label = ok ? 'OK' : 'Problem';
          let bg = ok ? '#e6ffe6' : '#ffe6e6';
          let fg = ok ? '#1a4' : '#833';
          if (emergency){ label = 'Not‑Aus aktiv'; bg = '#ffe6e6'; fg = '#833'; }
          pill.textContent = label;
          pill.style.background = bg;
          pill.style.color = fg;
          const mdl = m?.ollama?.model ? (' – '+m.ollama.model) : '';
          pill.setAttribute('title', `Ollama: ${ok? 'verfügbar' : 'nicht verfügbar'}${mdl}`);
          // Self-Health ampel like Shell
          if (selfAmp){
            const hb = Number(m.worker_heartbeat_age||0);
            const anomalies = Array.isArray(m.anomalies)? m.anomalies : [];
            let sym = '🟢';
            if (anomalies.length>0 || hb>120) sym = '🔴';
            else if (hb>60) sym = '🟡';
            selfAmp.textContent = sym;
            selfAmp.setAttribute('title', `HB:${hb}s · steps:${m.plan_steps_queued||0} · jobs:${m.jobs||0} · anomalies:${anomalies.join(',')}`);
          }
          // LLM round lamp (green/red)
          if (llmLamp){
            llmLamp.classList.toggle('on', ok);
            llmLamp.classList.toggle('off', !ok);
            llmLamp.setAttribute('title', m?.ollama?.model ? `LLM: ${ok? 'OK' : 'Offline'} – ${m.ollama.model}` : (ok? 'LLM: OK' : 'LLM: Offline'));
          }
        }catch{
          pill.textContent = 'Offline';
          pill.style.background = '#ffe6e6';
          pill.style.color = '#833';
          pill.setAttribute('title', 'System offline');
          if (llmLamp){ llmLamp.classList.remove('on'); llmLamp.classList.add('off'); llmLamp.setAttribute('title','LLM: Offline'); }
        }
      }
      poll();
      setInterval(poll, 7000);
    }catch{}
  })();
      if (!hasAdmin){ lamp.style.display = 'none'; return; }
      let hbTimer = null;
      let hbStopped = false;
      async function poll(){
        try{
          const r = await fetch('/api/jobs/heartbeats', { credentials: 'include' });
          if (!r.ok) throw new Error('hb_http_'+r.status);
          const j = await r.json();
          const arr = Array.isArray(j?.items) ? j.items : [];
          const alive = arr.some(w => (w && typeof w.age === 'number' && w.age <= 60));
          lamp.classList.toggle('on', alive);
          lamp.classList.toggle('off', !alive);
          const tip = arr.map(w => `${w.name||'?'} ${Math.max(0, Math.round(w.age||0))}s`).join(', ');
          lamp.setAttribute('title', tip || (alive ? 'Worker aktiv' : 'Keine Heartbeats'));
        }catch{
          lamp.classList.remove('on'); lamp.classList.add('off'); lamp.setAttribute('title','Worker Status unbekannt');
          // Stop polling after first failure to keep console quiet on missing endpoint
          if (!hbStopped && hbTimer){ clearInterval(hbTimer); hbStopped = true; }
        }
      }
      poll();
      hbTimer = setInterval(poll, 10000);
    }catch{}
  })();

  // Allow manual extra roles via localStorage for debugging (comma separated)
  try{
    const extra = localStorage.getItem('kiana.roles.extra') || '';
    toSet(extra).forEach(x => userCaps.roles.add(x));
  }catch{}

  const root = host.querySelector('.site-header') || host;
  const links = root.querySelectorAll('.nav-links a');

  // 3) Sichtbarkeit: data-auth / data-guest / data-role / data-role-not / data-submind / data-submind-id
  links.forEach(a => {
    const needAuth   = a.hasAttribute('data-auth');
    const needGuest  = a.hasAttribute('data-guest');
    const needRole   = a.getAttribute('data-role');      // "creator" oder "creator,admin"
    const blockRole  = a.getAttribute('data-role-not');  // optional Negativfilter
    const needSm     = a.getAttribute('data-submind');   // "1" → mind. ein Submind
    const needSmId   = a.getAttribute('data-submind-id');// spezifisches Submind (z.B. "emo-001")

    // auth/guest
    if (needAuth && !me)   { a.style.display = 'none'; return; }
    if (needGuest && me)   { a.style.display = 'none'; return; }

    // Rollenfilter
    if (needRole && !hasAnyRole(needRole)) {
      // Light debug for Papa/Viewer visibility issues
      try{
        const name = (a.textContent||'').trim().toLowerCase();
        if (name === 'papa' || name.includes('viewer')){
          console.debug('nav: hiding', name, 'needed roles=', needRole, 'have=', Array.from(userCaps.roles));
        }
      }catch{}
      a.style.display = 'none'; return; }
    if (blockRole && !lacksNoRole(blockRole)) { a.style.display = 'none'; return; }

    // Caps-based gating (in addition to roles):
    try{
      const patt = (a.getAttribute('data-match')||'').toLowerCase();
      if (patt.includes('viewer')){
        if (!(caps && caps.can_view_block_viewer)) { a.style.display = 'none'; return; }
      }
      if (patt.includes('admin')){
        if (!(caps && caps.can_view_admin)) { a.style.display = 'none'; return; }
      }
    }catch{}

    // Submind-Filter
    if (needSm != null) { // Attribut existiert
      if (!hasSubmind(needSmId)) { a.style.display = 'none'; return; }
    }
  });

  // 3b) Dropdown-Container verstecken, wenn alle Kind-Links versteckt sind
  root.querySelectorAll('details.dropdown').forEach(d => {
    const items = Array.from(d.querySelectorAll('.submenu a'));
    const visible = items.some(x => x.style.display !== 'none');
    if (!visible) d.style.display = 'none';
  });

  // 4) Aktiven Link markieren
  const path = location.pathname;
  links.forEach(a => {
    const patt = a.getAttribute('data-match');
    if (!patt) return;
    try {
      const re = new RegExp(patt);
      if (re.test(path)) {
        a.classList.add('active');
        // Parent-Dropdown (falls vorhanden) nur visuell markieren – nicht automatisch geöffnet lassen
        const parentDetails = a.closest('details.dropdown');
        if (parentDetails) {
          const sum = parentDetails.querySelector('summary');
          if (sum) sum.classList.add('active');
        }
      }
    } catch { /* ignore invalid regex */ }
  });

  // 5) Hamburger-Menü
  const toggle = root.querySelector('.nav-toggle');
  const menu   = root.querySelector('.nav-links');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    // Menü schließen beim Klick auf einen Link (mobil)
    menu.addEventListener('click', (e) => {
      const a = e.target.closest('a');
      if (!a) return;
      // Offene Dropdowns schließen, damit das Menü nicht "kleben" bleibt
      root.querySelectorAll('details[open]').forEach(d => d.removeAttribute('open'));
      if (menu.classList.contains('open')) {
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  // 6) Language selector
  const sel = root.querySelector('#langSelect');
  if (sel && window.i18n){
    try { sel.value = window.i18n.lang || (localStorage.getItem('lang') || 'de'); } catch {}
    sel.addEventListener('change', (e) => {
      const val = sel.value || 'de';
      window.i18n.setLang(val);
    });
    // update select on external changes
    window.addEventListener('i18n:change', (ev) => {
      if (!sel) return;
      const lang = ev?.detail?.lang || window.i18n.lang;
      if (lang && sel.value !== lang) sel.value = lang;
    });
  }

  // 7) Mixed-content sanitizer: rewrite http:// to https:// for media/links
  (function httpsSanitizer(){
    try{
      const isLocal = (u)=> /^(http:\/\/)?(localhost|127\.0\.0\.1)(:|\/|$)/i.test(u||'');
      const fix = (el, attr)=>{
        try{
          const v = el.getAttribute(attr);
          if (!v || typeof v !== 'string') return;
          if (v.startsWith('http://') && !isLocal(v)){
            el.setAttribute(attr, 'https://' + v.slice('http://'.length));
          }
        }catch{}
      };
      const scan = (root)=>{
        try{
          const tags = [
            ['a','href'], ['link','href'], ['img','src'], ['script','src'],
            ['audio','src'], ['video','src'], ['source','src'],
            ['iframe','src']
          ];
          for (const [tag, attr] of tags){
            root.querySelectorAll(tag+'['+attr+']').forEach(el=>fix(el, attr));
          }
        }catch{}
      };
      // initial pass
      scan(document);
      // observe future additions
      const mo = new MutationObserver((mutList)=>{
        for (const m of mutList){ if (m.addedNodes){ m.addedNodes.forEach(n=>{ if (n.nodeType===1) scan(n); }); } }
      });
      mo.observe(document.documentElement || document.body, { childList:true, subtree:true });
    }catch{}
  })();
})();
