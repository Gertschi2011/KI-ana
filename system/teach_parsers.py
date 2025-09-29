from __future__ import annotations
import re
from datetime import datetime
from profile_memory import (
    load_profile, save_profile, set_active_speaker, ensure_speaker,
    set_display_name, add_nickname, add_like, add_dislike,
    forget_like, forget_dislike, set_birthday_for_active, summary_for
)

def _prep(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())

def _iso_from_datefrag(dd: str, mm: str, yyyy: str) -> str | None:
    try:
        d, m, y = int(dd), int(mm), int(yyyy)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return None

def teach_from_sentence(text: str) -> tuple[bool, str]:
    t = _prep(text)
    tl = t.lower()

    # --- Sprecherwechsel ---
    # "ich bin [Name]" | "hier spricht [Name]" | "wechsle sprecher zu [Name]"
    m = re.search(r'\b(ich bin|hier spricht|ich spreche|wechsle (?:den )?sprecher (?:zu|auf))\s+(.+)$', tl)
    if m:
        raw = t[m.start(2):].strip().strip(".! ")
        who = set_active_speaker(raw)
        return True, f"Okay, {who}. Ich spreche jetzt mit dir."

    # --- Selbstvorstellung / Name ---
    # "ich heiße X" / "mein name ist X" / "nenn mich X" / "du darfst mich X nennen"
    m = re.search(r'\b(ich heiße|ich heisse|mein name ist|nenn mich|du darfst mich .* nennen)\s+(.+)$', tl)
    if m:
        raw = t[m.start(2):].strip().strip(".! ")
        set_display_name(raw)
        who, _ = ensure_speaker(None), None
        return True, f"Freut mich, {raw}! Ich merke mir das."

    # --- Spitzname ---
    m = re.search(r'\b(mein spitzname ist|nenn mich kurz)\s+(.+)$', tl)
    if m:
        raw = t[m.start(2):].strip().strip(".! ")
        add_nickname(raw)
        return True, f"Spitzname gespeichert: {raw}."

    # --- Likes / Loves ---
    m = re.search(r'\b(ich mag|ich liebe)\s+(?!nicht\b)(.+)$', tl)
    if m:
        item = t[m.start(2):].strip().strip(".! ")
        add_like(item)
        return True, f"Gemacht: Du magst {item}."

    # --- Dislikes / Hates / “mag nicht” ---
    m = re.search(r'\b(ich mag nicht|ich hasse)\s+(.+)$', tl)
    if m:
        item = t[m.start(2):].strip().strip(".! ")
        add_dislike(item)
        return True, f"Verstanden: Du magst nicht {item}."

    # --- Vergessen (Like/Dislike) ---
    m = re.search(r'\b(vergiss|lösch|entfern)\s+(dass\s+)?ich\s+(nicht\s+)?mag\s+(.+)$', tl)
    if m:
        neg = bool(m.group(3))
        thing = t[m.start(4):].strip().strip(".! ")
        ok = forget_dislike(thing) if neg else forget_like(thing)
        return True, ("Gelöscht. 👍" if ok else "War nicht eingetragen.") 

    # --- Geburtstag (dd.mm.yyyy oder yyyy-mm-dd) ---
    m = re.search(r'\bmein geburtstag ist am\s+(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b', tl)
    if not m:
        m = re.search(r'\bmein geburtstag ist am\s*(\d{4})-(\d{1,2})-(\d{1,2})\b', tl)
        if m:
            iso = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        else:
            iso = None
    else:
        iso = _iso_from_datefrag(*m.groups())
    if iso:
        set_birthday_for_active(iso)
        return True, f"Geburtstag notiert: {iso} 🎂"

    # --- Abfragen ---
    if re.search(r'\b(wer bin ich|wie nennst du mich)\b', tl):
        p = load_profile()
        nm = p.get("active_speaker")
        if not nm: return True, "Ich kenne deinen Namen noch nicht. Sag mir: „Ich heiße …“"
        person = p["persons"][nm]
        disp = person.get("display_name") or nm
        nicks = ", ".join(person.get("nicknames") or []) or "—"
        return True, f"Du bist {disp}. Spitznamen: {nicks}"

    if re.search(r'\b(was mag ich|was mag ich nicht)\b', tl):
        p = load_profile(); nm = p.get("active_speaker")
        if not nm: return True, "Sag mir zuerst deinen Namen."
        person = p["persons"][nm]
        likes = ", ".join(person.get("likes") or []) or "—"
        dislikes = ", ".join(person.get("dislikes") or []) or "—"
        return True, f"Mag: {likes}\nMag nicht: {dislikes}"

    if re.search(r'\b(zeig (mir )?profil|profil zeigen)\b', tl):
        p = load_profile(); nm = p.get("active_speaker") or None
        return True, summary_for(nm)

    # nichts gelernt
    return False, ""
