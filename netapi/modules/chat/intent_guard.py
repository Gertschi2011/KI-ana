from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional


@dataclass(frozen=True)
class IntentGuardResult:
    should_block: bool
    intent: str
    missing_fields: List[str]
    questions: List[str]
    note: str
    debug: Dict[str, object]


_TRANSLATE_RX = re.compile(r"\b(\u00fcbersetz\w*|translate\w*)\b", re.IGNORECASE)
_SUMMARIZE_RX = re.compile(r"\b(zusammenfass\w*|fass\s+zusammen|summary|tl;dr)\b", re.IGNORECASE)
_WRITE_RX = re.compile(
    r"\b(schreib\w*|formulier\w*|entwurf\w*|email|e-mail|nachricht\w*|bewerbung\w*|k\u00fcndig\w*|anschreib\w*|cover\s*letter)\b",
    re.IGNORECASE,
)
_DEBUG_RX = re.compile(r"\b(fehl(er\w*|ermeldung\w*)|bug\w*|crash\w*|exception\w*|traceback|stack\s*trace|geht\s+nicht)\b", re.IGNORECASE)

# New clarify intents (productization: Fragen & Merken)
_STELLUNGNAHME_RX = re.compile(
    r"\b(stellungnahme|statement|positionspapier|position\b|meinungstext|erkl\u00e4rung\s+f\u00fcr\s+.*(beh\u00f6rde|amt))\b",
    re.IGNORECASE,
)
_DRAFT_LETTER_RX = re.compile(
    r"\b(entwurf|draft|brief|anschreiben|antwortschreiben|reply\s+letter)\b",
    re.IGNORECASE,
)
_CODE_CHANGE_RX = re.compile(
    r"\b(\u00e4nder\w*\s+den\s+code|code\s+\u00e4nder\w*|refactor\w*|implementier\w*|implement\w*|patch\w*|fix\w*|bugfix\w*|pull\s*request|pr\b)\b",
    re.IGNORECASE,
)
_RESEARCH_FACTS_RX = re.compile(
    r"\b("
    r"recherchier\w*|recherche|"
    r"fakten\s*check|faktencheck|fact\s*check|"
    r"pr\u00fcf\w*\s+das|beleg\w*|quellen\b|studien\b|"
    r"gesetz\w*|verordnung\w*|parlament\b|pdf\b|"
    r"zahlen\b|statistik\w*|beleg\b|quelle\b|"
    r"aktuell\b|heute\b|latest\b|news\b"
    r")\b",
    re.IGNORECASE,
)

# General "research triggers" for intent routing / web gating.
_RESEARCH_TRIGGERS_RX = _RESEARCH_FACTS_RX
_RECOMMEND_BUY_RX = re.compile(
    r"\b(kauf\s*beratung|kaufberatung|empfehl\w*|welches\s+.*\s+kaufen|buy\s+recommendation|kauf\s*empfehl\w*)\b",
    re.IGNORECASE,
)

# Selftalk / smalltalk intent (must never trigger missing-context blocking).
_SELFTALK_RX = re.compile(
    r"\b("
    r"was\s+machst\s+du|was\s+tust\s+du|what\s+do\s+you\s+do|"
    r"wer\s+bist\s+du|was\s+bist\s+du|was\s+kannst\s+du|"
    r"who\s+are\s+you|what\s+are\s+you|"
    r"wie\s+geht('s)?\s+dir|wie\s+geht\s+es\s+dir|"
    r"are\s+you\s+there|bist\s+du\s+da|"
    r"hallo|hi|hey|guten\s+morgen|guten\s+tag|guten\s+abend|"
    r"hello|good\s+morning|good\s+evening|"
    r"danke|dankesch\u00f6n|thx|thanks|"
    r"lol|ok|okay|alles\s+klar|super|nice|gg|"
    r"kiana|ki_ana"
    r")\b",
    re.IGNORECASE,
)
_SELFTALK_PRONOUN_RX = re.compile(r"\b(du|dir|dich|dein(e|em|en|er|es)?)\b", re.IGNORECASE)

_EMAIL_RX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_CODEBLOCK_RX = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_URL_RX = re.compile(r"https?://\S+", re.IGNORECASE)


def _normalize(text: str) -> str:
    return (text or "").strip()


