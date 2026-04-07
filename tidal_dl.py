import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import subprocess
import shutil
import json
import re
import questionary
from ui import print_banner, print_section, print_status, print_welcome, menu_interactive, print_menu_table, print_info_box, console, print_download_progress, print_album_progress, print_track_downloading, print_batch_progress, show_download_summary

__version__ = "1.9.7"
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

def _copy_file_safe(src_path):
    """Copia un archivo a un directorio temporal para evitar locks de Windows.
    Retorna la ruta temporal (str) o None si falla."""
    import tempfile
    try:
        suffix = src_path.suffix if hasattr(src_path, 'suffix') else ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        shutil.copy2(str(src_path), tmp.name)
        return tmp.name
    except Exception:
        return None


def _auto_extract_tidal_token():
    """Extrae el token del Tidal desktop automaticamente desde IndexedDB.

    Funciona en Windows con la app de Tidal instalada.
    Guarda el token en el formato que espera tidal-wave.
    """
    import re, base64, json, time
    from pathlib import Path

    token_file = Path.home() / "AppData" / "Local" / "tidal-wave" / "android-tidal.token"

    # Buscar en múltiples ubicaciones posibles
    possible_dirs = [
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "IndexedDB" / "https_desktop.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Local" / "TIDAL" / "IndexedDB" / "https_desktop.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "IndexedDB" / "https_app.tidal.com_0.indexeddb.leveldb",
        Path.home() / "AppData" / "Local" / "TIDAL" / "IndexedDB" / "https_app.tidal.com_0.indexeddb.leveldb",
        # Local Storage — también puede tener el token
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "Local Storage" / "leveldb",
        Path.home() / "AppData" / "Local" / "TIDAL" / "Local Storage" / "leveldb",
        # Fallback: carpetas padre
        Path.home() / "AppData" / "Roaming" / "TIDAL" / "IndexedDB",
        Path.home() / "AppData" / "Local" / "TIDAL" / "IndexedDB",
        Path.home() / "AppData" / "Roaming" / "TIDAL",
        Path.home() / "AppData" / "Local" / "TIDAL",
    ]

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

            # Intentar copiar a temp primero para evitar locks de Windows
            tmp_path = _copy_file_safe(f)
            read_path = Path(tmp_path) if tmp_path else None

            if read_path is None:
                # Si no se pudo copiar, intentar leer directamente
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
    """Verifica si hay nueva versión en GitHub y ofrece actualizar."""
    try:
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=5
        )
        if r.status_code != 200:
            return
        
        data = r.json()
        tag_name = data.get("tag_name", "")   # e.g. "v1.9.7"
        latest = tag_name.lstrip("v")          # e.g. "1.9.7" para comparar

        if not latest:
            return

        # Comparar versiones como tuplas para evitar errores de string comparison
        def _ver(s):
            try:
                return tuple(int(x) for x in s.split("."))
            except Exception:
                return (0,)

        if _ver(latest) > _ver(__version__):
            console.print(f"\n  [bold deep_sky_blue1]┌─ Actualización disponible ─────────────────────┐[/bold deep_sky_blue1]")
            console.print(f"  [bold gold1]│  Nueva versión: v{latest}  (tenés v{__version__})[/bold gold1]".ljust(52) + "[bold deep_sky_blue1]│[/bold deep_sky_blue1]")
            console.print(f"  [bold deep_sky_blue1]└────────────────────────────────────────────────┘[/bold deep_sky_blue1]")

            choice = menu_interactive(
                "",
                ["✅ Actualizar ahora", "⏭️  Hacer después"],
                "¿Qué hacemos?"
            )

            if choice == 0:
                console.print("[cyan]  ⟳ Actualizando desde GitHub...[/cyan]")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
                     f"git+https://github.com/{GITHUB_REPO}.git@{tag_name}"],
                    check=False
                )
                if result.returncode == 0:
                    console.print("[green1]  ✓ Actualizado! Reiniciando...[/green1]")
                    subprocess.run([sys.executable] + sys.argv)
                    sys.exit()
                else:
                    console.print("[red]  ✗ Error al actualizar. Revisá tu conexión o instalá manualmente.[/red]")
    except requests.exceptions.RequestException:
        pass  # Sin internet
    except Exception:
        pass

