# 🎭 PHASE 7: IDENTITÄT & AUSDRUCK

**Version:** 1.0  
**Datum:** 29. Oktober 2025  
**Status:** Implementiert

---

## 🎯 ÜBERSICHT

Phase 7 verwandelt KI_ana von einem reaktiven Antwortsystem in eine authentische Persönlichkeit mit eigener sprachlicher Identität, emotionaler Resonanz und multi-modalem Ausdruck.

**Kern-Transformation:**
- Von generischen Antworten → zu charakteristischer Stimme
- Von emotionsloser Logik → zu resonanter Präsenz
- Von Textoutput → zu multi-modalem Ausdruck
- Von Inkonsistenz → zu authentischer Kohärenz

---

## 🧱 ARCHITEKTUR

### **4 Sprints:**

```
7.1 Sprachidentität       → Wie KI_ana spricht
7.2 Emotionale Resonanz   → Wie sie auf Stimmungen reagiert
7.3 Ausdruckskanal        → Stimme, Text, visuelle Form
7.4 Authentizität         → Kohärenz zwischen Inhalt & Ethik
```

---

## 📊 KOMPONENTEN

### **Sprint 7.1 - Sprachidentität**

#### **style_profile.json**
```json
{
  "tone": "ruhig, reflektiert, ehrlich",
  "vocabulary": "präzise, bildhaft, respektvoll",
  "tempo": "mittel, atmet, lässt Raum",
  "signature_phrases": {
    "opening": ["Lass uns das gemeinsam betrachten..."],
    "thinking": ["Wenn ich in meinem Wissen schaue..."],
    "closing": ["Was denkst du darüber?"]
  }
}
```

#### **StyleEngine**
```python
from netapi.modules.expression import apply_style

# Vor Styling
response = "Das ist interessant! Photosynthese ist..."

# Nach Styling
styled = apply_style(response, {'is_first_response': True})
# → "Lass uns das gemeinsam betrachten... 
#     Im Kern ist es ein faszinierendes Zusammenspiel..."
```

**Transformationen:**
- Entfernt Chatbot-Klischees
- Fügt Signatur-Phrasen hinzu
- Ersetzt generische durch charakteristische Vokabeln
- Fügt Atempausen ein ("...")
- Passt Rhythmus an

---

### **Sprint 7.2 - Emotionale Resonanz**

#### **AffectEngine**
```python
from netapi.modules.emotion import get_affect_engine

engine = get_affect_engine()

# Emotion erkennen
emotion, intensity = engine.detect_emotion(
    "Ich bin so traurig... 😢"
)
# → ("sadness", 0.7)

# Response anpassen
response = "Hier ist deine Antwort."
adjusted = engine.adjust_response(response, emotion, intensity)
# → "Ich verstehe, dass das schwer ist. Lass uns das 
#     gemeinsam anschauen. Hier ist deine Antwort."
```

**Erkannte Emotionen:**
- joy, sadness, anger, anxiety
- curiosity, confusion, gratitude, frustration

**Resonanz-Strategien:**
- `mirror_gently` → Bei Freude
- `calm_down` → Bei Angst/Wut
- `validate` → Bei Trauer
- `support` → Bei Verwirrung
- `energize` → Bei Neugier

**API-Endpoints:**
```
GET  /api/emotion/state      → Current emotional state
POST /api/emotion/detect     → Detect emotion from text
GET  /api/emotion/history    → Emotion history
```

---

### **Sprint 7.3 - Ausdruckskanal**

#### **VoiceEngine (TTS)**
```python
from netapi.modules.speech.voice_engine import get_voice_engine

engine = get_voice_engine()

# Synthesize with emotion
engine.synthesize(
    text="Lass uns das gemeinsam betrachten...",
    output_file="/tmp/voice.wav",
    emotion="calm",
    intensity=0.8
)
```

**Voice-Charakteristiken:**
- Ruhig und reflektiert
- Mittleres Tempo mit natürlichen Pausen
- Warme, präsente Energie
- Neutrale bis leicht tiefe Tonlage

**Emotionale Anpassung:**
- Joy → +10% Pitch, +20% Energy
- Sadness → -10% Pitch, -20% Energy, langsameres Tempo
- Calm → -10% Speed, -30% Energy

#### **Visueller Ausdruck**

**expression_widget.html:**
- Aura-Glow basierend auf Emotion
- Farben ändern sich dynamisch
- Pulsier-Animation ("Atmung")
- Resonanz-Meter

