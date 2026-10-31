"""Local document library with SQLite FTS5 search. Document text is always treated as data."""

import hashlib
import io
import re

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy import select, text

from atlas.db import Document, session_scope

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
        try:
            return [p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages]
        except (PyPdfError, ValueError, KeyError) as exc:
            raise DocumentError(f"Could not read PDF: {exc}") from exc
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
        rows = db.execute(text("SELECT c.document_id, c.page, c.body, d.filename, d.uploaded_at FROM doc_chunks c JOIN documents d ON d.id = c.document_id "
                               "WHERE doc_chunks MATCH :m ORDER BY bm25(doc_chunks) LIMIT :l"), {"m": match, "l": limit}).all()
    return [{"document_id": r[0], "page": r[1], "text": r[2], "filename": r[3], "uploaded_at": str(r[4])} for r in rows]


def list_documents() -> list[dict]:
    with session_scope() as db:
        return [{"id": d.id, "filename": d.filename, "pages": d.pages, "chunks": d.chunks, "uploaded_at": d.uploaded_at.isoformat() + "Z"}
                for d in db.scalars(select(Document).order_by(Document.uploaded_at.desc()))]


def delete(doc_id: int) -> bool:
    with session_scope() as db:
        doc = db.get(Document, doc_id)
        if not doc:
            return False
        db.execute(text("DELETE FROM doc_chunks WHERE document_id = :d"), {"d": doc_id})
        db.delete(doc)
        return True