# ─── Helpers ─────────────────────────────────────────────────────────────────

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

def ask(prompt, options=None):
    """Usa questionary para seleccionar de opciones (sin números)."""
    if options is None:
        return input(prompt).strip()
    
    # Crear opciones con emojis y estilos
    answer = questionary.select(
        prompt,
        choices=options,
        pointer="→ ►",
        style=questionary.Style([
            ('pointer', 'fg:#ff69b4 bold'),
            ('highlighted', 'fg:#00d4ff bold'),
            ('selected', 'fg:#00ff00 bold'),
        ])
    ).ask()
    
    return answer if answer else options[0]

def pick(items, label_fn, title=""):
    """Selecciona un item de una lista usando menú con flechas."""
    if not items:
        console.print("[yellow]No hay items para seleccionar.[/yellow]")
        return None
    
    if title:
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
    
    # Crear opciones con labels y mostrar preview coloreado
    options = [label_fn(item) for item in items]
    
    # Mostrar opciones con colores
    color_palette = ["hot_pink", "deep_sky_blue1", "gold1", "green1", "medium_purple", "orange1", "cyan1", "magenta"]
    for idx, opt in enumerate(options):
        color = color_palette[idx % len(color_palette)]
        icon = ["🎵", "🎸", "🎹", "🎤", "🎧", "📀", "🎼", "🌟"][idx % 8]
        console.print(f"  [{color}]{icon}[/{color}] {opt}")
    
    options.append("🚪 Volver")
    
    answer = questionary.select(
        "\nSelecciona un item:",
        choices=options,
        pointer="→ ►",
        style=questionary.Style([
            ('pointer', 'fg:#ff69b4 bold'),
            ('highlighted', 'fg:#00d4ff bold'),
            ('selected', 'fg:#00ff00 bold'),
        ])
    ).ask()
    
    if answer is None or answer == "🚪 Volver":
        return None
    
    # Remover el icono para encontrar el índice correcto
    for idx, opt in enumerate(options[:-1]):  # Excluir "Volver"
        if opt in answer:
            return items[idx]
    
    return None

