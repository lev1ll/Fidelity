import re
import sys
from pathlib import Path

from ui import (
    console, menu_interactive, print_info_box, print_error_box,
    print_album_progress, print_track_downloading, show_download_summary,
)
from utils import (
    ensure_installed, _copy_file_safe, _setup_tw_logging,
    sanitize, fmt_duration, ask, pick, pick_multi, print_setup_instructions,
)
from config import SESSION_FILE

_tw_session = None

_TIDAL_VIDEO_QUALITIES = [
    ("Alta",  "1080p", "high"),
    ("Media",  "720p", "medium"),
    ("Baja",   "480p", "low"),
]

# ─── Token extraction ─────────────────────────────────────────────────────────

def _auto_extract_tidal_token():
    """Extrae el token del Tidal desktop automaticamente desde IndexedDB."""
    import base64, json, time

    token_file = Path.home() / "AppData" / "Local" / "tidal-wave" / "android-tidal.token"

    possible_dirs = [
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "IndexedDB" / "https_desktop.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Local"   / "TIDAL" / "IndexedDB" / "https_desktop.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "IndexedDB" / "https_app.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Local"   / "TIDAL" / "IndexedDB" / "https_app.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "Local Storage" / "leveldb",
        Path.home() / "AppData" / "Local"   / "TIDAL" / "Local Storage" / "leveldb",
    ]

    # MS Store: búsqueda dinámica de paquetes TIDAL
    packages_dir = Path.home() / "AppData" / "Local" / "Packages"
    if packages_dir.exists():
        for pkg in packages_dir.glob("*TIDAL*"):
            for variant in [
                "https_desktop.tidal.com_0.indexeddb.leveldb",
                "https_app.tidal.com_0.indexeddb.leveldb",
            ]:
                possible_dirs.append(pkg / "LocalCache" / "Local" / "TIDAL" / "IndexedDB" / variant)
            possible_dirs.append(pkg / "LocalCache" / "Local" / "TIDAL" / "Local Storage" / "leveldb")

    best_token = None
    best_exp = 0
    best_cid = "?"
    found_dirs = []
    skipped_locked = 0

    patterns = [
        r'"accessToken"\s*:\s*"(eyJ[A-Za-z0-9_\-\.]+)"',
        r"'accessToken'\s*:\s*'(eyJ[A-Za-z0-9_\-\.]+)'",
        r'accessToken"\s*:\s*"(eyJ[A-Za-z0-9_\-\.]+)',
        r'"access_token"\s*:\s*"(eyJ[A-Za-z0-9_\-\.]+)"',
        r'(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})',
    ]

    for idb_dir in possible_dirs:
        if not idb_dir.exists():
            continue

        found_dirs.append(str(idb_dir))

        try:
            search_paths = list(idb_dir.glob("**/*")) if idb_dir.is_dir() else [idb_dir]
        except Exception:
            continue

        for f in search_paths:
            if f.is_dir():
                continue
            if f.suffix.lower() not in (".log", ".ldb", ""):
                continue
            try:
                if f.stat().st_size > 5 * 1024 * 1024:
                    continue
            except Exception:
                continue

            tmp_path = _copy_file_safe(f)
            read_path = Path(tmp_path) if tmp_path else None

            if read_path is None:
                skipped_locked += 1
                read_path = f

            try:
                try:
                    data = read_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    data = read_path.read_bytes().decode("utf-8", errors="ignore")

                for pattern in patterns:
                    matches = re.findall(pattern, data)
                    for t in matches:
                        if not t.startswith("eyJ"):
                            continue
                        try:
                            parts = t.split(".")
                            if len(parts) != 3:
                                continue
                            payload = parts[1]
                            payload += "=" * (4 - len(payload) % 4)
                            try:
                                decoded = json.loads(base64.b64decode(payload))
                            except Exception:
                                continue
                            exp = decoded.get("exp", 0)
                            cid = decoded.get("cid", "?")
                            if exp > time.time() and exp > best_exp:
                                best_token = t
                                best_exp = exp
                                best_cid = cid
                        except Exception:
                            continue
            except Exception:
                pass
            finally:
                if tmp_path:
                    try:
                        Path(tmp_path).unlink()
                    except Exception:
                        pass

    if not best_token:
        if found_dirs:
            print(f"\n  ℹ Carpetas buscadas: {len(found_dirs)}")
            for d in found_dirs:
                print(f"    · {d}")
            if skipped_locked:
                print(f"  ⚠ {skipped_locked} archivo(s) no pudieron copiarse (posiblemente bloqueados por el SO)")
        return False

    print(f" [cid={best_cid}]", end="", flush=True)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    import json as _json, base64 as _b64
    token_data = _json.dumps({"access_token": best_token})
    token_file.write_bytes(_b64.b64encode(token_data.encode("utf-8")))
    return True

