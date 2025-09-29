/**
 * pricing.js – robust & session‑aware
 * - shows current year
 * - creates pay links (needs session cookie)
 * - lists public subminds with graceful empty state
 */

(async () => {
  // Tiny helpers
  const byId = (id) => document.getElementById(id);
  const $year = byId("year");
  if ($year) $year.textContent = new Date().getFullYear();

  // JSON fetch with sensible defaults
  async function j(url, opts = {}) {
    const res = await fetch(url, {
      credentials: "include",          // send cookies for session
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    const isJSON = (res.headers.get("content-type") || "").includes("application/json");
    const body = isJSON ? await res.json() : { ok: false, error: await res.text() };
    if (!res.ok) {
      const err = new Error((body && body.detail) || body.error || res.statusText);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  }

  // Status outlet (optional)
  const statusEl = byId("msg");
  const setStatus = (txt) => { if (statusEl) statusEl.textContent = txt || ""; };

  // Disable/enable all plan buttons while working
  function setPlanButtonsDisabled(disabled) {
    document.querySelectorAll("[data-plan-btn]").forEach(btn => {
      btn.disabled = !!disabled;
      btn.setAttribute("aria-busy", disabled ? "true" : "false");
    });
  }

  // Create payment/signup link for a plan and redirect
  window.getLink = async (plan) => {
    try {
      setPlanButtonsDisabled(true);
      setStatus("Erzeuge Link …");
      // Keep GET for compatibility; backend expects ?plan=
      const data = await j(`/api/paylink?plan=${encodeURIComponent(plan)}`, { method: "GET" });
      if (data && data.ok && data.url) {
        location.href = data.url;
      } else {
        setStatus(data?.error || "Nicht verfügbar");
      }
    } catch (e) {
      if (e.status === 401) {
        setStatus("Bitte zuerst einloggen.");
      } else {
        setStatus(e.message || "Fehler beim Erzeugen des Links.");
      }
    } finally {
      setPlanButtonsDisabled(false);
    }
  };

  // Download KI_ana OS package (requires active plan)
  async function downloadOS() {
    const msg = byId('osMsg');
    try {
      setStatus(''); if (msg) msg.textContent = '';
      const res = await fetch('/api/os/package', { credentials: 'include' });
      if (!res.ok) {
        if (res.status === 402) { if (msg) msg.textContent = 'Abo erforderlich. Bitte zuerst abonnieren.'; return; }
        if (res.status === 401) { if (msg) msg.textContent = 'Bitte zuerst einloggen.'; return; }
        if (msg) msg.textContent = 'Download derzeit nicht verfügbar.'; return;
      }
      // Convert to blob and trigger download
      const blob = await res.blob();
      const a = document.createElement('a');
      const url = URL.createObjectURL(blob);
      a.href = url; a.download = 'kiana_os.tar.gz'; a.click();
      setTimeout(()=>URL.revokeObjectURL(url), 2000);
    } catch (e) {
      if (msg) msg.textContent = 'Fehler beim Download.';
    }
  }

  document.getElementById('downloadOS')?.addEventListener('click', downloadOS);

  // Download personal Submind package (requires active plan)
  async function downloadSubmind() {
    const msg = byId('subMsg');
    try {
      setStatus(''); if (msg) msg.textContent = '';
      const res = await fetch('/api/subminds/package', { credentials: 'include' });
      if (!res.ok) {
        if (res.status === 402) { if (msg) msg.textContent = 'Abo erforderlich. Bitte zuerst abonnieren.'; return; }
        if (res.status === 401) { if (msg) msg.textContent = 'Bitte zuerst einloggen.'; return; }
        if (msg) msg.textContent = 'Download derzeit nicht verfügbar.'; return;
      }
      const blob = await res.blob();
      const a = document.createElement('a');
      const url = URL.createObjectURL(blob);
      const disp = res.headers.get('content-disposition') || '';
      const m = /filename\s*=\s*([^;]+)/i.exec(disp);
      const fname = m ? m[1].replace(/\"/g,'').trim() : 'submind_app.tar.gz';
      a.href = url; a.download = fname; a.click();
      setTimeout(()=>URL.revokeObjectURL(url), 2000);
    } catch (e) {
      if (msg) msg.textContent = 'Fehler beim Download.';
    }
  }

  // Mark plan buttons (for disabling UX)
  document.querySelectorAll(".plan .btn.primary").forEach(btn => {
    btn.setAttribute("data-plan-btn", "1");
  });

  // Bind download buttons
  document.getElementById('downloadOS')?.addEventListener('click', downloadOS);
  document.getElementById('downloadSubmind')?.addEventListener('click', downloadSubmind);
})();
