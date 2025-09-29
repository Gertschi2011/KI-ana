import os
import json
import base64
from typing import Dict, Any
from nacl import signing
from nacl.encoding import Base64Encoder

# Load/generate server signing key. Prefer deterministic seed via env.
_SERVER_SEED_B64 = os.getenv("COORD_SEED_B64")  # must be base64-encoded 32 bytes
if _SERVER_SEED_B64:
    _seed = base64.b64decode(_SERVER_SEED_B64)
    _signer = signing.SigningKey(_seed)
else:
    # Ephemeral for dev; DO NOT use in production.
    _signer = signing.SigningKey.generate()

_verify_key = _signer.verify_key
SERVER_PUBKEY_B64: str = _verify_key.encode(encoder=Base64Encoder).decode()


def sign_obj(obj: Dict[str, Any]) -> str:
    msg = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()
    sig = _signer.sign(msg).signature
    return base64.b64encode(sig).decode()
