"""
Current Information Detection
Detects when user asks about current/recent events that need web search
"""
import re
from datetime import datetime
from typing import Tuple

CURRENT_YEAR = datetime.now().year

def needs_current_info(message: str) -> Tuple[bool, str]:
    """
    Detect if message asks about current/recent information
    Returns: (needs_web, reason)
    """
    msg_lower = message.lower()
    
    # Current time indicators
    current_keywords = [
        'aktuell', 'momentan', 'jetzt', 'heute', 'gerade',
        'derzeit', 'zurzeit', 'gegenwärtig', 'neueste',
        'letzte', 'kürzlich', 'vor kurzem', 'gestern',
        'diese woche', 'diesen monat', 'dieses jahr'
    ]
    
    # Year detection - any year >= 2023 needs web
    year_patterns = [
        r'\b(202[3-9]|20[3-9]\d)\b',  # 2023-2099
        r'\b(Jahr\s+202[3-9])\b',
        r'\b(seit\s+202[3-9])\b'
    ]
    
    for pattern in year_patterns:
        if re.search(pattern, message):
            return True, f"Erwähnt Jahr >= 2023 (Training Cut-off)"
    
    # Current keywords
    for keyword in current_keywords:
        if keyword in msg_lower:
            return True, f"Fragt nach aktuellen Informationen (Keyword: '{keyword}')"
    
    # Question about events/news
    news_patterns = [
        r'was\s+(ist|sind|war|waren)\s+(passiert|geschehen|neu)',
        r'gibt\s+es\s+(etwas\s+)?neue',
        r'(neuigkeiten|news|nachrichten)',
        r'(ereignisse|entwicklungen)',
        r'was\s+weißt\s+du\s+(über|zu|von)\s+.*(heute|jetzt|aktuell)'
    ]
    
    for pattern in news_patterns:
        if re.search(pattern, msg_lower):
            return True, f"Fragt nach aktuellen Ereignissen"
    
    # Topics that are inherently current
    current_topics = [
        'wetter', 'börsenkurs', 'aktienkurs', 'wahlerg', 
        'corona', 'covid', 'pandemie', 'ukraine', 'krieg',
        'regierung', 'politik', 'präsident', 'kanzler',
        'fussball', 'bundesliga', 'weltmeister', 'olympia'
    ]
    
    for topic in current_topics:
        if topic in msg_lower:
            return True, f"Aktuelles Thema erkannt: '{topic}'"
    
    # Price/cost queries (often current)
    if re.search(r'(wie\s+viel|was\s+kostet|preis|kosten)', msg_lower):
        if any(word in msg_lower for word in ['aktuell', 'heute', 'momentan', 'jetzt']):
            return True, "Fragt nach aktuellem Preis"
    
    return False, ""

def inject_current_prompt(base_prompt: str, message: str) -> str:
    """
    Inject instruction to use web search for current info
    """
    needs_web, reason = needs_current_info(message)
    
    if not needs_web:
        return base_prompt
    
    current_instruction = f"""
WICHTIG: Diese Frage erfordert aktuelle Informationen (Grund: {reason}).
Dein Training endet 2023. Für Ereignisse/Daten nach 2023 oder aktuelle Themen:
1. NUTZE AKTIV die Web-Suche
2. Sage EXPLIZIT wenn du Web-Daten nutzt
3. Gib Quellen/Datum an
4. Sei transparent über Informationsstand

Aktuelles Jahr: {CURRENT_YEAR}
"""
    
    return current_instruction + "\n\n" + base_prompt

def format_with_source_date(response: str, source_date: str = None) -> str:
    """
    Add source date to response for transparency
    """
    if not source_date:
        source_date = datetime.now().strftime("%Y-%m-%d")
    
    footer = f"\n\n📅 Stand der Information: {source_date}"
    return response + footer
