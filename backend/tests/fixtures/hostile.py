"""Rejected-upload inputs (macro DOCX, over-compressed DOCX, executable header, bad signatures).

None of these are stored in the repository: antivirus scanners (e.g. Windows Defender) may flag such
files inside a downloaded ZIP. They are built at test time into pytest's temporary directory and are
harmless — the "macro" part is a few plain bytes, not VBA code, and the "executable" is only a
two-byte header.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

# assembled at run time so the source itself contains no file signatures
EXE_HEADER = bytes([0x4D, 0x5A])
MACRO_PART = "word/" + "vba" + "Project.bin"


def macro_docx(base_docx: bytes) -> bytes:
    """A copy of a valid DOCX with an (empty, inert) macro part added."""
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base_docx)) as src, zipfile.ZipFile(buf, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr(MACRO_PART, b"inert placeholder")
    return buf.getvalue()


def write_hostile_files(base_docx: bytes, out_dir: Path) -> dict[str, Path]:
    """Write every rejected-upload sample to ``out_dir`` and return name -> path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "macro.docx": macro_docx(base_docx),
        "program.exe": EXE_HEADER + b"....",
        "fake.pdf": b"PK\x03\x04 not a pdf",
        "fake.docx": b"%PDF-1.4 fake",
        "binary.txt": b"\x00\x01\x02binary",
        "empty.txt": b"",
    }
    paths = {}
    for name, data in files.items():
        p = out_dir / name
        p.write_bytes(data)
        paths[name] = p
    return paths
