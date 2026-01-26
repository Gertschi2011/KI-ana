# Phase‑2 Vorbereitung (Konzept, nicht umsetzen)

Stand: 2026‑01‑26

**Wichtig:** Phase‑1 ist abgenommen. In folgenden Bereichen werden *keine* weiteren Text-/UX‑Änderungen umgesetzt (außer Bugfixes):
- Landing (Startseite)
- Pakete
- Login / Register
- Dashboard
- Chat
- Einstellungen
- Papa Tools

Dieses Dokument ist eine **Vorbereitungs‑/Konzeptvorlage** für den nächsten Auftrag. Keine Implementierung.

---

## Zielbild Phase‑2

Phase‑2 soll KI_ana spürbar „lebendiger“ machen, ohne laut zu werden:
- Subtile Mikro‑Emotionen (Bewegung/Timing statt Emojis/Overlays)
- Mehr inhaltliche Tiefe (sanft erklärend, nicht technisch)
- Kein Kitsch, keine Gamification, kein "Sales"‑Druck

---

## Phase‑2a: Mikro‑Emotion & Playfulness (subtile Animationen)

### Leitplanken
- **Max. 150–250ms** für Micro‑Transitions, easing: `easeOut`/`easeInOut`
- **Nur dort animieren, wo es Bedeutung hat:** Hover/Focus, Statuswechsel, Antwort‑Eingang
- **Keine** Konfetti, Punkte, Level, Badges mit Druck, Popups als „Belohnung“
- Motion muss **optional degradieren** (prefers-reduced-motion)

### Kandidaten (ohne Umsetzung)

#### 1) Hover‑Reaktionen (Buttons, Cards)
- Buttons: leichtes „Lift“ (1–2px), minimaler Schatten‑Shift, kein Zoom > 1.02
- Cards: sanfter Hintergrund‑Gradient‑Shift oder Border‑Glow bei hover/focus
- Form‑Inputs: Focus‑Ring weich, nicht aggressiv

**Technik‑Optionen:**
- CSS-only (Tailwind + transitions) als Default
- framer-motion nur dort, wo Statuswechsel/Entrance wichtig ist

#### 2) Sanfte Transitions
- Page‑Sections: reveal-on-scroll ist bereits teils vorhanden → vereinheitlichen (nur Phase‑2 Auftrag)
- Kleine opacity/y transitions bei Wechsel von „leer“ → „gefüllt“ (z.B. Dashboard Widgets)

#### 3) Chat: „Antwort‑Bewegung“
- Beim Eintreffen einer Assistant‑Nachricht: leichte `opacity` + `y` (6–10px) + very subtle blur (optional)
- Beim „KI_ana denkt nach …“: statt Spinner eine ruhige Puls‑Animation des Bubble‑Containers
- Beim Senden: Input kurz „settled“ (z.B. `scale: 0.995` zurück auf 1.0), aber *nur* wenn nicht störend

**A11y:**
- `prefers-reduced-motion`: alle Entrance‑Animationen abschalten → nur instant state

### DoD Phase‑2a
- Motion wirkt ruhig, nicht „app‑y“
- Keine Animationen auf jeder Kleinigkeit
- Mobile: kein Layout‑Jump, kein janky scrolling

---

## Phase‑2b: Inhaltliche Tiefe (sanft erklärt)

### Dashboard: „Was passiert gerade mit KI_ana?“
Ziel: Vertrauen + Orientierung. Ohne Technik‑Wörter.

**Inhaltsskizze:**
- 1 Satz: „Worauf achtet KI_ana gerade?“ (z.B. Themen, Ziele, offene Fragen)
- 1 Satz: „Was hat KI_ana zuletzt gelernt (mit Zustimmung)?“ (hoch-level)
- 1 Satz: „Was ist heute dran?“ (sanfter Vorschlag)

**Form:**
- Kleines Card‑Modul, optional einklappbar

### Pakete: „User Pro“ inhaltlich schärfen (ohne Bewerben)
Ziel: Klarheit, nicht Upsell.

**Inhaltsskizze:**
- Für wen es ist (1 Satz)
- Was sich besser anfühlt/leichter wird (2–3 bullets)
- Was es *nicht* ist (1 bullet: kein Druck, kein Muss)

### Vertrauen: Mini‑Erklärung „Was merkt sich KI_ana – und was nicht?“
Ziel: Sicherheit & Kontrolle.

**Inhaltsskizze (nicht technisch):**
- „KI_ana merkt sich nur, was du ihr gibst.“
- „Wenn etwas bleiben soll, fragt sie dich.“
- „Flüchtiges darf flüchtig bleiben.“
- „Du kannst jederzeit aufräumen/ändern.“

**Platzierungs‑Optionen (entscheidet Phase‑2 Auftrag):**
- Settings: kleiner Infoblock
- Chat: im „Transparenz“‑Bereich (creator-only) nicht ideal für User → evtl. public trust block an anderer Stelle
- Pakete: kurzer Hinweis, 1–2 Zeilen

### DoD Phase‑2b
- Keine Implementierungs‑Details, keine internen Begriffe
- Texte sind kurz, warm, klar
- Keine neuen Pfade/Flows ohne expliziten Auftrag

---

## Empfohlene Umsetzungsschritte (für den späteren Auftrag)

1) Phase‑2a zuerst (Motion): 2–3 Stellen, nicht überall
2) Danach Phase‑2b: Dashboard‑Modul + Trust‑Mini‑Erklärung
3) Abschließend: Konsistenz‑Review (Ton, A11y, Reduced Motion)

---

## Offene Fragen (für den Phase‑2 Auftrag)
- Soll Motion global vereinheitlicht werden oder nur punktuell?
- Wo ist der beste Ort für „Was merkt sich KI_ana – und was nicht?“ (Settings vs. Pakete vs. separate Trust‑Section)?
- Welche 2–3 Chat‑Micro‑Momente sind am wichtigsten (Eintreffen, Denken, Senden)?
