import sys
import subprocess
import shutil
import json
import time
import webbrowser
import urllib.parse
import http.server
import threading
import base64
import secrets

__version__ = "1.1.0"
GITHUB_REPO  = "lev1ll/Fidelity"

# ─── Auto-install dependencias base ──────────────────────────────────────────

REQUIRED_BASE = ["tidalapi", "requests", "mutagen"]

def _can_import(pkg):
    try:
        __import__(pkg.replace("-", "_").split("[")[0])
        return True
    except ImportError:
        return False

def ensure_installed(packages):
    for pkg in packages:
        if not _can_import(pkg):
            print(f"  Instalando {pkg}...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print(f"  ✓ {pkg} instalado")

def check_and_install():
    missing = [p for p in REQUIRED_BASE if not _can_import(p)]
    if missing:
        print("\n  Faltan dependencias. Las instalo automaticamente...\n")
        ensure_installed(missing)
        print("\n  Reiniciando...\n")
        subprocess.run([sys.executable] + sys.argv)
        sys.exit()

check_and_install()

# ─── Imports ─────────────────────────────────────────────────────────────────

import tidalapi
import requests
import re
from pathlib import Path
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

# ─── Spotify App Credentials ─────────────────────────────────────────────────

SPOTIFY_CLIENT_ID     = "e9d1e7f322194c43a26f491473773adc"
SPOTIFY_CLIENT_SECRET = "2d89d33e935a4b069910a40782840652"
SPOTIFY_REDIRECT_URI  = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES        = "playlist-read-private user-library-read"
SPOTIFY_TOKEN_FILE    = Path.home() / ".musicdl" / "spotify_token.json"

# ─── Config ──────────────────────────────────────────────────────────────────

CONFIG_FILE  = Path.home() / ".musicdl" / "config.json"
SESSION_FILE = Path.home() / ".musicdl" / "tidal_session.json"

DEFAULT_CONFIG = {
    "download_dir": str(Path.home() / "Downloads" / "Musica"),
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def get_download_dir(cfg):
    return Path(cfg["download_dir"])

# ─── Auto-update ─────────────────────────────────────────────────────────────

def check_for_updates():
    try:
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=4
        )
        if r.status_code != 200:
            return
        latest = r.json().get("tag_name", "").lstrip("v")
        if latest and latest != __version__:
            print(f"\n  ┌─ Actualización disponible ─────────────────────┐")
            print(f"  │  Nueva versión: v{latest}  (tenés v{__version__})".ljust(52) + "│")
            print(f"  └────────────────────────────────────────────────┘")
            ans = input("  ¿Actualizar ahora? (s/n): ").strip().lower()
            if ans == "s":
                print("  Actualizando...")
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade",
                     f"git+https://github.com/{GITHUB_REPO}.git"],
                    check=True
                )
                print("  ✓ Actualizado! Reiniciando...")
                subprocess.run([sys.executable] + sys.argv)
                sys.exit()
    except Exception:
        pass  # Sin internet o repo privado, seguimos igual

# ─── Helpers ─────────────────────────────────────────────────────────────────

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

def ask(prompt, options=None):
    while True:
        val = input(prompt).strip()
        if options is None or val.lower() in [str(o).lower() for o in options]:
            return val
        print(f"  Opcion invalida. Elegí entre: {', '.join(str(o) for o in options)}")

def pick(items, label_fn, title=""):
    if title:
        print(f"\n{title}")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {label_fn(item)}")
    print("  0. Volver")
    while True:
        sel = input("\n  Elegí un número (o 0 para volver): ").strip()
        if sel == "0":
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(items):
            return items[int(sel) - 1]
        print("  Número inválido.")

def pick_multi(items, label_fn, title=""):
    if title:
        print(f"\n{title}")
    for i, item in enumerate(items, 1):
        print(f"  {i}. {label_fn(item)}")
    print("  0. Volver")
    print("  * Para descargar todo escribí 'todo'")
    while True:
        sel = input("\n  Elegí números separados por coma (ej: 1,3,5) o 'todo': ").strip()
        if sel == "0":
            return None
        if sel.lower() == "todo":
            return items
        parts = [p.strip() for p in sel.split(",")]
        if all(p.isdigit() and 1 <= int(p) <= len(items) for p in parts):
            return [items[int(p) - 1] for p in parts]
        print("  Selección inválida.")