# ─── tidal-wave patches ───────────────────────────────────────────────────────

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
    _G = "\033[92m"   # verde brillante
    _C = "\033[96m"   # cyan
    _Y = "\033[93m"   # amarillo
    _D = "\033[90m"   # gris oscuro
    _R = "\033[0m"    # reset

    def _download_urls_with_progress(self, session):
        import threading
        from tidal_wave.utils import temporary_file
        import shutil, ffmpeg
        from pathlib import Path as _Path
        from Crypto.Cipher import AES
        from Crypto.Util import Counter

        show_bar = threading.current_thread() is threading.main_thread()
        total = len(self.urls)

        with temporary_file(suffix=".mp4") as ntf:
            for i, u in enumerate(self.urls, 1):
                if show_bar:
                    pct = i / total * 100
                    filled = int(pct / 5)
                    bar = f"{_G}{'█' * filled}{_D}{'░' * (20 - filled)}{_R}"
                    print(f"\r  [{bar}] {_C}{pct:5.1f}%{_R}  {_Y}({i}/{total}){_R}", end="", flush=True)
                with session.get(url=u, headers=self.download_headers, params=self.download_params) as resp:
                    if not resp.ok:
                        if show_bar:
                            print()
                        return None
                    ntf.write(resp.content)

            if show_bar:
                print(f"\r  [{_G}{'█'*20}{_R}] {_C}100.0%{_R}  {_Y}procesando...{_R}      ", flush=True)
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

            if show_bar:
                print(f"\r  [{_G}{'█'*20}{_R}] {_G}✓ listo{_R}                              ")
            return self.outfile

    TWTrack.download_urls = _download_urls_with_progress

    # ── Fix 3: barra de progreso en download_url (BTS/single URL) ────────────
    def _download_url_with_progress(self, session, out_dir):
        import threading
        from tidal_wave.requesting import fetch_content_length, http_request_range_headers
        from tidal_wave.utils import temporary_file
        import shutil, ffmpeg

        show_bar = threading.current_thread() is threading.main_thread()
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
                if show_bar:
                    pct = i / total_chunks * 100
                    filled = int(pct / 5)
                    bar = f"{_G}{'█' * filled}{_D}{'░' * (20 - filled)}{_R}"
                    print(f"\r  [{bar}] {_C}{pct:5.1f}%{_R}  {_Y}({i}/{total_chunks}){_R}", end="", flush=True)
                with session.get(
                    self.urls[0],
                    params=self.download_params,
                    headers={"Range": rh},
                ) as rr:
                    if not rr.ok:
                        if show_bar:
                            print()
                        return None
                    ntf.write(rr.content)

            if show_bar:
                print(f"\r  [{_G}{'█'*20}{_R}] {_C}100.0%{_R}  {_Y}procesando...{_R}", flush=True)
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

            if show_bar:
                print(f"\r  [{_G}{'█'*20}{_R}] {_G}✓ listo{_R}                         ")
            return self.outfile

    TWTrack.download_url = _download_url_with_progress

    # ── Fix 4: estructura de carpetas simple artista/album sin [id] [año] ────
    def _simple_album_dir(self, out_dir):
        import re as _re2
        def _clean(s):
            return _re2.sub(r'[<>:"/\\|?*]', '_', str(s).replace("..", "").replace("/", " and ")).strip()

        artist = _clean(self.album.artist.name) if hasattr(self, 'album') and self.album else "Unknown"
        album  = _clean(self.album.name)        if hasattr(self, 'album') and self.album else "Unknown"

        self.album_dir = out_dir / artist / album
        self.album_dir.mkdir(parents=True, exist_ok=True)
        self.cover_path = self.album_dir / "cover.jpg"

        if hasattr(self.album, 'number_of_volumes') and self.album.number_of_volumes > 1:
            volume = f"Volume {self.metadata.volume_number}"
            (self.album_dir / volume).mkdir(parents=True, exist_ok=True)

    TWTrack.set_album_dir = _simple_album_dir

