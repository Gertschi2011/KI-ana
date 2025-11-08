# netapi/modules/memory/router.py
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from ...deps import get_db, require_user
from ...deps import require_role
from ... import memory_store
from pathlib import Path
import logging
import json, time, os, sqlite3, csv, io

router = APIRouter()
logger = logging.getLogger(__name__)

# Keep addressbook.json (Papa‑Modus Wissens‑Index) in sync
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../netapi
MEM_INDEX_DIR = PROJECT_ROOT / "memory" / "index"
ADDRBOOK_PATH = MEM_INDEX_DIR / "addressbook.json"
MEM_BLOCKS_REL = "memory/long_term/blocks"

def _upsert_addressbook(topic: str, *, block_id: str, path: str, source: str = "") -> None:
    try:
        MEM_INDEX_DIR.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any]
        if ADDRBOOK_PATH.exists():
            try:
                data = json.loads(ADDRBOOK_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {"blocks": []}
        else:
            data = {"blocks": []}
        blocks = data.get("blocks") if isinstance(data, dict) else None
        if not isinstance(blocks, list):
            blocks = []
        # Normalize path to relative store path
        p = path
        if p and "/" not in p:
            p = f"{MEM_BLOCKS_REL}/{p}"
        # Merge by (topic, block_id)
        ts = int(time.time())
        updated = False
        for b in blocks:
            if b.get("topic") == topic and b.get("block_id") == block_id:
                if p: b["path"] = p
                if source: b["source"] = source
                b["timestamp"] = b.get("timestamp") or ts
                updated = True
                break
        if not updated:
            blocks.append({
                "topic": topic,
                "block_id": block_id,
                "path": p,
                "source": source or "",
                "timestamp": ts,
                "rating": 0,
            })
        ADDRBOOK_PATH.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        # best-effort only
        pass

class MemoryAddIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: Optional[List[str]] = None
    url: Optional[str] = None

class MemorySearchOut(BaseModel):
    title: str
    snippet: str
    score: float
    id: Optional[str] = None
    url: Optional[str] = None
    tags: Optional[List[str]] = None

@router.post("/add")
def add_memory(body: MemoryAddIn, request: Request, db=Depends(get_db)):
    # Schreibzugriff nur mit Login
    user = require_user(request, db)  # raises 401 wenn nicht eingeloggt
    try:
        mid = memory_store.add_block(
            title=body.title.strip(),
            content=body.content.strip(),
            tags=body.tags or [],
            url=body.url,
        )
        # Auto‑update addressbook (topic heuristic: prefer first tag, fallback to title)
        try:
            topic = (body.tags or [None])[0] or body.title
            path = f"{mid}.json"
            _upsert_addressbook(str(topic)[:120], block_id=str(mid), path=path, source=body.url or "")
        except Exception:
            pass
        return {"ok": True, "id": mid}
    except Exception as e:
        raise HTTPException(500, f"memory add failed: {e}")

class MemoryRateIn(BaseModel):
    id: str = Field(min_length=3)
    score: float = Field(ge=0.0, le=1.0)
    proof_url: Optional[str] = None
    comment: Optional[str] = None

@router.post("/rate")
def rate_memory(body: MemoryRateIn, request: Request, db=Depends(get_db)):
    user = require_user(request, db)
    # Only admin or papa may rate memory blocks
    require_role(user, {"admin", "papa"})
    try:
        res = memory_store.rate_block(body.id, body.score, proof_url=body.proof_url, reviewer=str(user.get("username") or user.get("id")), comment=body.comment)
        return {"ok": True, "rating": res}
    except Exception as e:
        raise HTTPException(500, f"memory rate failed: {e}")

class MemoryImportIn(BaseModel):
    blocks: List[MemoryAddIn] = Field(default_factory=list)

@router.post("/import")
def import_blocks(payload: MemoryImportIn, request: Request, db=Depends(get_db)):
    user = require_user(request, db)
    # Only admin or papa may import blocks in bulk
    require_role(user, {"admin", "papa"})
    ids: List[str] = []
    try:
        for b in payload.blocks:
            bid = memory_store.add_block(title=b.title, content=b.content, tags=b.tags or [], url=b.url)
            if isinstance(bid, str):
                ids.append(bid)
                try:
                    topic = (b.tags or [None])[0] or b.title
                    _upsert_addressbook(str(topic)[:120], block_id=str(bid), path=f"{bid}.json", source=b.url or "")
                except Exception:
                    pass
        return {"ok": True, "imported": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(500, f"memory import failed: {e}")

@router.get("/search")
def search_memory(q: str, limit: int = 10):
    if not q or not q.strip():
        raise HTTPException(400, "query 'q' required")
    try:
        results = memory_store.search_blocks(q.strip(), limit=limit)  # erwartet deine bestehende Funktion
        return {"ok": True, "results": results}
    except AttributeError:
        # Fallback, falls es nur eine simple get_all() gibt
        items = getattr(memory_store, "get_all_blocks", lambda: [])()
        # naive Filter
        ql = q.lower()
        hits = []
        for it in items:
            title = it.get("title","")
            content = it.get("content","")
            if ql in title.lower() or ql in content.lower():
                hits.append({
                    "title": title,
                    "snippet": (content[:180] + "…") if len(content) > 180 else content,
                    "score": 0.0,
                    "id": it.get("id"),
                    "url": it.get("url"),
                    "tags": it.get("tags"),
                })
        return {"ok": True, "results": hits[:limit]}
    except Exception as e:
        raise HTTPException(500, f"memory search failed: {e}")

# Minimal JSON blocks viewer (filesystem) for quick UI/debug
@router.get("/blocks")
def list_blocks_fs():
    try:
        root = Path(os.getenv("KI_ROOT", str(Path.home() / "ki_ana")))
        blk_dir = root / "memory" / "long_term" / "blocks"
        files = sorted(blk_dir.glob("*.json"))
        items = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append({
                "file": f.name,
                "id": data.get("id") or f.stem,
                "topic": data.get("topic") or data.get("title"),
                "source": data.get("source", ""),
                "timestamp": data.get("timestamp") or int(f.stat().st_mtime),
                "summary": (data.get("content") or data.get("text") or "")[:200],
                "tags": data.get("tags") or [],
            })
        return {"ok": True, "count": len(items), "items": items[:500]}
    except Exception as e:
        raise HTTPException(500, f"list blocks failed: {e}")

# -----------------------
# knowledge_blocks viewer API (SQLite-backed)
# -----------------------

def _db_path_from_env() -> str:
    # Use separate env variable for knowledge blocks SQLite DB
    knowledge_db = os.getenv("KNOWLEDGE_DB_PATH")
    if knowledge_db:
        return os.path.expanduser(knowledge_db)
    
    # Fallback: Check if DATABASE_URL is SQLite
    db_url = os.getenv("DATABASE_URL", "")
    try:
        if db_url.startswith("sqlite:///"):
            return os.path.expanduser(db_url[len("sqlite:///"):])
        if db_url.startswith("sqlite://"):
            return os.path.expanduser(db_url[len("sqlite://"):])
    except Exception:
        pass
    
    # Default: Use KI_ROOT if available
    ki_root = os.getenv("KI_ROOT", "/app")
    default_path = f"{ki_root}/memory/knowledge.db"
    return default_path


@router.get("/list")
def knowledge_list(q: Optional[str] = None, tag: Optional[str] = None, page: int = 1, limit: int = 50, sort: Optional[str] = None):
    try:
        page = max(1, int(page or 1)); limit = max(1, min(200, int(limit or 50)))
        db_path = _db_path_from_env()
        where = []
        params: List[Any] = []
        if q and q.strip():
            where.append("(LOWER(source) LIKE ? OR LOWER(content) LIKE ?)")
            needle = f"%{q.strip().lower()}%"; params.extend([needle, needle])
        if tag and tag.strip():
            where.append("(tags LIKE ?)")
            params.append(f"%{tag.strip()}%")
        sql_where = (" WHERE " + " AND ".join(where)) if where else ""
        total = 0
        rows: List[Dict[str, Any]] = []
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) AS c FROM knowledge_blocks{sql_where}", params)
            total = int(cur.fetchone()[0])
            offset = (page - 1) * limit
            order = "DESC"
            try:
                if isinstance(sort, str) and sort.lower() in ("asc", "desc"):
                    order = sort.upper()
            except Exception:
                order = "DESC"
            cur.execute(
                f"SELECT id, ts, source, type, tags, substr(content,1,400) AS preview, hash, created_at, updated_at FROM knowledge_blocks{sql_where} ORDER BY id {order} LIMIT ? OFFSET ?",
                params + [limit, offset]
            )
            for r in cur.fetchall():
                rows.append({
                    "id": f"BLK_{int(r['id'])}",
                    "row_id": int(r['id']),
                    "timestamp": int(r['ts'] or 0),
                    "source": r['source'] or '',
                    "type": r['type'] or '',
                    "tags": r['tags'] or '',
                    "preview": r['preview'] or '',
                    "hash": r['hash'] or '',
                    "created_at": int(r['created_at'] or 0),
                    "updated_at": int(r['updated_at'] or 0),
                })
        pages = max(1, (total + limit - 1) // limit)
        return {"ok": True, "items": rows, "total": total, "page": page, "pages": pages, "limit": limit}
    except Exception as e:
        raise HTTPException(500, f"knowledge list failed: {e}")


@router.get("/item/{row_id}")
def knowledge_item(row_id: int):
    try:
        db_path = _db_path_from_env()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge_blocks WHERE id = ? LIMIT 1", (row_id,))
            r = cur.fetchone()
            if not r:
                raise HTTPException(404, "not found")
            obj = {k: r[k] for k in r.keys()}
            obj["id"] = f"BLK_{int(r['id'])}"
            return {"ok": True, "item": obj}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"knowledge item failed: {e}")


@router.get("/export.csv")
def knowledge_export_csv(q: Optional[str] = None, tag: Optional[str] = None):
    try:
        db_path = _db_path_from_env()
        where = []
        params: List[Any] = []
        if q and q.strip():
            where.append("(LOWER(source) LIKE ? OR LOWER(content) LIKE ?)")
            needle = f"%{q.strip().lower()}%"; params.extend([needle, needle])
        if tag and tag.strip():
            where.append("(tags LIKE ?)")
            params.append(f"%{tag.strip()}%")
        sql_where = (" WHERE " + " AND ".join(where)) if where else ""
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["row_id","id","source","type","tags","ts","created_at","updated_at","hash","content"])
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM knowledge_blocks{sql_where} ORDER BY id DESC", params)
            for r in cur.fetchall():
                rid = int(r['id']); bid = f"BLK_{rid}"
                w.writerow([
                    rid,
                    bid,
                    r['source'] or '',
                    r['type'] or '',
                    r['tags'] or '',
                    int(r['ts'] or 0),
                    int(r['created_at'] or 0),
                    int(r['updated_at'] or 0),
                    r['hash'] or '',
                    (r['content'] or '').replace('\n',' ').replace('\r',' ')
                ])
        data = buf.getvalue().encode('utf-8')
        return Response(content=data, media_type='text/csv; charset=utf-8', headers={"Content-Disposition": "attachment; filename=knowledge_blocks.csv"})
    except Exception as e:
        raise HTTPException(500, f"knowledge export csv failed: {e}")