def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

# ─── Banner ──────────────────────────────────────────────────────────────────

def print_banner():
    W   = 51
    def row(text=""):
        return f"  ║  {text:<{W}}║"
    sep = "═" * (W + 2)
    v   = __version__

    print()
    print(f"  ╔{sep}╗")
    print(row())
    print(row("  ▶  F · I · D · E · L · I · T · Y"))
    print(row("     high  fidelity  music  downloader"))
    print(row(f"                             by lev1ll  v{v}"))
    print(row())
    print(f"  ╚{sep}╝")
    print()
    print("  Hola! Bienvenido.")
    print()

def print_setup_instructions(download_dir):
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │            PRIMERA VEZ — Setup                  │")
    print("  └─────────────────────────────────────────────────┘")
    print()
    print("  Requisitos:")
    print("  · Python 3.10+  →  https://www.python.org/downloads/")
    print("  · Las dependencias se instalan solas la primera vez")
    print("  · Para YouTube/Spotify también necesitás ffmpeg:")
    print("    https://ffmpeg.org/download.html")
    print()
    print("  Cuentas necesarias por plataforma:")
    print("  · Tidal   → Cuenta HiFi o HiFi Plus")
    print("  · YouTube → Sin cuenta")
    print("  · Spotify → Cuenta Spotify (cualquier plan)")
    print()
    print(f"  Descargas en: {download_dir}")
    print("  (Podés cambiarlo en Configuración)")
    print()
    input("  Presioná Enter para continuar...")
    print()

# ─── Settings ────────────────────────────────────────────────────────────────

def menu_settings(cfg):
    while True:
        print("\n  ── Configuración ─────────────────────────────────")
        print(f"  Carpeta de descarga: {cfg['download_dir']}")
        print()
        print("  1. Cambiar carpeta de descarga")
        print("  0. Volver")

        choice = ask("\n  Elegí: ", ["0", "1"])
        if choice == "0":
            break

        elif choice == "1":
            print(f"\n  Carpeta actual: {cfg['download_dir']}")
            nueva = input("  Nueva carpeta (Enter para cancelar): ").strip()
            if not nueva:
                continue
            p = Path(nueva)
            try:
                p.mkdir(parents=True, exist_ok=True)
                cfg["download_dir"] = str(p)
                save_config(cfg)
                print(f"  ✓ Guardado: {p}")
            except Exception as e:
                print(f"  Error: {e}")

# ─── TIDAL ───────────────────────────────────────────────────────────────────

def get_tidal_session(download_dir):
    first_time = not SESSION_FILE.exists()
    if first_time:
        print_setup_instructions(download_dir)

    config = tidalapi.Config(quality=tidalapi.Quality.high_lossless)
    session = tidalapi.Session(config)

    if SESSION_FILE.exists():
        try:
            if session.load_session_from_file(SESSION_FILE):
                print(f"  ✓ Sesion Tidal cargada ({session.country_code})")
                return session
        except Exception:
            pass

    print("  Abrí el link en el navegador para iniciar sesión en Tidal:")
    print()
    session.login_oauth_simple()
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    session.save_session_to_file(SESSION_FILE)
    print("  ✓ Sesion guardada!")
    return session

def tidal_embed_cover(dest_path, cover_url):
    try:
        r = requests.get(cover_url)
        if r.status_code != 200:
            return
        cover_data = r.content
        if str(dest_path).endswith(".flac"):
            audio = FLAC(dest_path)
            pic = Picture()
            pic.data = cover_data
            pic.type = 3
            pic.mime = "image/jpeg"
            audio.add_picture(pic)
            audio.save()
        elif str(dest_path).endswith(".m4a"):
            audio = MP4(dest_path)
            audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
    except Exception:
        pass

