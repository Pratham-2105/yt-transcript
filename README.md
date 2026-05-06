# yt-transcript

A tiny Python CLI that grabs YouTube transcripts with timestamps and saves them to a folder of your choice. Built because paid "transcript extractor" sites started gating the feature behind credits and logins — which is absurd for something the YouTube player itself serves for free.

One command, from anywhere:

```
> yt https://youtu.be/lgPxucqRazM
→ Video ID: lgPxucqRazM
→ Title: I'm back: Winning Codeforces Round 1062 (Div. 4)
✓ Saved to D:\transcripts\Im_back_Winning_Codeforces_Round_1062_Div_4.txt
```

## What the output looks like

Paragraphs grouped in ~30-second chunks, one timestamp per paragraph. Reads like a transcript, not a chaotic subtitle dump, and plays nicely if you paste it into an LLM for summarization.

```
I'm back: Winning Codeforces Round 1062 (Div. 4)
https://www.youtube.com/watch?v=lgPxucqRazM
============================================================

[00:00:00] Hey everyone, welcome back to the channel. Today I want to walk
through the Codeforces round I did last night...

[00:00:30] The first problem was a straightforward ad hoc, but the second
one had a subtle greedy insight that cost me about four minutes...
```

## Install

```bash
git clone https://github.com/Pratham-2105/yt-transcript.git
cd yt-transcript

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

## Usage

```bash
# normal use
python yt_transcript.py <youtube_url>

# override the save folder just for this run
python yt_transcript.py <url> --folder D:\some\other\path

# change the default save folder
python yt_transcript.py --set-folder D:\transcripts
```

On first run it asks where to save transcripts and remembers the answer in `%APPDATA%\yt_transcript\config.json` (or `~/.config/yt_transcript/` on Unix). You'll never be asked again.

Accepts any common YouTube URL format — `watch?v=`, `youtu.be`, `/shorts/`, `/embed/` — or a bare 11-character video ID.

## Make it a one-word command

The whole point is skipping friction, so drop a shell script somewhere on your `PATH` and you can run it from anywhere without activating the venv.

### Windows

Create `C:\tools\yt.bat`:

```bat
@echo off
C:\path\to\yt-transcript\.venv\Scripts\python.exe C:\path\to\yt-transcript\yt_transcript.py %*
```

Add `C:\tools` to your user `PATH` (Win key → "environment variables" → edit user `Path` → New). Open a fresh terminal, then:

```
yt https://youtu.be/<id>
```

> Watch out for Notepad silently appending `.txt` to the filename. Save with the filename in quotes (`"yt.bat"`) and **Save as type** set to **All Files**.

### macOS / Linux

Create `~/bin/yt`:

```bash
#!/usr/bin/env bash
/path/to/yt-transcript/.venv/bin/python /path/to/yt-transcript/yt_transcript.py "$@"
```

Then:

```bash
chmod +x ~/bin/yt
# ensure ~/bin is on your PATH, e.g. in ~/.bashrc or ~/.zshrc:
export PATH="$HOME/bin:$PATH"
```

## How it works

```
yt <url>
   │
   ▼
parse video ID from URL
   │
   ▼
youtube-transcript-api  →  list of {text, start, duration} snippets
   │
   ▼
scrape page for video title (stdlib urllib, no extra dep)
   │
   ▼
group snippets into ~30s paragraphs with timestamps
   │
   ▼
slugify title → write .txt to the configured folder
```

Falls back to auto-translated English if the video only has captions in another language.

## When it breaks

`youtube-transcript-api` scrapes YouTube's internal endpoints, so it occasionally breaks when YouTube changes something under the hood. The maintainer is usually fast with fixes. First thing to try:

```bash
pip install -U youtube-transcript-api
```

Other common failures, all handled with a single-line error message rather than a stack trace:

- Captions disabled by the uploader
- Video is private, deleted, or region-locked
- No captions in any language

## Caveats

- This uses an unofficial library that scrapes the caption data YouTube serves to its own player. It's fine for personal use; don't build a paid service on it without reading YouTube's ToS carefully.
- Some videos only have `[Music]` auto-captions. That's a YouTube thing, not a bug here.

## License

MIT