# ─── Sessions ─────────────────────────────────────────────────────────────────

def get_tidal_session(download_dir):
    import tidalapi
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
    """Sesion de tidal-wave para descarga Hi-Res 24-bit usando token del Tidal desktop."""
    global _tw_session
    if _tw_session is not None:
        return _tw_session

    ensure_installed(["tidal-wave", "cachecontrol"])
    import time
    _setup_tw_logging()
    _patch_tidal_wave()

    print()
    print("  Buscando token Hi-Res del Tidal desktop...", end="", flush=True)

    found = False
    for attempt in range(3):
        if _auto_extract_tidal_token():
            print(" ✓ encontrado!")
            found = True
            break
        if attempt < 2:
            print(".", end="", flush=True)
            time.sleep(1)

    if not found:
        print(" no encontrado.")
        print()
        print("  ✗ No se pudo extraer token Hi-Res del Tidal desktop.")
        print("  Asegúrate de:")
        print("    • Tener la app Tidal instalada y abierta")
        print("    • Estar logueado con cuenta HiFi/HiFi Plus")
        print("    • Haber descargado al menos una canción Hi-Res")
        print()
        raise RuntimeError("Token Hi-Res no disponible")

    try:
        from tidal_wave.login import login_android
        session = login_android()
        if session is None:
            raise RuntimeError("Sesión Hi-Res inválida")
        _tw_session = session
        print("  ✓ Sesion Hi-Res lista!")
        return _tw_session
    except Exception as e:
        print(f"  ✗ Error en sesión Hi-Res: {e}")
        print("  Intenta cerrar sesión (logout) y loguearte nuevamente en Tidal desktop.")
        raise

# ─── Downloads ────────────────────────────────────────────────────────────────

def _probe_albums_quality(session, albums):
    """Obtiene bitdepth y sample_rate del primer track de cada álbum via tidalapi.
    Corre en paralelo. Devuelve dict {album_id: (bit_depth, sample_rate)}.
    """
    from concurrent.futures import ThreadPoolExecutor

    quality = {}

    def _probe_one(album):
        try:
            track = next(iter(album.tracks()), None)
            if track is None:
                return album.id, None, None
            bd = getattr(track, 'bit_depth', None)
            sr = getattr(track, 'sample_rate', None)
            if bd:
                return album.id, int(bd), int(sr) if sr else None
        except Exception:
            pass
        return album.id, None, None

    with ThreadPoolExecutor(max_workers=6) as ex:
        for aid, bd, sr in ex.map(_probe_one, albums):
            if bd:
                quality[aid] = (bd, sr)

    return quality


def _read_file_quality(filepath):
    """Lee bitdepth y sample_rate del archivo descargado con mutagen."""
    try:
        from pathlib import Path as _P
        p = _P(filepath)
        if p.suffix.lower() == ".flac":
            import mutagen.flac
            audio = mutagen.flac.FLAC(str(p))
            bd = audio.info.bits_per_sample
            sr = audio.info.sample_rate
            return bd, sr
        elif p.suffix.lower() in (".m4a", ".mp4"):
            import mutagen.mp4
            audio = mutagen.mp4.MP4(str(p))
            sr = audio.info.sample_rate
            return None, sr
    except Exception:
        pass
    return None, None