def tidal_embed_tags(dest_path, track, album=None):
    try:
        if str(dest_path).endswith(".flac"):
            audio = FLAC(dest_path)
            audio["title"] = track.name
            audio["artist"] = ", ".join(a.name for a in track.artists)
            if album:
                audio["album"] = album.name
                audio["albumartist"] = album.artist.name if album.artist else ""
                audio["date"] = str(album.release_date.year) if album.release_date else ""
                audio["tracknumber"] = str(getattr(track, "track_num", ""))
            audio.save()
    except Exception:
        pass

def tidal_download_file(url, dest_path):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")
    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                print(f"\r  Descargando... {downloaded/total*100:.0f}%", end="", flush=True)
    print()

def tidal_download_track(session, track, dest_dir, album=None, num=None, total=None):
    prefix = f"[{num}/{total}] " if num else ""
    artist = ", ".join(a.name for a in track.artists)
    track_num = str(getattr(track, "track_num", 0)).zfill(2)
    filename = sanitize(f"{track_num}. {artist} - {track.name}")

    url = track.get_url()
    ext = "m4a" if "mp4" in url.split("?")[0] else "flac"
    dest_path = dest_dir / f"{filename}.{ext}"

    if dest_path.exists():
        print(f"  {prefix}Ya existe: {filename}.{ext}")
        return

    print(f"\n  {prefix}{artist} - {track.name}")
    tidal_download_file(url, dest_path)

    if album:
        try:
            tidal_embed_cover(dest_path, album.image(1280))
        except Exception:
            pass
    tidal_embed_tags(dest_path, track, album)
    print(f"  ✓ {dest_path.stat().st_size / 1024 / 1024:.1f} MB — {ext.upper()}")

def tidal_download_album(session, album, dest_base):
    year = album.release_date.year if album.release_date else ""
    folder = dest_base / "Tidal" / sanitize(f"{album.artist.name} - {album.name} ({year})")
    folder.mkdir(parents=True, exist_ok=True)
    tracks = list(album.tracks())
    print(f"\n  Descargando album: {album.name} ({len(tracks)} tracks)")
    for i, track in enumerate(tracks, 1):
        tidal_download_track(session, track, folder, album, i, len(tracks))
    print(f"\n  ✓ Album completo en: {folder}")

