(() => {
  const $ = (sel, p=document) => p.querySelector(sel);
  const qEl = $('#q');
  const tagEl = $('#tag');
  const limitEl = $('#limit');
  const reloadBtn = $('#reload');
  const listEl = $('#list');
  const modal = $('#modal');
  const modalBody = $('#modalBody');
  const modalClose = $('#modalClose');
  const pagerInfoEl = $('#pagerInfo');
  const prevBtn = $('#prev');
  const nextBtn = $('#next');
  const exportCsvBtn = $('#exportCsv');
  const exportJsonBtn = $('#exportJson');
  const exportMinioBtn = $('#exportMinio');
  const countEl = $('#count');
  const toasts = document.getElementById('toasts');

  let page = 1;
  let pages = 1;
  let limit = 50;

  function debounce(fn, ms){ let t=null; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(null,a),ms); } }

  async function fetchJSON(url){
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json().catch(()=>null);
    if (!res.ok) throw new Error('HTTP '+res.status);
    return data;
  }

  function buildQuery(extra={}){
    const p = new URLSearchParams();
    const q = (qEl?.value||'').trim(); if (q) p.set('q', q);
    const tg = (tagEl?.value||'').trim(); if (tg) p.set('tag', tg);
    p.set('page', String(page));
    p.set('limit', String(limit));
    Object.entries(extra).forEach(([k,v])=>{ if (v!=null) p.set(k, String(v)); });
    return p.toString();
  }

  function authHeaders(){
    // Try Bearer from localStorage (ki_token) or fall back to cookie-only
    const tok = localStorage.getItem('ki_token');
    const h = {};
    if (tok && tok.trim()) h['Authorization'] = 'Bearer ' + tok.trim();
    return h;
  }

  function showToast(text, type){
    if (!toasts) { alert(text); return; }
    const el = document.createElement('div');
    el.textContent = text;
    el.style.padding = '8px 12px';
    el.style.borderRadius = '8px';
    el.style.color = type==='error'? '#fff' : '#0b3';
    el.style.background = type==='error'? '#c33' : '#e9f9f1';
    el.style.border = '1px solid ' + (type==='error'? '#a22' : '#b8efcf');
    el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
    toasts.appendChild(el);
    setTimeout(()=>{ try{ toasts.removeChild(el); }catch{} }, 4000);
  }

  async function load(){
    try{
      listEl.innerHTML = '<p>Lade…</p>';
      const qs = buildQuery();
      const j = await fetchJSON(`/api/memory/knowledge/list?${qs}`);
      const items = Array.isArray(j.items) ? j.items : [];
      pages = Math.max(1, parseInt(j.pages||1,10));
      page = Math.max(1, Math.min(pages, parseInt(j.page||page,10)));
      const total = parseInt(j.total||items.length,10);
      pagerInfoEl.textContent = total ? `${(page-1)*limit+1}-${Math.min(total,page*limit)} von ${total}` : '—';
      countEl.textContent = `${items.length} Einträge`;
      render(items);
      prevBtn.disabled = (page<=1);
      nextBtn.disabled = (page>=pages);
    }catch(e){ console.error(e); listEl.innerHTML = '<p>⚠️ Fehler beim Laden.</p>'; }
  }

  function esc(s){ return String(s||'').replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

  function render(items){
    if (!items.length){ listEl.innerHTML = '<p>Keine Einträge.</p>'; return; }
    const rows = items.map(it => {
      const rid = Number(it.row_id||0);
      const bid = esc(it.id||`BLK_${rid}`);
      const src = esc(it.source||'');
      const typ = esc(it.type||'');
      const tags = esc(it.tags||'');
      const ts = Number(it.timestamp||0);
      const dt = ts ? new Date(ts*1000).toLocaleString() : '';
      const prev = esc(it.preview||'');
      return `<tr data-row-id="${rid}" data-id="${bid}" class="row-item">
        <td>${bid}</td>
        <td>${src}</td>
        <td>${typ}</td>
        <td>${tags}</td>
        <td>${dt}</td>
        <td>
          <div class="preview">${prev}</div>
          <div style="margin-top:6px;"><button class="btn btn-details" data-row-id="${rid}">Details ansehen</button></div>
        </td>
      </tr>`;
    }).join('');
    listEl.innerHTML = `<table><thead><tr><th>ID</th><th>Topic</th><th>Type</th><th>Tags</th><th>Zeit</th><th>Vorschau</th></tr></thead><tbody>${rows}</tbody></table>`;

    // Wire row click and details buttons
    listEl.querySelectorAll('tr.row-item').forEach(tr => {
      tr.addEventListener('click', (ev) => {
        const rid = tr.getAttribute('data-row-id');
        if (!rid) return;
        if (ev.target && (ev.target.closest('button'))) return; // let button handler fire instead
        openDetails(rid);
      });
    });
    listEl.querySelectorAll('button.btn-details').forEach(btn => {
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        const rid = btn.getAttribute('data-row-id');
        openDetails(rid);
      });
    });

    // Highlight support via URL param ?highlight=BLK_xxx
    try{
      const url = new URL(window.location.href);
      const h = url.searchParams.get('highlight');
      const scrollLast = url.searchParams.get('scroll');
      if (h){
        const tr = listEl.querySelector(`[data-id='${CSS.escape(h)}']`);
        if (tr){
          tr.classList.add('highlight');
          tr.scrollIntoView({behavior:'smooth', block:'center'});
        }
      } else if (scrollLast === 'last') {
        const rows = listEl.querySelectorAll('tr.row-item');
        if (rows && rows.length){
          const last = rows[rows.length - 1];
          last.classList.add('highlight');
          last.scrollIntoView({behavior:'smooth', block:'center'});
        }
      }
    }catch{}
  }

  async function openDetails(rid){
    if (!rid) return;
    try{
      const j = await fetchJSON(`/api/memory/knowledge/item/${encodeURIComponent(rid)}`);
      const it = j && j.item ? j.item : null;
      if (!it){ throw new Error('not found'); }
      const header = `${it.id || 'BLK_'+rid} — ${it.source || ''}`;
      const meta = `Tags: ${it.tags || ''}\nType: ${it.type || ''}\nZeit: ${it.ts ? new Date(it.ts*1000).toLocaleString() : ''}`;
      const content = (it.content || '').trim();
      modalBody.textContent = `${header}\n\n${meta}\n\n${content}`;
      modal.style.display = 'block';
    }catch(e){
      console.error(e);
      alert('Konnte Details nicht laden.');
    }
  }

  modalClose?.addEventListener('click', ()=>{ modal.style.display = 'none'; });
  modal?.addEventListener('click', (e)=>{ if (e.target === modal){ modal.style.display = 'none'; } });

  // Events
  qEl?.addEventListener('input', debounce(()=>{ page = 1; load(); }, 250));
  tagEl?.addEventListener('input', debounce(()=>{ page = 1; load(); }, 250));
  limitEl?.addEventListener('change', ()=>{ const v = parseInt(limitEl.value||'50',10); limit = isNaN(v)?50: v; page=1; load(); });
  reloadBtn?.addEventListener('click', ()=> load());
  prevBtn?.addEventListener('click', ()=>{ if (page>1){ page--; load(); } });
  nextBtn?.addEventListener('click', ()=>{ if (page<pages){ page++; load(); } });
  exportCsvBtn?.addEventListener('click', ()=>{
    const qs = buildQuery();
    window.open(`/api/memory/knowledge/export.csv?${qs}`, '_blank');
  });
  exportJsonBtn?.addEventListener('click', ()=>{
    const qs = buildQuery();
    window.open(`/api/memory/knowledge/export.json?${qs}`, '_blank');
  });

  exportMinioBtn?.addEventListener('click', async ()=>{
    try{
      const qs = buildQuery();
      const res = await fetch(`/api/memory/knowledge/export.minio?${qs}`, {
        method: 'GET',
        headers: authHeaders(),
        credentials: 'include'
      });
      const j = await res.json().catch(()=>({}));
      if (!res.ok || !j || j.status !== 'ok'){
        throw new Error((j && (j.detail||j.error)) || `HTTP ${res.status}`);
      }
      showToast(`Exportiert: ${j.object}`, 'ok');
    }catch(e){
      showToast(`Export fehlgeschlagen: ${e && e.message ? e.message : e}`, 'error');
    }
  });

  // Init
  try{ const v = parseInt(limitEl?.value||'50',10); limit = isNaN(v)?50:v; }catch{}
  // Show export buttons only for specific roles
  (async function roleBasedVisibility(){
    try{
      const r = await fetch('/api/me', { credentials:'include' });
      if (!r.ok) return;
      const me = await r.json();
      const roles = new Set([].concat(me.role||[], me.roles||[]).join(',').split(',').map(s=>String(s||'').trim().toLowerCase()).filter(Boolean));
      const canExport = roles.has('admin') || roles.has('creator') || roles.has('papa');
      if (canExport){
        try{ exportCsvBtn.style.display=''; }catch{}
        try{ exportJsonBtn.style.display=''; }catch{}
        try{ exportMinioBtn.style.display=''; }catch{}
      } else {
        try{ exportCsvBtn.style.display='none'; }catch{}
        try{ exportJsonBtn.style.display='none'; }catch{}
        try{ exportMinioBtn.style.display='none'; }catch{}
      }
    }catch{}
  })();
  load();
})();
