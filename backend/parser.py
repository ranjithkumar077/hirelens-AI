from pathlib import Path

from pypdf import PdfReader
from docx import Document

from backend.config import ALLOWED_EXTENSIONS, MAX_FILE_BYTES, MAX_TEXT_CHARS


class ParseError(ValueError):
    pass


def _normalize(text: str) -> str:
    cleaned = " ".join((text or "").replace("\x00", " ").split())
    if len(cleaned) > MAX_TEXT_CHARS:
        cleaned = cleaned[:MAX_TEXT_CHARS] + "\n[truncated]"
    return cleaned


def extract_text_from_pdf(path: str | Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return _normalize("\n".join(pages))


def extract_text_from_docx(path: str | Path) -> str:
    doc = Document(str(path))
    return _normalize("\n".join(p.text for p in doc.paragraphs))


def extract_text_from_txt(path: str | Path) -> str:
    data = Path(path).read_bytes()
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return _normalize(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    return _normalize(data.decode("utf-8", errors="ignore"))


def extract_text(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise ParseError("File not found.")
    if file_path.stat().st_size == 0:
        raise ParseError("Empty file.")
    if file_path.stat().st_size > MAX_FILE_BYTES:
        raise ParseError(f"File is too large. Max {MAX_FILE_BYTES // (1024 * 1024)} MB.")

    suffix = file_path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ParseError("Unsupported file type. Use PDF, DOCX, or TXT.")

    if suffix == ".pdf":
        text = extract_text_from_pdf(file_path)
    elif suffix == ".docx":
        text = extract_text_from_docx(file_path)
    else:
        text = extract_text_from_txt(file_path)

    if not text or len(text.strip()) < 20:
        raise ParseError("Could not extract enough text from this file.")
    return text


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ParseError("Unsupported file type. Use PDF, DOCX, or TXT.")
    if not data:
        raise ParseError("Empty file.")
    if len(data) > MAX_FILE_BYTES:
        raise ParseError(f"File is too large. Max {MAX_FILE_BYTES // (1024 * 1024)} MB.")

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return extract_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
