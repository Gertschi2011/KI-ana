import json
import os
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional

from nacl import signing, encoding  # PyNaCl for Ed25519

BASE_DIR = Path(__file__).resolve().parent
PERSONA_DIR = (BASE_DIR / "persona").resolve()

class SubKIAgent:
    def __init__(self, owner_id: str, subki_id: str, persona_name: str = "mini_ana"):
        self.owner_id = owner_id
        self.subki_id = subki_id
        self.persona_name = persona_name
        self.root = PERSONA_DIR / owner_id
        self.mem_lt = self.root / "memory" / "long_term"
        self.pending = self.root / "pending_blocks"
        self.profile_path = self.root / "profile.json"
        for p in [self.root, self.mem_lt, self.pending]:
            p.mkdir(parents=True, exist_ok=True)
        self._init_keypair()

    def _init_keypair(self) -> None:
        key_path = self.root / "subki_ed25519.key"
        if key_path.exists():
            sk_hex = key_path.read_text().strip()
            self._sk = signing.SigningKey(sk_hex, encoder=encoding.HexEncoder)
        else:
            self._sk = signing.SigningKey.generate()
            key_path.write_text(self._sk.encode(encoder=encoding.HexEncoder).decode())
        self._vk = self._sk.verify_key

    def pubkey_hex(self) -> str:
        return self._vk.encode(encoder=encoding.HexEncoder).decode()

    def _hash_block(self, block: Dict[str, Any]) -> str:
        raw = json.dumps(block, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _sign_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        msg = json.dumps(block, ensure_ascii=False, sort_keys=True).encode("utf-8")
        sig = self._sk.sign(msg).signature
        block["signature"] = encoding.HexEncoder.encode(sig).decode()
        block["pubkey"] = self.pubkey_hex()
        block["subki_id"] = self.subki_id
        return block

    def learn(self, title: str, content: str, tags: Optional[List[str]] = None, source: Optional[str] = None) -> Dict[str, Any]:
        block = {
            "owner": self.owner_id,
            "persona": self.persona_name,
            "title": title[:160],
            "content": content,
            "tags": tags or [],
            "source": source or None,
            "ts": int(time.time()),
        }
        block["hash"] = self._hash_block(block)
        block = self._sign_block(block)
        # store as pending
        (self.pending / f"{block['hash']}.json").write_text(json.dumps(block, ensure_ascii=False, indent=2))
        return block

    def reflect_on_pending(self) -> List[Dict[str, Any]]:
        """Simple heuristics: mark blocks ready_for_sync if they have source or multiple tags."""
        out = []
        for f in self.pending.glob("*.json"):
            try:
                blk = json.loads(f.read_text())
                ready = bool(blk.get("source")) or len(blk.get("tags", [])) >= 2 or len(blk.get("content","")) > 240
                blk["ready_for_sync"] = bool(ready)
                f.write_text(json.dumps(blk, ensure_ascii=False, indent=2))
                out.append(blk)
            except Exception:
                continue
        return out

    def promote_to_long_term(self, block: Dict[str, Any]) -> None:
        (self.mem_lt / f"{block['hash']}.json").write_text(json.dumps(block, ensure_ascii=False, indent=2))

    def ready_blocks(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for f in self.pending.glob("*.json"):
            try:
                blk = json.loads(f.read_text())
                if blk.get("ready_for_sync"):
                    items.append(blk)
            except Exception:
                continue
        return items
