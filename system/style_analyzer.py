import re
from typing import Dict, List

# Simple heuristic-based German style analyzer (MVP)
# Detects anrede, formality, dialect markers, tone, filler phrases.

DIALECT_TOKENS = {
    'NÖ': [
        'wos', 'ned', 'net', 'guad', 'mei', 'oida', 'gschicht', 'leiwand', 'bissl', 'heast', 'wia', 'da', 'des', 'weu'
    ],
    'BAY': [
        'ois', 'fei', 'servus', 'ois', 'gell', 'hob', 'i bin', 'mia', 'eha', 'gaaanz'
    ],
}

FLOSKEL_RX = re.compile(r"\b(jo mei|oida|na guad|passt|passt scho|eh|eigentlich|halt|quasi|sozusagen)\b", re.I)
AGGR_RX = re.compile(r"\b(dumm|blöd|sch*|sinnlos|niemals|auf keinen fall)\b", re.I)
SARK_RX = re.compile(r"\b(na klar|ja eh|genau|super|toll|ironisch)\b", re.I)
UNSICHER_RX = re.compile(r"\b(vielleicht|glaub|meine|unsicher|nicht sicher|bin mir nicht sicher)\b", re.I)

ANREDE_DU_RX = re.compile(r"\b(du|dein|dir|dich)\b", re.I)
ANREDE_SIE_RX = re.compile(r"\b(Sie|Ihr|Ihnen|Ihre|Ihnen)\b")
ANREDE_IHR_RX = re.compile(r"\b(ihr|euch|eure)\b", re.I)

FORMELL_RX = re.compile(r"\b(Sehr geehrte|Mit freundlichen Grüßen|MfG|vielen Dank|bitte|könnten Sie|würden Sie)\b", re.I)
LOCKER_RX = re.compile(r"\b(hey|hi|servus|na|yo|oida|passt|tschuldi|kein ding)\b", re.I)

QUESTION_RX = re.compile(r"\?|\b(warum|wieso|wie|was|welche|wo|wann|wer)\b", re.I)


def analyze_text(text: str, lang: str = 'de') -> Dict:
    t = (text or '').strip()
    low = t.lower()

    # anrede
    anrede = 'du'
    if ANREDE_SIE_RX.search(t):
        anrede = 'Sie'
    elif ANREDE_IHR_RX.search(low):
        anrede = 'ihr'

    # formality
    formell = bool(FORMELL_RX.search(t))
    if not formell and LOCKER_RX.search(low):
        formell = False

    # dialect markers
    dialekt_merkmale: List[str] = []
    dialekt_guess = None
    for region, toks in DIALECT_TOKENS.items():
        hits = [w for w in toks if re.search(rf"\b{re.escape(w)}\b", low)]
        dialekt_merkmale.extend(hits)
        if hits and not dialekt_guess:
            dialekt_guess = region

    # tone
    tonfall = 'neutral'
    if SARK_RX.search(low):
        tonfall = 'sarkastisch'
    elif AGGR_RX.search(low):
        tonfall = 'aggressiv'
    elif UNSICHER_RX.search(low):
        tonfall = 'unsicher'
    elif QUESTION_RX.search(low):
        tonfall = 'fragend'
    elif LOCKER_RX.search(low):
        tonfall = 'locker'

    # floskeln
    floskeln = list({m.group(0) for m in FLOSKEL_RX.finditer(low)})

    return {
        'sprache': 'de',
        'anrede': anrede,
        'formell': bool(formell),
        'dialekt_merkmale': dialekt_merkmale[:8],
        'dialekt': dialekt_guess,
        'tonfall': tonfall,
        'floskeln': floskeln[:8],
    }
