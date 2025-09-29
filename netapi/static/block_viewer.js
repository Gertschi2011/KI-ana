(() => {
  const $ = (sel, p = document) => p.querySelector(sel);
  const qEl = $('#q');
  const verifiedEl = $('#verifiedOnly');
  const sortSel = $('#sortBy');
  const listEl = $('#list');
  const countEl = $('#count');
  const viewModeSel = $('#viewMode');
  const pagerInfoEl = $('#pagerInfo');
  const prevBtn = $('#prevPage');
  const nextBtn = $('#nextPage');
  const pageSizeSel = $('#pageSize');
  const pageJumpInp = $('#pageJump');
  const goPageBtn = $('#goPage');
  const exportAllToggle = $('#exportAllToggle');
  const exportBtn = $('#exportCsv');
  let items = [];
  let health = null;
  let meCaps = null;
  let page = 1;
  let pages = 1;
  let limit = 50;
  let viewMode = 'table';

  // --- i18n helper (uses global window.i18n if present) ---
  const tr = (key, fallback) => {
    try { return (window.i18n && window.i18n.t(key, fallback)) || fallback; } catch { return fallback; }
  };
  const roleDeniedMsg = () => tr('toast.role_denied', '⚠️ Keine Berechtigung für diese Aktion.');
  const loginRequiredMsg = () => tr('toast.login_required', '⚠️ Login erforderlich.');

  // Modal elements
  const modal = {
    root: document.getElementById('detail-modal'),
    btnClose: document.getElementById('detail-close'),
    title: document.getElementById('detail-title'),
    elId: document.getElementById('detail-block-id'),
    elTopic: document.getElementById('detail-topic'),
    elSource: document.getElementById('detail-source'),
    elPath: document.getElementById('detail-path'),
    elTs: document.getElementById('detail-ts'),
    elTrust: document.getElementById('detail-trust'),
    elJson: document.getElementById('detail-json'),
    inputRating: document.getElementById('detail-rating'),
    btnRate: document.getElementById('detail-rate-btn'),
    rateStatus: document.getElementById('detail-rate-status'),
    btnRehash: document.getElementById('detail-rehash-btn'),
    rehashStatus: document.getElementById('detail-rehash-status'),
    openJson: document.getElementById('detail-open-json'),
    openDownload: document.getElementById('detail-download'),
  };

  function openModal(){ if (modal.root) modal.root.style.display = 'flex'; }
  function closeModal(){ if (modal.root) modal.root.style.display = 'none'; }
  modal.btnClose?.addEventListener('click', closeModal);

  function debounce(fn, ms){ let t=null; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(null,a),ms); } }
  function escapeHtml(s){ return String(s||'').replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
  function escapeAttr(s){ try{ return String(s).replace(/"/g, '%22'); }catch{return s;} }

  // --- URL query sync ------------------------------------------------------
  function readStateFromUrl(){
    try{
      const u = new URL(window.location.href);
      const p = u.searchParams;
      // q
      const qv = p.get('q'); if (qv!=null && qEl) { qEl.value = qv; }
      // verified (1/true)
      const vv = p.get('verified'); if (vv!=null && verifiedEl){ const b = (vv==='1'||vv==='true'); verifiedEl.checked = b; }
      // sort
      const sv = p.get('sort'); if (sv && sortSel){ sortSel.value = sv; }
      // page/limit
      const pv = parseInt(p.get('page')||'', 10); if (!isNaN(pv) && pv>0) page = pv;
      const lv = parseInt(p.get('limit')||'', 10); if (!isNaN(lv) && lv>0) limit = Math.max(1, Math.min(200, lv));
      // view
      const vw = p.get('view'); if (vw && (vw==='table'||vw==='cards')){ viewMode = vw; if (viewModeSel) viewModeSel.value = vw; }
    }catch{}
  }
  function updateUrl(){
    try{
      const u = new URL(window.location.href);
      const p = u.searchParams;
      if (qEl){ const v = (qEl.value||'').trim(); if (v) p.set('q', v); else p.delete('q'); }
      if (verifiedEl){ p.set('verified', verifiedEl.checked ? '1' : '0'); }
      if (sortSel){ const v = String(sortSel.value||'none'); if (v && v!=='none') p.set('sort', v); else p.delete('sort'); }
      p.set('page', String(page));
      p.set('limit', String(limit));
      p.set('view', String(viewMode||'table'));
      const nxt = u.pathname + '?' + p.toString() + u.hash;
      window.history.replaceState(null, '', nxt);
    }catch{}
  }

  async function fetchJSON(url, opts = {}){
    const hdrs = Object.assign({}, opts.headers||{});
    const token = localStorage.getItem('kiana_jwt');
    if (token) hdrs['Authorization'] = `Bearer ${token}`;
    const res = await fetch(url, { ...opts, headers: hdrs, credentials: 'include' });
    const data = await res.json().catch(()=>null);
    if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), {res, data});
    return data;
  }

  async function showBlockDetail(blockId){
    try{
      // Metadaten aus bereits geladener Liste entnehmen (Quelle/Path/Trust/Rating)
      const it = items.find(x => x.id === blockId) || {};
      const topic = it.topic || '';
      const source = it.source || '';
      const path = it.file || '';
      const ts = it.timestamp || '';
      if (modal.title) modal.title.textContent = `Block Details – ${topic}`;
      if (modal.elId) modal.elId.textContent = blockId;
      if (modal.elTopic) modal.elTopic.textContent = topic;
      if (modal.elSource){
        if (source && /^https?:\/\//i.test(source)){
          // Enforce https to avoid mixed content warnings
          const s = String(source).replace(/^http:\/\//i, 'https://');
          modal.elSource.innerHTML = `<a href="${escapeAttr(s)}" target="_blank" rel="noopener">Quelle öffnen</a>`;
        } else {
          modal.elSource.textContent = source || '';
        }
      }
      if (modal.elPath) modal.elPath.textContent = path;
      if (modal.elTs) modal.elTs.textContent = ts;
      if (modal.inputRating) modal.inputRating.value = (typeof it.rating_avg === 'number' ? it.rating_avg : '').toString();
      if (modal.rateStatus) modal.rateStatus.textContent = '';
      // Trust aus signals formatieren
      try{
        if (modal.elTrust){
          if (it && it.trust && typeof it.trust.score === 'number'){
            const s = Number(it.trust.score);
            const sig = it.trust.signals || {};
            const parts = [];
            if (typeof sig.rating === 'number') parts.push(`rating:${Number(sig.rating).toFixed(2)}`);
            if (typeof sig.source === 'number') parts.push(`source:${Number(sig.source).toFixed(2)}`);
            if (typeof sig.age === 'number') parts.push(`age:${Number(sig.age).toFixed(2)}`);
            if (typeof sig.consistency === 'number') parts.push(`cons:${Number(sig.consistency).toFixed(2)}`);
            modal.elTrust.textContent = `${s.toFixed(2)}${parts.length? ' ('+parts.join(', ')+')':''}`;
          } else {
            modal.elTrust.textContent = '';
          }
        }
      }catch{}
  // Sign ALL button in toolbar
  try{
    const signAllBtn = document.getElementById('signAllBtn');
    const signAllStatus = document.getElementById('signAllStatus');
    signAllBtn?.addEventListener('click', async ()=>{
      if (!signAllBtn) return;
      signAllBtn.disabled = true; if (signAllStatus) signAllStatus.textContent = 'Signiere…';
      try{
        const res = await fetchJSON('/viewer/api/block/sign-all', { method: 'POST' });
        if (signAllStatus) signAllStatus.textContent = `✓ geprüft: ${res.checked||0}, signiert: ${res.signed||0}`;
        setTimeout(()=>{ if (signAllStatus) signAllStatus.textContent=''; }, 2500);
        load();
      }catch(e){
        const status = (e && e.res && e.res.status) || 0;
        if (signAllStatus) signAllStatus.textContent = status===403? roleDeniedMsg() : 'Fehler beim Signieren';
        setTimeout(()=>{ if (signAllStatus) signAllStatus.textContent=''; }, 3500);
      } finally { if (signAllBtn) signAllBtn.disabled = false; }
    });
  }catch{}
      // JSON-Inhalt per /viewer/api/block/by-id/{id} laden
      let content = {};
      try{
        const data = await fetchJSON(`/viewer/api/block/by-id/${encodeURIComponent(blockId)}`);
        content = (data && data.block) ? data.block : {};
      }catch(e){ console.error('by-id fetch failed', e); }
      if (modal.elJson) modal.elJson.textContent = JSON.stringify(content, null, 2);
      // Links setzen
      try{
        if (modal.openJson){ modal.openJson.href = `/viewer/api/block/by-id/${encodeURIComponent(blockId)}`; }
        if (modal.openDownload && path){ modal.openDownload.href = `/viewer/api/block/download?file=${encodeURIComponent(path)}`; }
      }catch{}
      openModal();
    }catch(e){
      console.error(e);
      const status = (e && e.res && e.res.status) || 0;
      if (status === 401) alert(loginRequiredMsg());
      else if (status === 403) alert(roleDeniedMsg());
      else alert(tr('viewer.error.detail_load_failed', 'Konnte Details nicht laden.'));
    }
  }

  modal.btnRate?.addEventListener('click', async () => {
    const bid = (modal.elId?.textContent || '').trim();
    let rating = NaN;
    try{ rating = parseFloat(modal.inputRating?.value || ''); }catch{}
    if (!bid || Number.isNaN(rating)){
      if (modal.rateStatus) modal.rateStatus.textContent = 'Bitte gültige Werte angeben.';
      return;
    }
    try{
      const res = await fetchJSON('/viewer/api/block/rate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: bid, score: rating })
      });
      if (modal.rateStatus) modal.rateStatus.textContent = 'Gespeichert ✓';
      // Update Rating in Tabelle (live)
      try{
        const newRating = (typeof res?.avg === 'number') ? res.avg : (typeof res?.rating === 'number' ? res.rating : rating);
        const item = items.find(x => x.id === bid);
        if (item) item.rating_avg = newRating;
        const row = listEl.querySelector(`tr[data-block-id="${bid}"]`);
        if (row){
          const cells = row.querySelectorAll('td');
          if (cells && cells[7]) cells[7].textContent = (Number(newRating).toFixed(2));
        }
      }catch{}
      setTimeout(()=>{ if (modal.rateStatus) modal.rateStatus.textContent=''; }, 1500);
    }catch(e){
      console.error(e);
      const status = (e && e.res && e.res.status) || 0;
      const msg = status === 401 ? loginRequiredMsg() : (status === 403 ? roleDeniedMsg() : tr('viewer.error.save_failed','Fehler beim Speichern'));
      if (modal.rateStatus) modal.rateStatus.textContent = msg;
    }
  });

  async function load(){
    try{
      listEl.innerHTML = '<p>Lade Blöcke…</p>';
      const vo = verifiedEl?.checked ? 'true' : 'false';
      const q = encodeURIComponent(String(qEl?.value||''));
      const sort = encodeURIComponent(String(sortSel?.value||'none'));
      const url = `/viewer/api/blocks?verified_only=${vo}&q=${q}&sort=${sort}&page=${page}&limit=${limit}`;
      const j = await fetchJSON(url);
      items = Array.isArray(j.items) ? j.items : [];
      pages = Math.max(1, parseInt(j.pages||1,10));
      page = Math.max(1, Math.min(pages, parseInt(j.page||page,10)));
      // set UI
      try{
        if (pagerInfoEl){
          const total = parseInt(j.total||items.length,10);
          const start = total? ((page-1)*limit + 1) : 0;
          const end = Math.min(total, page*limit);
          pagerInfoEl.textContent = total ? `${start}-${end} von ${total}` : '—';
        }
        if (prevBtn) prevBtn.disabled = (page<=1);
        if (nextBtn) nextBtn.disabled = (page>=pages);
        if (pageSizeSel) { const v = String(limit); if (pageSizeSel.value !== v) pageSizeSel.value = v; }
        if (pageJumpInp) pageJumpInp.value = String(page);
      }catch{}
      updateUrl();
      render();
    }catch(e){ console.error(e); listEl.innerHTML = '<p>⚠️ Netzwerkfehler.</p>'; }
  }

  function render(){
    let q = (qEl?.value || '').trim().toLowerCase();
    let data = !q ? items.slice() : items.filter(it => {
      const hay = `${it.title||''} ${it.topic||''} ${it.source||''} ${it.origin||''}`.toLowerCase();
      return hay.includes(q);
    });
    // Sortierschalter anwenden
    const mode = sortSel?.value || 'none';
    try{
      if (mode === 'trust'){
        data.sort((a,b) => (Number(b?.trust?.score||0) - Number(a?.trust?.score||0)));
      } else if (mode === 'rating'){
        data.sort((a,b) => (Number(b?.rating_avg||0) - Number(a?.rating_avg||0)));
      } else if (mode === 'time'){
        const toTs = (x) => { if (!x) return 0; if (typeof x==='number') return x; const d=Date.parse(x); return isNaN(d)?0:d; };
        data.sort((a,b)=> toTs(b?.timestamp) - toTs(a?.timestamp));
      }
    }catch{}
    countEl.textContent = `${data.length} Einträge (Seite ${page}/${pages})`;
    if (!data.length){ listEl.innerHTML = '<p>Keine Einträge.</p>'; return; }
    if (viewMode === 'cards'){
      const cards = data.map(it => {
        const id = escapeHtml(it.id);
        const t = escapeHtml(it.title || '');
        const topic = escapeHtml(it.topic || '');
        const origin = escapeHtml(it.origin || '');
        const src = escapeHtml(it.source || '');
        const srcLink = (it.source && /^https?:\/\//i.test(it.source)) ? String(it.source).replace(/^http:\/\//i,'https://') : '';
        const valid = (it.valid && it.sig_valid) ? '✅ verifiziert' : '⚠️ unsicher';
        const trust = (it.trust && typeof it.trust.score === 'number') ? Number(it.trust.score).toFixed(2) : '';
        const ts = escapeHtml(it.timestamp || '');
        const dl = `/viewer/api/block/download?file=${encodeURIComponent(it.file || '')}`;
        return `<div class="card-item" data-block-id="${id}">
          <div class="card-head">
            <div class="card-title">${t || id}</div>
            <span class="badge">Trust ${trust||'—'}</span>
          </div>
          <div class="muted-sm">${topic ? ('Topic: '+topic+' · ') : ''}${origin}</div>
          <div>${srcLink ? `<a href="${escapeAttr(srcLink)}" target="_blank" rel="noopener">Quelle</a>` : (src||'')}</div>
          <div class="muted-sm">${valid} · ${ts}</div>
          <div class="row-actions">
            <a href="#" data-action="detail" data-bid="${id}">Details</a>
            ${it.file ? `<a href="${dl}" target="_blank" rel="noopener">Download</a>` : ''}
          </div>
        </div>`;
      }).join('');
      listEl.innerHTML = `<div class="cards">${cards}</div>`;
      return;
    }
    const rows = data.map(it => {
      const id = escapeHtml(it.id);
      const t = escapeHtml(it.title || '');
      const topic = escapeHtml(it.topic || '');
      const origin = escapeHtml(it.origin || '');
      const src = escapeHtml(it.source || '');
      const valid = (it.valid && it.sig_valid) ? '✅' : '⚠️';
      const size = typeof it.size === 'number' ? String(it.size) : '';
      const ts = escapeHtml(it.timestamp || '');
      const trust = (it.trust && typeof it.trust.score === 'number') ? Number(it.trust.score).toFixed(2) : '';
      const byId = `/viewer/api/block/by-id/${encodeURIComponent(id)}`;
      const dl = `/viewer/api/block/download?file=${encodeURIComponent(it.file || '')}`;
      const srcLink = (it.source && /^https?:\/\//i.test(it.source)) ? String(it.source).replace(/^http:\/\//i,'https://') : '';
      return `<tr data-block-id="${id}">
        <td>${id}</td>
        <td>${t}</td>
        <td>${topic}</td>
        <td>${origin}</td>
        <td>${srcLink ? `<a href="${escapeAttr(srcLink)}" target="_blank" rel="noopener">Quelle</a>` : src}</td>
        <td>${valid}</td>
        <td>${size}</td>
        <td>${escapeHtml(String(it.rating_avg ?? ''))}</td>
        <td>${trust}</td>
        <td>${ts}</td>
        <td class="row-actions">
          <a href="#" data-action="detail" data-bid="${id}">Details</a>
          ${it.file ? `<a href="${dl}" target="_blank" rel="noopener">Download</a>` : ''}
        </td>
      </tr>`;
    }).join('');
    listEl.innerHTML = `<table id="blocks-table">
      <thead><tr>
        <th>ID</th><th>Titel</th><th>Topic</th><th>Quelle</th><th>Source</th><th>OK</th><th>Bytes</th><th>Rating</th><th>Trust</th><th>Zeit</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }

  qEl?.addEventListener('input', debounce(()=>{ page = 1; updateUrl(); render(); }, 200));
  verifiedEl?.addEventListener('change', ()=>{ page = 1; updateUrl(); load(); });
  sortSel?.addEventListener('change', ()=>{ page = 1; updateUrl(); render(); });
  // Also reload from server when sort changes to apply server-side sort
  sortSel?.addEventListener('change', ()=>{ page = 1; updateUrl(); load(); });
  viewModeSel?.addEventListener('change', ()=>{ try{ viewMode = String(viewModeSel.value||'table'); localStorage.setItem('viewer.viewMode', viewMode); }catch{} render(); });
  pageSizeSel?.addEventListener('change', ()=>{ try{ limit = parseInt(pageSizeSel.value||'50',10)||50; }catch{ limit=50; } try{ localStorage.setItem('viewer.pageSize', String(limit)); }catch{} page = 1; updateUrl(); load(); });
  prevBtn?.addEventListener('click', ()=>{ if (page>1){ page--; updateUrl(); load(); } });
  nextBtn?.addEventListener('click', ()=>{ if (page<pages){ page++; updateUrl(); load(); } });
  goPageBtn?.addEventListener('click', ()=>{ try{ const v = parseInt(pageJumpInp.value||'1',10)||1; page = Math.max(1, Math.min(pages, v)); updateUrl(); load(); }catch{} });
  pageJumpInp?.addEventListener('keydown', (e)=>{ if (e.key==='Enter'){ e.preventDefault(); goPageBtn?.click(); } });
  exportBtn?.addEventListener('click', async ()=>{
    try{
      const exportAll = !!(exportAllToggle && exportAllToggle.checked);
      const headers = ['id','title','topic','source','origin','timestamp','valid','sig_valid','rating_avg','rating_count','trust_score'];
      const rows = [headers.join(',')];
      const writeItem = (it)=>{
        const vals = [
          it.id,
          (it.title||'').replaceAll('"','""'),
          (it.topic||'').replaceAll('"','""'),
          (it.source||'').replaceAll('"','""'),
          (it.origin||'').replaceAll('"','""'),
          (it.timestamp||'').toString().replaceAll('"','""'),
          it.valid ? '1':'0',
          it.sig_valid ? '1':'0',
          (it.rating_avg!=null? it.rating_avg : ''),
          (it.rating_count!=null? it.rating_count : ''),
          (it.trust && it.trust.score!=null? it.trust.score : ''),
        ].map(v => (typeof v === 'string' ? `"${v}"` : String(v)));
        rows.push(vals.join(','));
      };
      if (!exportAll){
        items.forEach(writeItem);
      } else {
        // Page through results with current filters
        const MAX_ROWS = 10000; // safety cap
        const query = new URLSearchParams({
          verified_only: (verifiedEl?.checked ? 'true' : 'false'),
          q: String(qEl?.value||''),
          sort: String(sortSel?.value||'none')
        });
        let pCur = 1;
        const lim = 200;
        let total = 0;
        let written = 0;
        countEl && (countEl.textContent = 'Export…');
        while (true){
          const url = `/viewer/api/blocks?${query.toString()}&page=${pCur}&limit=${lim}`;
          const j = await fetchJSON(url);
          const list = Array.isArray(j.items)? j.items : [];
          if (pCur === 1){ total = parseInt(j.total||list.length,10); }
          if (!list.length) break;
          for (const it of list){ writeItem(it); written++; if (written >= MAX_ROWS) break; }
          countEl && (countEl.textContent = `Export ${Math.min(written, total)}/${total}`);
          if (written >= MAX_ROWS) break;
          pCur++;
          if (pCur > Math.max(1, parseInt(j.pages||pCur,10))) break;
        }
      }
      const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = exportAll ? 'blocks_all.csv' : `blocks_page_${page}.csv`;
      document.body.appendChild(a); a.click();
      setTimeout(()=>{ URL.revokeObjectURL(url); a.remove(); }, 0);
      countEl && (countEl.textContent = `${items.length} Einträge (Seite ${page}/${pages})`);
    }catch(e){ console.error('CSV export failed', e); }
  });
  // Fetch /api/me caps for permission gating
  async function loadCaps(){
    try{
      const r = await fetch('/api/me', { credentials: 'include' });
      if (r.ok){ const j = await r.json(); meCaps = (j && j.user && j.user.caps) ? j.user.caps : null; }
    }catch{ meCaps = null; }
  }
  // Rehash ALL button in toolbar
  try{
    const rehashAllBtn = document.getElementById('rehashAllBtn');
    const rehashAllStatus = document.getElementById('rehashAllStatus');
    // gate by caps
    (async ()=>{ try{ await loadCaps(); if (rehashAllBtn && meCaps && meCaps.can_rehash_blocks === false){ rehashAllBtn.disabled = true; rehashAllBtn.title = 'Keine Berechtigung'; } }catch{} })();
    rehashAllBtn?.addEventListener('click', async ()=>{
      if (!rehashAllBtn) return;
      rehashAllBtn.disabled = true; if (rehashAllStatus) rehashAllStatus.textContent = 'Rechne neu…';
      try{
        const res = await fetchJSON('/viewer/api/block/rehash-all', { method: 'POST' });
        if (rehashAllStatus) rehashAllStatus.textContent = `✓ geprüft: ${res.checked||0}, korrigiert: ${res.fixed||0}`;
        setTimeout(()=>{ if (rehashAllStatus) rehashAllStatus.textContent=''; }, 2500);
        load();
      }catch(e){
        const status = (e && e.res && e.res.status) || 0;
        if (rehashAllStatus) rehashAllStatus.textContent = status===403? roleDeniedMsg() : 'Fehler beim Rehash-All';
        setTimeout(()=>{ if (rehashAllStatus) rehashAllStatus.textContent=''; }, 3500);
      } finally { if (rehashAllBtn) rehashAllBtn.disabled = false; }
    });
  }catch{}
  // Delegate clicks for Details/view
  listEl?.addEventListener('click', (ev) => {
    const a = ev.target?.closest('a[data-action="detail"]');
    if (a){
      ev.preventDefault();
      const bid = a.getAttribute('data-bid');
      if (bid) showBlockDetail(bid);
      return;
    }
    const tr = ev.target?.closest('tr[data-block-id]');
    if (tr){
      const bid = tr.getAttribute('data-block-id');
      if (bid) showBlockDetail(bid);
    }
  });
  // Per-file rehash button (in modal)
  modal.btnRehash?.addEventListener('click', async ()=>{
    const p = (modal.elPath?.textContent||'').trim();
    if (!p){ if (modal.rehashStatus) modal.rehashStatus.textContent = 'Kein Pfad'; return; }
    // permission gate
    try{ if (meCaps && meCaps.can_rehash_blocks === false){ if (modal.rehashStatus) modal.rehashStatus.textContent = roleDeniedMsg(); return; } }catch{}
    if (modal.btnRehash) modal.btnRehash.disabled = true; if (modal.rehashStatus) modal.rehashStatus.textContent = 'Rechne neu…';
    try{
      await fetchJSON('/viewer/api/block/rehash', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ file: p }) });
      if (modal.rehashStatus) modal.rehashStatus.textContent = '✓ aktualisiert';
      setTimeout(()=>{ if (modal.rehashStatus) modal.rehashStatus.textContent=''; }, 2000);
      // Reload list to reflect status
      load();
    }catch(e){
      const status = (e && e.res && e.res.status) || 0;
      if (modal.rehashStatus) modal.rehashStatus.textContent = status===401? loginRequiredMsg() : 'Fehler beim Rehash';
      setTimeout(()=>{ if (modal.rehashStatus) modal.rehashStatus.textContent=''; }, 3500);
    } finally { if (modal.btnRehash) modal.btnRehash.disabled = false; }
  });
  // Health pills
  async function loadHealth(){
    try{
      const j = await fetchJSON('/viewer/api/blocks/health');
      health = j;
      const pill = document.getElementById('healthPill');
      const cov = document.getElementById('coveragePill');
      const signBtn = document.getElementById('signAllBtn');
      if (pill && j && j.signer){
        const ok = !!j.signer.available;
        const keys = !!j.signer.keys_present;
        pill.style.display = '';
        pill.textContent = ok ? (keys ? 'Signer: OK (Keys)' : 'Signer: OK (Keys fehlen)') : 'Signer: nicht verfügbar';
        pill.style.background = ok ? '#e6ffe6' : '#ffe6e6';
        pill.style.color = ok ? '#1a4' : '#833';
        if (signBtn){
          // gate by signer and caps
          if (!ok){ signBtn.disabled = true; signBtn.title = 'Signer nicht verfügbar'; }
          try{ if (meCaps && meCaps.can_sign_blocks === false){ signBtn.disabled = true; signBtn.title = (signBtn.title? (signBtn.title+'; '):'') + 'Keine Berechtigung'; } }catch{}
        }
      }
      if (cov && j && j.stats){
        const total = Number(j.stats.total||0);
        const ok = Number(j.stats.signature_ok||0);
        cov.style.display = '';
        cov.textContent = total ? `Verifiziert: ${ok}/${total} (${Number(j.stats.verified_ok_percent||0).toFixed(1)}%)` : 'Verifiziert: 0';
      }
    }catch{}
  }
  (async ()=>{
    try{
      // URL takes precedence, then localStorage fallbacks
      readStateFromUrl();
      // Apply persisted defaults if URL missing
      const saved = localStorage.getItem('viewer.pageSize');
      if (saved && !(new URL(window.location.href)).searchParams.get('limit')){
        const n = parseInt(saved,10); if (n && !isNaN(n)) limit = Math.max(1, Math.min(200, n));
      }
      if (pageSizeSel) { const v = String(limit); if (pageSizeSel.value !== v) pageSizeSel.value = v; }
    }catch{}
    try{
      const urlVM = (new URL(window.location.href)).searchParams.get('view');
      if (!urlVM){
        const vm = localStorage.getItem('viewer.viewMode');
        if (vm){ viewMode = (vm==='cards'?'cards':'table'); if (viewModeSel) viewModeSel.value = viewMode; }
      }
    }catch{}
    try{ await loadCaps(); }catch{}; loadHealth(); load();
  })();
})();
