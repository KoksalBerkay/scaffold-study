"""Materials folder: scan, classify, extract text per page, search, render pages."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pymupdf as fitz

from .config import WORKSPACE

SUPPORTED = {".pdf", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PAGES = 400

KIND_RULES = [
    ("solution", r"sol(ution|uzion|uz)?s?\b|solved|answers?|correct(ion|ed)|svolt|risolt"),
    ("exam", r"exam|esame|appello|compito|midterm|final|quiz|poliquiz|test\b|prova|past[ _-]?paper"),
    ("slides", r"slide|lecture|lezione|lesson|chapter|capitolo|\bch\d"),
    ("exercises", r"exercis|esercit|sheet|homework|hw\d|problem|lab\b|lab\d|tutorial|practice"),
    ("notes", r"notes|appunti|summary|riassunt|cheat"),
]

DATE_PATTERNS = [
    (r"(20\d\d)[-_.](\d\d)[-_.](\d\d)", lambda m: (m[1], m[2], m[3])),
    (r"(?<!\d)(20\d\d)(\d\d)(\d\d)(?!\d)", lambda m: (m[1], m[2], m[3])),
    (r"(?<!\d)(\d\d)[-_.](\d\d)[-_.](20\d\d)", lambda m: (m[3], m[2], m[1])),
]

QUESTION_RE = re.compile(
    r"^\s*(?:Q(?:uestion)?|Exercise|Ex\.?|Esercizio|Domanda|Problem|Problema|Task|R)\s*\.?\s*(\d{1,2})\b"
    r"|^\s*(\d{1,2})[.)]\s+[A-Z]", re.I | re.M)


def guess_kind(rel: str) -> str:
    low = rel.lower()
    for kind, pat in KIND_RULES:
        if re.search(pat, low):
            return kind
    if re.search(r"(?<!\d)20\d\d", low) and low.endswith(".pdf"):
        return "exam"
    return "other"


def guess_date(text: str) -> str | None:
    for pat, fn in DATE_PATTERNS:
        m = re.search(pat, text)
        if m:
            y, mo, d = fn(m)
            if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31:
                return f"{y}-{mo}-{d}"
    return None


def _cache_file(path: Path) -> Path:
    st = path.stat()
    h = hashlib.sha1(f"{path}|{st.st_mtime}|{st.st_size}".encode()).hexdigest()[:16]
    return WORKSPACE / "index" / "pages" / f"{h}.json"


def extract_pages(path: Path) -> list[str]:
    """Text per page (cached). Images return [] (they are viewed, not read)."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return []
    cf = _cache_file(path)
    if cf.exists():
        try:
            return json.loads(cf.read_text())
        except Exception:
            pass
    if ext == ".pdf":
        try:
            with fitz.open(path) as doc:
                pages = [doc[i].get_text("text") for i in range(min(len(doc), MAX_PAGES))]
        except Exception:
            pages = []
    else:
        text = path.read_text(errors="replace")
        chunks = [text[i:i + 3000] for i in range(0, len(text), 3000)] or [""]
        pages = chunks[:MAX_PAGES]
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(pages))
    return pages


def page_count(path: Path) -> int:
    if path.suffix.lower() == ".pdf":
        try:
            with fitz.open(path) as doc:
                return len(doc)
        except Exception:
            return 0
    return 1


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        if p.is_file() and p.suffix.lower() in SUPPORTED:
            yield p


def scan(root: Path) -> list[dict]:
    """Courses = top-level subfolders. Files directly in root go to 'General'."""
    courses: dict[str, list[dict]] = {}
    for p in iter_files(root):
        rel = p.relative_to(root)
        course = rel.parts[0] if len(rel.parts) > 1 else "General"
        pages = extract_pages(p)
        inner = str(Path(*rel.parts[1:])) if len(rel.parts) > 1 else str(rel)
        kind = guess_kind(inner)
        first = " ".join(pages[0].split())[:300] if pages else ""
        questions = len({m.group(1) or m.group(2) for t in pages for m in QUESTION_RE.finditer(t)}) if kind == "exam" else 0
        courses.setdefault(course, []).append({
            "path": str(p), "rel": str(rel), "name": p.name, "kind": kind,
            "pages": len(pages) if pages else page_count(p),
            "date": guess_date(p.name) or guess_date(first),
            "questions": questions or None,
            "link": p.as_uri(),
        })
    out = []
    for name, files in sorted(courses.items()):
        counts: dict[str, int] = {}
        for f in files:
            counts[f["kind"]] = counts.get(f["kind"], 0) + 1
        out.append({"name": name, "files": files, "counts": counts})
    return out


