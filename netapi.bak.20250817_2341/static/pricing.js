(async ()=>{
  const $ = (id)=>document.getElementById(id);
  if ($("year")) $("year").textContent = new Date().getFullYear();

  async function j(url, opts){ const r=await fetch(url,opts||{}); return r.json(); }

  window.getLink = async (plan)=>{
    const msg = document.getElementById('msg');
    msg.textContent = "Erzeuge Link …";
    try{
      const r = await j(`/api/paylink?plan=${encodeURIComponent(plan)}`);
      if(r.ok && r.url){ location.href = r.url; }
      else { msg.textContent = r.error || "Nicht verfügbar"; }
    }catch(e){ msg.textContent = e.message; }
  };

  // Liste Subminds (öffentlich)
  try{
    const d = await j("/api/subminds");
    const root = document.getElementById("subs");
    root.innerHTML = "";
    d.items.forEach(x=>{
      const a = document.createElement("a");
      a.href = x.url; a.className = "btn secondary"; a.textContent = "Download "+x.name;
      root.appendChild(a);
    });
  }catch{}
})();