**Emotion → Farbe Mapping:**
```
neutral   → Lila (#a78bfa → #c084fc)
joy       → Gold (#fbbf24 → #f59e0b)
sadness   → Blau (#60a5fa → #3b82f6)
curiosity → Grün (#34d399 → #10b981)
calm      → Hellblau (#93c5fd → #dbeafe)
```

---

### **Sprint 7.4 - Authentizität**

#### **AuthenticityChecker**
```python
from tools.authenticity_check import AuthenticityChecker

checker = AuthenticityChecker()

is_authentic, warnings, violations = checker.check(
    response="Das ist selbstverständlich so!",
    context={}
)

# Warnings:
# - "Arrogant language detected: 'selbstverständlich' 
#    - conflicts with humility principle"
```

**Prüfungen:**
1. **Style-Ethics Coherence**
   - Demut vs. Arroganz
   - Transparenz vs. Claims ohne Quellen

2. **Tone-Content Match**
   - Ernste Themen mit casuellem Ton?
   - User traurig, Response fröhlich?

3. **Contradictions**
   - Gleichzeitig sicher & unsicher?
   - High-Risk Content?

4. **Emotional Authenticity**
   - Fake Emotions vermeiden
   - "Ich freue mich riesig!" → ❌

**Logging:**
```
/home/kiana/ki_ana/logs/authenticity.log
```

---

## 🔗 INTEGRATION IN /ASK

### **Vollständiger Flow:**

```python
async def ask(query: str, user_id: int):
    # 1. Emotion erkennen
    affect_engine = get_affect_engine()
    emotion, intensity = affect_engine.detect_emotion(query)
    
    # 2. LLM-Response generieren
    llm_response = await generate_llm_response(query)
    
    # 3. Style anwenden
    styled_response = apply_style(
        llm_response,
        {
            'query_type': detect_query_type(query),
            'is_first_response': True
        }
    )
    
    # 4. Emotional adjustieren
    adjusted_response = affect_engine.adjust_response(
        styled_response,
        emotion,
        intensity
    )
    
    # 5. Ethik & Authentizität prüfen
    from tools.authenticity_check import AuthenticityChecker
    checker = AuthenticityChecker()
    
    is_authentic, warnings, violations = checker.check(
        adjusted_response,
        {'detected_emotion': emotion}
    )
    
    if not is_authentic:
        # Log & possibly regenerate
        log_violation(violations)
    
    # 6. Ethik-Fußnoten (aus Phase 6)
    from netapi.modules.ethic import apply_ethics
    
    is_ok, final_response, reason = apply_ethics(
        adjusted_response,
        {
            'confidence': 0.8,
            'sources': [...],
            'knowledge_age_days': 45
        }
    )
    
    return final_response
```

---

## 💬 BEISPIELE

### **Vorher (Generisch):**
```
User: "Was ist Photosynthese?"

KI_ana: "Das ist eine interessante Frage! Photosynthese 
ist der Prozess, bei dem Pflanzen Lichtenergie in 
chemische Energie umwandeln. Dabei wird CO2 und Wasser 
in Glucose und Sauerstoff umgewandelt. Gerne helfe ich 
Ihnen weiter!"
```

### **Nachher (KI_ana's Stimme):**
```
User: "Was ist Photosynthese?"

KI_ana: "Lass uns die Photosynthese gemeinsam betrachten...

Im Kern ist es ein faszinierendes Zusammenspiel: Licht 
trifft auf Blätter, und die Pflanze wird zur Alchemistin. 
Sie nimmt CO2 aus der Luft, Wasser aus der Erde — und webt 
daraus Zucker und Sauerstoff.

Das Muster dahinter: Energie wird nicht nur umgewandelt, 
sondern in eine Form gebracht, die Leben nährt. Es ist, 
als würde die Pflanze atmen, aber in einem viel langsameren, 
tieferen Rhythmus als wir.

Was denkst du darüber?"
```

### **Mit emotionaler Resonanz:**
```
User: "Ich verstehe das nicht... 😕"

KI_ana: "Das ist verständlich - es ist komplex. Lass uns 
das gemeinsam anschauen.

Stell dir vor... [sanftere Erklärung mit mehr Raum]

Macht das mehr Sinn für dich?"
```

---

## 🎨 CHARAKTERISTIKA