def inventory_text(root: Path, courses: list[dict], include: set[str] | None = None,
                   budget: int = 150_000) -> str:
    """Compact text inventory for the Planner."""
    lines = [f"Material root: {root}"]
    chosen = [c for c in courses if not include or c["name"] in include]
    per_course = max(4000, budget // max(1, len(chosen)))
    for c in chosen:
        block = [f"\n## Course folder: {c['name']} ({len(c['files'])} files)"]
        files = sorted(c["files"], key=lambda f: (f["kind"] != "exam", f["kind"], f["date"] or "0", f["rel"]),
                       reverse=False)
        # exams newest first
        exams = sorted([f for f in files if f["kind"] == "exam"], key=lambda f: f["date"] or "0", reverse=True)
        files = exams + [f for f in files if f["kind"] != "exam"]
        for f in files:
            meta = [f"type: {f['kind']}", f"pages: {f['pages']}"]
            if f["date"]:
                meta.append(f"date: {f['date']}")
            if f["questions"]:
                meta.append(f"numbered items detected: ~{f['questions']}")
            block.append(f"- {f['rel']} | " + " | ".join(meta) + f" | link: {f['link']}")
            pages = extract_pages(Path(f["path"]))
            n_preview = 8 if f["kind"] in ("exam", "solution", "exercises") else 1
            for i, t in enumerate(pages[:n_preview]):
                snippet = " ".join(t.split())[:260 if f["kind"] == "exam" else 160]
                if snippet:
                    block.append(f"    p{i + 1}: {snippet}")
        text = "\n".join(block)
        if len(text) > per_course:
            text = text[:per_course] + "\n    … (inventory truncated for this course)"
        lines.append(text)
    return "\n".join(lines)


# ---------- search + pages for the tutor ----------

_WORD = re.compile(r"[\wÀ-ɏ]{3,}")


def search(root: Path, query: str, k: int = 5) -> list[dict]:
    terms = {w.lower() for w in _WORD.findall(query)}
    if not terms:
        return []
    hits = []
    for p in iter_files(root):
        for i, t in enumerate(extract_pages(p)):
            low = t.lower()
            score = sum(low.count(w) for w in terms) + 3 * sum(1 for w in terms if w in p.name.lower())
            if score:
                hits.append({"file": str(p.relative_to(root)), "page": i + 1, "score": score,
                             "text": " ".join(t.split())[:1500]})
    hits.sort(key=lambda h: -h["score"])
    return hits[:k]


def safe_path(root: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute() or rel_or_abs.startswith("file://"):
        if rel_or_abs.startswith("file://"):
            from urllib.parse import unquote, urlparse
            p = Path(unquote(urlparse(rel_or_abs).path))
    else:
        p = root / p
    p = p.resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise ValueError("Path outside the materials folder")
    return p


def read_pages(path: Path, pages: str | None, max_chars: int = 12000) -> str:
    all_pages = extract_pages(path)
    idx = list(range(len(all_pages)))
    if pages:
        idx = []
        for part in str(pages).split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                idx += list(range(int(a) - 1, int(b)))
            elif part.strip():
                idx.append(int(part) - 1)
    out = []
    for i in idx:
        if 0 <= i < len(all_pages):
            out.append(f"[page {i + 1}]\n{all_pages[i].strip()}")
    return "\n\n".join(out)[:max_chars]


def render_page(path: Path, page: int, zoom: float = 2.0) -> Path:
    if path.suffix.lower() in IMAGE_EXT:
        return path
    h = hashlib.sha1(f"{path}|{path.stat().st_mtime}|{page}|{zoom}".encode()).hexdigest()[:16]
    out = WORKSPACE / "cache" / "pages" / f"{h}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        with fitz.open(path) as doc:
            pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pix.save(out)
    return out
