from __future__ import annotations
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time, hashlib, os
from sqlalchemy import text as sql_text

from ...deps import get_current_user_required, require_role
from ...db import SessionLocal
from ...models import KnowledgeBlock

try:
    from ..admin.router import write_audit  # type: ignore
except Exception:
    def write_audit(*args, **kwargs):  # type: ignore
        return None

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KBCreate(BaseModel):
    source: str = ""
    type: str = "text"
    tags: List[str] | str | None = None
    content: str
    ts: Optional[int] = None


def _norm_tags(tags: List[str] | str | None) -> str:
    if tags is None:
        return ""
    if isinstance(tags, str):
        parts = [t.strip().lower() for t in tags.split(",") if t.strip()]
    else:
        parts = [str(t).strip().lower() for t in tags if str(t).strip()]
    return ",".join(sorted(set(parts)))


def _fts_enabled() -> bool:
    try:
        return (os.getenv("KI_KNOWLEDGE_USE_FTS", "0").strip() in {"1", "true", "True"})
    except Exception:
        return False


def _ensure_fts(db) -> None:
    if not _fts_enabled():
        return
    try:
        db.execute(sql_text(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_blocks_fts
            USING fts5(content, source, tags, content='knowledge_blocks', content_rowid='id');

            CREATE TRIGGER IF NOT EXISTS kb_ai AFTER INSERT ON knowledge_blocks BEGIN
              INSERT INTO knowledge_blocks_fts(rowid, content, source, tags) VALUES (new.id, new.content, new.source, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS kb_ad AFTER DELETE ON knowledge_blocks BEGIN
              INSERT INTO knowledge_blocks_fts(knowledge_blocks_fts, rowid, content, source, tags) VALUES('delete', old.id, old.content, old.source, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS kb_au AFTER UPDATE ON knowledge_blocks BEGIN
              INSERT INTO knowledge_blocks_fts(knowledge_blocks_fts, rowid, content, source, tags) VALUES('delete', old.id, old.content, old.source, old.tags);
              INSERT INTO knowledge_blocks_fts(rowid, content, source, tags) VALUES (new.id, new.content, new.source, new.tags);
            END;
            """
        ))
        db.commit()
    except Exception:
        # best-effort; fallback will still work
        pass


def _fts_query_from(q: str) -> str:
    """Very small query sugar → FTS5 expression.
    Supports:
      - phrases in quotes: "foo bar"
      - column scoping: content:foo, tags:bar, source:baz
      - OR/AND (uppercase) tokens
    Anything unscoped will search content.
    """
    import shlex
    try:
        parts = shlex.split(q)
    except Exception:
        parts = q.split()
    out: list[str] = []
    for t in parts:
        if t in {"OR", "AND", "NOT"}:
            out.append(t)
            continue
        col = None
        val = t
        if ":" in t:
            pfx, rest = t.split(":", 1)
            if pfx in {"content", "tags", "source"} and rest:
                col = pfx
                val = rest
        # Quote value if contains spaces or special
        if any(c.isspace() for c in val) or any(c in val for c in {'"', "'", "*"}):
            val = f'"{val.replace("\"","\"\"")}"'
        if col:
            out.append(f"{col}:{val}")
        else:
            out.append(f"content:{val}")
    return " ".join(out)


@router.post("")
def kb_create(body: KBCreate, user = Depends(get_current_user_required)):
    # Allow creators and trusted system roles (admin/worker) to ingest knowledge
    require_role(user, {"creator", "admin", "worker"})
    now = int(time.time())
    ts = int(body.ts or now)
    tags_csv = _norm_tags(body.tags)
    h = hashlib.sha256((body.source + "\n" + body.type + "\n" + tags_csv + "\n" + body.content).encode("utf-8")).hexdigest()
    with SessionLocal() as db:
        _ensure_fts(db)
        # Upsert by hash
        row = db.query(KnowledgeBlock).filter(KnowledgeBlock.hash == h).first()
        if row:
            row.ts = ts
            row.source = body.source[:120]
            row.type = body.type[:60]
            row.tags = tags_csv[:400]
            row.content = body.content
            row.updated_at = now
            kb_id = row.id
        else:
            kb = KnowledgeBlock(
                ts=ts,
                source=body.source[:120],
                type=body.type[:60],
                tags=tags_csv[:400],
                content=body.content,
                hash=h,
                created_at=now,
                updated_at=now,
            )
            db.add(kb)
            db.flush()
            kb_id = int(kb.id)
        db.commit()
        try:
            write_audit("knowledge_add", actor_id=int(user.get("id") or 0), target_type="knowledge", target_id=int(kb_id or 0), meta={"source": body.source, "type": body.type, "tags": tags_csv})
        except Exception:
            pass
    return {"ok": True, "id": kb_id, "hash": h}


@router.get("/search")
def kb_search(
    q: Optional[str] = Query(default=None, description="free text query"),
    tags: Optional[str] = Query(default=None, description="comma-separated tags"),
    source: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    user = Depends(get_current_user_required),
):
    # Allow all authenticated roles to search
    limit = max(1, min(int(limit or 50), 500))
    tags_csv = _norm_tags(tags)
    with SessionLocal() as db:
        items: List[Dict[str, Any]] = []
        use_fts = bool(q) and _fts_enabled()
        if use_fts:
            _ensure_fts(db)
            # FTS5 search with snippet highlighting
            # Note: snippet args: (table, column, start_mark, end_mark, ellipsis, tokens)
            base_sql = (
                "SELECT kb.id, kb.ts, kb.source, kb.type, kb.tags, kb.content, kb.hash, kb.created_at, kb.updated_at, "
                "snippet(knowledge_blocks_fts, 0, '<mark>', '</mark>', '…', 10) AS snip_content, "
                "snippet(knowledge_blocks_fts, 1, '<mark>', '</mark>', '…', 10) AS snip_source, "
                "snippet(knowledge_blocks_fts, 2, '<mark>', '</mark>', '…', 10) AS snip_tags "
                "FROM knowledge_blocks_fts f JOIN knowledge_blocks kb ON kb.id = f.rowid "
                "WHERE f MATCH :q"
            )
            match_expr = _fts_query_from(q)
            params: Dict[str, Any] = {"q": match_expr}
            # Apply additional filters via outer WHERE conditions
            if tags_csv:
                for i, t in enumerate([t for t in tags_csv.split(',') if t]):
                    base_sql += f" AND kb.tags LIKE :tg{i}"
                    params[f"tg{i}"] = f"%{t}%"
            if source:
                base_sql += " AND kb.source = :src"
                params["src"] = source
            if type:
                base_sql += " AND kb.type = :typ"
                params["typ"] = type
            base_sql += " ORDER BY kb.ts DESC LIMIT :lim"
            params["lim"] = int(limit)
            try:
                res = db.execute(sql_text(base_sql), params).fetchall()
                for r in res:
                    items.append({
                        "id": int(r[0]),
                        "ts": int(r[1] or 0),
                        "source": r[2] or "",
                        "type": r[3] or "",
                        "tags": r[4] or "",
                        "content": r[5] or "",
                        "hash": r[6] or "",
                        "created_at": int(r[7] or 0),
                        "updated_at": int(r[8] or 0),
                        "snippet": r[9] or "",
                        "snippet_source": r[10] or "",
                        "snippet_tags": r[11] or "",
                    })
            except Exception:
                # Fallback to LIKE if FTS failed at runtime
                use_fts = False
        if not use_fts:
            qry = db.query(KnowledgeBlock)
            if q:
                like = f"%{q}%"
                qry = qry.filter(KnowledgeBlock.content.like(like))
            if tags_csv:
                for t in tags_csv.split(","):
                    qry = qry.filter(KnowledgeBlock.tags.like(f"%{t}%"))
            if source:
                qry = qry.filter(KnowledgeBlock.source == source)
            if type:
                qry = qry.filter(KnowledgeBlock.type == type)
            rows = qry.order_by(KnowledgeBlock.ts.desc()).limit(limit).all()
            for r in rows:
                items.append({
                    "id": int(r.id),
                    "ts": int(r.ts or 0),
                    "source": r.source or "",
                    "type": r.type or "",
                    "tags": (r.tags or ""),
                    "content": r.content or "",
                    "hash": r.hash or "",
                    "created_at": int(r.created_at or 0),
                    "updated_at": int(r.updated_at or 0),
                })
        try:
            write_audit("knowledge_search", actor_id=int(user.get("id") or 0), target_type="knowledge", target_id=0, meta={"q": q or "", "tags": tags_csv, "source": source or "", "type": type or "", "limit": limit, "hits": len(items)})
        except Exception:
            pass
        return {"ok": True, "items": items}


@router.get("/stats")
def kb_stats(limit: int = 5, user = Depends(get_current_user_required)):
    # Only creator/admin can view global stats
    require_role(user, {"creator", "admin"})
    now = int(time.time())
    since_24h = now - 24*3600
    limit = max(1, min(int(limit or 5), 20))
    with SessionLocal() as db:
        total = int(db.query(KnowledgeBlock).count() or 0)
        last_24h = int(db.query(KnowledgeBlock).filter(KnowledgeBlock.ts >= since_24h).count() or 0)
        # Collect tags & sources distribution (sample all; small-scale acceptable)
        rows = db.query(KnowledgeBlock.source, KnowledgeBlock.tags).all()
        tag_counts: Dict[str, int] = {}
        src_counts: Dict[str, int] = {}
        for src, tags in rows:
            s = (src or "").strip() or ""
            if s:
                src_counts[s] = src_counts.get(s, 0) + 1
            if tags:
                for t in str(tags).split(","):
                    tt = t.strip()
                    if not tt: continue
                    tag_counts[tt] = tag_counts.get(tt, 0) + 1
        top_tags = sorted(({"tag": k, "count": v} for k, v in tag_counts.items()), key=lambda x: (-x["count"], x["tag"]))[:limit]
        top_sources = sorted(({"source": k, "count": v} for k, v in src_counts.items()), key=lambda x: (-x["count"], x["source"]))[:limit]
        return {"ok": True, "total": total, "last_24h": last_24h, "top_tags": top_tags, "top_sources": top_sources}
