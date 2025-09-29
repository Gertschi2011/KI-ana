(function(){
  try{
    // Nur Startseite (wir taggen body data-page="home")
    const bodyIsHome = (document.body && document.body.dataset && document.body.dataset.page === "home");
    if (!bodyIsHome) return;
    if (window.__kiana_greeted__) return;

    const DAY_MS = 24*60*60*1000;
    const last = Number(localStorage.getItem("ki_greet_ts")||0);
    if (Date.now() - last < DAY_MS) return;

    window.__kiana_greeted__ = true;

    const lineDE = "Hallo, ich bin Kiana. Schön, dass du da bist!";
    const lineEN = "Hi, I'm Kiana. I'm happy you're here!";
    const lang = (navigator.language||"").toLowerCase().startsWith("de") ? "de" : "en";
    const text = lang === "de" ? lineDE : lineEN;

    function pickVoice(){
      const voices = speechSynthesis.getVoices() || [];
      const want = lang === "de" ? ["de", "German"] : ["en", "English"];
      let best = voices.find(v => want.some(w => (v.lang||"").toLowerCase().includes(w.toLowerCase())));
      return best || voices[0] || null;
    }

    function speakOnce(){
      try{
        const u = new SpeechSynthesisUtterance(text);
        const v = pickVoice(); if (v) u.voice = v;
        u.rate = 1.0; u.pitch = 1.05; u.volume = 1.0;
        speechSynthesis.cancel(); speechSynthesis.speak(u);
        localStorage.setItem("ki_greet_ts", String(Date.now()));
      }catch(e){}
    }

    const onFirstInteract = () => {
      document.removeEventListener("pointerdown", onFirstInteract, true);
      document.removeEventListener("keydown", onFirstInteract, true);
      const ready = () => {
        if (speechSynthesis.getVoices().length) { speakOnce(); }
        else setTimeout(ready, 150);
      };
      ready();
    };
    document.addEventListener("pointerdown", onFirstInteract, true);
    document.addEventListener("keydown", onFirstInteract, true);
  }catch(e){}
})();
