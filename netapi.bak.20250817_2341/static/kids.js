(()=> {
  const $ = id => document.getElementById(id);
  if ($("year")) $("year").textContent = new Date().getFullYear();
  const log = (t)=>{ $("box").textContent += (t+"\n"); };
  async function send(){
    const m = $("msg").value.trim(); if(!m) return;
    $("msg").value = ""; log("👧: "+m);
    try{
      const r = await fetch("/chat", {
        method:"POST",
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({message:m})
      });
      const d = await r.json();
      log("🤖: " + (d.reply||"(keine Antwort)"));
    }catch(e){ log("⚠️ "+e.message); }
  }
  $("send").onclick = send;
  $("msg").addEventListener("keydown", ev => { if(ev.key==="Enter"){ ev.preventDefault(); send(); }});
})();
