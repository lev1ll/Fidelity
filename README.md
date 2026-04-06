# Fidelity

Multi-platform music downloader with support for Tidal (lossless FLAC), YouTube, and Spotify.

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
| Spotify | Up to 320kbps | Yes — any plan |

> Spotify downloads are matched to YouTube with full Spotify metadata (cover art, artist, album, lyrics).

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

Search by name or paste a URL. For Tidal, you'll be prompted to log in the first time — just open the link in your browser. The session is saved so you won't need to log in again.

Downloads are organized by platform:

```
~/Downloads/Musica/
  Tidal/
  YouTube/
  Spotify/
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