def tidal_download_track(session, track, dest_dir, album=None, num=None, total=None):
    from tidal_wave.track import Track as TWTrack
    from tidal_wave.media import AudioFormat as TWAudioFormat

    prefix = f"[{num}/{total}] " if num else ""
    artist = ", ".join(a.name for a in track.artists)
    print(f"\n  {prefix}{artist} - {track.name}")
    print("  Descargando...", flush=True)

    tw_track = TWTrack(track_id=track.id)
    try:
        result = tw_track.get(
            session=session,
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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
    )
    import threading
    import time

    folder = dest_base / "Tidal"
    folder.mkdir(parents=True, exist_ok=True)

    # ── Header del álbum ──────────────────────────────────────────────────────
    q = (getattr(album, "audio_quality", "") or "").upper()
    if "HI_RES" in q:
        q_label = "[bold red]24-bit Hi-Res FLAC[/bold red]"
    elif "LOSSLESS" in q:
        q_label = "[bold green1]16-bit FLAC[/bold green1]"
    else:
        q_label = f"[yellow]{q or '?'}[/yellow]"
    year = album.release_date.year if album.release_date else "?"
    artist_name = album.artist.name if album.artist else "?"

    console.print()
    console.print(f"[bold hot_pink]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold hot_pink]")
    console.print(f"  [bold gold1]💿 {album.name}[/bold gold1]  [dim]({year})[/dim]  ·  [medium_purple]{artist_name}[/medium_purple]  ·  {q_label}  ·  [cyan]{album.num_tracks} tracks[/cyan]")
    console.print(f"[bold hot_pink]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold hot_pink]")
    console.print()

    tw_session = get_tw_session()
    start_time = time.time()
    downloaded = 0
    errors = 0
    total_size_mb = 0.0
    _lock = threading.Lock()

    try:
        tw_album = TWAlbum(album_id=album.id)
        tw_album.set_metadata(tw_session)
        tw_album.set_tracks(tw_session)
        tracks = list(tw_album.tracks)
        total_tracks = len(tracks)

        with Progress(
            SpinnerColumn(spinner_name="dots", style="hot_pink"),
            TextColumn("{task.description}", justify="left"),
            BarColumn(
                bar_width=22,
                style="deep_sky_blue1",
                complete_style="green1",
                finished_style="green1",
                pulse_style="hot_pink",
            ),
            TextColumn("[cyan]{task.percentage:>5.1f}%[/cyan]"),
            console=console,
            transient=False,
        ) as progress:

            def download_single_track(track_info):
                nonlocal total_size_mb, downloaded, errors
                track, num = track_info

                artist = ", ".join(a.name for a in track.artists) if track.artists else "?"
                name = track.name
                label = f"[deep_sky_blue1][{num:>2}/{total_tracks}][/deep_sky_blue1] [gold1]{name[:32]}[/gold1]  [dim]{artist[:20]}[/dim]"

                with _lock:
                    tid = progress.add_task(label, total=None)

                try:
                    from tidal_wave.track import Track as TWTrack
                    tw_track = TWTrack(track_id=track.id)
                    result = tw_track.get(
                        session=tw_session,
                        audio_format=TWAudioFormat.hi_res,
                        out_dir=folder,
                        no_extra_files=True,
                    )

                    if result:
                        size_mb = result.stat().st_size / 1024 / 1024
                        bd, sr = _read_file_quality(result)
                        if bd and sr:
                            detail = f"[bold red]{bd}-bit[/bold red] [dim]/[/dim] [bold cyan]{sr/1000:.1f} kHz[/bold cyan]  [dim]{size_mb:.1f} MB[/dim]"
                        else:
                            detail = f"[dim]{size_mb:.1f} MB[/dim]"
                        done_label = f"[green1]✓[/green1] [deep_sky_blue1][{num:>2}/{total_tracks}][/deep_sky_blue1] [gold1]{name[:32]}[/gold1]  {detail}"
                        with _lock:
                            progress.update(tid, total=1, completed=1, description=done_label)
                            total_size_mb += size_mb
                            downloaded += 1
                        return (True, size_mb)
                    else:
                        fail_label = f"[red]✗[/red] [deep_sky_blue1][{num:>2}/{total_tracks}][/deep_sky_blue1] [gold1]{name[:32]}[/gold1]  [red]no descargado[/red]"
                        with _lock:
                            progress.update(tid, total=1, completed=1, description=fail_label)
                            errors += 1
                        return (False, 0)

                except Exception as e:
                    err_label = f"[red]✗[/red] [deep_sky_blue1][{num:>2}/{total_tracks}][/deep_sky_blue1] [gold1]{name[:32]}[/gold1]  [red]{str(e)[:40]}[/red]"
                    with _lock:
                        progress.update(tid, total=1, completed=1, description=err_label)
                        errors += 1
                    return (False, 0)

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(download_single_track, (t, i)): i
                    for i, t in enumerate(tracks, 1)
                }
                for future in as_completed(futures):
                    future.result()

        duration = time.time() - start_time
        artist_folder = sanitize(album.artist.name) if album.artist else "Unknown"
        album_folder  = sanitize(album.name)
        show_download_summary(downloaded, total_size_mb, duration, success_count=downloaded, error_count=errors)
        console.print(f"[cyan]📁 Guardado en:[/cyan] {folder / artist_folder / album_folder}\n")

    except Exception as e:
        print_error_box("Error en descarga", str(e))