def pick_multi(items, label_fn, title=""):
    """Selecciona múltiples items con checkboxes (ESPACIO para marcar, ENTER para confirmar)."""
    if not items:
        console.print("[yellow]No hay items para seleccionar.[/yellow]")
        return None

    if title:
        console.print(f"\n[bold cyan]{title}[/bold cyan]")

    console.print("[bold gold1]📝 ESPACIO para marcar, ENTER para confirmar, Ctrl+C para cancelar[/bold gold1]\n")

    icons = ["📁", "💿", "🎵", "🎸", "🎹", "🎤", "🎧", "📀"]
    choices = [
        questionary.Choice(
            title=f"{icons[i % 8]} {label_fn(item)}",
            value=i
        )
        for i, item in enumerate(items)
    ]

    try:
        selected_indices = questionary.checkbox(
            "Selecciona items:",
            choices=choices,
            style=questionary.Style([
                ('checkbox', 'fg:#ff69b4'),
                ('checkbox-selected', 'fg:#00ff00 bold'),
                ('highlighted', 'fg:#00d4ff bold'),
                ('pointer', 'fg:#ff69b4 bold'),
            ])
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado.[/yellow]")
        return None

    if selected_indices is None:
        return None
    if not selected_indices:
        console.print("[red]❌ No seleccionaste ningún item.[/red]")
        return None

    return [items[i] for i in selected_indices]

def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"



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
    print("  · Tidal   → Cuenta HiFi o HiFi Plus (app abierta)")
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
        console.print(f"\n[bold deep_sky_blue1]── Configuración ──────────────────────[/bold deep_sky_blue1]")
        console.print(f"[gold1]📁 Carpeta de descarga:[/gold1] [cyan]{cfg['download_dir']}[/cyan]\n")
        
        settings_options = [
            "📁 Cambiar carpeta de descarga",
            "⬅️  Volver"
        ]
        
        choice = menu_interactive(
            "CONFIGURACIÓN",
            settings_options,
            "Selecciona una opción"
        )
        
        if choice == 1:  # Volver
            break

        elif choice == 0:  # Cambiar carpeta
            console.print(f"\n[cyan]Carpeta actual:[/cyan] {cfg['download_dir']}")
            nueva = input("  📁 Nueva carpeta (Enter para cancelar): ").strip()
            if not nueva:
                continue
            p = Path(nueva)
            try:
                p.mkdir(parents=True, exist_ok=True)
                cfg["download_dir"] = str(p)
                save_config(cfg)
                print_success_box("Guardado", f"Carpeta actualizada a: {p}")
            except Exception as e:
                print_error_box("Error", str(e))

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
    """Sesion de tidal-wave para descarga Hi-Res 24-bit usando token del Tidal desktop."""
    global _tw_session
    if _tw_session is not None:
        return _tw_session
    
    ensure_installed(["tidal-wave", "cachecontrol"])
    import time
    _patch_tidal_wave()

    print()
    print("  Buscando token Hi-Res del Tidal desktop...", end="", flush=True)
    
    # Reintentar extracción con delay
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
        # Usar tidal-wave.login_android para que configure la sesión correctamente
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

def tidal_download_track(session, track, dest_dir, album=None, num=None, total=None):
    from tidal_wave.track import Track as TWTrack
    from tidal_wave.media import AudioFormat as TWAudioFormat

    prefix = f"[{num}/{total}] " if num else ""
    artist = ", ".join(a.name for a in track.artists)
    print(f"\n  {prefix}{artist} - {track.name}")
    print("  Descargando...", flush=True)

    tw_session = session  # Usar sesión pasada (no llamar get_tw_session)
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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    folder = dest_base / "Tidal" / sanitize(album.name)
    folder.mkdir(parents=True, exist_ok=True)

    print_album_progress(album.name, 0, 1)
    console.print("[cyan]  (descargando hasta 3 tracks simultáneamente)[/cyan]\n")
    
    tw_session = get_tw_session()
    _setup_tw_logging()
    
    start_time = time.time()
    downloaded = 0
    errors = 0
    total_size_mb = 0
    
    try:
        tw_album = TWAlbum(album_id=album.id)
        # Obtener lista de tracks
        tracks = list(tw_album.tracks())
        total_tracks = len(tracks)
        
        def download_single_track(track_info):
            """Descarga un track individual"""
            nonlocal total_size_mb
            track, num = track_info
            try:
                artist = ", ".join(a.name for a in track.artists) if track.artists else "Unknown"
                print_track_downloading(num, total_tracks, artist, track.name)
                
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
                    total_size_mb += size_mb
                    console.print(f"  [green1]✓[/green1] [{num}/{total_tracks}] {size_mb:.1f} MB")
                    return (True, size_mb)
                else:
                    console.print(f"  [red]✗[/red] [{num}/{total_tracks}] No se descargó")
                    return (False, 0)
            except Exception as e:
                console.print(f"  [red]✗[/red] [{num}/{total_tracks}] Error: {str(e)[:50]}")
                return (False, 0)
        
        # Descargar en paralelo (máximo 3 simultáneos)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(download_single_track, (t, i)): i 
                for i, t in enumerate(tracks, 1)
            }
            for future in as_completed(futures):
                success, size = future.result()
                if success:
                    downloaded += 1
                else:
                    errors += 1
        
        duration = time.time() - start_time
        show_download_summary(downloaded, total_size_mb, duration, success_count=downloaded, error_count=errors)
        console.print(f"[cyan]📁 Guardado en:[/cyan] {folder}\n")
        
    except Exception as e:
        print_error_box("Error en descarga", str(e))

_TIDAL_VIDEO_QUALITIES = [
    ("Alta",  "1080p", "high"),
    ("Media",  "720p", "medium"),
    ("Baja",   "480p", "low"),
]

