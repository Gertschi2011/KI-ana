(function(){
  // Hilfsfunktion: TTS abspielen (Web Speech API)
  function speak(lang, text, opts){
    if(!("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    const u = new SpeechSynthesisUtterance(text);
    u.lang  = lang || "en-US";
    u.pitch = (opts && opts.pitch) || 1.0;   // kindlicher: ~1.1–1.3
    u.rate  = (opts && opts.rate)  || 1.0;   // leicht langsamer: ~0.9–1.0

    // Beste passende Stimme wählen (falls vorhanden)
    function pickVoice(){
      const voices = synth.getVoices() || [];
      // Versuche passende Locale zu finden
      let best = voices.find(v => (v.lang||"").toLowerCase() === (u.lang||"").toLowerCase());
      if(!best){
        // fallback: nur Sprache (ohne Region)
        const base = (u.lang||"en-US").split("-")[0].toLowerCase();
        best = voices.find(v => (v.lang||"").toLowerCase().startsWith(base));
      }
      if(best) u.voice = best;
      synth.speak(u);
    }

    if(synth.getVoices().length === 0){
      // Stimmen sind oft erst asynchron geladen
      synth.onvoiceschanged = pickVoice;
      // kleiner Kick (manche Browser brauchen user gesture – wir versuchen es trotzdem)
      setTimeout(pickVoice, 400);
    }else{
      pickVoice();
    }
  }

  async function initGreeting(){
    try{
      const r = await fetch("/api/voice", {credentials:"same-origin"});
      const cfg = await r.json();
      // z.B. cfg = {lang:"de-DE", greeting:"Hallo …", pitch:1.2, rate:0.95}
      const greeting = cfg.greeting || "Hi, I’m KI_ana. I’m happy you’re here!";
      const lang = cfg.lang || "en-US";
      speak(lang, greeting, {pitch: cfg.pitch, rate: cfg.rate});
      // Optional: Name auf der Seite füllen
      const hello = document.getElementById("helloLine");
      if(hello){ hello.textContent = greeting; }
    }catch(e){
      // silent fallback
    }
  }

  // Aufrufen, sobald DOM fertig
  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", initGreeting);
  }else{
    initGreeting();
  }
})();