def menu_tidal(session, download_dir):
    while True:
        print("\n  ── Tidal ─────────────────────────────────────────")
        print("  Calidad: Lossless FLAC / Hi-Res · Requiere cuenta HiFi")
        print()
        print("  1. Buscar artista")
        print("  2. Buscar album")
        print("  3. Buscar track")
        print("  4. Pegar URL de Tidal")
        print("  5. Cerrar sesion (logout)")
        print("  0. Volver")

        choice = ask("\n  Elegí: ", ["0","1","2","3","4","5"])

        if choice == "0":
            break

        elif choice == "5":
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
                print("\n  ✓ Sesion cerrada.")
            else:
                print("\n  No hay sesion activa.")

        elif choice == "1":
            query = input("\n  Nombre del artista: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.artist.Artist], limit=10)
            artists = results.get("artists", [])
            if not artists:
                print("\n  No se encontraron artistas.")
                continue
            artist = pick(artists, lambda a: a.name, "  Artistas encontrados:")
            if not artist:
                continue
            print(f"\n  ¿Qué querés de {artist.name}?")
            print("  1. Albums")
            print("  2. Singles y EPs")
            print("  3. Todo")
            sub = ask("  Elegí: ", ["1","2","3"])
            all_items = []
            if sub in ("1","3"):
                all_items += list(artist.get_albums())
            if sub in ("2","3"):
                all_items += list(artist.get_ep_singles())
            if not all_items:
                print("\n  No se encontraron releases.")
                continue
            selected = pick_multi(
                all_items,
                lambda a: f"{a.name} ({a.release_date.year if a.release_date else '?'}) — {a.num_tracks} tracks",
                "  Releases disponibles:"
            )
            if selected:
                for album in selected:
                    tidal_download_album(session, album, download_dir)

        elif choice == "2":
            query = input("\n  Nombre del album: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.album.Album], limit=10)
            albums = results.get("albums", [])
            if not albums:
                print("\n  No se encontraron albums.")
                continue
            album = pick(albums,
                lambda a: f"{a.name} — {a.artist.name} ({a.release_date.year if a.release_date else '?'})",
                "  Albums encontrados:")
            if album:
                tidal_download_album(session, album, download_dir)

        elif choice == "3":
            query = input("\n  Nombre del track: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.media.Track], limit=15)
            tracks = results.get("tracks", [])
            if not tracks:
                print("\n  No se encontraron tracks.")
                continue
            selected = pick_multi(
                tracks,
                lambda t: f"{t.name} — {', '.join(a.name for a in t.artists)} ({t.album.name if t.album else ''})",
                "  Tracks encontrados:")
            if selected:
                folder = download_dir / "Tidal" / "Singles"
                folder.mkdir(parents=True, exist_ok=True)
                for i, track in enumerate(selected, 1):
                    album = session.album(track.album.id) if track.album else None
                    tidal_download_track(session, track, folder, album, i, len(selected))

        elif choice == "4":
            url = input("\n  Pegá el link de Tidal: ").strip()
            if "track/" in url:
                m = re.search(r"track/(\d+)", url)
                if m:
                    track = session.track(int(m.group(1)))
                    album = session.album(track.album.id) if track.album else None
                    folder = download_dir / "Tidal" / "Singles"
                    folder.mkdir(parents=True, exist_ok=True)
                    tidal_download_track(session, track, folder, album)
            elif "album/" in url:
                m = re.search(r"album/(\d+)", url)
                if m:
                    album = session.album(int(m.group(1)))
                    tidal_download_album(session, album, download_dir)
            elif "playlist/" in url:
                m = re.search(r"playlist/([a-z0-9\-]+)", url)
                if m:
                    playlist = session.playlist(m.group(1))
                    folder = download_dir / "Tidal" / sanitize(playlist.name)
                    folder.mkdir(parents=True, exist_ok=True)
                    tracks = list(playlist.tracks())
                    print(f"\n  Playlist: {playlist.name} — {len(tracks)} tracks")
                    for i, track in enumerate(tracks, 1):
                        album = session.album(track.album.id) if track.album else None
                        tidal_download_track(session, track, folder, album, i, len(tracks))
            else:
                print("\n  URL no reconocida.")

# ─── YOUTUBE ─────────────────────────────────────────────────────────────────

def yt_search(query, limit=10):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        return info.get("entries", [])

def yt_get_formats(url):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    audio_fmts = []
    seen = set()
    for f in sorted(info.get("formats", []), key=lambda x: x.get("abr") or 0, reverse=True):
        if f.get("vcodec") not in (None, "none"):
            continue
        if f.get("acodec") in (None, "none"):
            continue
        abr = int(f.get("abr") or f.get("tbr") or 0)
        codec = f.get("acodec", "?").split(".")[0]
        ext = f.get("ext", "?")
        key = (codec, abr, ext)
        if key not in seen:
            seen.add(key)
            audio_fmts.append({
                "format_id": f["format_id"],
                "ext": ext,
                "codec": codec,
                "abr": abr,
                "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
            })
    return info, audio_fmts[:8]

def yt_download(url, dest_dir, format_id=None):
    import yt_dlp
    has_ffmpeg = check_ffmpeg()
    fmt = format_id if format_id else "bestaudio/best"
    postprocessors = []
    if has_ffmpeg:
        postprocessors += [
            {"key": "FFmpegExtractAudio", "preferredcodec": "flac"},
            {"key": "FFmpegMetadata"},
        ]
    opts = {
        "format": fmt,
        "outtmpl": str(dest_dir / "%(title)s.%(ext)s"),
        "postprocessors": postprocessors,
        "quiet": False,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def menu_youtube(download_dir):
    ensure_installed(["yt-dlp"])

    while True:
        print("\n  ── YouTube ───────────────────────────────────────")
        print("  Catálogo enorme: conciertos, lives, rarezas · Sin cuenta")
        if check_ffmpeg():
            print("  Calidad: hasta ~160kbps Opus → convertido a FLAC")
        else:
            print("  Calidad: mejor audio nativo (opus/m4a) · ffmpeg no encontrado")
        print()
        print("  1. Buscar por nombre")
        print("  2. Pegar URL de YouTube")
        print("  0. Volver")

        choice = ask("\n  Elegí: ", ["0","1","2"])
        if choice == "0":
            break

        url = None
        if choice == "1":
            query = input("\n  Qué buscás (canción, concierto, artista...): ").strip()
            if not query:
                continue
            print("\n  Buscando...")
            results = yt_search(query)
            if not results:
                print("  No se encontró nada.")
                continue
            entry = pick(
                results,
                lambda e: f"{e.get('title','?')}  [{fmt_duration(e.get('duration'))}]  — {e.get('channel') or e.get('uploader','?')}",
                "  Resultados:"
            )
            if not entry:
                continue
            url = f"https://www.youtube.com/watch?v={entry['id']}"

        elif choice == "2":
            url = input("\n  Pegá el link de YouTube: ").strip()
            if not url:
                continue

        print("\n  Obteniendo info del video...")
        try:
            info, fmts = yt_get_formats(url)
        except Exception as e:
            print(f"  Error: {e}")
            continue

        print(f"\n  {info.get('title','?')}  —  {info.get('channel') or info.get('uploader','?')}")
        print(f"  Duración: {fmt_duration(info.get('duration'))}")
        print()

        format_id = None
        if fmts:
            print("  Formatos de audio disponibles:")
            for i, f in enumerate(fmts, 1):
                size = f" (~{f['filesize']/1024/1024:.0f} MB)" if f['filesize'] else ""
                print(f"  {i}. {f['codec'].upper()}  {f['abr']}kbps  .{f['ext']}{size}")
            print("  0. Cancelar")
            print()
            sel = input("  Elegí formato (o Enter para el mejor): ").strip()
            if sel == "0":
                continue
            if sel.isdigit() and 1 <= int(sel) <= len(fmts):
                format_id = fmts[int(sel)-1]["format_id"]

        dest = download_dir / "YouTube"
        dest.mkdir(parents=True, exist_ok=True)
        print()
        yt_download(url, dest, format_id)
        print(f"\n  ✓ Guardado en: {dest}")

# ─── SPOTIFY ─────────────────────────────────────────────────────────────────

def _spotify_exchange_code(code):
    creds = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        },
    )
    r.raise_for_status()
    return r.json()

def _spotify_refresh(refresh_token):
    creds = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    r.raise_for_status()
    data = r.json()
    if "refresh_token" not in data:
        data["refresh_token"] = refresh_token
    return data

def _spotify_save_token(data):
    data["expires_at"] = time.time() + data.get("expires_in", 3600) - 60
    SPOTIFY_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPOTIFY_TOKEN_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_spotify_token():
    # Intentar cargar token guardado
    if SPOTIFY_TOKEN_FILE.exists():
        try:
            with open(SPOTIFY_TOKEN_FILE) as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time():
                return data["access_token"]
            if data.get("refresh_token"):
                print("  Renovando sesión Spotify...")
                refreshed = _spotify_refresh(data["refresh_token"])
                _spotify_save_token(refreshed)
                return refreshed["access_token"]
        except Exception:
            pass

    # OAuth flow completo
    state = secrets.token_urlsafe(16)
    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode({
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "scope": SPOTIFY_SCOPES,
            "state": state,
        })
    )

    code_holder = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if params.get("state", [""])[0] == state and "code" in params:
                code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<h2>Listo! Podés cerrar esta ventana y volver a Fidelity.</h2>"
                )
            else:
                self.send_response(400)
                self.end_headers()
        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 8888), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    print("\n  Abrí el link en el navegador para iniciar sesión en Spotify:")
    print()
    print(f"  {auth_url}")
    print()
    webbrowser.open(auth_url)

    thread.join(timeout=120)
    server.server_close()

    if "code" not in code_holder:
        raise Exception("No se recibió respuesta de Spotify. Intentá de nuevo.")

    token_data = _spotify_exchange_code(code_holder["code"])
    _spotify_save_token(token_data)
    print("  ✓ Sesión Spotify guardada!")
    return token_data["access_token"]

