"""
yt_transcript.py — Fetch YouTube transcripts with timestamps.

Usage:
    python yt_transcript.py <youtube_url>
    python yt_transcript.py <youtube_url> --folder D:\other\path
    python yt_transcript.py --set-folder D:\transcripts
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


# ─── config: where to save transcripts ──────────────────────────────────────

CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "yt_transcript"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_output_folder(override: str | None) -> Path:
    """Returns the folder to save transcripts to. Asks on first run."""
    if override:
        return Path(override).expanduser().resolve()

    cfg = load_config()
    if "output_folder" in cfg:
        return Path(cfg["output_folder"])

    # first run — ask once
    print("Where should transcripts be saved?")
    print("(Enter a full path, e.g. D:\\transcripts)")
    chosen = input("> ").strip().strip('"')
    folder = Path(chosen).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)

    cfg["output_folder"] = str(folder)
    save_config(cfg)
    print(f"✓ Saved. Future runs will use: {folder}\n")
    return folder


# ─── URL parsing ────────────────────────────────────────────────────────────

# Matches the 11-char video ID from any common YouTube URL format.
VIDEO_ID_RE = re.compile(
    r"(?:v=|/shorts/|/embed/|youtu\.be/|/v/|/watch\?.*?v=)([A-Za-z0-9_-]{11})"
)


def parse_video_id(url: str) -> str:
    match = VIDEO_ID_RE.search(url)
    if not match:
        # maybe they pasted just the bare ID
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", url.strip()):
            return url.strip()
        raise ValueError(f"Couldn't find a YouTube video ID in: {url}")
    return match.group(1)


# ─── fetching ───────────────────────────────────────────────────────────────

def fetch_transcript(video_id: str) -> list[dict]:
    """Returns list of {'text': str, 'start': float, 'duration': float}."""
    # Try English first, fall back to anything available (auto-translate).
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except NoTranscriptFound:
        # fall back: grab whatever language exists, translated to English
        transcript_list = api.list(video_id)
        transcript = next(iter(transcript_list))
        if transcript.is_translatable:
            fetched = transcript.translate("en").fetch()
        else:
            fetched = transcript.fetch()

    # normalize to plain dicts (the library returns FetchedTranscriptSnippet objects)
    return [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]


def fetch_video_title(video_id: str) -> str:
    """Scrape the video title from the YouTube page. Returns '' on failure."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        # title sits in <meta name="title" content="...">
        m = re.search(r'<meta name="title" content="([^"]+)"', html)
        if m:
            # unescape common HTML entities
            title = m.group(1)
            title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
            return title
    except Exception:
        pass
    return ""


# ─── formatting ─────────────────────────────────────────────────────────────

def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_transcript(segments: list[dict], chunk_seconds: int = 30) -> str:
    """Group segments into ~chunk_seconds paragraphs, one timestamp each."""
    if not segments:
        return ""

    paragraphs = []
    chunk_start = segments[0]["start"]
    chunk_texts = []

    for seg in segments:
        # if this segment pushes us past the chunk size, flush
        if seg["start"] - chunk_start >= chunk_seconds and chunk_texts:
            paragraphs.append(
                f"[{format_timestamp(chunk_start)}] {' '.join(chunk_texts).strip()}"
            )
            chunk_start = seg["start"]
            chunk_texts = []
        chunk_texts.append(seg["text"].replace("\n", " "))

    # flush the last chunk
    if chunk_texts:
        paragraphs.append(
            f"[{format_timestamp(chunk_start)}] {' '.join(chunk_texts).strip()}"
        )

    return "\n\n".join(paragraphs)


# ─── filename helpers ───────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 80) -> str:
    # keep alphanumerics, spaces, hyphens; collapse whitespace to underscores
    cleaned = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned[:max_len].strip("_") or "transcript"


def make_filename(video_id: str, title: str) -> str:
    base = slugify(title) if title else video_id
    return f"{base}.txt"


# ─── main ───────────────────────────────────────────────────────────────────

def run(url: str, folder_override: str | None) -> int:
    try:
        video_id = parse_video_id(url)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    print(f"→ Video ID: {video_id}")

    try:
        segments = fetch_transcript(video_id)
    except TranscriptsDisabled:
        print("✗ This video has transcripts disabled.", file=sys.stderr)
        return 1
    except VideoUnavailable:
        print("✗ Video is unavailable (private, deleted, or region-locked).", file=sys.stderr)
        return 1
    except NoTranscriptFound:
        print("✗ No transcript available in any language.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"✗ Failed to fetch transcript: {e}", file=sys.stderr)
        print("  Try: pip install -U youtube-transcript-api", file=sys.stderr)
        return 1

    title = fetch_video_title(video_id)
    if title:
        print(f"→ Title: {title}")

    body = format_transcript(segments, chunk_seconds=30)
    header = (
        f"{title or video_id}\n"
        f"https://www.youtube.com/watch?v={video_id}\n"
        f"{'=' * 60}\n\n"
    )

    folder = get_output_folder(folder_override)
    folder.mkdir(parents=True, exist_ok=True)
    out_path = folder / make_filename(video_id, title)
    out_path.write_text(header + body, encoding="utf-8")

    print(f"✓ Saved to {out_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch YouTube transcripts with timestamps.")
    parser.add_argument("url", nargs="?", help="YouTube URL or video ID")
    parser.add_argument("--folder", help="Override the output folder for this run")
    parser.add_argument("--set-folder", help="Change the default output folder and exit")
    args = parser.parse_args()

    if args.set_folder:
        folder = Path(args.set_folder).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        cfg = load_config()
        cfg["output_folder"] = str(folder)
        save_config(cfg)
        print(f"✓ Default folder set to: {folder}")
        return 0

    if not args.url:
        parser.print_help()
        return 1

    return run(args.url, args.folder)


if __name__ == "__main__":
    sys.exit(main())