def detect_intent(message: str) -> str:
    """Deterministic, conservative intent classifier.

    Only returns a 'needs-context' intent when the message strongly matches.
    Otherwise returns 'general'.
    """
    text = _normalize(message)
    low = text.lower()

    # Selftalk / smalltalk should be recognized early.
    # Keep it short and directed at the assistant (pronoun/name heuristic).
    try:
        if _SELFTALK_RX.search(low):
            return "selftalk"
        # Pronoun heuristic: only if message is short and seems directly addressed.
        if len(low) <= 60 and _SELFTALK_PRONOUN_RX.search(low) and ("?" in low or "kiana" in low or "ki_ana" in low):
            return "selftalk"
    except Exception:
        pass

    # Quick exemptions: short factual/math questions should never be blocked.
    if re.fullmatch(r"[0-9\s+\-*/().,]+", low) and any(ch.isdigit() for ch in low):
        return "general"
    if "?" in low and not any(rx.search(low) for rx in (_TRANSLATE_RX, _SUMMARIZE_RX, _WRITE_RX, _DEBUG_RX)):
        return "general"

    if _TRANSLATE_RX.search(low):
        return "translate"
    if _SUMMARIZE_RX.search(low):
        return "summarize"

    # More specific writing intents before generic write
    if _STELLUNGNAHME_RX.search(low):
        return "stellungnahme"
    # "draft_letter" overlaps with write; keep distinct for clarify.
    if _DRAFT_LETTER_RX.search(low) and _WRITE_RX.search(low):
        return "draft_letter"

    if _CODE_CHANGE_RX.search(low):
        return "code_change"
    if _RESEARCH_FACTS_RX.search(low):
        return "research_facts"
    if _RECOMMEND_BUY_RX.search(low):
        return "recommendation_buy"

    if _WRITE_RX.search(low):
        return "write"
    if _DEBUG_RX.search(low):
        return "debug"

    return "general"


def classify(message: str) -> str:
    """Public intent classification entry point.

    This is intentionally deterministic and conservative.
    """
    return detect_intent(message)


def has_research_trigger(message: str) -> bool:
    """Return True if message indicates it should use web/PDF sources.

    Used for routing and for guarding against accidental web lookup on short/smalltalk messages.
    """
    try:
        return bool(_RESEARCH_TRIGGERS_RX.search((message or "").lower()))
    except Exception:
        return False


