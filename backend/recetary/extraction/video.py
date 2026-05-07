"""Fetch recipe content from video URLs (YouTube, Instagram, Twitter/X).

Extracts transcripts/captions and thumbnails so the LLM extractor
can process them as text + image — no video download or ffmpeg needed.
Twitter videos are downloaded via yt-dlp for Gemini video processing.
"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

# Maximum video size we'll send to Gemini (20 MB)
_MAX_VIDEO_BYTES = 20 * 1024 * 1024


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
    re.compile(r"instagram\.com/(?:reel|reels|p)/([\w-]+)"),
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

def _fetch_youtube(video_id: str) -> VideoContent:
    from youtube_transcript_api import YouTubeTranscriptApi

    ytt = YouTubeTranscriptApi()

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
    text = " ".join(seg.text for seg in segments)

    if not text.strip():
        raise VideoExtractionError(
            f"Transcript is empty for YouTube video {video_id}"
        )

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
        raise VideoExtractionError(
            f"Could not fetch Instagram post {shortcode} "
            f"(may be private or deleted): {e}"
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
            "format": "best[ext=mp4]/best",
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
                f"Maximum supported size is {_MAX_VIDEO_BYTES // (1024 * 1024)} MB."
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
