#!/usr/bin/env python3
"""Patch nginx vhost for ki-ana.at.

- Finds the server { } block whose server_name contains "ki-ana.at".
- Removes existing location blocks for chat/app/ops endpoints to avoid duplicates.
- Inserts the consolidated location blocks before the end of that server block.
- Creates a timestamped backup (optional).

This is a pragmatic parser (brace-counting) intended for typical nginx site files.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import shutil
import sys
from typing import Iterable, List, Optional, Tuple


TARGET_SERVER_NAME = "ki-ana.at"


def _strip_comment(line: str) -> str:
    # Nginx comments start with #. We keep it simple and treat the first # as comment start.
    # This is good enough for typical site files.
    return line.split("#", 1)[0]


def _brace_delta(line: str) -> int:
    s = _strip_comment(line)
    return s.count("{") - s.count("}")


def _parse_location_header(stripped_no_comment: str) -> Optional[Tuple[Optional[str], str]]:
    # Returns (modifier, uri) where modifier in {"=", "^~", "~", "~*"} or None.
    if not stripped_no_comment.startswith("location"):
        return None

    # Normalize spacing and remove trailing '{' and ';' for token parsing.
    head = stripped_no_comment
    # cut at first '{' if present
    if "{" in head:
        head = head.split("{", 1)[0].strip()

    tokens = head.split()
    if len(tokens) < 2:
        return None

    if tokens[0] != "location":
        return None

    modifiers = {"=", "^~", "~", "~*"}
    if len(tokens) >= 3 and tokens[1] in modifiers:
        return tokens[1], tokens[2]

    # No modifier: next token is URI/pattern
    return None, tokens[1]


def _is_target_location(mod: Optional[str], uri: str) -> bool:
    targets = {
        ("=", "/health"),
        ("=", "/login"),
        ("=", "/chat"),
        ("=", "/papa"),
        ("=", "/settings"),
        ("=", "/admin"),
        ("^~", "/admin"),
        ("^~", "/admin/"),
        # Optional single public entrypoint
        ("=", "/"),
        # Dedicated SSE endpoint (must disable buffering)
        ("=", "/api/chat/stream"),
        ("^~", "/app/"),
        ("^~", "/_next/"),
        ("=", "/static/chat.html"),
        ("^~", "/ops/grafana/"),
        ("^~", "/ops/prometheus/"),
        ("=", "/grafana/"),
        ("=", "/prometheus/"),
        # Classic tools shortcuts (static HTML)
        ("=", "/dashboard"),
        ("=", "/adressbuch"),
        ("=", "/addressbook"),
        ("=", "/blockviewer"),
        ("=", "/timeflow"),
    }
    return (mod, uri) in targets


def _find_server_blocks(lines: List[str]) -> List[Tuple[int, int]]:
    blocks: List[Tuple[int, int]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = _strip_comment(line).strip()

        # Handle "server {" and the two-line variant "server" then "{".
        is_server_start = False
        if re.match(r"^server\s*\{\s*$", stripped):
            is_server_start = True
        elif stripped == "server" and i + 1 < len(lines) and _strip_comment(lines[i + 1]).strip().startswith("{"):
            is_server_start = True

        if not is_server_start:
            i += 1
            continue

        start = i
        depth = 0
        # server start may have "{" on same line or next line
        j = i
        while j < len(lines):
            depth += _brace_delta(lines[j])
            if depth == 0 and j > start:
                blocks.append((start, j))
                i = j + 1
                break
            j += 1
        else:
            # Unbalanced braces
            break

    return blocks


def _server_block_has_name(block_lines: Iterable[str], name: str) -> bool:
    for line in block_lines:
        stripped = _strip_comment(line).strip()
        m = re.match(r"^server_name\s+([^;]+);\s*$", stripped)
        if not m:
            continue
        names = m.group(1).split()
        if name in names:
            return True
    return False


def _detect_location_indent(block_lines: Iterable[str], fallback: str) -> str:
    for line in block_lines:
        if re.match(r"^\s*location\b", _strip_comment(line)):
            return re.match(r"^(\s*)", line).group(1)  # type: ignore[union-attr]
    return fallback


INSERT_BLOCK = """# --- Chat: konsolidiert auf Next UI ---
location = /health {
    proxy_pass http://127.0.0.1:28000/health;
    proxy_set_header Host $host;
    # curl -I uses HEAD; force GET upstream so /health is 200 for HEAD too
    proxy_method GET;
}