def tidal_download_video(session, video, dest_dir):
    ensure_installed(["yt-dlp"])
    print(f"\n  {video.name}  —  {video.artist.name if video.artist else '?'}")
    print(f"  Duración: {fmt_duration(video.duration)}")
    print()
    print("  Calidad de video:")
    for i, (label, res, _) in enumerate(_TIDAL_VIDEO_QUALITIES, 1):
        print(f"  {i}. {label:<6}  {res}")
    print("  0. Cancelar")

    sel = ask("\n  Elegí: ", ["0","1","2","3"])
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

    import yt_dlp
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

def menu_tidal(session, download_dir):
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

        if choice == 6:  # Volver
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
                print("\n  No se encontraron artistas.")
                continue
            artist = pick(artists, lambda a: a.name, "🎤 Artistas encontrados:")
            if not artist:
                continue
            
            # Menú para elegir qué tipo de releases quere
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
            if release_choice in (0, 2):  # Albums o Todo
                all_items += list(artist.get_albums())
            if release_choice in (1, 2):  # Singles/EPs o Todo
                all_items += list(artist.get_ep_singles())
            
            if not all_items:
                print_info_box("Sin resultados", "No se encontraron releases para este artista.")
                continue
            
            def _release_label(a):
                q = getattr(a, "audio_quality", None) or ""
                q_tag = ""
                if "HI_RES" in q.upper():
                    q_tag = " 🔴 [24-bit Hi-Res]"
                elif "LOSSLESS" in q.upper():
                    q_tag = " 🟢 [16-bit FLAC]"
                return f"{a.name} ({a.release_date.year if a.release_date else '?'}) — {a.num_tracks} tracks{q_tag}"
            selected = pick_multi(
                all_items,
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
            def _album_quality_label(a):
                q = getattr(a, "audio_quality", None) or ""
                q_tag = ""
                if "HI_RES" in q.upper():
                    q_tag = " 🔴 [24-bit Hi-Res]"
                elif "LOSSLESS" in q.upper():
                    q_tag = " 🟢 [16-bit FLAC]"
                return f"{a.name} — {a.artist.name} ({a.release_date.year if a.release_date else '?'}){q_tag}"
            albums_sorted = sorted(
                albums,
                key=lambda a: 0 if "HI_RES" in (getattr(a, "audio_quality", "") or "").upper() else 1
            )
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

# ─── YOUTUBE ─────────────────────────────────────────────────────────────────

def yt_search(query, limit=10):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        return info.get("entries", [])

_VIDEO_CODEC_NAMES = {
    "av01": "AV1", "vp09": "VP9", "vp9": "VP9",
    "avc1": "H.264", "hvc1": "H.265", "dvh1": "H.265",
}

def yt_get_all_formats(url):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Audio-only formats
    audio_fmts = []
    seen_a = set()
    for f in sorted(info.get("formats", []), key=lambda x: x.get("abr") or 0, reverse=True):
        if f.get("vcodec") not in (None, "none"):
            continue
        if f.get("acodec") in (None, "none"):
            continue
        abr = int(f.get("abr") or f.get("tbr") or 0)
        codec = f.get("acodec", "?").split(".")[0]
        ext = f.get("ext", "?")
        key = (codec, abr, ext)
        if key not in seen_a:
            seen_a.add(key)
            audio_fmts.append({
                "format_id": f["format_id"],
                "ext": ext,
                "codec": codec,
                "abr": abr,
                "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
            })

    # Video-only formats (se combinan con el mejor audio via ffmpeg)
    video_fmts = []
    seen_v = set()
    for f in sorted(
        info.get("formats", []),
        key=lambda x: ((x.get("height") or 0), (x.get("fps") or 0), (x.get("vbr") or x.get("tbr") or 0)),
        reverse=True,
    ):
        if f.get("vcodec") in (None, "none"):
            continue
        if f.get("acodec") not in (None, "none"):
            continue  # omitir streams combinados (muxed)
        height = f.get("height") or 0
        fps = int(f.get("fps") or 0)
        vcodec_raw = f.get("vcodec", "?").split(".")[0]
        vcodec = _VIDEO_CODEC_NAMES.get(vcodec_raw, vcodec_raw.upper())
        vbr = int(f.get("vbr") or f.get("tbr") or 0)
        key = (height, fps, vcodec_raw)
        if key not in seen_v:
            seen_v.add(key)
            video_fmts.append({
                "format_id": f["format_id"],
                "ext": f.get("ext", "?"),
                "vcodec": vcodec,
                "height": height,
                "fps": fps,
                "vbr": vbr,
                "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
            })

    return info, audio_fmts[:8], video_fmts[:8]

def yt_download(url, dest_dir, format_id=None):
    import yt_dlp
    has_ffmpeg = check_ffmpeg()
    # Prefer: 256kbps AAC (YouTube Music) → 160kbps Opus → best available
    if format_id:
        fmt = format_id
    elif has_ffmpeg:
        fmt = "bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio/best"
    else:
        fmt = "bestaudio/best"
    postprocessors = []
    if has_ffmpeg:
        postprocessors += [
            {"key": "FFmpegExtractAudio", "preferredcodec": "opus"},
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

def yt_download_video(url, dest_dir, video_format_id, audio_format_id=None):
    import yt_dlp
    has_ffmpeg = check_ffmpeg()
    if has_ffmpeg:
        audio = audio_format_id or "bestaudio[acodec=opus]/bestaudio[acodec=aac]/bestaudio"
        fmt = f"{video_format_id}+{audio}"
    else:
        fmt = video_format_id
    opts = {
        "format": fmt,
        "outtmpl": str(dest_dir / "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def menu_youtube(download_dir):
    ensure_installed(["yt-dlp"])

    while True:
        console.print("\n[bold deep_sky_blue1]── YouTube ────────────────────────────[/bold deep_sky_blue1]")
        console.print("[gold1]Catálogo enorme: conciertos, lives, rarezas · Sin cuenta[/gold1]")
        if check_ffmpeg():
            console.print("[green1]Audio: Opus/AAC  |  Video: hasta 4K · ffmpeg ✓[/green1]")
        else:
            console.print("[orange1]Audio: mejor nativo · Video: requiere ffmpeg (no encontrado)[/orange1]")
        
        menu_options = [
            "🔍 Buscar por nombre",
            "🔗 Pegar URL de YouTube",
            "⬅️  Volver"
        ]
        
        choice = menu_interactive(
            "MENÚ YOUTUBE",
            menu_options,
            "Selecciona una opción"
        )
        
        if choice == 2:  # Volver
            break

        url = None
        if choice == 0:  # Buscar
            query = input("\n  🔍 Qué buscás (canción, concierto, artista...): ").strip()
            if not query:
                continue
            console.print("\n  [bold cyan]⟳ Buscando...[/bold cyan]")
            results = yt_search(query)
            if not results:
                print_info_box("Sin resultados", "No se encontró nada en YouTube.")
                continue
            selected = pick_multi(
                results,
                lambda e: f"{e.get('title','?')}  [{fmt_duration(e.get('duration'))}]  — {e.get('channel') or e.get('uploader','?')}",
                "📺 Resultados (selecciona los que quieras descargar):"
            )
            if not selected:
                continue
            for entry in selected:
                url = f"https://www.youtube.com/watch?v={entry['id']}"

        elif choice == 1:  # Pegar URL
            url = input("\n  🔗 Pegá el link de YouTube: ").strip()
            if not url:
                continue
            
            # Si no hay URL de búsqueda anterior
            for entry in [{"url": url}]:  # Simulamos una selección
                console.print("\n  [bold cyan]⟳ Obteniendo formatos disponibles...[/bold cyan]")
                try:
                    info, audio_fmts, video_fmts = yt_get_all_formats(url)
                except Exception as e:
                    print_error_box("Error", str(e))
                    continue

                console.print(f"\n  [bold gold1]{info.get('title','?')}[/bold gold1]  — [cyan]{info.get('channel') or info.get('uploader','?')}[/cyan]")
                console.print(f"  [medium_purple]Duración:[/medium_purple] {fmt_duration(info.get('duration'))}\n")
                
                download_options = [
                    "🔊 Audio (Opus/AAC - mejor calidad)",
                    "📹 Video (MP4 - video + mejor audio)",
                    "❌ Cancelar"
                ]
                
                mode = menu_interactive(
                    "¿Qué querés descargar?",
                    download_options,
                    "Selecciona el formato"
                )
                
                if mode == 2:  # Cancelar
                    continue

                dest = download_dir / "YouTube"
                dest.mkdir(parents=True, exist_ok=True)

                if mode == 0:  # Audio
                    best = audio_fmts[0] if audio_fmts else None
                    if best:
                        size = f" (~{best['filesize']/1024/1024:.0f} MB)" if best['filesize'] else ""
                        console.print(f"  [green1]🔊 Audio: {best['codec'].upper()}  {best['abr']}kbps  .{best['ext']}{size}  ★ mejor disponible[/green1]\n")
                    yt_download(url, dest, best["format_id"] if best else None)
                    print_success_box("Descarga completada", f"Guardado en: {dest}")

                elif mode == 1:  # Video
                    if not video_fmts:
                        print_info_box("Sin formatos", "No se encontraron formatos de video.")
                        continue
                    if not check_ffmpeg():
                        print_info_box("⚠ ffmpeg no encontrado", "El video se descargará sin audio separado.\nInstalá ffmpeg para obtener video + mejor audio combinados.")

                    best_audio = audio_fmts[0] if audio_fmts else None
                    if best_audio:
                        _ac = {"opus": "Opus", "aac": "AAC", "mp4a": "AAC"}
                        audio_tag = f"  + {_ac.get(best_audio['codec'], best_audio['codec'].upper())} {best_audio['abr']}kbps"
                    else:
                        audio_tag = ""

                    def _video_label(v):
                        res    = f"{v['height']}p" if v['height'] else "?"
                        fps_s  = f" {v['fps']}fps" if v['fps'] and v['fps'] != 30 else "     "
                        vbr_s  = f"  {v['vbr']}kbps" if v['vbr'] else ""
                        size_s = f"  ~{v['filesize']/1024/1024:.0f}MB" if v['filesize'] else ""
                        return f"{res:<6}{fps_s}  {v['vcodec']:<7}{vbr_s}{size_s}{audio_tag}"

                    fmt = pick(
                        video_fmts,
                        _video_label,
                        "📹 Calidades de video disponibles:"
                    )
                    if not fmt:
                        continue

                    yt_download_video(url, dest, fmt["format_id"],
                                      best_audio["format_id"] if best_audio else None)
                    print_success_box("Descarga completada", f"Guardado en: {dest}")
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
        console.print(f"\n  [bold deep_sky_blue1]📁 Descargas:[/bold deep_sky_blue1] [gold1]{cfg['download_dir']}[/gold1]\n")
        
        # Menú principal con navegación por flechas
        menu_options = [
            "🎵 Tidal - FLAC / Video (Hi-Res 24-bit)",
            "▶️  YouTube - Opus / AAC / Video",
            "⚙️  Configuración",
            "🚪 Salir"
        ]
        
        choice = menu_interactive(
            "MENÚ PRINCIPAL",
            menu_options,
            "Navega con ↑↓ y selecciona con ENTER"
        )

        if choice == 3:  # Salir
            print_info_box("Hasta luego", "Gracias por usar Fidelity. ¡Nos vemos pronto!")
            break

        elif choice == 2:  # Configuración
            menu_settings(cfg)
            download_dir = get_download_dir(cfg)
            download_dir.mkdir(parents=True, exist_ok=True)

        elif choice == 0:  # Tidal
            if tidal_session is None:
                tidal_session = get_tidal_session(download_dir)
            menu_tidal(tidal_session, download_dir)

        elif choice == 1:  # YouTube
            menu_youtube(download_dir)

if __name__ == "__main__":
    main()
