import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import subprocess
import shutil
import json
import re

__version__ = "1.4.2"
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
import logging
from pathlib import Path
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

logging.basicConfig(level=logging.WARNING, format="  %(message)s")

def _setup_tw_logging():
    """Configura logging de tidal-wave para ver INFO y WARNING."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("  [tw] %(message)s"))
    root = logging.getLogger("tidal_wave")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    root.propagate = False

def _auto_extract_tidal_token():
    """Extrae el token del Tidal desktop automaticamente desde IndexedDB.

    Funciona en Windows con la app de Tidal instalada.
    Guarda el token en el formato que espera tidal-wave.
    """
    import re, base64, json, time
    from pathlib import Path

    token_file = Path.home() / ".config" / "tidal-wave" / "windows-tidal.token"
    idb_dir = Path.home() / "AppData" / "Roaming" / "TIDAL" / "IndexedDB" / \
              "https_desktop.tidal.com_0.indexeddb.leveldb"

    if not idb_dir.exists():
        return False

    best_token = None
    best_exp = 0

    # Buscar en .log y .ldb
    for pattern in ("*.log", "*.ldb"):
        for f in idb_dir.glob(pattern):
            try:
                data = f.read_bytes().decode("utf-8", errors="ignore")
                for t in re.findall(
                    r'accessToken":"(eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',
                    data
                ):
                    try:
                        payload = t.split(".")[1]
                        payload += "=" * (4 - len(payload) % 4)
                        decoded = json.loads(base64.b64decode(payload))
                        exp = decoded.get("exp", 0)
                        cid = decoded.get("cid", "?")
                        if exp > time.time() and exp > best_exp:
                            best_token = t
                            best_exp = exp
                            best_cid = cid
                    except Exception:
                        continue
            except Exception:
                continue

    if not best_token:
        return False

    print(f" [cid={best_cid}]", end="", flush=True)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_data = json.dumps({"access_token": best_token})
    token_file.write_bytes(base64.b64encode(token_data.encode("utf-8")))
    return True


def _patch_tidal_wave():
    """Parchea build_urls y download_url de tidal-wave."""
    import re as _re
    from tidal_wave.dash import XMLDASHManifest
    from tidal_wave.track import Track as TWTrack

    # ── Fix 1: loop infinito en build_urls ───────────────────────────────────
    def _fixed_build_urls(self, session):
        if len(self.segment_timeline.s) == 0:
            return None

        def sub_n(n, p=r"\$Number\$", s=self.media):
            return _re.sub(p, str(n), s)

        try:
            r = next(S.r for S in self.segment_timeline.s)
        except StopIteration:
            r = None

        if r is None:
            urls_list = [self.initialization]
            number = 1
            while number < 10000:
                try:
                    code = session.head(url=sub_n(number), timeout=10).status_code
                except Exception:
                    break
                if code >= 400:
                    break
                urls_list.append(sub_n(number))
                number += 1
            return urls_list

        urls_list = [self.initialization] + [sub_n(i) for i in range(self.startNumber, r + 1)]
        number = r + 1
        while number < 10000:
            try:
                code = session.head(url=sub_n(number), timeout=10).status_code
            except Exception:
                break
            if code >= 400:
                break
            urls_list.append(sub_n(number))
            number += 1
        return urls_list

    XMLDASHManifest.build_urls = _fixed_build_urls

    # ── Fix 2: barra de progreso en download_urls (DASH segments) ────────────
    def _download_urls_with_progress(self, session):
        from tidal_wave.utils import temporary_file
        import shutil, ffmpeg
        from pathlib import Path as _Path
        from Crypto.Cipher import AES
        from Crypto.Util import Counter

        total = len(self.urls)
        with temporary_file(suffix=".mp4") as ntf:
            for i, u in enumerate(self.urls, 1):
                pct = i / total * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                print(f"\r  [{bar}] {pct:5.1f}%  ({i}/{total})", end="", flush=True)
                with session.get(url=u, headers=self.download_headers, params=self.download_params) as resp:
                    if not resp.ok:
                        print()
                        return None
                    ntf.write(resp.content)
            print(f"\r  [{'█'*20}] 100.0%  — procesando...      ", flush=True)
            ntf.seek(0)

            if (self.manifest.key is not None) and (self.manifest.nonce is not None):
                counter = Counter.new(64, prefix=self.manifest.nonce, initial_value=0)
                decryptor = AES.new(self.manifest.key, AES.MODE_CTR, counter=counter)
                with temporary_file(suffix=".mp4") as f_dec:
                    f_dec.write(decryptor.decrypt(_Path(ntf.name).read_bytes()))
                    if self.codec == "flac":
                        ffmpeg.input(f_dec.name, hide_banner=None, y=None).output(
                            self.absolute_outfile, acodec="copy", loglevel="quiet").run()
                    elif self.codec == "m4a":
                        shutil.copyfile(f_dec.name, self.outfile)
            else:
                if self.codec == "flac":
                    ffmpeg.input(ntf.name, hide_banner=None, y=None).output(
                        self.absolute_outfile, acodec="copy", loglevel="quiet").run()
                elif self.codec == "m4a":
                    shutil.copyfile(ntf.name, self.outfile)

            print(f"\r  [{'█'*20}] 100.0%  ✓                         ")
            return self.outfile

    TWTrack.download_urls = _download_urls_with_progress

    # ── Fix 3: barra de progreso en download_url (BTS/single URL) ────────────
    _orig_download_url = TWTrack.download_url

    def _download_url_with_progress(self, session, out_dir):
        from tidal_wave.requesting import fetch_content_length, http_request_range_headers
        from tidal_wave.utils import temporary_file
        import shutil, ffmpeg

        range_size = 1024 * 1024
        content_length = fetch_content_length(session=session, url=self.urls[0])
        if content_length == 0:
            return None

        range_headers = list(http_request_range_headers(
            content_length=content_length,
            range_size=range_size,
            return_tuple=False,
        ))
        total_chunks = len(range_headers)

        with temporary_file(suffix=".mp4") as ntf:
            for i, rh in enumerate(range_headers, 1):
                pct = i / total_chunks * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                print(f"\r  [{bar}] {pct:5.1f}%  ({i}/{total_chunks})", end="", flush=True)
                with session.get(
                    self.urls[0],
                    params=self.download_params,
                    headers={"Range": rh},
                ) as rr:
                    if not rr.ok:
                        print()
                        return None
                    ntf.write(rr.content)
            print(f"\r  [{'█'*20}] 100.0%  — procesando...", flush=True)
            ntf.seek(0)

            from pathlib import Path as _Path
            from Crypto.Cipher import AES
            from Crypto.Util import Counter

            if (self.manifest.key is not None) and (self.manifest.nonce is not None):
                counter = Counter.new(64, prefix=self.manifest.nonce, initial_value=0)
                decryptor = AES.new(self.manifest.key, AES.MODE_CTR, counter=counter)
                with temporary_file(suffix=".mp4") as f_dec:
                    f_dec.write(decryptor.decrypt(_Path(ntf.name).read_bytes()))
                    if self.codec == "flac":
                        ffmpeg.input(f_dec.name, hide_banner=None, y=None).output(
                            self.absolute_outfile, acodec="copy", loglevel="quiet"
                        ).run()
                    elif self.codec == "m4a":
                        shutil.copyfile(f_dec.name, self.outfile)
            else:
                if self.codec == "flac":
                    ffmpeg.input(ntf.name, hide_banner=None, y=None).output(
                        self.absolute_outfile, acodec="copy", loglevel="quiet"
                    ).run()
                elif self.codec == "m4a":
                    shutil.copyfile(ntf.name, self.outfile)

            print(f"\r  [{'█'*20}] 100.0%  ✓                    ")
            return self.outfile

    TWTrack.download_url = _download_url_with_progress

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
    print("  · Para YouTube también necesitás ffmpeg:")
    print("    https://ffmpeg.org/download.html")
    print()
    print("  Cuentas necesarias por plataforma:")
    print("  · Tidal   → Cuenta HiFi o HiFi Plus")
    print("  · YouTube → Sin cuenta")
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

_tw_session = None

def get_tidal_session(download_dir):
    first_time = not SESSION_FILE.exists()
    if first_time:
        print_setup_instructions(download_dir)

    config = tidalapi.Config(quality=tidalapi.Quality.hi_res_lossless)
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

def get_tw_session():
    """Sesion de tidal-wave para descarga Hi-Res 24-bit."""
    global _tw_session
    if _tw_session is not None:
        return _tw_session
    ensure_installed(["tidal-wave", "cachecontrol"])
    from tidal_wave.login import login as tw_login
    from tidal_wave.media import AudioFormat as TWAudioFormat
    from cachecontrol import CacheControl
    _patch_tidal_wave()

    # Siempre re-extraer token del Tidal desktop para asegurarse que no expiró
    token_file = Path.home() / ".config" / "tidal-wave" / "windows-tidal.token"
    print()
    print("  Buscando token Hi-Res del Tidal desktop...", end="", flush=True)
    if _auto_extract_tidal_token():
        print(" ✓ encontrado!")
    else:
        print(" no encontrado.")
        if not token_file.exists():
            print()
            print("  ── Autenticación Hi-Res (tidal-wave) ────────────────")
            print("  Seguí las instrucciones en pantalla.")
            print()

    session, _ = tw_login(audio_format=TWAudioFormat.hi_res)
    _tw_session = CacheControl(session)
    print("  ✓ Sesion Hi-Res lista!")
    return _tw_session

def tidal_download_track(session, track, dest_dir, album=None, num=None, total=None):
    from tidal_wave.track import Track as TWTrack
    from tidal_wave.media import AudioFormat as TWAudioFormat

    prefix = f"[{num}/{total}] " if num else ""
    artist = ", ".join(a.name for a in track.artists)
    print(f"\n  {prefix}{artist} - {track.name}")
    print("  Descargando...", flush=True)

    tw_session = get_tw_session()
    _setup_tw_logging()
    tw_track = TWTrack(track_id=track.id)
    try:
        result = tw_track.get(
            session=tw_session,
            audio_format=TWAudioFormat.hi_res,
            out_dir=dest_dir,
            no_extra_files=True,
        )
        if result:
            size = result.stat().st_size / 1024 / 1024
            print(f"  ✓ {size:.1f} MB — {result.suffix.lstrip('.').upper()}")
            print(f"  → {result}")
        else:
            print("  ✗ No se pudo descargar.")
    except Exception as e:
        print(f"  ✗ Error: {e}")

def tidal_download_album(session, album, dest_base):
    from tidal_wave.album import Album as TWAlbum
    from tidal_wave.media import AudioFormat as TWAudioFormat

    folder = dest_base / "Tidal"
    folder.mkdir(parents=True, exist_ok=True)

    print(f"\n  Descargando album: {album.name}")
    print("  (tidal-wave mostrará el progreso track a track)\n")
    tw_session = get_tw_session()
    _setup_tw_logging()
    try:
        tw_album = TWAlbum(album_id=album.id)
        tw_album.get(
            session=tw_session,
            audio_format=TWAudioFormat.hi_res,
            out_dir=folder,
            no_extra_files=True,
        )
        print(f"\n  ✓ Album descargado en: {folder}")
    except Exception as e:
        print(f"\n  ✗ Error: {e}")

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
            def _release_label(a):
                q = getattr(a, "audio_quality", None) or ""
                q_tag = ""
                if "HI_RES" in q.upper():
                    q_tag = " [24-bit Hi-Res]"
                elif "LOSSLESS" in q.upper():
                    q_tag = " [16-bit FLAC]"
                return f"{a.name} ({a.release_date.year if a.release_date else '?'}) — {a.num_tracks} tracks{q_tag}"
            selected = pick_multi(
                all_items,
                _release_label,
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
            def _album_quality_label(a):
                q = getattr(a, "audio_quality", None) or ""
                q_tag = ""
                if "HI_RES" in q.upper():
                    q_tag = " [24-bit Hi-Res]"
                elif "LOSSLESS" in q.upper():
                    q_tag = " [16-bit FLAC]"
                return f"{a.name} — {a.artist.name} ({a.release_date.year if a.release_date else '?'}){q_tag}"
            albums_sorted = sorted(
                albums,
                key=lambda a: 0 if "HI_RES" in (getattr(a, "audio_quality", "") or "").upper() else 1
            )
            album = pick(albums_sorted, _album_quality_label, "  Albums encontrados (ordenados por calidad):")
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

        best = fmts[0] if fmts else None
        if best:
            size = f" (~{best['filesize']/1024/1024:.0f} MB)" if best['filesize'] else ""
            print(f"  Calidad: {best['codec'].upper()}  {best['abr']}kbps  .{best['ext']}{size}  ★ mejor disponible")
        print()

        dest = download_dir / "YouTube"
        dest.mkdir(parents=True, exist_ok=True)
        format_id = best["format_id"] if best else None
        yt_download(url, dest, format_id)
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
        print("  ├─────────────────────────────────────────────────────────┤")
        print("  │  c. Configuración                                       │")
        print("  │  0. Salir                                               │")
        print("  └─────────────────────────────────────────────────────────┘")

        choice = ask("\n  Elegí: ", ["0","1","2","c"])

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

if __name__ == "__main__":
    main()
