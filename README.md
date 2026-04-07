# Fidelity

Multi-platform music downloader with support for Tidal (lossless FLAC) and YouTube.

---

## Requirements

- [Python 3.10+](https://www.python.org/downloads/)
- [ffmpeg](https://ffmpeg.org/download.html) — required for YouTube and Spotify

---

## Install

```bash
pip install fidelity-dl
```

Then run from anywhere:

```bash
fidelity
```

Or install directly from source:

```bash
pip install git+https://github.com/lev1ll/Fidelity.git
```

Or without installing:

```bash
git clone https://github.com/lev1ll/Fidelity.git
cd Fidelity
python tidal_dl.py
```

Dependencies install automatically on first run.

---

## Platforms

| Platform | Quality | Account needed |
|---|---|---|
| Tidal | Lossless FLAC / Hi-Res | Yes — HiFi or HiFi Plus |
| YouTube | Up to ~160kbps Opus | No |

---

## Features

- Lossless FLAC downloads from Tidal
- Search by artist, album, or track
- Multi-select: download several albums at once
- Paste any Tidal / YouTube / Spotify URL directly
- Embeds cover art and metadata into every file
- Configurable download folder
- Auto-update notifications

---

## Usage

### Tidal Hi-Res Downloads (FLAC 24-bit)

**Requirements:**
- Tidal app must be **open and logged in** with a HiFi or HiFi Plus account
- Fidelity automatically extracts the Hi-Res token from the Tidal desktop app
- **No browser login needed** — everything is automatic

Simply run:
```bash
fidelity
```

Select "1. Tidal" → Search or paste a URL → Fidelity will automatically find and use your Tidal token for Hi-Res downloads.

### YouTube Downloads

No account needed. Select "2. YouTube" and paste a URL or search for anything.

### Search or Direct Links

- **Tidal:** Artist name, album, track, or paste `https://tidal.com/artist/...`
- **YouTube:** Song name, artist name, or paste any YouTube link
- **Multiple selections:** Use commas to download several items at once (e.g., `1,3,5`)

Downloads are organized by platform:

```
~/Downloads/Musica/
  Tidal/
  YouTube/
```

---

## Legal Disclaimer

This project is intended for **educational and personal use only**.

- This tool does not host, store, or distribute any copyrighted content.
- Users are solely responsible for how they use this software and must comply with the Terms of Service of each platform (Tidal, YouTube, Spotify) and the copyright laws of their country.
- Downloading copyrighted material without authorization may violate applicable laws. The author does not condone or encourage piracy.
- This project is not affiliated with, endorsed by, or connected to Tidal, YouTube, or Spotify in any way.

---

Enjoy.
