#!/usr/bin/env python3
from __future__ import annotations
import json, time, uuid
from importlib.machinery import SourceFileLoader
from pathlib import Path

BASE_DIR = Path.home() / "ki_ana"
BLOCK_UTILS_PATH = BASE_DIR / "system" / "block_utils.py"
BLOCK_SIGNER_PATH = BASE_DIR / "system" / "block_signer.py"
REFLECT_PATH = BASE_DIR / "system" / "reflection_engine.py"


def _load(name: str, p: Path):
    return SourceFileLoader(name, str(p)).load_module()  # type: ignore


def make_block(topic: str, content: str) -> dict:
    bid = uuid.uuid4().hex[:16]
    return {
        "id": bid,
        "topic": topic,
        "title": f"Testblock {bid}",
        "content": content,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "meta": {"provenance": "test_fixture", "tags": ["test:true"]},
    }


def main():
    bu = _load("block_utils", BLOCK_UTILS_PATH)
    bs = _load("block_signer", BLOCK_SIGNER_PATH)
    re = _load("reflection_engine", REFLECT_PATH)

    topic = "Verantwortung"
    fixtures = [
        make_block(topic, "KI ist immer objektiv."),
        make_block(topic, "Trainingsdaten enthalten oft unbewusste Vorurteile."),
        make_block(topic, "Technische Systeme sind neutral."),
    ]

    for b in fixtures:
        sig, pub, signed_at = bs.sign_block(b)  # type: ignore
        b["signature"] = sig
        b["pubkey"] = pub
        b["signed_at"] = signed_at
        res = bu.validate_and_store_block(b)  # type: ignore
        assert res.get("ok"), f"store failed: {res}"

    # Now reflect
    out = re.reflect_on_topic(topic)  # type: ignore
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
