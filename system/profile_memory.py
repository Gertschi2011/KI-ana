from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json, re, difflib

BASE = Path.home() / "ki_ana"
MEM  = BASE / "memory"
PROF = MEM / "profile.json"

def _ensure():
    MEM.mkdir(parents=True, exist_ok=True)
    if not PROF.exists():
        PROF.write_text(json.dumps({
            "active_speaker": None,        # "Papa" | "Gerald" | "Luna" ...
            "persons": {},                 # name -> person dict
            "updated_at": datetime.utcnow().isoformat()+"Z"
        }, indent=2, ensure_ascii=False), encoding="utf-8")

def load_profile() -> dict:
    _ensure()
    try:
        return json.loads(PROF.read_text(encoding="utf-8"))
    except Exception:
        return {"active_speaker": None, "persons": {}, "updated_at": None}

def save_profile(p: dict):
    p["updated_at"] = datetime.utcnow().isoformat()+"Z"
    PROF.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")

def _norm_name(n: str) -> str:
    return re.sub(r"\s+", " ", (n or "").strip()).strip()

def _get_or_create_person(p: dict, name: str) -> dict:
    name = _norm_name(name)
    if not name: name = "Unbekannt"
    persons = p.setdefault("persons", {})
    if name not in persons:
        persons[name] = {
            "display_name": name,
            "nicknames": [],
            "likes": [],
            "dislikes": [],
            "birthday": None,
            "created_at": datetime.utcnow().isoformat()+"Z"
        }
    return persons[name]

def _active_name(p: dict) -> str | None:
    a = p.get("active_speaker")
    if a and a in p.get("persons", {}):
        return a
    return None

def set_active_speaker(name: str) -> str:
    p = load_profile()
    name = _norm_name(name)
    # Fuzzy against existing keys
    keys = list(p.get("persons", {}).keys())
    if keys and name not in keys:
        match = difflib.get_close_matches(name, keys, n=1, cutoff=0.6)
        if match: name = match[0]
    _get_or_create_person(p, name)
    p["active_speaker"] = name
    save_profile(p)
    return name

def current_person() -> tuple[str | None, dict | None]:
    p = load_profile()
    nm = _active_name(p)
    if not nm:
        return None, None
    return nm, p["persons"][nm]

def ensure_speaker(name: str | None) -> str:
    if name and name.strip():
        return set_active_speaker(name)
    p = load_profile()
    nm = _active_name(p)
    if nm: return nm
    # kein aktiver Sprecher → neutral “Du”
    return set_active_speaker("Du")

def set_display_name(name: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p) or "Du")
    person = _get_or_create_person(p, who)
    name = _norm_name(name)
    person["display_name"] = name
    if name and name not in person["nicknames"]:
        person["nicknames"].append(name)
    save_profile(p)
    return True

def add_nickname(nick: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p))
    person = _get_or_create_person(p, who)
    nick = _norm_name(nick)
    if nick and nick not in person["nicknames"]:
        person["nicknames"].append(nick)
        save_profile(p)
        return True
    return False

def _contains_casefold(lst: list[str], it: str) -> bool:
    L = [x.casefold() for x in lst]
    return (it or "").casefold() in L

def add_like(item: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p))
    person = _get_or_create_person(p, who)
    it = _norm_name(item)
    if it and not _contains_casefold(person["likes"], it):
        person["likes"].append(it)
        # remove from dislikes if present
        person["dislikes"] = [x for x in person["dislikes"] if x.casefold()!=it.casefold()]
        save_profile(p)
        return True
    return False

def add_dislike(item: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p))
    person = _get_or_create_person(p, who)
    it = _norm_name(item)
    if it and not _contains_casefold(person["dislikes"], it):
        person["dislikes"].append(it)
        # remove from likes if present
        person["likes"] = [x for x in person["likes"] if x.casefold()!=it.casefold()]
        save_profile(p)
        return True
    return False

def forget_like(item: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p))
    person = _get_or_create_person(p, who)
    it = _norm_name(item)
    old = len(person["likes"])
    person["likes"] = [x for x in person["likes"] if x.casefold()!=it.casefold()]
    save_profile(p)
    return len(person["likes"]) < old

def forget_dislike(item: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p))
    person = _get_or_create_person(p, who)
    it = _norm_name(item)
    old = len(person["dislikes"])
    person["dislikes"] = [x for x in person["dislikes"] if x.casefold()!=it.casefold()]
    save_profile(p)
    return len(person["dislikes"]) < old

def set_birthday_for_active(iso_date: str):
    p = load_profile()
    who = ensure_speaker(_active_name(p))
    person = _get_or_create_person(p, who)
    person["birthday"] = iso_date
    save_profile(p)
    return True

def summary_for(name: str | None = None) -> str:
    p = load_profile()
    if not name:
        name = _active_name(p)
    if not name or name not in p.get("persons", {}):
        return "Kein Profil gefunden."
    d = p["persons"][name]
    likes = ", ".join(d["likes"]) if d["likes"] else "—"
    dislikes = ", ".join(d["dislikes"]) if d["dislikes"] else "—"
    bd = d["birthday"] or "—"
    nicks = ", ".join(d["nicknames"]) if d["nicknames"] else "—"
    disp = d.get("display_name") or name
    return f"👤 {disp}\n• Spitznamen: {nicks}\n• Mag: {likes}\n• Mag nicht: {dislikes}\n• Geburtstag: {bd}"
