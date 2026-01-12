from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_e2e_06_learning_ask_creates_candidate_and_accept_persists(verified_user_session):
    _user, client = verified_user_session

    # Trigger: policy.learning=ask + correction-like message prefix
    resp = client.post(
        "/api/v2/chat",
        json={
            "message": "Korrektur: Die Hauptstadt von Österreich ist Wien.",
            "policy": {"learning": "ask"},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    meta = data.get("meta") or {}
    autonomy = meta.get("autonomy") or {}
    assert autonomy.get("ask_learning_consent") is True
    cand_id = autonomy.get("learning_candidate_id")
    preview = autonomy.get("learning_candidate_preview")
    assert isinstance(cand_id, str) and cand_id
    assert isinstance(preview, dict)
    assert "content" in preview

    # Candidate visible
    cand_resp = client.get("/api/v2/learning/candidates", params={"status": "pending", "limit": 50})
    assert cand_resp.status_code == 200, cand_resp.text
    items = cand_resp.json().get("items") or []
    assert any(i.get("candidate_id") == cand_id for i in items)

    # Accept -> persists block + updates addressbook
    accept = client.post(
        "/api/v2/learning/consent",
        json={"candidate_id": cand_id, "decision": "accept", "notes": "ok"},
    )
    assert accept.status_code == 200, accept.text
    out = accept.json()
    assert out.get("ok") is True
    assert out.get("applied") is True
    blk = out.get("persisted_block_id")
    assert isinstance(blk, str) and blk.startswith("BLK_")
    assert out.get("addressbook_updated") is True

    # Block file exists
    block_path = _repo_root() / "memory" / "long_term" / "blocks" / f"{blk}.json"
    assert block_path.exists(), f"missing block file: {block_path}"
    obj = json.loads(block_path.read_text(encoding="utf-8"))
    assert isinstance(obj.get("meta"), dict)
    assert obj["meta"].get("type") == "learning_correction"

    # Addressbook index updated
    addr_path = _repo_root() / "memory" / "index" / "addressbook.json"
    assert addr_path.exists(), f"missing addressbook.json: {addr_path}"
    addr = json.loads(addr_path.read_text(encoding="utf-8"))
    idx = addr.get("learning_corrections") or {}
    assert isinstance(idx, dict)
    assert any(blk in (v.get("block_ids") or []) for v in idx.values() if isinstance(v, dict))

    # Idempotent accept
    accept2 = client.post(
        "/api/v2/learning/consent",
        json={"candidate_id": cand_id, "decision": "accept"},
    )
    assert accept2.status_code == 200, accept2.text
    out2 = accept2.json()
    assert out2.get("ok") is True
    assert out2.get("applied") is False
    assert out2.get("persisted_block_id") == blk


def test_e2e_06_learning_deny_marks_candidate_no_persist(verified_user_session):
    _user, client = verified_user_session

    resp = client.post(
        "/api/v2/chat",
        json={
            "message": "Correction: 2+2 ist 4.",
            "policy": {"learning": "ask"},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    cand_id = (((data.get("meta") or {}).get("autonomy") or {}).get("learning_candidate_id"))
    assert isinstance(cand_id, str) and cand_id

    deny = client.post(
        "/api/v2/learning/consent",
        json={"candidate_id": cand_id, "decision": "deny"},
    )
    assert deny.status_code == 200, deny.text
    out = deny.json()
    assert out.get("ok") is True
    assert out.get("applied") is True
    assert out.get("persisted_block_id") is None
    assert out.get("addressbook_updated") is False

    # Candidate no longer pending
    cand_resp = client.get("/api/v2/learning/candidates", params={"status": "pending", "limit": 50})
    assert cand_resp.status_code == 200, cand_resp.text
    items = cand_resp.json().get("items") or []
    assert all(i.get("candidate_id") != cand_id for i in items)
