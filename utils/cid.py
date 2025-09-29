from hashlib import sha256
from pathlib import Path


def file_cid(path: str) -> str:
    """Compute a simple CID as SHA-256 hex of the file contents."""
    h = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
