"""Image helpers: read bytes and detect the media type."""
from __future__ import annotations

import mimetypes
from pathlib import Path

_DEFAULT_MEDIA_TYPE = "image/jpeg"
_SUPPORTED = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def detect_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed in _SUPPORTED:
        return guessed
    return _DEFAULT_MEDIA_TYPE


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()
