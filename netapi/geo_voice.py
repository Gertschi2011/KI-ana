from __future__ import annotations
from typing import Dict, Any, Optional
import json, os, urllib.request

VOICE_MAP: Dict[str, Dict[str, Any]] = {
    "AT":{"lang":"de-DE","greeting":"Hallo, ich bin KI_ana. Schön, dass du da bist!"},
    "DE":{"lang":"de-DE","greeting":"Hallo, ich bin KI_ana. Schön, dass du da bist!"},
    "CH":{"lang":"de-DE","greeting":"Hoi, ich bin KI_ana. Schön, dass du da bist!"},
    "US":{"lang":"en-US","greeting":"Hi, I’m KI_ana. I’m happy you’re here!"},
    "GB":{"lang":"en-GB","greeting":"Hi, I’m KI_ana. I’m happy you’re here!"},
    "FR":{"lang":"fr-FR","greeting":"Salut, je suis KI_ana. Je suis contente que tu sois là !"},
    "ES":{"lang":"es-ES","greeting":"Hola, soy KI_ana. ¡Me alegra que estés aquí!"},
    "IT":{"lang":"it-IT","greeting":"Ciao, sono KI_ana. Sono felice che tu sia qui!"},
    "RO":{"lang":"ro-RO","greeting":"Bună, eu sunt KI_ana. Mă bucur că ești aici!"},
    "DEFAULT":{"lang":"en-US","greeting":"Hi, I’m KI_ana. I’m happy you’re here!"},
}

def _http_json(url:str, timeout:float=1.5)->Optional[dict]:
    try:
        req=urllib.request.Request(url, headers={"User-Agent":"KI_ana/voice"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8","replace"))
    except Exception:
        return None

def country_from_ip(ip:str)->Optional[str]:
    if not ip or ip.startswith(("127.","10.","192.168.","172.")):
        return None
    d=_http_json(f"https://ip-api.com/json/{ip}?fields=status,countryCode")
    if d and d.get("status")=="success":
        cc=d.get("countryCode")
        if isinstance(cc,str) and len(cc)==2:
            return cc.upper()
    return None

def detect_voice(client_ip: str | None)->Dict[str,Any]:
    cc = country_from_ip(client_ip or "") or os.getenv("KI_ANA_DEFAULT_CC") or "DEFAULT"
    cfg = VOICE_MAP.get(cc, VOICE_MAP["DEFAULT"]).copy()
    cfg["country_code"] = cc if cc!="DEFAULT" else None
    cfg["pitch"] = 1.2
    cfg["rate"] = 0.95
    return cfg
