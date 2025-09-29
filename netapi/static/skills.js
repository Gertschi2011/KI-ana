const $ = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));

const state = { all: [], filtered: [] };

function renderRow(s) {
  const caps = (s.capabilities||[]).map(c => `<span class="pill">${c}</span>`).join(' ');
  const sched = s.schedule_every ? `${s.schedule_every}s` : '—';
  return `
    <tr>
      <td><strong>${s.name}</strong></td>
      <td>${s.version || ''}</td>
      <td><code>${s.entrypoint}</code></td>
      <td>${caps || '—'}</td>
      <td>${s.run_mode}</td>
      <td>${sched}</td>
      <td class="row-actions">
        <button data-act="exec" data-skill="${s.name}">Run…</button>
        <button data-act="detail" data-skill="${s.name}">Details</button>
      </td>
    </tr>
  `;
}

function render() {
  const tbody = $("#skills tbody");
  tbody.innerHTML = state.filtered.map(renderRow).join("");
  $("#empty").style.display = state.filtered.length ? "none" : "block";
}

function applyFilter(q) {
  const t = (q||"").toLowerCase().trim();
  if (!t) { state.filtered = state.all.slice(); return }
  state.filtered = state.all.filter(s => {
    const hay = [s.name, s.version, s.entrypoint, s.run_mode, String(s.schedule_every||""), ...(s.capabilities||[])]
      .map(x => String(x||"").toLowerCase()).join(" ");
    return hay.includes(t);
  });
}

async function load() {
  const res = await fetch("/api/kernel/skills");
  const data = await res.json();
  state.all = data.items || [];
  state.filtered = state.all.slice();
  render();
}

async function showDetail(name) {
  const res = await fetch(`/api/kernel/skills/${encodeURIComponent(name)}`);
  if (!res.ok) { alert("Skill nicht gefunden."); return; }
  const d = await res.json();
  alert(JSON.stringify(d, null, 2));
}

function openExec(name) {
  const dlg = $("#execDlg");
  $("#dlgTitle").textContent = `Skill ausführen: ${name}`;
  $("#action").value = "selftest";
  $("#args").value = "{}";
  $("#result").textContent = "";
  dlg.dataset.skill = name;
  dlg.showModal();
}

async function runExec() {
  const name = $("#execDlg").dataset.skill;
  let args;
  try {
    args = JSON.parse($("#args").value || "{}");
  } catch {
    alert("Args sind kein valides JSON.");
    return;
  }
  const payload = {
    skill: name,
    action: $("#action").value || "selftest",
    args
  };
  const btn = $("#runNow");
  btn.disabled = true; btn.setAttribute("aria-busy","true");
  try {
    const res = await fetch("/api/kernel/exec", {
      method: "POST",
      headers: { "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json().catch(() => ({}));
    $("#result").textContent = JSON.stringify(data, null, 2);
  } finally {
    btn.disabled = false; btn.removeAttribute("aria-busy");
  }
}

function bind() {
  $("#reload").addEventListener("click", async () => {
    const r = await fetch("/api/kernel/reload", { method: "POST" });
    if (r.ok) { await load(); }
    else { alert("Reload fehlgeschlagen."); }
  });

  $("#skills").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const skill = btn.dataset.skill;
    if (btn.dataset.act === "detail") showDetail(skill);
    if (btn.dataset.act === "exec") openExec(skill);
  });

  $("#runNow").addEventListener("click", runExec);
  $("#search").addEventListener("input", (e) => { applyFilter(e.target.value); render(); });
}

window.addEventListener("DOMContentLoaded", async () => {
  bind();
  await load();
});
