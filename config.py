import json
from pathlib import Path
from ui import console, menu_interactive, print_error_box
from ui import print_success_box

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

        if choice == 1:
            break

        elif choice == 0:
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