@router.get("/export.json")
def knowledge_export_json(request: Request, q: Optional[str] = None, tag: Optional[str] = None, db=Depends(get_db)):
    try:
        user = require_user(request, db)
        require_role(user, {"admin", "creator", "papa"})
        # Reuse list endpoint to get filtered items
        data = knowledge_list(q=q, tag=tag, page=1, limit=10000)
        return Response(content=json.dumps(data, ensure_ascii=False), media_type='application/json; charset=utf-8', headers={"Content-Disposition": "attachment; filename=knowledge_blocks.json"})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"knowledge export json failed: {e}")


@router.get("/export.minio")
def knowledge_export_minio(request: Request, q: Optional[str] = None, tag: Optional[str] = None, db=Depends(get_db)):
    """
    Export current filtered knowledge list as JSON to MinIO (S3-compatible).
    Requires authenticated user with role admin|creator|papa.
    Env:
      MINIO_ENDPOINT (host:port or URL)
      MINIO_ACCESS_KEY
      MINIO_SECRET_KEY
      MINIO_BUCKET (default: kiana-exports)
      MINIO_USE_SSL (optional: '1' for https)
    """
    try:
        user = require_user(request, db)
        require_role(user, {"admin", "creator", "papa"})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Unauthorized")

    try:
        # materialize filtered data
        data = knowledge_list(q=q, tag=tag, page=1, limit=10000)
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")

        # MinIO config
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000").strip()
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin").strip()
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin").strip()
        bucket = os.getenv("MINIO_BUCKET", "kiana-exports").strip()
        use_ssl = os.getenv("MINIO_USE_SSL", "0").strip() in {"1", "true", "True"}
        scheme = "https" if use_ssl or endpoint.startswith("https://") else "http"
        endpoint_url = endpoint if endpoint.startswith("http") else f"{scheme}://{endpoint}"

        # filename
        ts = int(time.time())
        base = (q or "export").strip()[:40] or "export"
        base = base.replace("/", "_").replace(" ", "_")
        key = f"knowledge/{base}_{ts}.json"

        # Upload via boto3 (S3 compatible)
        try:
            import boto3  # type: ignore
        except Exception:
            raise HTTPException(500, "boto3 not installed")

        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name="us-east-1",
            )
            s3.put_object(Bucket=bucket, Key=key, Body=payload, ContentType="application/json; charset=utf-8")
            return {"status": "ok", "object": f"s3://{bucket}/{key}"}
        except Exception as e:
            try:
                logger.exception("MinIO export failed: %s", e)
            except Exception:
                pass
            return Response(content=json.dumps({"status":"error","detail":str(e)}), media_type="application/json", status_code=500)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"knowledge export minio failed: {e}")
