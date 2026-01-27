from __future__ import annotations

import json
import time
import os
from pathlib import Path
from typing import Any, Optional


def _safe_inc_metric(name: str, *, ok: bool | None = None, kind: str = "block") -> None:
    """Best-effort hook into the in-process metrics exporter.

    Avoids hard dependency/cycles; if metrics module isn't available, this is a no-op.
    """

    try:
        from netapi.modules.observability import metrics as _m  # type: ignore

        if name == "memory_block_write" and ok is not None:
            _m.inc_memory_block_write(ok=bool(ok), kind=kind)
        elif name == "memory_block_quarantine":
            _m.inc_memory_block_quarantine(kind=kind)
    except Exception:
        return


def _quarantine_dir_for(path: Path, *, kind: str = "block") -> Path:
    # Keep quarantine near the target tree for easy forensics.
    if kind == "block" and path.parent.name == "blocks":
        return path.parent / "_quarantine"
    return path.parent / "_quarantine"


def quarantine_file(path: Path, *, reason: str, kind: str = "block") -> Optional[Path]:
    """Move a problematic file to a quarantine folder (best-effort).

    Returns the quarantine path or None if move failed.
    """

    try:
        qdir = _quarantine_dir_for(path, kind=kind)
        qdir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        qp = qdir / f"{path.name}.quarantine.{ts}"
        try:
            os.replace(path, qp)
        except Exception:
            return None

        # Drop a tiny README once (best-effort) so later we remember why it exists.
        try:
            readme = qdir / "README.txt"
            if not readme.exists():
                atomic_write_text(
                    readme,
                    (
                        "Quarantine folder for suspicious/invalid memory files.\n"
                        "- 0 bytes or JSON validation failed\n"
                        "- files are moved here instead of silently being overwritten\n"
                        "- keep for forensics; 0-byte files cannot be recovered\n"
                    ),
                )
        except Exception:
            pass

        _safe_inc_metric("memory_block_quarantine", kind=kind)
        return qp
    except Exception:
        return None


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Atomically write text to `path`.

    Writes to a sibling temp file, flushes + fsyncs, then `os.replace`s.
    Best-effort directory fsync to reduce risk of 0-byte or missing files on crash.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")

    with open(tmp, "w", encoding=encoding) as f:
        f.write(text)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass

    os.replace(tmp, path)

    # Best-effort: fsync the directory entry as well.
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        pass


def atomic_write_json(
    path: Path,
    obj: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    sort_keys: bool = True,
    ensure_ascii: bool = False,
    min_bytes: int = 8,
    validate: bool = True,
    kind: str = "block",
) -> None:
    """Atomically write JSON to `path` with optional validation + quarantine.

    Validation is intentionally lightweight:
    - ensure produced JSON parses
    - ensure encoded size is >= `min_bytes`
    - after write, ensure file size is >= `min_bytes`
    """

    try:
        text = json.dumps(obj, ensure_ascii=ensure_ascii, indent=indent, sort_keys=sort_keys)
    except Exception as e:
        _safe_inc_metric("memory_block_write", ok=False, kind=kind)
        raise

    if validate:
        try:
            json.loads(text)
        except Exception:
            _safe_inc_metric("memory_block_write", ok=False, kind=kind)
            raise ValueError(f"atomic_write_json: invalid JSON for {path}")

        try:
            if len(text.encode(encoding)) < int(min_bytes):
                raise ValueError(f"atomic_write_json: too small (<{min_bytes} bytes) for {path}")
        except Exception:
            _safe_inc_metric("memory_block_write", ok=False, kind=kind)
            raise

    atomic_write_text(path, text, encoding=encoding)

    try:
        if validate and path.stat().st_size < int(min_bytes):
            quarantine_file(path, reason=f"size<{min_bytes}", kind=kind)
            _safe_inc_metric("memory_block_write", ok=False, kind=kind)
            raise ValueError(f"atomic_write_json: written file too small (<{min_bytes} bytes): {path}")
    except Exception:
        raise

    _safe_inc_metric("memory_block_write", ok=True, kind=kind)
