from typing import Dict, List
import re

# MVP: apply a light-weight style transformation to a reply
# - honor anrede (du/Sie/ihr)
# - insert 0-1 dialect tokens and floskeln tastefully
# - reflect tone label in minor phrasing changes

PRONOUN_MAP_DU = [
    (r"\bSie\b", "du"), (r"\bIhnen\b", "dir"), (r"\bIhr\b", "dein"), (r"\bIhre\b", "deine"), (r"\bIhren\b", "deinen"),
]
PRONOUN_MAP_SIE = [
    (r"\bdu\b", "Sie"), (r"\bdir\b", "Ihnen"), (r"\bdein\b", "Ihr"), (r"\bdeine\b", "Ihre"), (r"\bdeinen\b", "Ihren"),
]
PRONOUN_MAP_IHR = [
    (r"\bdu\b", "ihr"), (r"\bdir\b", "euch"), (r"\bdein\b", "euer"), (r"\bdeine\b", "eure"),
]


def _apply_anrede(text: str, anrede: str) -> str:
    s = text
    maps = {
        'du': PRONOUN_MAP_DU,
        'Sie': PRONOUN_MAP_SIE,
        'ihr': PRONOUN_MAP_IHR,
    }.get(anrede or 'du', [])
    for pat, rep in maps:
        s = re.sub(pat, rep, s)
    return s


def _inject_tokens(text: str, tokens: List[str]) -> str:
    if not tokens:
        return text
    # Insert one token at the start if not already present
    tok = tokens[0]
    if len(text) > 12 and tok.lower() not in text.lower():
        return f"{tok.capitalize()} – " + text
    return text


def _apply_tone(text: str, tone: str, formell: bool) -> str:
    t = text.strip()
    if not t:
        return t
    if tone == 'locker' and not formell:
        # softer opening
        if not re.match(r"^[A-Za-zÄÖÜäöü]", t):
            return t
        return "Kurz gesagt: " + t if len(t) < 280 else t
    if tone == 'sarkastisch':
        return t  # avoid risky changes by default
    if tone == 'aggressiv':
        return t  # do not amplify
    if tone == 'unsicher':
        return t  # content stays, confidence not altered in MVP
    return t


def apply_style(reply: str, profile: Dict) -> str:
    if not reply:
        return reply
    prof = profile or {}
    out = reply
    out = _apply_anrede(out, prof.get('anrede') or 'du')
    # Inject a dialect token or a familiar phrase if available
    tokens = []
    if isinstance(prof.get('dialekt_merkmale'), list):
        tokens.extend([t for t in prof.get('dialekt_merkmale') if isinstance(t, str)])
    if isinstance(prof.get('floskeln'), list):
        tokens.extend([t for t in prof.get('floskeln') if isinstance(t, str)])
    out = _inject_tokens(out, tokens[:1])
    out = _apply_tone(out, prof.get('tonfall') or 'neutral', bool(prof.get('formell')))
    return out
