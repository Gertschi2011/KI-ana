# netapi/modules/chat/intent.py (robust)
import re
from typing import Literal, Optional

Choice = Literal["kurz", "zusammenfassung", "plan"]

# --- Normalisierung ---------------------------------------------------------
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[\.,;:!\?\-–—_]+")

def norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s)
    return s

# --- Muster für direkte Wahl ------------------------------------------------
# Viele Synonyme, Kommandos und Kurzformen.
CHOICE_PATTERNS = {
    "kurz": [
        r"\bkurz(?:e?r?\s*(?:version|fassung|erkl[aä]r(?:ung)?))?\b",
        r"\b(?:bitte\s*)?(?:sehr\s*)?kurz\b",
        r"\bkurz\s*und\s*knapp\b",
        r"\btl\s*;?\s*dr\b",
        r"\b(?:mach|machst|erkl[aä]r|gib)\s+(?:es|das)?\s*kurz\b",
        r"\bkompakt(?:e|er)?\b",
        r"\bkurze\s+erkl[aä]rung\b",
        # häufige Kurzform ohne "kurz": "nur erklären bitte"
        r"\b(?:nur\s*)?erkl[aä]r(?:e|en)?(?:\s*bitte)?\b",
    ],
    "zusammenfassung": [
        r"\bzusammenfassung\b",
        r"\bzusammenfassen\b",
        r"\b(?:kurze?r?\s*)?(overview|überblick)\b",
        r"\bkurze?\s+fassung\b",
        r"\bstichpunkte?\b",
        r"\bin\s+stichpunkten\b",
        r"\bfasse\s+(?:es|das)?\s*zusammen\b",
    ],
    "plan": [
        r"\bplan\b",
        r"\blernplan\b",
        r"\bfahrplan\b",
        r"\bschritte\b",
        r"\broadmap\b",
        r"\bwie\s+gehe[nr]?\s+wir\s+vor\b",
        r"\bwie\s+anfangen\b",
        r"\bmach\s+(?:mir|uns)?\s*einen\s*plan\b",
    ],
}

CHOICE_REGEX = {k: [re.compile(p, re.I) for p in ps] for k, ps in CHOICE_PATTERNS.items()}

# Negationen vermeiden Fehltrigger: "nicht kurz", "kein plan", …
_NEG = re.compile(r"\b(nicht|kein|keine|keinen|nein|stop|abbruch|abbrechen)\b", re.I)

def pick_choice(user: str) -> Optional[Choice]:
    u = norm(user)
    if not u or _NEG.search(u):
        return None
    for choice, regs in CHOICE_REGEX.items():
        if any(r.search(u) for r in regs):
            return choice  # type: ignore[return-value]
    return None

# --- Bestätigungserkennung --------------------------------------------------
# Großzügige Positivliste; Negation schlägt Affirmation.
_AFFIRM = re.compile(
    r"\b("
    r"ja|jo|jup|jep|yep|yup|genau|passt|passt so|klar|na klar|natürlich|"
    r"gern|gerne|bitte|okay|ok|okey|oke|alles klar|in ordnung|"
    r"mach|mach das|mach’s|machs|los|leg los|go|start|kannst anfangen|"
    r"klingt gut|gut so"
    r")\b",
    re.I,
)

def is_affirmation(user: str) -> bool:
    u = norm(user)
    if not u:
        return False
    if _NEG.search(u):
        return False
    return bool(_AFFIRM.search(u))

# --- Mini-Selbsttest (nur manuell) -----------------------------------------
if __name__ == "__main__":
    tests = [
        ("kurz bitte", "kurz"),
        ("mach es kurz", "kurz"),
        ("tl;dr", "kurz"),
        ("kurze erklärung", "kurz"),
        ("zusammenfassung bitte", "zusammenfassung"),
        ("gib mir einen Überblick", "zusammenfassung"),
        ("in Stichpunkten", "zusammenfassung"),
        ("gib mir einen plan", "plan"),
        ("wie gehen wir vor", "plan"),
        ("kein plan", None),
        ("nicht kurz", None),
    ]
    for t, exp in tests:
        print(t, "->", pick_choice(t), "/", exp)
    aff = ["ja", "gern", "ok", "mach das", "passt", "nein"]
    for a in aff:
        print(a, "->", is_affirmation(a))
