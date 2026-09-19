"""Fetch recipe content from video URLs (YouTube, Instagram, Twitter/X).

YouTube: transcript via youtube_transcript_api + description via yt-dlp.
Instagram and Twitter: video downloaded via yt-dlp for Gemini video processing.
Instagram falls back to instaloader (caption + image) if yt-dlp fails.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

_log = logging.getLogger(__name__)

# Hard cap — videos larger than this are rejected outright.
# Files between 20 MB and this limit are handled via the Gemini File API.
_MAX_VIDEO_BYTES = 200 * 1024 * 1024

# Instagram (and increasingly Twitter/X) block their graphql/query API for
# unauthenticated requests, returning 403 even for public posts. yt-dlp can
# reuse a logged-in browser session by reading cookies straight from the local
# browser profile. Defaults to Firefox; override with RECETARY_COOKIES_BROWSER
# (e.g. "chrome", "edge") or set it empty to disable cookie loading entirely.
_COOKIES_BROWSER = os.environ.get("RECETARY_COOKIES_BROWSER", "firefox").strip()


def _browser_cookie_opts() -> dict:
    """yt-dlp options to load cookies from the local browser, if configured."""
    if not _COOKIES_BROWSER:
        return {}
    return {"cookiesfrombrowser": (_COOKIES_BROWSER,)}


class VideoExtractionError(Exception):
    """Raised when video content cannot be fetched."""


@dataclass
class VideoContent:
    text: str
    thumbnail_bytes: Optional[bytes] = None
    thumbnail_media_type: str = "image/jpeg"
    source_url: str = ""
    platform: str = ""
    video_bytes: Optional[bytes] = None
    video_mime_type: str = "video/mp4"


# ---------------------------------------------------------------------------
# URL detection
# ---------------------------------------------------------------------------

_YT_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})"),
]

_IG_PATTERNS = [
    re.compile(r"instagram\.com/(?:[^/?#]+/)?(?:reel|reels|p)/([\w-]+)"),
]

_TW_PATTERNS = [
    re.compile(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)"),
]


def _extract_youtube_id(url: str) -> Optional[str]:
    for pat in _YT_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


def _extract_instagram_shortcode(url: str) -> Optional[str]:
    for pat in _IG_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


def _extract_twitter_status_id(url: str) -> Optional[str]:
    for pat in _TW_PATTERNS:
        m = pat.search(url)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

def _fetch_youtube_description(video_id: str) -> str:
    """Fetch the video description via yt-dlp (metadata only, no download)."""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return (info or {}).get("description") or ""
    except Exception:
        return ""


def _fetch_youtube(video_id: str) -> VideoContent:
    from youtube_transcript_api import YouTubeTranscriptApi

    ytt = YouTubeTranscriptApi()

    # Fetch video description (ingredients, links, etc.) in parallel-safe way
    description = _fetch_youtube_description(video_id)

    try:
        transcript_list = ytt.list(video_id)
    except Exception as e:
        raise VideoExtractionError(
            f"Could not access transcripts for YouTube video {video_id} "
            f"(may be private or have no captions): {e}"
        ) from e

    # Priority: Spanish manual > English manual > Spanish auto > English auto > any
    transcript = None
    for lang in ("es", "en"):
        try:
            transcript = transcript_list.find_transcript([lang])
            break
        except Exception:
            pass

    if transcript is None:
        try:
            transcript = transcript_list.find_generated_transcript(["es", "en"])
        except Exception:
            pass

    if transcript is None:
        # Take whatever is available
        try:
            transcript = next(iter(transcript_list))
        except StopIteration:
            raise VideoExtractionError(
                f"No captions available for YouTube video {video_id}"
            )

    segments = transcript.fetch()
    transcript_text = " ".join(seg.text for seg in segments)

    if not transcript_text.strip():
        raise VideoExtractionError(
            f"Transcript is empty for YouTube video {video_id}"
        )

    # Combine description + transcript for richer context
    parts = []
    if description.strip():
        parts.append(f"Video description:\n{description.strip()}")
    parts.append(f"Transcript:\n{transcript_text}")
    text = "\n\n".join(parts)

    # Fetch thumbnail
    thumbnail_bytes = None
    for quality in ("maxresdefault", "hqdefault", "mqdefault"):
        thumb_url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        try:
            resp = httpx.get(thumb_url, timeout=10, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                thumbnail_bytes = resp.content
                break
        except httpx.HTTPError:
            continue

    return VideoContent(
        text=text,
        thumbnail_bytes=thumbnail_bytes,
        source_url=f"https://www.youtube.com/watch?v={video_id}",
        platform="youtube",
    )


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------

def _fetch_instagram(shortcode: str) -> VideoContent:
    """Fetch Instagram reel/post content.

    Metadata (caption, thumbnail) and the video download are handled as two
    independent steps. Instagram's CDN sometimes returns 500/429 for a reel's
    video streams (typically DASH-only posts that require a separate
    video+audio merge) even though the caption is available; in that case we
    still return the caption instead of throwing everything away. Falls back to
    instaloader only when yt-dlp cannot get metadata at all.
    """
    import yt_dlp

    ig_url = f"https://www.instagram.com/reel/{shortcode}/"

    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")
        base_opts = {
            # Prefer a single progressive file to avoid the flaky DASH
            # video+audio merge; fall back to DASH only if nothing else exists.
            "format": "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            # Retry transient CDN errors (500/429) before giving up.
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 3,
            **_browser_cookie_opts(),
        }

        # Step 1: metadata only. If this fails, yt-dlp genuinely can't see the
        # post — fall back to instaloader.
        try:
            with yt_dlp.YoutubeDL({**base_opts, "skip_download": True}) as ydl:
                info = ydl.extract_info(ig_url, download=False)
            if info is None:
                raise VideoExtractionError("yt-dlp returned no info")
        except VideoExtractionError:
            raise
        except Exception:
            return _fetch_instagram_fallback(shortcode)

        caption = info.get("description") or ""
        source_url = info.get("webpage_url") or f"https://www.instagram.com/p/{shortcode}/"

        # Fetch thumbnail
        thumbnail_bytes = None
        thumb_url = info.get("thumbnail")
        if thumb_url:
            try:
                resp = httpx.get(thumb_url, timeout=10, follow_redirects=True)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    thumbnail_bytes = resp.content
            except httpx.HTTPError:
                pass

        # Step 2: video download. A CDN failure here (500/429) is not fatal —
        # degrade to caption-only rather than losing the recipe text.
        video_bytes = None
        video_mime_type = "video/mp4"
        try:
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                ydl.download([ig_url])
            downloaded = list(Path(tmpdir).glob("*.*"))
            if downloaded:
                video_path = downloaded[0]
                raw = video_path.read_bytes()
                if len(raw) > _MAX_VIDEO_BYTES:
                    size_mb = len(raw) / (1024 * 1024)
                    raise VideoExtractionError(
                        f"Instagram video is too large ({size_mb:.1f} MB). "
                        f"Maximum supported size is 200 MB."
                    )
                video_bytes = raw
                ext = video_path.suffix.lstrip(".")
                video_mime_type = f"video/{ext}" if ext else "video/mp4"
        except VideoExtractionError:
            raise
        except Exception as e:
            _log.warning(
                "Instagram %s: video download failed (%s); "
                "continuing with caption only.",
                shortcode, e,
            )

        if not caption.strip() and video_bytes is None:
            raise VideoExtractionError(
                f"Instagram post {shortcode} has no caption and its video "
                f"could not be downloaded (Instagram CDN error). Nothing to "
                f"extract a recipe from."
            )

        return VideoContent(
            text=caption,
            thumbnail_bytes=thumbnail_bytes,
            source_url=source_url,
            platform="instagram",
            video_bytes=video_bytes,
            video_mime_type=video_mime_type,
        )


def _fetch_instagram_fallback(shortcode: str) -> VideoContent:
    """Fallback: fetch Instagram post via instaloader (caption + image, no video)."""
    import instaloader

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    try:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
    except Exception as e:
        # Instagram rejects unauthenticated API calls (403 / empty response),
        # which surfaces as opaque errors like "'NoneType' object is not
        # subscriptable". This is almost never a private/deleted post — it is a
        # missing browser session. Point the user at the real fix.
        hint = (
            f"set RECETARY_COOKIES_BROWSER to the browser where you are logged "
            f"into Instagram (currently '{_COOKIES_BROWSER}')"
            if _COOKIES_BROWSER
            else "set RECETARY_COOKIES_BROWSER to a browser where you are logged into Instagram"
        )
        raise VideoExtractionError(
            f"Could not fetch Instagram post {shortcode}. Instagram blocks "
            f"unauthenticated requests, so this usually means the browser "
            f"session cookies are missing or expired (not that the post is "
            f"private or deleted). Try to {hint}, and make sure that browser "
            f"is logged into Instagram. Underlying error: {e}"
        ) from e

    caption = post.caption or ""
    if not caption.strip():
        raise VideoExtractionError(
            f"Instagram post {shortcode} has no caption text to extract a recipe from"
        )

    # Fetch display image as thumbnail
    thumbnail_bytes = None
    if post.url:
        try:
            resp = httpx.get(post.url, timeout=15, follow_redirects=True)
            if resp.status_code == 200:
                thumbnail_bytes = resp.content
        except httpx.HTTPError:
            pass

    return VideoContent(
        text=caption,
        thumbnail_bytes=thumbnail_bytes,
        source_url=f"https://www.instagram.com/p/{shortcode}/",
        platform="instagram",
    )


# ---------------------------------------------------------------------------
# Twitter / X
# ---------------------------------------------------------------------------

def _fetch_twitter(status_id: str) -> VideoContent:
    import yt_dlp

    tweet_url = f"https://x.com/i/status/{status_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        outtmpl = str(Path(tmpdir) / "%(id)s.%(ext)s")
        ydl_opts = {
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "outtmpl": outtmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(tweet_url, download=True)
        except Exception as e:
            raise VideoExtractionError(
                f"Could not download Twitter video {status_id} "
                f"(may be private or not contain a video): {e}"
            ) from e

        if info is None:
            raise VideoExtractionError(
                f"yt-dlp returned no info for Twitter status {status_id}"
            )

        # Find the downloaded file
        downloaded = list(Path(tmpdir).glob("*.*"))
        if not downloaded:
            raise VideoExtractionError(
                f"yt-dlp did not produce a file for Twitter status {status_id}"
            )
        video_path = downloaded[0]
        video_bytes = video_path.read_bytes()

        if len(video_bytes) > _MAX_VIDEO_BYTES:
            size_mb = len(video_bytes) / (1024 * 1024)
            raise VideoExtractionError(
                f"Twitter video is too large ({size_mb:.1f} MB). "
                f"Maximum supported size is 200 MB."
            )

        # Detect mime type from extension before tmpdir is cleaned up
        ext = video_path.suffix.lstrip(".")
        mime_type = f"video/{ext}" if ext else "video/mp4"

    description = info.get("description") or ""
    source_url = info.get("webpage_url") or tweet_url

    # Fetch thumbnail
    thumbnail_bytes = None
    thumb_url = info.get("thumbnail")
    if thumb_url:
        try:
            resp = httpx.get(thumb_url, timeout=10, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 1000:
                thumbnail_bytes = resp.content
        except httpx.HTTPError:
            pass

    return VideoContent(
        text=description,
        thumbnail_bytes=thumbnail_bytes,
        source_url=source_url,
        platform="twitter",
        video_bytes=video_bytes,
        video_mime_type=mime_type,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_video_content(url: str) -> VideoContent:
    """Fetch recipe content from a YouTube, Instagram, or Twitter/X video URL."""
    yt_id = _extract_youtube_id(url)
    if yt_id:
        return _fetch_youtube(yt_id)

    ig_code = _extract_instagram_shortcode(url)
    if ig_code:
        return _fetch_instagram(ig_code)

    tw_id = _extract_twitter_status_id(url)
    if tw_id:
        return _fetch_twitter(tw_id)

    raise VideoExtractionError(
        f"Unsupported video URL: {url}. Supported platforms: YouTube, Instagram, Twitter/X"
    )