def tidal_download_video(session, video, dest_dir):
    import yt_dlp
    import tidalapi
    ensure_installed(["yt-dlp"])
    print(f"\n  {video.name}  —  {video.artist.name if video.artist else '?'}")
    print(f"  Duración: {fmt_duration(video.duration)}")
    print()
    print("  Calidad de video:")
    for i, (label, res, _) in enumerate(_TIDAL_VIDEO_QUALITIES, 1):
        print(f"  {i}. {label:<6}  {res}")
    print("  0. Cancelar")

    sel = ask("\n  Elegí: ", ["0", "1", "2", "3"])
    if sel == "0":
        return

    _, _, quality_key = _TIDAL_VIDEO_QUALITIES[int(sel) - 1]
    orig_quality = session.config.video_quality
    session.config.video_quality = getattr(tidalapi.VideoQuality, quality_key)
    try:
        m3u8_url = video.get_url()
    except Exception as e:
        print(f"  ✗ No se pudo obtener la URL: {e}")
        session.config.video_quality = orig_quality
        return
    session.config.video_quality = orig_quality

    dest_dir.mkdir(parents=True, exist_ok=True)
    title = sanitize(f"{video.artist.name if video.artist else 'Unknown'} - {video.name}")
    opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": str(dest_dir / f"{title}.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": True,
    }
    print()
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([m3u8_url])
    print(f"\n  ✓ Guardado en: {dest_dir}")

# ─── Menu ─────────────────────────────────────────────────────────────────────

