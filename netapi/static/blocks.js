(function(){
  const $ = (s,p=document)=>p.querySelector(s);
  const listEl = $('#list');
  const qEl = $('#q');
  const topicEl = $('#topic');
  const tagsEl = $('#tags');
  const hostEl = $('#host');
  const minRatingEl = $('#minRating');
  const minCountEl = $('#minCount');
  const searchBtn = $('#searchBtn');
  const sortByEl = $('#sortBy');
  const resetBtn = $('#resetBtn');
  const countEl = $('#count');
  const sortInfoEl = $('#sortInfo');
  const presetBtn = $('#presetToolUsage');

  async function fetchJSON(url){
    const r = await fetch(url, { credentials:'include' });
    try{ return await r.json(); }catch{ return {}; }
  }

  // ---- Persist/Restore toolbar state ----
  const LS_KEY = 'blocks_filters_v1';
  function saveFilters(){
    try{
      const obj = {
        q: qEl?.value||'',
        topic: topicEl?.value||'',
        tags: tagsEl?.value||'',
        host: hostEl?.value||'',
        minRating: minRatingEl?.value||'0',
        minCount: minCountEl?.value||'',
        sortBy: sortByEl?.value||'rating_desc',
      };
      localStorage.setItem(LS_KEY, JSON.stringify(obj));
    }catch{}
  }
  function loadFilters(){
    try{
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return;
      const o = JSON.parse(raw);
      if (qEl && typeof o.q==='string') qEl.value = o.q;
      if (topicEl && typeof o.topic==='string') topicEl.value = o.topic;
      if (tagsEl && typeof o.tags==='string') tagsEl.value = o.tags;
      if (hostEl && typeof o.host==='string') hostEl.value = o.host;
      if (minRatingEl && typeof o.minRating==='string') minRatingEl.value = o.minRating;
      if (minCountEl && (typeof o.minCount==='string' || typeof o.minCount==='number')) minCountEl.value = String(o.minCount);
      if (sortByEl && typeof o.sortBy==='string') sortByEl.value = o.sortBy;
    }catch{}
  }

  function renderBlocks(items){
    // Summary for tool_usage blocks
    try{
      const map = {};
      for (const b of (items||[])){
        const tags = (b.tags||[]).map(x=>String(x).toLowerCase());
        if (!tags.includes('tool_usage')) continue;
        const text = String(b.content||'');
        for (const line of text.split('\n')){
          const s = line.trim().replace(/^•\s*/,'');
          if (!s.includes(':')) continue;
          const name = s.split(':',1)[0].trim().toLowerCase();
          if (!name) continue;
          map[name] = (map[name]||0) + 1;
        }
      }
      const keys = Object.keys(map).sort((a,b)=>map[b]-map[a]);
      const summary = keys.length ? keys.map(k=>`${k} (${map[k]}x)`).join(', ') : '';
      let summaryEl = document.getElementById('toolSummary');
      if (!summaryEl){
        summaryEl = document.createElement('div');
        summaryEl.id = 'toolSummary';
        summaryEl.className = 'muted';
        summaryEl.style.margin = '8px 0';
        listEl.parentElement.insertBefore(summaryEl, listEl);
      }
      summaryEl.textContent = summary ? `Nutzung: ${summary}` : '';
    }catch{}
    listEl.innerHTML = '';
    (items||[]).forEach(b => {
      const card = document.createElement('div');
      card.className = 'card';
      const title = b.title || b.topic || b.id || 'Block';
      const source = b.source || b.url || '';
      const ts = b.timestamp ? new Date(b.timestamp*1000).toLocaleString() : '';
      const tags = Array.isArray(b.tags) ? b.tags : [];
      const snippet = b.content ? String(b.content).slice(0,220) + (String(b.content).length>220?'…':'') : (b.snippet||'');
      const bid = deriveId(b);
      const meta = [];
      if (b.topic) meta.push(`Thema: <span class="mono">${escapeHTML(b.topic)}</span>`);
      if (source) meta.push(`<a href="${escapeAttr(source)}" target="_blank" rel="noopener">Quelle</a>`);
      if (ts) meta.push(ts);
      const r = (typeof b.rating==='number') ? b.rating : (b.trust?.score || null);
      const rc = (typeof b.rating_count==='number') ? b.rating_count : null;
      const badge = (typeof r === 'number') ? `<span class="tag" title="Rating">⭐ ${r.toFixed(2)}${(rc!=null?` (${rc})`:'')}</span>` : '';
      card.innerHTML = `
        <h3>${escapeHTML(title)}</h3>
        <div class="meta">${meta.join(' • ')} ${badge}</div>
        ${snippet? `<p style="margin:8px 0 10px">${escapeHTML(snippet)}</p>`:''}
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          ${tags.map(t=>`<span class="tag">${escapeHTML(t)}</span>`).join('')}
          <button class="btn" data-act="toggle">Details</button>
          <div style="margin-left:auto" class="muted mono">${bid?`ID: ${escapeHTML(bid)}`:''}</div>
        </div>
        <div class="details" style="display:none;margin-top:8px;border-top:1px dashed #e5e7eb;padding-top:8px"></div>
      `;
      const details = card.querySelector('.details');
      const btn = card.querySelector('button[data-act="toggle"]');
      btn.addEventListener('click', async ()=>{
        if (!details) return;
        if (details.dataset.loaded!=='1'){
          await populateDetails(details, b, bid);
          details.dataset.loaded = '1';
        }
        const vis = details.style.display!=='none';
        details.style.display = vis? 'none' : 'block';
        btn.textContent = vis? 'Details' : 'Schließen';
      });
      listEl.appendChild(card);
    });
  }

  function deriveId(b){
    try{
      if (b.id) return String(b.id);
      const p = b.path || b.block_file || '';
      if (p){
        const nm = String(p).split('/').pop();
        return nm ? nm.replace(/\.json$/,'') : '';
      }
      return '';
    }catch{ return ''; }
  }

  async function populateDetails(detailsEl, b, bid){
    try{
      const full = b.content ? String(b.content) : (b.snippet||'');
      detailsEl.innerHTML = `
        <pre style="white-space:pre-wrap;font-family:inherit;line-height:1.4;background:#fafafa;border:1px solid #eee;border-radius:8px;padding:10px;max-height:320px;overflow:auto">${escapeHTML(full)}</pre>
        <div class="row" style="margin-top:8px;justify-content:space-between">
          <div class="muted">Bewerten:</div>
          <div class="row" style="gap:6px">
            <button class="btn" data-rate="1">⭐️⭐️⭐️⭐️⭐️</button>
            <button class="btn" data-rate="0.8">⭐️⭐️⭐️⭐️</button>
            <button class="btn" data-rate="0.6">⭐️⭐️⭐️</button>
            <button class="btn" data-rate="0.4">⭐️⭐️</button>
            <button class="btn" data-rate="0.2">⭐️</button>
          </div>
        </div>
      `;
      detailsEl.querySelectorAll('button[data-rate]').forEach(btn => {
        btn.addEventListener('click', async ()=>{
          const score = parseFloat(btn.getAttribute('data-rate')||'1');
          const id = bid || deriveId(b);
          if (!id){ alert('Kein Block‑ID gefunden.'); return; }
          try{
            const r = await fetch('/api/memory/rate', { method:'POST', credentials:'include', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ id, score }) });
            const j = await r.json().catch(()=>({}));
            if (r.ok && j && j.ok){ toast('Bewertung gespeichert.'); }
            else { toast('Konnte Bewertung nicht speichern.'); }
          }catch{ toast('Netzwerkfehler.'); }
        });
      });
    }catch{}
  }

  function escapeHTML(s){
    return String(s||'').replace(/[&<>"']/g, c=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'
    })[c]);
  }
  function escapeAttr(s){
    return String(s||'').replace(/"/g, '&quot;');
  }

  async function runSearch(){
    const q = (qEl?.value||'').trim();
    const topic = (topicEl?.value||'').trim();
    const tags = (tagsEl?.value||'').trim();
    const hostFilter = (hostEl?.value||'').trim().toLowerCase();
    const minRating = parseFloat(minRatingEl?.value||'0') || 0;

    let items = [];
    try{
      if (q){
        const res = await fetchJSON(`/api/memory/search?q=${encodeURIComponent(q)}&limit=200`);
        if (res && res.ok && Array.isArray(res.results)){
          items = res.results.map(x => ({
            title: x.title,
            snippet: x.snippet,
            url: x.url,
            tags: x.tags||[],
            timestamp: 0,
            rating: typeof x.rating==='number'? x.rating : 0,
          }));
        }
      } else {
        const qs = new URLSearchParams();
        if (topic) qs.set('topic', topic);
        if (tags) qs.set('tags', tags);
        const res = await fetchJSON(`/blocks?${qs.toString()}`);
        if (res && res.ok && Array.isArray(res.items)){
          items = res.items;
        }
      }
    }catch(e){ console.error(e); }
    // client-side filters: host + minRating + minCount
    const filtered = items.filter(b => {
      try{
        const q = (qEl?.value||'').trim().toLowerCase();
        const topic = (topicEl?.value||'').trim().toLowerCase();
        const tagsFilter = (tagsEl?.value||'').trim().toLowerCase();
        const hostFilter = (hostEl?.value||'').trim().toLowerCase();
        const minR = parseFloat(minRatingEl?.value||'0')||0;
        const minC = parseInt(minCountEl?.value||'0',10)||0;
        if (q){
          const hay = `${b.title||''} ${b.content||''} ${b.topic||''}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        if (topic && String(b.topic||'').toLowerCase()!==topic) return false;
        if (tagsFilter){
          const have = (Array.isArray(b.tags)?b.tags:[]).map(x=>String(x).toLowerCase());
          const want = tagsFilter.split(',').map(s=>s.trim()).filter(Boolean);
          for (const t of want){ if (!have.includes(t)) return false; }
        }
        const r = parseFloat(b.rating||0)||0;
        if (r < minR) return false;
        if (minC>0){
          const cnt = parseInt(b.rating_count||0,10)||0;
          if (cnt < minC) return false;
        }
        if (hostFilter){
          const u = b.url || b.source;
          if (!u) return false;
          try{
            const h = new URL(u, location.origin).hostname.toLowerCase();
            if (!h.includes(hostFilter)) return false;
          }catch{ return false; }
        }
        return true;
      }catch{ return true; }
    });

    // sort
    const sortBy = (sortByEl?.value||'rating_desc');
    filtered.sort((a,b)=>{
      const ra = parseFloat(a.rating||0)||0, rb = parseFloat(b.rating||0)||0;
      const ta = parseInt(a.timestamp||0,10)||0, tb = parseInt(b.timestamp||0,10)||0;
      const ca = parseInt(a.rating_count||0,10)||0, cb = parseInt(b.rating_count||0,10)||0;
      if (sortBy==='rating_asc') return (ra - rb) || (cb - ca) || (tb - ta);
      if (sortBy==='count_desc') return (cb - ca) || (rb - ra) || (tb - ta);
      if (sortBy==='count_asc') return (ca - cb) || (rb - ra) || (tb - ta);
      if (sortBy==='time_desc') return (tb - ta) || (rb - ra) || (cb - ca);
      if (sortBy==='time_asc') return (ta - tb) || (rb - ra) || (cb - ca);
      return (rb - ra) || (cb - ca) || (tb - ta); // rating_desc default
    });
    countEl.textContent = `${filtered.length} Blocks`;
    try{
      const map = { rating_desc: 'Rating ↓', rating_asc: 'Rating ↑', count_desc: 'Bewertungen ↓', count_asc: 'Bewertungen ↑', time_desc: 'Neueste', time_asc: 'Älteste' };
      sortInfoEl.textContent = `Sortiert nach: ${map[sortBy]||'Rating ↓'}`;
    }catch{}
    renderBlocks(filtered);
  }

  searchBtn?.addEventListener('click', runSearch);
  qEl?.addEventListener('keydown', (e)=>{ if (e.key==='Enter') runSearch(); });
  topicEl?.addEventListener('keydown', (e)=>{ if (e.key==='Enter') runSearch(); });
  tagsEl?.addEventListener('keydown', (e)=>{ if (e.key==='Enter') runSearch(); });
  hostEl?.addEventListener('keydown', (e)=>{ if (e.key==='Enter') runSearch(); });
  minRatingEl?.addEventListener('change', runSearch);
  sortByEl?.addEventListener('change', runSearch);
  minCountEl?.addEventListener('change', runSearch);
  // persist on any change
  for (const el of [qEl, topicEl, tagsEl, hostEl, minRatingEl, minCountEl, sortByEl]){
    el?.addEventListener('change', saveFilters);
    el?.addEventListener('keydown', (e)=>{ if (e.key==='Enter') saveFilters(); });
  }
  resetBtn?.addEventListener('click', ()=>{
    try{
      qEl.value=''; topicEl.value=''; tagsEl.value=''; hostEl.value='';
      if (minRatingEl) minRatingEl.value='0';
      if (sortByEl) sortByEl.value='rating_desc';
      if (minCountEl) minCountEl.value='';
    }catch{}
    saveFilters();
    runSearch();
  });

  // initial load
  loadFilters();
  runSearch();

  // Preset: Tool Usage
  presetBtn?.addEventListener('click', ()=>{
    try{
      if (qEl) qEl.value = 'tag:tool_usage';
      saveFilters();
    }catch{}
    runSearch();
  });
})();