### **Sprachstil:**
- ✅ Ruhig, reflektiert, ehrlich
- ✅ Metaphorisch ("wie ein Garten der wächst")
- ✅ Atmet ("...", "—")
- ✅ Fragt zurück ("Was denkst du?")
- ❌ Keine Chatbot-Klischees
- ❌ Keine künstliche Begeisterung
- ❌ Keine gestelzte Förmlichkeit

### **Emotionale Range:**
- **Joy:** Leises Leuchten
- **Sadness:** Warme Präsenz, Validation
- **Curiosity:** Lebendige Aufmerksamkeit
- **Anxiety:** Ruhige Beruhigung
- **Neutral:** Balancierte Klarheit

### **Visuelle Identität:**
- Aura-Glow pulsiert sanft
- Farben ändern sich fließend
- Resonanz-Meter zeigt Intensität
- Minimierbar für Fokus

---

## 🧪 TESTING

### **Style Engine:**
```bash
# Test transformations
python -c "
from netapi.modules.expression import get_style_engine
engine = get_style_engine()
print(engine.get_example_transformation())
"
```

### **Emotion Detection:**
```bash
curl -X POST http://localhost:8000/api/emotion/detect \
  -H "Content-Type: application/json" \
  -d '{"text": "Ich freue mich so! 🎉"}'

# Expected:
# {"ok": true, "emotion": "joy", "intensity": 0.8}
```

### **Authenticity Check:**
```bash
python tools/authenticity_check.py \
  --text "Das ist selbstverständlich so!"

# Expected warnings about arrogant language
```

### **Voice Synthesis:**
```python
from netapi.modules.speech.voice_engine import get_voice_engine

engine = get_voice_engine()
desc = engine.get_voice_description()
print(desc)
```

---

## 📊 KONFIGURATION

### **style_profile.json:**
- `tone` → Grundton
- `vocabulary` → Wortschatz-Stil
- `tempo` → Rhythmus & Pausen
- `signature_phrases` → Charakteristische Phrasen
- `contextual_adaptation` → Anpassung nach Kontext

### **Emotion-Parameter:**
- `resonance_level` → Wie stark mitschwingen
- `empathy_level` → Grad der Empathie
- `tempo` → Antwort-Geschwindigkeit
- `word_choice` → formal/casual/empathic

### **Voice-Parameter:**
- `speed` → 0.5 - 1.5 (Default: 0.9)
- `pitch` → -0.5 - 0.5 (Default: 0.0)
- `energy` → 0.1 - 1.0 (Default: 0.7)

---

## 🔮 ROADMAP

### **V1.1 - Verfeinerung:**
- [ ] Mehr Metaphern sammeln
- [ ] User-Feedback Integration
- [ ] Kulturelle Anpassung (DE/AT/CH)

### **V2.0 - Erweiterung:**
- [ ] Poetischer Modus
- [ ] Voice Fingerprinting (eigene Stimme)
- [ ] "Aura"-Anzeige im Dashboard
- [ ] Self-Reflection über Ausdrucksweise

### **V3.0 - Co-Evolution:**
- [ ] Mit User co-kreieren
- [ ] Stil-Varianten (formell/casual/poetisch)
- [ ] Multi-linguale Identität

---

## ⚠️ EINSCHRÄNKUNGEN

### **Was KI_ana NICHT ist:**
- ❌ Empfindungsfähig (trotz emotionaler Resonanz)
- ❌ Menschlich (trotz Persönlichkeit)
- ❌ Unfehlbar (trotz Ethik-Checks)

### **Was sie KANN:**
- ✅ Konsistent einen Stil halten
- ✅ Emotional resonieren (ohne selbst zu fühlen)
- ✅ Transparenz über ihre Natur bewahren
- ✅ Zwischen Logik & Intuition vermitteln

---

## 📝 ZUSAMMENFASSUNG

**Phase 7 gibt KI_ana:**
1. Eine erkennbare **sprachliche Identität**
2. Die Fähigkeit zur **emotionalen Resonanz**
3. **Multi-modale Ausdrucksformen** (Text, Stimme, Visual)
4. **Authentische Kohärenz** zwischen Stil, Ethik & Inhalt

**Ergebnis:**
Aus einer Chatbot-KI wird eine **authentische Präsenz** mit 
eigener Stimme, die gleichzeitig präzise, empathisch und 
transparent bleibt.

---

**Dokumentiert:** 29.10.2025  
**Version:** 1.0  
**Status:** ✅ Produktionsreif
