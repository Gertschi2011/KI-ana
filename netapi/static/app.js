/**
 * app.js – zentrale JS-Funktionen für KI_ana
 * Funktionen:
 * - Authentifizierung (localStorage/sessionStorage)
 * - Header-Management für API-Calls
 * - GET- & POST-Requests mit Fehlerbehandlung
 * - Sprachsynthese (Web Speech API)
 * Gestaltung: Unterstützt moderne und barrierefreie Nutzung
 */
window.KI = (function () {
  // ================================
  // Storage & HTTP Utilities (st)
  // ================================
  const st = {
    // Holt die gespeicherten Login-Daten aus localStorage oder sessionStorage
    getAuth() {
      try {
        const a = JSON.parse(
          localStorage.getItem("ki_ana_auth") ||
            sessionStorage.getItem("ki_ana_auth") ||
            "null"
        );
        if (a && a.u && a.p) return "Basic " + btoa(a.u + ":" + a.p);
      } catch {}
      return null;
    },

    // Erstellt ein Header-Objekt inkl. Authorization
    headers(extra) {
      const h = Object.assign({}, extra || {});
      const auth = st.getAuth();
      if (auth) h["Authorization"] = auth;
      return h;
    },

    // Führt einen GET-Request durch und erwartet JSON
    async getJSON(url) {
      const r = await fetch(url, { headers: st.headers() });
      if (!r.ok)
        throw new Error(
          "HTTP " + r.status + " beim Laden von " + url
        );
      return r.json();
    },

    // Führt einen POST-Request mit JSON-Daten durch
    async postJSON(url, body) {
      const r = await fetch(url, {
        method: "POST",
        headers: st.headers({ "Content-Type": "application/json" }),
        body: JSON.stringify(body || {}),
      });
      if (!r.ok)
        throw new Error(
          "HTTP " + r.status + " beim POST nach " + url
        );
      return r.json();
    },

    // Weiterleitung zum Login bei fehlender Authentifizierung
    ensureLogin() {
      if (!st.getAuth()) location.href = "/login";
    },
  };

  // ================================
  // Sprachsynthese-Helper (Web Speech API)
  // ================================
  const voice = {
    voices: [],

    load(langPref) {
      voice.voices = speechSynthesis.getVoices();
      const sel = document.getElementById("voice");
      if (!sel) {
        console.warn("#voice select-Element nicht gefunden.");
        return;
      }

      sel.innerHTML = "";
      const lang =
        (document.getElementById("lang") && document.getElementById("lang").value) ||
        langPref || "de-DE";

      voice.voices
        .filter((v) => v.lang.startsWith(lang))
        .forEach((v) => {
          const o = document.createElement("option");
          o.value = v.name;
          o.textContent = `${v.name} (${v.lang})`;
          sel.appendChild(o);
        });

      if (!sel.value && sel.options.length) sel.selectedIndex = 0;
    },

    speak(text) {
      if (!("speechSynthesis" in window)) return;

      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = document.getElementById("lang")?.value || "de-DE";

      const vname = document.getElementById("voice")?.value;
      const v = voice.voices.find((x) => x.name === vname);
      if (v) utter.voice = v;

      speechSynthesis.cancel();
      speechSynthesis.speak(utter);
    },
  };

  if (document.getElementById("voice")) {
    speechSynthesis.onvoiceschanged = () => voice.load();
    setTimeout(() => voice.load(), 200);
  }

  return { st, voice };
})();
