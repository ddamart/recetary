"""PDF helpers: read bytes, extract a cover image from page 1."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

import pypdfium2 as pdfium


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def render_cover_png(pdf_bytes: bytes, *, max_width: int = 1400) -> Optional[bytes]:
    """Render the first PDF page to a PNG byte string suitable for storage.

    Returns None if rendering fails (corrupt PDF, etc.).
    """
    try:
        pdf = pdfium.PdfDocument(BytesIO(pdf_bytes))
        if len(pdf) == 0:
            return None
        page = pdf[0]
        width_pt = page.get_width()
        scale = max(1.0, min(4.0, max_width / width_pt))
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except Exception:
        return None
