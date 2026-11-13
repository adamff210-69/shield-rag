"""
Document Text Extraction and Sanitization Engine.

Supports extracting clean plain text from:
- Microsoft Word (.docx) documents (via python-docx and OpenXML ZIP fallback)
- Legacy Word (.doc) documents (via olefile and OLE2 stream / regex string extraction)
- PDF (.pdf) documents (via pypdf / PyPDF2)
- Plain Text (.txt, .md, .json, .csv) with auto-encoding detection (UTF-8, UTF-8-SIG, UTF-16, CP1252)
- Binary garbage detection & sanitization (filters out unprintable / non-text artifact characters)
"""

import io
import re
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional


PLAIN_TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".csv", ".log", ".py", ".js", 
    ".html", ".css", ".yaml", ".yml", ".xml", ".tsv", ".ini", ".env", ".rst"
}


def parse_document_text(content_bytes_or_str: Any, filename: str = "") -> str:
    """
    Extract clean, human-readable text from uploaded content or file bytes with fast extension dispatch.
    """
    if not content_bytes_or_str:
        return ""

    filename_lower = (filename or "").lower()
    ext = os.path.splitext(filename_lower)[1]

    # Fast Path: Plain Text Extensions
    if ext in PLAIN_TEXT_EXTENSIONS:
        if isinstance(content_bytes_or_str, str):
            return clean_text(content_bytes_or_str)
        return clean_text(decode_text_bytes(content_bytes_or_str))

    # Convert str to bytes if needed for binary format checks
    if isinstance(content_bytes_or_str, str):
        if is_mostly_printable(content_bytes_or_str) and not content_bytes_or_str.startswith("PK\x03\x04") and not content_bytes_or_str.startswith("\xD0\xCF\x11\xE0"):
            return clean_text(content_bytes_or_str)
        try:
            content_bytes = content_bytes_or_str.encode("latin-1")
        except Exception:
            content_bytes = content_bytes_or_str.encode("utf-8", errors="ignore")
    else:
        content_bytes = content_bytes_or_str

    if not isinstance(content_bytes, bytes):
        content_bytes = bytes(content_bytes)

    # 1. Check DOCX (ZIP format)
    if content_bytes.startswith(b"PK\x03\x04") or ext == ".docx":
        docx_text = extract_docx_text(content_bytes)
        if docx_text and len(docx_text.strip()) > 0:
            return clean_text(docx_text)

    # 2. Check Legacy DOC (OLE2 format)
    if content_bytes.startswith(b"\xd0\xcf\x11\xe0") or ext == ".doc":
        doc_text = extract_doc_legacy_text(content_bytes)
        if doc_text and len(doc_text.strip()) > 0:
            return clean_text(doc_text)

    # 3. Check PDF (%PDF header)
    if content_bytes.startswith(b"%PDF") or ext == ".pdf":
        pdf_text = extract_pdf_text(content_bytes)
        if pdf_text and len(pdf_text.strip()) > 0:
            return clean_text(pdf_text)

    # 4. Plain Text Auto-Encoding Decoding
    text = decode_text_bytes(content_bytes)
    return clean_text(text)


def extract_docx_text(file_bytes: bytes) -> str:
    """Extract clean plain text from Word .docx file bytes using python-docx with zipfile fallback."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        if paragraphs:
            return "\n\n".join(paragraphs)
    except Exception as e:
        print(f"[Parser Debug] python-docx failed: {e}")

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            if "word/document.xml" not in z.namelist():
                return ""
            xml_data = z.read("word/document.xml")
            tree = ET.fromstring(xml_data)

            paragraphs = []
            for p in tree.iter():
                if p.tag.endswith('}p'):  # paragraph tag <w:p>
                    texts = [node.text for node in p.iter() if node.tag.endswith('}t') and node.text]
                    if texts:
                        paragraphs.append("".join(texts))

            return "\n\n".join(paragraphs)
    except Exception as e:
        print(f"[Parser Warning] DOCX zip extraction error: {e}")
        return ""


def extract_doc_legacy_text(file_bytes: bytes) -> str:
    """Extract clean text from legacy MS Word .doc binary files using olefile or string extraction."""
    try:
        import olefile
        if olefile.isOleFile(io.BytesIO(file_bytes)):
            ole = olefile.OleFileIO(io.BytesIO(file_bytes))
            if ole.exists('WordDocument'):
                stream = ole.openstream('WordDocument').read()
                text_chunks = re.findall(rb'[\x20-\x7E\r\n\t]{4,}', stream[:500000])
                extracted = [c.decode('latin-1', errors='ignore').strip() for c in text_chunks]
                filtered = [s for s in extracted if len(s) > 3 and not s.startswith("Normal.") and not s.startswith("Microsoft")]
                if filtered:
                    return "\n\n".join(filtered)
    except Exception as e:
        print(f"[Parser Debug] olefile failed: {e}")

    printable_strings = re.findall(rb'[\x20-\x7E\r\n\t]{4,}', file_bytes[:500000])
    extracted = [s.decode('ascii', errors='ignore').strip() for s in printable_strings]
    filtered = [s for s in extracted if len(s) > 3 and not re.match(r'^[A-Z0-9_]{1,3}$', s)]
    return "\n".join(filtered[:200])


def extract_pdf_text(file_bytes: bytes) -> str:
    """Attempt PDF text extraction using pypdf or PyPDF2."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() for page in reader.pages if page.extract_text()]
        if pages:
            return "\n\n".join(pages)
    except Exception as e:
        print(f"[Parser Debug] pypdf failed: {e}")

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() for page in reader.pages if page.extract_text()]
        if pages:
            return "\n\n".join(pages)
    except Exception:
        pass

    printable = re.findall(rb'[\x20-\x7E\r\n\t]{4,}', file_bytes[:500000])
    extracted = [b.decode('ascii', errors='ignore') for b in printable if len(b) > 4]
    return "\n".join(extracted[:100])


def decode_text_bytes(file_bytes: bytes) -> str:
    """Auto-detect text encoding (UTF-8, UTF-8-SIG, UTF-16, Windows-1252) and return text."""
    if not file_bytes:
        return ""

    encodings = ["utf-8", "utf-8-sig", "utf-16", "cp1252", "latin-1"]
    for enc in encodings:
        try:
            decoded = file_bytes.decode(enc)
            if is_mostly_printable(decoded):
                return decoded
        except Exception:
            continue

    return file_bytes.decode("ascii", errors="ignore")


def is_mostly_printable(text: str) -> bool:
    """Return True if text sample consists mostly of valid printable characters (>75%). Efficient 4KB sampling."""
    if not text:
        return False
    # Sample first 4KB to make check near instantaneous (< 0.1ms)
    sample = text[:4096]
    printable_count = sum(1 for c in sample if c.isprintable() or c in '\n\r\t')
    return (printable_count / len(sample)) > 0.75


def clean_text(text: str) -> str:
    """Clean null bytes, binary garbage control characters, and unprintable artifacts."""
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'[\uFFFD\uFFFE\uFFFF]', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


