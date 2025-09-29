(() => {
  const $ = id => document.getElementById(id);
  const year = new Date().getFullYear();
  if ($("year")) $("year").textContent = year;

  // Remember Basic auth (for /status etc.)
  function setHello(name) {
    $("helloTitle").textContent = `Hallo ${name ? name : "👋"}! Wie kann ich helfen?`;
  }

  function authHeader() {
    const raw = localStorage.getItem("ki_basic");
    return raw ? { "Authorization": "Basic " + raw } : {};
  }

  async function fetchJSON(url, opts={}) {
    const r = await fetch(url, Object.assign({ headers: authHeader() }, opts));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  // Load me
  async function refreshMe() {
    try {
      const me = await fetchJSON("/me");
      if (me && me.username) {
        setHello(me.username);
        $("meBadge").textContent = `Eingeloggt als ${me.username}${me.role ? " ("+me.role+")" : ""}`;
        if (me.role === "creator" || me.role === "owner" || me.role === "admin") {
          $("papa").style.display = "";
          refreshStatus();
        } else {
          $("papa").style.display = "none";
        }
      } else {
        $("meBadge").textContent = "Nicht eingeloggt";
      }
    } catch {
      $("meBadge").textContent = "Nicht eingeloggt";
    }
  }

  async function refreshStatus() {
    try {
      const s = await fetchJSON("/status");
      const head = s.chain_head || {};
      const q = s.queue || { to_learn:0, open_questions:0 };
      const rm = s.recent_memories || [];
      $("statusBox").textContent =
        `Warteschlangen: to_learn=${q.to_learn}, open_questions=${q.open_questions}\n`+
        `Chain-Head: ${head.file||"-"} | ${head.type||""} | ${head.topic||""}\n`+
        `Signatur: ${head.signature?'ja':'nein'} | Quelle: ${head.source||''}\n\n`+
        `Letzte Memorys:\n`+
        rm.map(x => `• ${x.file} | ${x.type||''} | ${x.topic||''} | ${x.timestamp||''}`).join("\n");
    } catch(e) {
      $("statusBox").textContent = "⚠️ Zugriff verweigert (nur für Papa).";
    }
  }

  // Login form (uses Basic for now)
  $("loginForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const u = $("user").value.trim();
    const p = $("pass").value;
    const basic = btoa(u+":"+p);
    if ($("remember").checked) localStorage.setItem("ki_basic", basic);
    else localStorage.removeItem("ki_basic");
    $("loginMsg").textContent = "Eingeloggt (lokal).";
    setHello(u);
    refreshMe();
  });

  // Register form -> /api/register
  $("regForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const payload = {
      username: $("ruser").value.trim(),
      email: $("rmail").value.trim(),
      password: $("rpass").value
    };
    try{
      const r = await fetch("/api/register", {
        method:"POST",
        headers: Object.assign({ "Content-Type":"application/json" }, authHeader()),
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      $("regMsg").textContent = d.ok ? "Konto angelegt. Du kannst dich nun oben einloggen." : (d.error || "Fehler");
    }catch(e){
      $("regMsg").textContent = "Fehler: "+e.message;
    }
  });

  // Enqueue (Papa only)
  $("enqueueForm").addEventListener("submit", async (ev)=>{
    ev.preventDefault();
    const t = $("enqueue").value.trim();
    if(!t) return;
    try{
      const r = await fetchJSON("/enqueue?topic="+encodeURIComponent(t), { method:"POST" });
      $("enqueue").value = "";
      refreshStatus();
    }catch(e){
      alert("Nur für Papa. (Basic Auth nötig)");
    }
  });

  // Subminds list
  (async ()=>{
    try{
      const d = await fetchJSON("/api/subminds");
      const root = $("subminds");
      root.innerHTML = "";
      d.items.forEach(x => {
        const a = document.createElement("a");
        a.href = x.url; a.className = "btn secondary";
        a.textContent = `Download ${x.name}`;
        root.appendChild(a);
      });
    }catch{}
  })();

  $("tryStatus").addEventListener("click", (e)=>{
    e.preventDefault();
    document.location.hash = "#papa";
    refreshStatus();
  });

  refreshMe();
})();
