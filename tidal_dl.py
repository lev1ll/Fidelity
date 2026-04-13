import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import subprocess

# ─── Bootstrap: dependencias base antes de importar rich ─────────────────────
_REQUIRED = ["tidalapi", "requests", "mutagen"]

def _can_import(p):
    try:
        __import__(p.replace("-", "_").split("[")[0])
        return True
    except ImportError:
        return False

_missing = [p for p in _REQUIRED if not _can_import(p)]
if _missing:
    print("  Instalando dependencias base...")
    for p in _missing:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", p],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    import os
    os.execv(sys.executable, [sys.executable] + sys.argv)

# ─── Imports ──────────────────────────────────────────────────────────────────
from ui import print_banner, print_info_box, menu_interactive, console
from config import load_config, get_download_dir, menu_settings
from tidal import get_tidal_session, menu_tidal
from youtube import menu_youtube
from utils import check_for_updates

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print_banner()
    check_for_updates()

    cfg = load_config()
    download_dir = get_download_dir(cfg)
    download_dir.mkdir(parents=True, exist_ok=True)

    tidal_session = None

    while True:
        console.print(
            f"\n  [bold deep_sky_blue1]📁 Descargas:[/bold deep_sky_blue1] "
            f"[gold1]{cfg['download_dir']}[/gold1]\n"
        )

        choice = menu_interactive(
            "MENÚ PRINCIPAL",
            [
                "🎵 Tidal - FLAC / Video (Hi-Res 24-bit)",
                "▶️  YouTube - Opus / AAC / Video",
                "⚙️  Configuración",
                "🚪 Salir",
            ],
            "Navega con ↑↓ y selecciona con ENTER",
        )

        if choice == 3:
            print_info_box("Hasta luego", "Gracias por usar Fidelity.")
            break
        elif choice == 2:
            menu_settings(cfg)
            download_dir = get_download_dir(cfg)
            download_dir.mkdir(parents=True, exist_ok=True)
        elif choice == 0:
            if tidal_session is None:
                tidal_session = get_tidal_session(download_dir)
            menu_tidal(tidal_session, download_dir)
        elif choice == 1:
            menu_youtube(download_dir)

if __name__ == "__main__":
    main()
