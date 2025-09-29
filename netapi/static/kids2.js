(()=> {
  const $ = id => document.getElementById(id);
  const log = t => { const box=$("box"); box.textContent += (t+"\n"); box.scrollTop = box.scrollHeight; };

  // Login-Info aus Storage lesen
  function getAuth(){
    try{
      const a = JSON.parse(localStorage.getItem("ki_ana_auth") || sessionStorage.getItem("ki_ana_auth") || "null");
      if(a && a.u && a.p) return "Basic " + btoa(a.u+":"+a.p);
    }catch{}
    return null;
  }
  function headers(extra){
    const h = Object.assign({}, extra||{});
    const auth = getAuth();
    if(auth) h["Authorization"] = auth;
    return h;
  }

  // Stimmen laden
  let voices = [];
  const loadVoices = ()=>{
    voices = speechSynthesis.getVoices();
    const sel = $("voice"); if(!sel) return;
    sel.innerHTML = "";
    const lang = $("lang") ? $("lang").value : "de-DE";
    voices.filter(v=>v.lang.startsWith(lang)).forEach(v=>{
      const o=document.createElement("option");
      o.value=v.name; o.textContent=`${v.name} (${v.lang})`;
      sel.appendChild(o);
    });
    if(!sel.value && sel.options.length){ sel.selectedIndex=0; }
  };
  if(window.speechSynthesis){
    speechSynthesis.onvoiceschanged = loadVoices;
    setTimeout(loadVoices, 200);
  }

  async function send(){
    const m = $("msg").value.trim(); if(!m) return;
    $("msg").value = ""; log("👧: "+m);
    try{
      const r = await fetch("/chat", {
        method:"POST",
        headers: headers({'Content-Type':'application/json'}),
        body: JSON.stringify({message:m})
      });
      if(r.status===401){
        log("🔒 Bitte erst einloggen: https://ki-ana.at/static/login.html");
        return;
      }
      const d = await r.json();
      const reply = d.reply || "(keine Antwort)";
      log("🤖: " + reply);
      // optional vorlesen
      if(window.speechSynthesis && document.getElementById("speak")?.checked){
        const u = new SpeechSynthesisUtterance(reply);
        u.lang = document.getElementById("lang")?.value || "de-DE";
        const vname = document.getElementById("voice")?.value;
        const v = voices.find(x=>x.name===vname);
        if(v) u.voice = v;
        speechSynthesis.cancel(); speechSynthesis.speak(u);
      }
    }catch(e){ log("⚠️ "+e.message); }
  }

  const sendBtn = $("send");
  if(sendBtn){
    sendBtn.onclick = send;
    $("msg").addEventListener("keydown", ev => { if(ev.key==="Enter"){ ev.preventDefault(); send(); }});
    const langSel = $("lang");
    if(langSel) langSel.addEventListener("change", loadVoices);
  }

  // kleiner Hint bei fehlendem Login
  if(!getAuth()){
    log("ℹ️ Noch nicht eingeloggt. Bitte zuerst hier anmelden:");
    log("➡️ https://ki-ana.at/static/login.html");
  }
})();