def menu_tidal(session, download_dir):
    import tidalapi
    while True:
        console.print("\n[bold deep_sky_blue1]── Tidal ──────────────────────────────[/bold deep_sky_blue1]")
        console.print("[gold1]Calidad: FLAC Lossless 16-bit / Hi-Res 24-bit[/gold1]")
        console.print("[cyan1]  • Requiere: Tidal app abierta + HiFi/HiFi Plus[/cyan1]")
        console.print("[medium_purple]  • Token: se extrae automático (sin navegador)[/medium_purple]\n")

        menu_options = [
            "🔍 Buscar artista",
            "💿 Buscar album",
            "🎵 Buscar track",
            "📹 Buscar video",
            "🔗 Pegar URL de Tidal",
            "🚪 Cerrar sesión (logout)",
            "⬅️  Volver"
        ]

        choice = menu_interactive(
            "MENÚ TIDAL",
            menu_options,
            "Selecciona una opción"
        )

        if choice == 6:
            break

        elif choice == 5:  # Logout
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
                print_info_box("Sesión cerrada", "Token eliminado. Inicia sesion de nuevo en la proxima vez.")
            else:
                print("  No hay sesion activa.")

        elif choice == 0:  # Buscar artista
            query = input("\n  🔍 Nombre del artista: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.artist.Artist], limit=10)
            artists = results.get("artists", [])
            if not artists:
                console.print(f"\n  [yellow]No se encontraron artistas para «{query}».[/yellow]")
                # Fallback: buscar álbumes y tracks con el mismo nombre
                console.print("  [cyan]Buscando álbumes y tracks con ese nombre...[/cyan]")
                fb_results = session.search(query, models=[tidalapi.album.Album, tidalapi.media.Track], limit=8)
                fb_albums = fb_results.get("albums", [])
                fb_tracks = fb_results.get("tracks", [])
                if not fb_albums and not fb_tracks:
                    console.print("  [red]Sin resultados.[/red]  Probá con el nombre del álbum o pegá la URL de Tidal.")
                    continue
                # Mostrar álbumes encontrados
                if fb_albums:
                    console.print(f"\n  [bold]Álbumes encontrados ({len(fb_albums)}):[/bold]")
                    def _fb_album_label(a):
                        q = getattr(a, "audio_quality", None) or ""
                        q_tag = " 🔴 [24-bit Hi-Res]" if "HI_RES" in q.upper() else (" 🟢 [16-bit FLAC]" if "LOSSLESS" in q.upper() else "")
                        return f"{a.name} — {a.artist.name} ({a.release_date.year if a.release_date else '?'}){q_tag}"
                    fb_selected = pick_multi(fb_albums, _fb_album_label, "💿 Álbumes encontrados:")
                    if fb_selected:
                        for album in fb_selected:
                            tidal_download_album(session, album, download_dir)
                # Mostrar tracks encontrados si no había álbumes
                elif fb_tracks:
                    console.print(f"\n  [bold]Tracks encontrados ({len(fb_tracks)}):[/bold]")
                    fb_t_selected = pick_multi(
                        fb_tracks,
                        lambda t: f"{t.name} — {', '.join(a.name for a in t.artists)} ({t.album.name if t.album else ''})",
                        "🎵 Tracks encontrados:"
                    )
                    if fb_t_selected:
                        folder = download_dir / "Tidal" / "Singles"
                        folder.mkdir(parents=True, exist_ok=True)
                        for i, track in enumerate(fb_t_selected, 1):
                            album = session.album(track.album.id) if track.album else None
                            tidal_download_track(session, track, folder, album, i, len(fb_t_selected))
                continue
            artist = pick(artists, lambda a: a.name, "🎤 Artistas encontrados:")
            if not artist:
                continue

            release_type_options = [
                "💿 Albums",
                "🎸 Singles y EPs",
                "🎵 Todo (Albums + Singles + EPs)"
            ]
            release_choice = menu_interactive(
                f"¿Qué querés de {artist.name}?",
                release_type_options,
                "Selecciona el tipo de release"
            )

            all_items = []
            if release_choice in (0, 2):
                all_items += list(artist.get_albums())
            if release_choice in (1, 2):
                all_items += list(artist.get_ep_singles())

            if not all_items:
                print_info_box("Sin resultados", "No se encontraron releases para este artista.")
                continue

            # ── Deduplicar: mismo nombre → quedarse con la mejor calidad ────────
            def _quality_rank(a):
                q = (getattr(a, "audio_quality", "") or "").upper()
                if "HI_RES" in q:
                    return 0
                if "LOSSLESS" in q:
                    return 1
                return 2

            from collections import defaultdict as _dd
            _name_groups = _dd(list)
            for _item in all_items:
                _name_groups[_item.name.lower().strip()].append(_item)

            deduped = []
            for _group in _name_groups.values():
                best = min(_group, key=_quality_rank)
                best._dup_count = len(_group) - 1
                deduped.append(best)

            import datetime as _dt
            deduped.sort(
                key=lambda a: a.release_date or _dt.date.min,
                reverse=True
            )

            if len(deduped) < len(all_items):
                removed = len(all_items) - len(deduped)
                console.print(f"  [dim]({removed} versión/es duplicada/s ocultada/s — se muestra la mejor calidad de cada título)[/dim]")

            console.print("  [dim]Verificando calidad de audio...[/dim]", end="\r")
            _q_data = _probe_albums_quality(session, deduped)
            console.print("  " + " " * 45, end="\r")

            def _release_label(a):
                qc = _q_data.get(a.id)
                if qc:
                    bd, sr = qc
                    sr_str = f" / {sr/1000:.1f} kHz" if sr else ""
                    q_tag = f" 🔴 [{bd}-bit{sr_str}]"
                else:
                    q = getattr(a, "audio_quality", None) or ""
                    if "HI_RES" in q.upper():
                        q_tag = " 🔴 [24-bit Hi-Res]"
                    elif "LOSSLESS" in q.upper():
                        q_tag = " 🟢 [16-bit FLAC]"
                    else:
                        q_tag = ""
                dup = getattr(a, "_dup_count", 0)
                dup_tag = f" (+{dup} versión/es)" if dup > 0 else ""
                return f"{a.name} ({a.release_date.year if a.release_date else '?'}) — {a.num_tracks} tracks{q_tag}{dup_tag}"

            selected = pick_multi(
                deduped,
                _release_label,
                "🎵 Releases disponibles (selecciona los que quieras descargar):"
            )
            if selected:
                for album in selected:
                    tidal_download_album(session, album, download_dir)

        elif choice == 1:  # Buscar album
            query = input("\n  💿 Nombre del album: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.album.Album], limit=10)
            albums = results.get("albums", [])
            if not albums:
                print_info_box("Sin resultados", "No se encontraron albums.")
                continue

            albums_sorted = sorted(
                albums,
                key=lambda a: 0 if "HI_RES" in (getattr(a, "audio_quality", "") or "").upper() else 1
            )

            console.print("  [dim]Verificando calidad de audio...[/dim]", end="\r")
            _q_data_s = _probe_albums_quality(session, albums_sorted)
            console.print("  " + " " * 45, end="\r")

            def _album_quality_label(a):
                qc = _q_data_s.get(a.id)
                if qc:
                    bd, sr = qc
                    sr_str = f" / {sr/1000:.1f} kHz" if sr else ""
                    q_tag = f" 🔴 [{bd}-bit{sr_str}]"
                else:
                    q = getattr(a, "audio_quality", None) or ""
                    if "HI_RES" in q.upper():
                        q_tag = " 🔴 [24-bit Hi-Res]"
                    elif "LOSSLESS" in q.upper():
                        q_tag = " 🟢 [16-bit FLAC]"
                    else:
                        q_tag = ""
                return f"{a.name} — {a.artist.name} ({a.release_date.year if a.release_date else '?'}){q_tag}"

            selected = pick_multi(
                albums_sorted,
                _album_quality_label,
                "💿 Albums encontrados (ordenados por calidad):"
            )
            if selected:
                for album in selected:
                    tidal_download_album(session, album, download_dir)

        elif choice == 2:  # Buscar track
            query = input("\n  🎵 Nombre del track: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.media.Track], limit=15)
            tracks = results.get("tracks", [])
            if not tracks:
                print_info_box("Sin resultados", "No se encontraron tracks.")
                continue
            selected = pick_multi(
                tracks,
                lambda t: f"{t.name} — {', '.join(a.name for a in t.artists)} ({t.album.name if t.album else ''})",
                "🎵 Tracks encontrados (selecciona los que quieras descargar):"
            )
            if selected:
                folder = download_dir / "Tidal" / "Singles"
                folder.mkdir(parents=True, exist_ok=True)
                for i, track in enumerate(selected, 1):
                    album = session.album(track.album.id) if track.album else None
                    tidal_download_track(session, track, folder, album, i, len(selected))

        elif choice == 3:  # Buscar video
            query = input("\n  📹 Nombre del video: ").strip()
            if not query:
                continue
            results = session.search(query, models=[tidalapi.media.Video], limit=10)
            videos = results.get("videos", [])
            if not videos:
                print_info_box("Sin resultados", "No se encontraron videos.")
                continue
            selected = pick_multi(
                videos,
                lambda v: f"{v.name}  [{fmt_duration(v.duration)}]  — {v.artist.name if v.artist else '?'}",
                "📹 Videos encontrados (selecciona los que quieras descargar):"
            )
            if selected:
                for video in selected:
                    folder = download_dir / "Tidal" / "Videos"
                    tidal_download_video(session, video, folder)

        elif choice == 4:  # Pegar URL
            url = input("\n  🔗 Pegá el link de Tidal: ").strip()
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
            elif "video/" in url:
                m = re.search(r"video/(\d+)", url)
                if m:
                    video = session.video(int(m.group(1)))
                    folder = download_dir / "Tidal" / "Videos"
                    tidal_download_video(session, video, folder)
            else:
                print("\n  URL no reconocida.")