def _has_substantial_payload(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    if _CODEBLOCK_RX.search(t):
        return True
    # Heuristic: at least a few words beyond the command.
    return len(t) >= 30 and len(t.split()) >= 6


def _extract_after_command(message: str, rx: re.Pattern) -> str:
    """Best-effort: return part after matched command word."""
    m = rx.search(message)
    if not m:
        return ""
    return message[m.end() :].strip(" :\n\t")


def _missing_fields(intent: str, message: str) -> List[str]:
    text = _normalize(message)
    low = text.lower()

    if intent == "translate":
        after = _extract_after_command(text, _TRANSLATE_RX)
        missing: List[str] = []
        if not _has_substantial_payload(after):
            missing.append("text")
        # target language if not mentioned
        if not re.search(r"\b(ins?\s+(englisch|deutsch|franz\u00f6sisch|spanisch|italienisch)|to\s+(english|german|french|spanish|italian))\b", low):
            missing.append("target_language")
        return missing

    if intent == "summarize":
        after = _extract_after_command(text, _SUMMARIZE_RX)
        missing = []
        if not (_URL_RX.search(text) or _has_substantial_payload(after)):
            missing.append("text_or_link")
        return missing

    if intent == "write":
        missing = []
        # recipient: explicit email or "an ..." or "f\u00fcr ..."
        if not (_EMAIL_RX.search(text) or re.search(r"\b(an|f\u00fcr)\s+[^\n]{2,}", low)):
            missing.append("recipient")
        # purpose/context: simple keyword-based
        if not re.search(r"\b(wegen|bezug|betreff|um\s+zu|dass|weil|beziehungsweise|bzgl\.?|\u00fcber)\b", low):
            missing.append("purpose")
        return missing

    if intent in {"draft_letter", "stellungnahme"}:
        missing = []
        # Topic / subject
        if not re.search(r"\b(zu|\u00fcber|bzgl\.?|bezug|betreff|thema)\b", low):
            missing.append("topic")
        # Audience / recipient
        if not (_EMAIL_RX.search(text) or re.search(r"\b(an|f\u00fcr)\s+[^
]{2,}", low)):
            missing.append("audience")
        # Position / key points
        if intent == "stellungnahme":
            if not re.search(r"\b(pro|contra|daf\u00fcr|dagegen|neutral|position|standpunkt|kernsatz|kernaussage)\b", low):
                missing.append("position")
        # Constraints / length
        if not re.search(r"\b(\d+\s*(w\u00f6rter|worte|seiten)|kurz|knapp|ausf\u00fchrlich|1\s*seite|halbe\s*seite)\b", low):
            missing.append("length")
        return missing

    if intent == "code_change":
        missing = []
        # Goal / change requested
        if not re.search(r"\b(ziel|soll|muss|\u00e4ndern|fix|bug|feature|implement|refactor)\b", low):
            missing.append("goal")
        # Code context: file path or code block
        if not (_CODEBLOCK_RX.search(text) or re.search(r"\b[a-z0-9_./-]+\.(py|js|ts|tsx|java|go|rs|rb|php|cs|cpp|c|h)\b", low)):
            missing.append("code_or_file")
        # Expected vs actual for fixes
        if _DEBUG_RX.search(low) and not re.search(r"\b(erwart|sollte|expected|passiert|stattdessen)\b", low):
            missing.append("expected_vs_actual")
        return missing

    if intent == "research_facts":
        missing = []
        # Claim / question
        if not re.search(r"\?|\b(ob|stimmt|wahr|falsch|beleg|quelle|studie)\b", low):
            missing.append("claim_or_question")
        # Scope / timeframe
        if not re.search(r"\b(aktuell|heute|202\d|seit\s+\d{4}|letzte\w*\s+(woche|monat|jahr))\b", low):
            missing.append("timeframe")
        # Region / language
        if not re.search(r"\b(deutschland|\u00f6sterreich|schweiz|eu|usa|uk|weltweit|global)\b", low):
            missing.append("region")
        return missing

    if intent == "recommendation_buy":
        missing = []
        # Category / what to buy
        if not re.search(r"\b(kamera|laptop|handy|smartphone|kopfh\u00f6rer|monitor|staubsauger|drucker|router|pc|notebook|tablet|tv|fernseher)\b", low):
            missing.append("category")
        # Budget
        if not re.search(r"\b(\d+\s*\u20ac|\d+\s*eur|unter\s+\d+|bis\s+\d+)\b", low):
            missing.append("budget")
        # Use-case / constraints
        if not re.search(r"\b(f\u00fcr|einsatz|zweck|nutzen|gaming|office|studium|reise|foto|video)\b", low):
            missing.append("use_case")
        return missing

    if intent == "debug":
        missing = []
        has_error = bool(re.search(r"\b(traceback|exception|stack\s*trace|fehlermeldung|error)\b", low))
        has_payload = _CODEBLOCK_RX.search(text) is not None or len(text) >= 80
        if not (has_error or has_payload):
            missing.append("error_or_logs")
        if not re.search(r"\b(erwart|sollte|expected|passiert|stattdessen)\b", low):
            missing.append("expected_vs_actual")
        return missing

    return []


def _questions(intent: str, missing_fields: List[str], lang: str) -> List[str]:
    # Keep questions short and deterministic.
    # Currently German-first; lang hook is here for future expansion.
    if intent == "translate":
        qs: List[str] = []
        if "text" in missing_fields:
            qs.append("Welchen Text soll ich \u00fcbersetzen? (Bitte hier einf\u00fcgen)")
        if "target_language" in missing_fields:
            qs.append("In welche Zielsprache soll es gehen?")
        qs.append("Soll ich w\u00f6rtlich oder frei \u00fcbersetzen (Tonfall beibehalten)?")
        return qs[:4]

    if intent == "summarize":
        qs = []
        if "text_or_link" in missing_fields:
            qs.append("Welchen Text oder Link soll ich zusammenfassen?")
        qs.append("Wie kurz soll die Zusammenfassung sein (z.\u202fB. 5 Bullet Points / 1 Absatz)?")
        return qs[:4]

    if intent == "write":
        qs = []
        if "recipient" in missing_fields:
            qs.append("An wen geht es (Person/Team) und in welcher Beziehung stehst du dazu?")
        if "purpose" in missing_fields:
            qs.append("Worum genau geht es (Ziel/Anliegen) und welche Details m\u00fcssen unbedingt rein?")
        qs.append("Welcher Tonfall: kurz & sachlich, freundlich, formell, oder locker?")
        return qs[:4]

    if intent == "debug":
        qs = []
        if "error_or_logs" in missing_fields:
            qs.append("Welche Fehlermeldung/Logs bekommst du (bitte komplett einf\u00fcgen)?")
        if "expected_vs_actual" in missing_fields:
            qs.append("Was erwartest du, und was passiert stattdessen?")
        qs.append("Welche Umgebung: OS/Version, Python/Node/etc., und Schritte zum Reproduzieren?")
        return qs[:4]

    if intent == "stellungnahme":
        qs: List[str] = []
        if "topic" in missing_fields:
            qs.append("Zu welchem Thema/Anlass genau soll die Stellungnahme sein?")
        if "audience" in missing_fields:
            qs.append("Für wen ist sie gedacht (Behörde/Arbeitgeber/…)?")
        if "position" in missing_fields:
            qs.append("Welche Position/Kernaussagen soll ich vertreten (pro/contra/neutral)?")
        if "length" in missing_fields:
            qs.append("Wie lang soll sie sein (z. B. 1 Seite / 300 Wörter / sehr kurz)?")
        # Optional: tone
        qs.append("Soll sie eher sachlich-formell oder eher freundlich-kurz klingen?")
        return qs[:5]

    if intent == "draft_letter":
        qs = []
        if "topic" in missing_fields:
            qs.append("Worum geht es im Brief/Entwurf (Thema/Anliegen)?")
        if "audience" in missing_fields:
            qs.append("An wen geht der Brief (Empfänger + Beziehung)?")
        if "length" in missing_fields:
            qs.append("Wie lang soll es werden (kurz / 1 Seite / …) und welcher Ton?")
        qs.append("Gibt es Muss-Punkte oder Stichwörter, die unbedingt rein sollen?")
        return qs[:5]

    if intent == "code_change":
        qs = []
        if "goal" in missing_fields:
            qs.append("Was genau soll ich im Code ändern (Ziel/Feature/Fix)?")
        if "code_or_file" in missing_fields:
            qs.append("In welcher Datei/Code-Stelle passiert das (Pfad oder relevanter Code-Snippet)?")
        if "expected_vs_actual" in missing_fields:
            qs.append("Was erwartest du, und was passiert stattdessen?")
        qs.append("Welche Umgebung/Versionen und wie kann ich es reproduzieren?")
        return qs[:5]

    if intent == "research_facts":
        qs = []
        if "claim_or_question" in missing_fields:
            qs.append("Welche konkrete Behauptung/Frage soll ich pr\u00fcfen?")
        if "timeframe" in missing_fields:
            qs.append("Welcher Zeitraum ist relevant (aktuell/seit wann)?")
        if "region" in missing_fields:
            qs.append("Auf welches Land/Region oder welche Sprache soll ich mich beziehen?")
        qs.append("Wie streng sollen die Quellen sein (Studien/Beh\u00f6rden/News) und welche Quellen sind tabu?")
        return qs[:5]

    if intent == "recommendation_buy":
        qs = []
        if "category" in missing_fields:
            qs.append("Was genau willst du kaufen (Kategorie + 1–2 Beispiele)?")
        if "budget" in missing_fields:
            qs.append("Welches Budget hast du (max. Preis)?")
        if "use_case" in missing_fields:
            qs.append("Wof\u00fcr brauchst du es (Einsatz, Muss-/Kann-Kriterien)?")
        qs.append("Gibt es No-Gos (Marken, Gr\u00f6\u00dfe, Lautst\u00e4rke, OS, Lieferland)?")
        return qs[:5]

    return ["Kannst du kurz mehr Kontext geben?"]


def guard_missing_context(message: str, *, lang: str = "de-DE") -> Optional[IntentGuardResult]:
    """Return an IntentGuardResult when we must ask clarifying questions.

    Returns None when it is safe to continue with retrieval/memory/LLM.
    """
    text = _normalize(message)
    intent = detect_intent(text)
    # Never block selftalk / smalltalk.
    if intent == "selftalk":
        return None
    if intent == "general":
        return None

    missing = _missing_fields(intent, text)
    if not missing:
        return None

    # Apply product rule:
    # - 1–2 missing -> ask 2 questions (include 1 optional helper if only one missing)
    # - >=3 missing -> ask exactly 3 questions (mini form)
    qs_all = _questions(intent, missing, lang)
    if len(missing) >= 3:
        qs = list(qs_all[:3])
    elif len(missing) == 2:
        qs = list(qs_all[:2])
    else:  # len == 1
        qs = list(qs_all[:2])
    return IntentGuardResult(
        should_block=True,
        intent=intent,
        missing_fields=list(missing),
        questions=list(qs),
        note="Noch kein Kontext \u2013 KI_ana wartet auf Kl\u00e4rung.",
        debug={
            "intent": intent,
            "missing": list(missing),
        },
    )
