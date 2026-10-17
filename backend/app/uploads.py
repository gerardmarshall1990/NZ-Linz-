"""Upload handling: detect the real file type from its bytes, bound the size, store under an isolated directory with a sanitised name. Files are never executed."""
import hashlib, re
from pathlib import Path
from fastapi import HTTPException
from .config import MAX_UPLOAD_BYTES, upload_dir

SCAN_REFERENCE_EXT = {".obj", ".ply", ".usdz", ".glb", ".las"}   # raw scan exports: stored as reference only, never parsed

def detect_type(data: bytes, filename: str) -> str:
    head = data[:2048]
    if head.startswith(b"%PDF"): return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if head.startswith(b"\xff\xd8\xff"): return "jpg"
    if head.startswith(b"AutoCAD Binary DXF"): return "dxf_binary"
    if head.lstrip().startswith(b"0\r\nSECTION") or head.lstrip().startswith(b"0\nSECTION") or (b"SECTION" in head and b"HEADER" in head[:600] and head.isascii()): return "dxf"
    if head.startswith(b"ISO-10303-21"): return "ifc"
    if Path(filename).suffix.lower() in SCAN_REFERENCE_EXT: return "scan_reference"
    raise HTTPException(415, "unsupported or unrecognised file type (allowed: PDF, PNG, JPEG, DXF, IFC; raw scan meshes are kept as reference only)")

def safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "upload"
    return base[-120:]

def store(parcel_id: int, filename: str, data: bytes) -> dict:
    if len(data) == 0: raise HTTPException(422, "empty file")
    if len(data) > MAX_UPLOAD_BYTES: raise HTTPException(413, f"file too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    kind = detect_type(data, filename)
    sha = hashlib.sha256(data).hexdigest()
    d = upload_dir() / str(int(parcel_id)); d.mkdir(parents=True, exist_ok=True)
    stored = f"{sha[:16]}_{safe_name(filename)}"
    path = d / stored
    if not path.resolve().is_relative_to(upload_dir().resolve()): raise HTTPException(400, "bad path")
    path.write_bytes(data)
    pages = None
    if kind == "pdf":
        import pymupdf
        try: pages = len(pymupdf.open(stream=data, filetype="pdf"))
        except Exception as e: raise HTTPException(422, f"unreadable PDF: {e}")
    return {"detected_type": kind, "sha256": sha, "stored_name": stored, "size_bytes": len(data), "page_count": pages, "path": path}