def spotdl_run(args, dest_dir, token=None):
    cmd = [sys.executable, "-m", "spotdl"] + args + [
        "--output", str(dest_dir / "{artist} - {title}.{output-ext}"),
        "--client-id", SPOTIFY_CLIENT_ID,
        "--client-secret", SPOTIFY_CLIENT_SECRET,
    ]
    if token:
        cmd += ["--auth-token", token]
    subprocess.run(cmd)

def menu_spotify(download_dir):
    ensure_installed(["spotdl"])
    if not check_ffmpeg():
        print("\n  Spotify requiere ffmpeg para descargar.")
        print("  Descargalo en: https://ffmpeg.org/download.html")
        input("\n  Enter para volver...")
        return

    try:
        token = get_spotify_token()
    except Exception as e:
        print(f"\n  Error al iniciar sesión en Spotify: {e}")
        input("  Enter para volver...")
        return

    while True:
        print("\n  ── Spotify ───────────────────────────────────────")
        print("  Gran catálogo · Requiere cuenta Spotify")
        print("  Calidad: hasta 320kbps · Metadata de Spotify + audio de YouTube")
        print()
        print("  1. Buscar canción / artista / album")
        print("  2. Pegar URL de Spotify")
        print("  3. Cerrar sesión (logout)")
        print("  0. Volver")

        choice = ask("\n  Elegí: ", ["0","1","2","3"])
        if choice == "0":
            break

        if choice == "3":
            if SPOTIFY_TOKEN_FILE.exists():
                SPOTIFY_TOKEN_FILE.unlink()
                print("\n  ✓ Sesión cerrada.")
            else:
                print("\n  No hay sesión activa.")
            return

        dest = download_dir / "Spotify"
        dest.mkdir(parents=True, exist_ok=True)

        if choice == "1":
            query = input("\n  Qué buscás: ").strip()
            if not query:
                continue
            print()
            spotdl_run(["download", query], dest, token)

        elif choice == "2":
            url = input("\n  Pegá el link de Spotify: ").strip()
            if not url:
                continue
            if "spotify.com" not in url:
                print("  URL no válida.")
                continue
            print()
            spotdl_run(["download", url], dest, token)

        print(f"\n  ✓ Guardado en: {dest}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print_banner()
    check_for_updates()

    cfg = load_config()
    download_dir = get_download_dir(cfg)
    download_dir.mkdir(parents=True, exist_ok=True)

    tidal_session = None

    while True:
        print(f"\n  Descargas → {cfg['download_dir']}")
        print()
        print("  ┌─────────────────────────────────────────────────────────┐")
        print("  │  Plataforma            Calidad          Cuenta          │")
        print("  ├─────────────────────────────────────────────────────────┤")
        print("  │  1. Tidal              Lossless FLAC    Requerida HiFi  │")
        print("  │  2. YouTube            ~160kbps Opus    No necesaria    │")
        print("  │  3. Spotify            320kbps MP3*     Requerida       │")
        print("  │                        *matchea a YouTube               │")
        print("  ├─────────────────────────────────────────────────────────┤")
        print("  │  c. Configuración                                       │")
        print("  │  0. Salir                                               │")
        print("  └─────────────────────────────────────────────────────────┘")

        choice = ask("\n  Elegí: ", ["0","1","2","3","c"])

        if choice == "0":
            print("\n  Chau! Hasta la proxima.")
            break

        elif choice == "c":
            menu_settings(cfg)
            download_dir = get_download_dir(cfg)
            download_dir.mkdir(parents=True, exist_ok=True)

        elif choice == "1":
            if tidal_session is None:
                tidal_session = get_tidal_session(download_dir)
            menu_tidal(tidal_session, download_dir)

        elif choice == "2":
            menu_youtube(download_dir)

        elif choice == "3":
            menu_spotify(download_dir)
            # el token se guarda en archivo, se recarga solo la próxima vez

if __name__ == "__main__":
    main()
