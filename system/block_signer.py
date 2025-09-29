#!/usr/bin/env python3
from __future__ import annotations
import base64, json, time
from pathlib import Path
from typing import Dict, Any, Tuple

BASE_DIR = Path.home() / "ki_ana"
KEY_DIR = BASE_DIR / "system" / "keys"
PRIV_PATH = KEY_DIR / "ed25519.priv"
PUB_PATH = KEY_DIR / "ed25519.pub"

# Try cryptography first (widely available), then PyNaCl as fallback
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey  # type: ignore
    from cryptography.hazmat.primitives import serialization  # type: ignore
    _CRYPTO_OK = True
except Exception:
    _CRYPTO_OK = False

try:
    import nacl.signing  # type: ignore
    _NACL_OK = True
except Exception:
    _NACL_OK = False


def _canonical(obj: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(obj)
    for k in ("hash", "hash_stored", "hash_calc", "signature", "pubkey", "signed_at"):
        data.pop(k, None)
    return data


def canonical_bytes(obj: Dict[str, Any]) -> bytes:
    return json.dumps(_canonical(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def ensure_keys() -> Tuple[str, str]:
    """Ensure ed25519 keypair exists. Returns (pub_b64, priv_b64)."""
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    if PRIV_PATH.exists() and PUB_PATH.exists():
        pub_b64 = PUB_PATH.read_text(encoding="utf-8").strip()
        priv_b64 = PRIV_PATH.read_text(encoding="utf-8").strip()
        return pub_b64, priv_b64
    # generate
    if _CRYPTO_OK:
        priv = Ed25519PrivateKey.generate()
        pub = priv.public_key()
        priv_raw = priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_raw = pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    elif _NACL_OK:
        sk = nacl.signing.SigningKey.generate()
        vk = sk.verify_key
        priv_raw = sk.encode()
        pub_raw = vk.encode()
    else:
        raise RuntimeError("No ed25519 backend available (cryptography or PyNaCl)")
    priv_b64 = base64.b64encode(priv_raw).decode("ascii")
    pub_b64 = base64.b64encode(pub_raw).decode("ascii")
    PRIV_PATH.write_text(priv_b64, encoding="utf-8")
    PUB_PATH.write_text(pub_b64, encoding="utf-8")
    return pub_b64, priv_b64


def sign_block(block: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return (signature_b64, pubkey_b64, signed_at_iso)."""
    pub_b64, priv_b64 = ensure_keys()
    data = canonical_bytes(block)
    if _CRYPTO_OK:
        priv_raw = base64.b64decode(priv_b64)
        priv = Ed25519PrivateKey.from_private_bytes(priv_raw)
        sig = priv.sign(data)
    elif _NACL_OK:
        sk = nacl.signing.SigningKey(base64.b64decode(priv_b64))
        sig = sk.sign(data).signature
    else:
        raise RuntimeError("No ed25519 backend available")
    signed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return base64.b64encode(sig).decode("ascii"), pub_b64, signed_at


def verify_block(block: Dict[str, Any]) -> Tuple[bool, str]:
    sig_b64 = (block.get("signature") or "").strip()
    pub_b64 = (block.get("pubkey") or "").strip()
    if not sig_b64 or not pub_b64:
        return False, "signature_missing"
    try:
        sig = base64.b64decode(sig_b64)
        pub = base64.b64decode(pub_b64)
        data = canonical_bytes(block)
        if _CRYPTO_OK:
            vk = Ed25519PublicKey.from_public_bytes(pub)
            vk.verify(sig, data)
            return True, "ok"
        elif _NACL_OK:
            vk = nacl.signing.VerifyKey(pub)
            vk.verify(data, sig)
            return True, "ok"
        return False, "no_backend"
    except Exception as e:
        return False, f"verify_error:{type(e).__name__}"
