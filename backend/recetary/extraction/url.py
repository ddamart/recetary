"""Fetch and clean text from a web article URL."""
from __future__ import annotations

from typing import Optional

import trafilatura


def fetch_clean_text(url: str) -> Optional[str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )
    return extracted or None