# --- Public login (served by Next) ---
location = /login {
    proxy_pass http://127.0.0.1:23000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

location = / {
    return 302 /app/chat;
}

location = /chat {
    return 302 /app/chat;
}

# --- App entrypoints: immer unter /app/* ---
location = /papa {
    return 302 /app/papa;
}

location = /settings {
    return 302 /app/settings;
}

location = /admin {
    return 302 /app/admin/users;
}

location ^~ /admin/ {
    return 302 /app/admin/users;
}

# --- SSE: Chat Stream (no buffering) ---
location = /api/chat/stream {
    proxy_pass http://127.0.0.1:28000;

    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    proxy_buffering off;
    proxy_cache off;
    gzip off;
    add_header X-Accel-Buffering no;

    proxy_read_timeout 3600;
    proxy_send_timeout 3600;
}

location ^~ /app/ {
    # NOTE: trailing slash strips the /app/ prefix so /app/chat -> upstream /chat
    proxy_pass http://127.0.0.1:23000/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# Next.js assets are rooted at /_next/*
location ^~ /_next/ {
    proxy_pass http://127.0.0.1:23000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# --- Legacy Chat: immer auf /app/chat ---
location = /static/chat.html {
    return 302 /app/chat;
}

# --- Ops: Grafana (BasicAuth) ---
location ^~ /ops/grafana/ {
    auth_basic "Ops";
    auth_basic_user_file /etc/nginx/.htpasswd-ops;

    proxy_pass http://127.0.0.1:23001/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# --- Ops: Prometheus (BasicAuth) ---
location ^~ /ops/prometheus/ {
    auth_basic "Ops";
    auth_basic_user_file /etc/nginx/.htpasswd-ops;

    proxy_pass http://127.0.0.1:29090/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# Optional shortcuts
location = /grafana/ { return 302 /ops/grafana/; }
location = /prometheus/ { return 302 /ops/prometheus/; }

# --- Classic Tools shortcuts (static UI) ---
location = /dashboard   { return 302 /static/dashboard.html; }
location = /adressbuch  { return 302 /static/addressbook.html; }
location = /addressbook { return 302 /static/addressbook.html; }
location = /blockviewer { return 302 /static/block_viewer.html; }
location = /timeflow    { return 302 /static/timeflow.html; }
"""


def _remove_target_locations(block_lines: List[str]) -> List[str]:
    out: List[str] = []
    i = 0

    while i < len(block_lines):
        line = block_lines[i]
        stripped = _strip_comment(line).strip()

        if not stripped.startswith("location"):
            out.append(line)
            i += 1
            continue

        parsed = _parse_location_header(stripped)
        if not parsed:
            out.append(line)
            i += 1
            continue

        mod, uri = parsed
        if not _is_target_location(mod, uri):
            out.append(line)
            i += 1
            continue

        # Skip this location block (brace balanced).
        depth = 0
        j = i
        while j < len(block_lines):
            depth += _brace_delta(block_lines[j])
            # location can be single-line with { ... }
            if depth <= 0 and j > i:
                j += 1
                break
            # if header line has no '{' (unlikely), still skip until we see a '{' and return to 0
            if depth == 0 and j == i and "{" not in _strip_comment(block_lines[j]):
                pass
            j += 1
        i = j

    return out


def patch_file(path: str, *, backup: bool, dry_run: bool) -> int:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    blocks = _find_server_blocks(lines)
    if not blocks:
        print(f"ERROR: No server blocks found in {path}", file=sys.stderr)
        return 2

    target_blocks: List[Tuple[int, int]] = []
    for start, end in blocks:
        if _server_block_has_name(lines[start : end + 1], TARGET_SERVER_NAME):
            target_blocks.append((start, end))

    if not target_blocks:
        print(
            f"ERROR: No server block with server_name containing {TARGET_SERVER_NAME} found in {path}",
            file=sys.stderr,
        )
        return 3

    def patch_server_block(server_lines: List[str], server_start_line: str) -> List[str]:
        server_indent = re.match(r"^(\s*)", server_start_line).group(1)  # type: ignore[union-attr]
        location_indent = _detect_location_indent(server_lines, server_indent + "    ")

        cleaned_server_lines = _remove_target_locations(server_lines)
        if not cleaned_server_lines:
            raise RuntimeError("Unexpected empty server block after cleanup")

        # Identify the final closing brace line (from bottom upwards).
        close_idx = None
        for idx in range(len(cleaned_server_lines) - 1, -1, -1):
            if "}" in _strip_comment(cleaned_server_lines[idx]) and idx > 0:
                close_idx = idx
                break
        if close_idx is None:
            raise RuntimeError("Could not find server closing brace")

        insert_lines = [(location_indent + l if l else l) for l in INSERT_BLOCK.splitlines(True)]

        before = cleaned_server_lines[:close_idx]
        after = cleaned_server_lines[close_idx:]
        if before and before[-1].strip() != "":
            before.append("\n")

        if insert_lines and not insert_lines[-1].endswith("\n"):
            insert_lines[-1] += "\n"

        new_server_lines = before + insert_lines
        if new_server_lines and new_server_lines[-1].strip() != "":
            new_server_lines.append("\n")
        new_server_lines += after
        return new_server_lines

    new_lines = list(lines)

    # Apply replacements bottom-up so indices remain valid.
    for start, end in sorted(target_blocks, key=lambda t: t[0], reverse=True):
        server_lines = new_lines[start : end + 1]
        try:
            patched = patch_server_block(server_lines, new_lines[start])
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 4
        new_lines[start : end + 1] = patched

    if new_lines == lines:
        print("No changes needed (already patched).")
        return 0

    if dry_run:
        print("Patched content computed (dry-run). No file written.")
        return 0

    if backup:
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = f"{path}.bak-{ts}"
        shutil.copy2(path, backup_path)
        print(f"Backup written: {backup_path}")

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.replace(tmp_path, path)

    print(f"Patched: {path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="/etc/nginx/sites-available/ki-ana.at")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    return patch_file(args.file, backup=not args.no_backup, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
