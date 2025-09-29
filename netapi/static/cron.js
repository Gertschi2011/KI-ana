const $ = (s,r=document)=>r.querySelector(s);
const $$= (s,r=document)=>Array.from(r.querySelectorAll(s));

function fmtTs(x){
  if(!x) return "";
  const d = new Date(x*1000);
  return d.toLocaleString();
}
function schedText(s){
  if(!s) return "";
  if(s.every_seconds) return `every ${s.every_seconds}s`;
  if(s.cron) return `cron: ${s.cron}`;
  return "";
}
function row(j){
  const pill = j.enabled ? '<span class="pill ok">on</span>' : '<span class="pill off">off</span>';
  return `<tr>
    <td>${pill}</td>
    <td>${j.skill}</td>
    <td>${j.action}</td>
    <td>${schedText(j.schedule)}</td>
    <td><div class="muted">last:</div>${fmtTs(j.last_run) || "-"}<br><div class="muted">next:</div>${fmtTs(j.next_run) || "-"}</td>
    <td class="actions">
      <button data-act="toggle" data-id="${j.id}" data-enabled="${!j.enabled}">${j.enabled?"Pause":"Aktivieren"}</button>
      <button data-act="del" data-id="${j.id}">Löschen</button>
    </td>
  </tr>`;
}
async function load(){
  const res = await fetch("/kernel/jobs", {credentials:"include"});
  const data = await res.json();
  const items = data.items || [];
  $("#jobs tbody").innerHTML = items.map(row).join("");
  $("#empty").style.display = items.length ? "none":"block";
}
async function addJob(){
  const skill = $("#skill").value.trim();
  const action = $("#action").value.trim();
  let args = {};
  try { args = JSON.parse($("#args").value || "{}"); } catch(e){ alert("Args sind kein gültiges JSON"); return; }
  const kind = document.querySelector("input[name='sched']:checked").value;
  const schedule = kind==="every" ? { every_seconds: Number($("#every").value||0) } : { cron: $("#cron").value.trim() };
  const res = await fetch("/kernel/jobs", {
    method:"POST", credentials:"include",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ skill, action, args, enabled:true, schedule })
  });
  if(!res.ok){ alert("Konnte Job nicht anlegen (Login/Role?)"); return; }
  await load();
}
async function onTableClick(ev){
  const btn = ev.target.closest("button[data-act]");
  if(!btn) return;
  const id = btn.dataset.id;
  const act = btn.dataset.act;
  if(act==="del"){
    if(!confirm("Job löschen?")) return;
    await fetch(`/kernel/jobs/${id}`, {method:"DELETE", credentials:"include"});
    await load();
  }else if(act==="toggle"){
    const enabled = btn.dataset.enabled === "true";
    await fetch(`/kernel/jobs/${id}/toggle?enabled=${enabled}`, {method:"POST", credentials:"include"});
    await load();
  }
}
window.addEventListener("DOMContentLoaded", ()=>{
  $("#jobs").addEventListener("click", onTableClick);
  $("#addBtn").addEventListener("click", addJob);
  $("#reloadBtn").addEventListener("click", load);
  load();
});
