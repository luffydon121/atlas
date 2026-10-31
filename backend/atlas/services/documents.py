"""Local document library with SQLite FTS5 search. Document text is always treated as data."""

import hashlib
import io
import re

import httpx
import numpy as np
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy import select, text

from atlas.config import get_settings
from atlas.db import Document, DocVector, session_scope

ALLOWED = {".txt", ".md", ".csv", ".pdf"}
CHUNK_WORDS = 180
INJECTION = re.compile(
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+|your\s+)*(previous|prior|above|earlier|system)?\s*(instructions?|prompts?|rules?)"
    r"|you are now|new instructions|system prompt|<\s*/?\s*(system|assistant)\s*>", re.I)


class DocumentError(ValueError):
    pass


def neutralise(value: str) -> str:
    """Marks instruction-like phrases so they read as quoted data. The model never gets tools anyway."""
    return INJECTION.sub(lambda m: f"[flagged text: {m.group(0)}]", value)


def extract_pages(filename: str, raw: bytes) -> list[str]:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED:
        raise DocumentError(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED))}")
    if suffix == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise DocumentError("That file is not a valid PDF")
        try:
            return [p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages]
        except (PyPdfError, ValueError, KeyError) as exc:
            raise DocumentError(f"Could not read PDF: {exc}") from exc
    if b"\x00" in raw[:8192]:
        raise DocumentError("That file looks binary, not text")
    try:
        return [raw.decode("utf-8")]
    except UnicodeDecodeError as exc:
        raise DocumentError("File is not UTF-8 text") from exc


def chunk(page: str, size: int = CHUNK_WORDS) -> list[str]:
    words = page.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size - 30)] if words else []


def ingest(filename: str, raw: bytes) -> dict:
    safe_name = re.sub(r"[^\w.\- ]", "_", filename.rsplit("/", 1)[-1])[:200]
    pages = extract_pages(safe_name, raw)
    digest = hashlib.sha256(raw).hexdigest()
    with session_scope() as db:
        if existing := db.scalar(select(Document).where(Document.sha256 == digest)):
            return {"id": existing.id, "filename": existing.filename, "chunks": existing.chunks, "duplicate": True}
        doc = Document(filename=safe_name, sha256=digest, pages=len(pages))
        db.add(doc)
        db.flush()
        count = 0
        for number, page in enumerate(pages, 1):
            for body in chunk(page):
                db.execute(text("INSERT INTO doc_chunks(document_id, page, body) VALUES (:d, :p, :b)"), {"d": doc.id, "p": number, "b": body})
                count += 1
        if not count:
            raise DocumentError("No extractable text. Scanned PDFs need OCR first.")
        doc.chunks = count
        return {"id": doc.id, "filename": safe_name, "pages": len(pages), "chunks": count, "duplicate": False}


def _fts_query(q: str) -> str:
    terms = [t for t in re.findall(r"\w{3,}", q.lower()) if t not in {"the", "and", "what", "which", "show", "for", "with", "that", "this", "are", "how", "why", "from"}]
    return " OR ".join(f'"{t}"' for t in terms[:12])


def search(q: str, limit: int = 5) -> list[dict]:
    match = _fts_query(q)
    if not match:
        return []
    with session_scope() as db:
        rows = db.execute(text("SELECT c.document_id, c.page, c.body, d.filename, d.uploaded_at, c.rowid FROM doc_chunks c JOIN documents d ON d.id = c.document_id "
                               "WHERE doc_chunks MATCH :m ORDER BY bm25(doc_chunks) LIMIT :l"), {"m": match, "l": limit}).all()
    return [{"document_id": r[0], "page": r[1], "text": r[2], "filename": r[3], "uploaded_at": str(r[4]), "rowid": r[5]} for r in rows]


def _embed_model() -> str:
    return get_settings().ollama_embed_model


async def embed(texts: list[str]) -> list[np.ndarray] | None:
    """Local embeddings through Ollama. Returns None when no model is set or it is not running."""
    model = _embed_model()
    if not model or not texts:
        return None
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            res = await client.post(f"{get_settings().ollama_url}/api/embed", json={"model": model, "input": texts})
            res.raise_for_status()
            return [np.array(v, dtype="float32") for v in res.json()["embeddings"]]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def index_vectors(doc_id: int) -> int:
    model = _embed_model()
    if not model:
        return 0
    with session_scope() as db:
        rows = db.execute(text("SELECT rowid, body FROM doc_chunks WHERE document_id = :d"), {"d": doc_id}).all()
    vectors = await embed([r[1] for r in rows])
    if vectors is None:
        return 0
    with session_scope() as db:
        for (rowid, _), vector in zip(rows, vectors, strict=True):
            db.merge(DocVector(chunk_id=rowid, model=model, vector=vector.tobytes()))
    return len(vectors)


def _chunk_row(rowid: int) -> dict | None:
    with session_scope() as db:
        r = db.execute(text("SELECT c.document_id, c.page, c.body, d.filename, d.uploaded_at FROM doc_chunks c JOIN documents d ON d.id = c.document_id WHERE c.rowid = :r"), {"r": rowid}).first()
    return {"document_id": r[0], "page": r[1], "text": r[2], "filename": r[3], "uploaded_at": str(r[4]), "rowid": rowid} if r else None


async def hybrid_search(q: str, limit: int = 5) -> list[dict]:
    """Reciprocal rank fusion of keyword and vector results. Falls back to keywords alone."""
    keyword = search(q, limit * 2)
    query = await embed([q])
    if query is None:
        return keyword[:limit]
    with session_scope() as db:
        stored = db.execute(select(DocVector.chunk_id, DocVector.vector).where(DocVector.model == _embed_model())).all()
    if not stored:
        return keyword[:limit]
    q_vec = query[0] / (np.linalg.norm(query[0]) or 1)
    scored = sorted(((float(np.dot(q_vec, v := np.frombuffer(blob, dtype="float32")) / (np.linalg.norm(v) or 1)), rowid) for rowid, blob in stored), reverse=True)[: limit * 2]
    ranks: dict[int, float] = {}
    for rank, row in enumerate(keyword):
        ranks[row["rowid"]] = ranks.get(row["rowid"], 0) + 1 / (60 + rank)
    for rank, (_score, rowid) in enumerate(scored):
        ranks[rowid] = ranks.get(rowid, 0) + 1 / (60 + rank)
    best = sorted(ranks, key=ranks.get, reverse=True)[:limit]
    return [r for rowid in best if (r := _chunk_row(rowid))]


def list_documents() -> list[dict]:
    with session_scope() as db:
        return [{"id": d.id, "filename": d.filename, "pages": d.pages, "chunks": d.chunks, "uploaded_at": d.uploaded_at.isoformat() + "Z"}
                for d in db.scalars(select(Document).order_by(Document.uploaded_at.desc()))]


def delete(doc_id: int) -> bool:
    with session_scope() as db:
        doc = db.get(Document, doc_id)
        if not doc:
            return False
        db.execute(text("DELETE FROM doc_vectors WHERE chunk_id IN (SELECT rowid FROM doc_chunks WHERE document_id = :d)"), {"d": doc_id})
        db.execute(text("DELETE FROM doc_chunks WHERE document_id = :d"), {"d": doc_id})
        db.delete(doc)
        return True
