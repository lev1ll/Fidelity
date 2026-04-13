import sys
import subprocess
import shutil
import re
import questionary
from pathlib import Path
from ui import console, menu_interactive

__version__ = "2.0.11"
GITHUB_REPO  = "lev1ll/Fidelity"
REQUIRED_BASE = ["tidalapi", "requests", "mutagen"]

# ─── Auto-install ─────────────────────────────────────────────────────────────

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

# ─── Logging / archivos ───────────────────────────────────────────────────────

def _setup_tw_logging():
    """Silencia los logs internos de tidal-wave."""
    import logging
    root = logging.getLogger("tidal_wave")
    root.setLevel(logging.CRITICAL)
    root.handlers.clear()
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

# ─── Helpers generales ────────────────────────────────────────────────────────

def sanitize(name):
    return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()

def check_ffmpeg():
    return shutil.which("ffmpeg") is not None

def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def ask(prompt, options=None):
    """Usa questionary para seleccionar de opciones (sin números)."""
    if options is None:
        return input(prompt).strip()

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

    options = [label_fn(item) for item in items]

    color_palette = ["hot_pink", "deep_sky_blue1", "gold1", "green1", "medium_purple", "orange1", "cyan1", "magenta"]
    for idx, opt in enumerate(options):
        color = color_palette[idx % len(color_palette)]
        console.print(f"  [{color}]▶[/{color}] {opt}")

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

    for idx, opt in enumerate(options[:-1]):
        if opt in answer:
            return items[idx]

    return None

def pick_multi(items, label_fn, title=""):
    """Selecciona múltiples items por número."""
    if not items:
        console.print("[yellow]No hay items para seleccionar.[/yellow]")
        return None

    color_palette = ["hot_pink", "deep_sky_blue1", "gold1", "green1", "medium_purple", "orange1", "cyan1", "magenta"]

    console.print()
    console.print(f"[bold deep_sky_blue1]▓▓▓[/bold deep_sky_blue1] [bold hot_pink]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold hot_pink] [bold deep_sky_blue1]▓▓▓[/bold deep_sky_blue1]")
    if title:
        console.print(f"  [bold gold1]◈  {title}[/bold gold1]")
    console.print(f"[bold deep_sky_blue1]▓▓▓[/bold deep_sky_blue1] [bold hot_pink]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold hot_pink] [bold deep_sky_blue1]▓▓▓[/bold deep_sky_blue1]")
    console.print()

    for i, item in enumerate(items):
        color = color_palette[i % len(color_palette)]
        label = label_fn(item)
        label_short = label[:68] + "…" if len(label) > 68 else label
        console.print(
            f"  [bold deep_sky_blue1][[/bold deep_sky_blue1][bold {color}]{i + 1:2d}[/bold {color}][bold deep_sky_blue1]][/bold deep_sky_blue1] "
            f"💿 [bold {color}]{label_short}[/bold {color}]"
        )

    console.print()
    console.print(f"[bold deep_sky_blue1]╔══════════════════════════════════════════════════╗[/bold deep_sky_blue1]")
    console.print(f"[bold deep_sky_blue1]║[/bold deep_sky_blue1]  [bold hot_pink]Números separados por comas[/bold hot_pink]  [medium_purple]ej: 1,3,5[/medium_purple]          [bold deep_sky_blue1]║[/bold deep_sky_blue1]")
    console.print(f"[bold deep_sky_blue1]║[/bold deep_sky_blue1]  [bold gold1]'a'[/bold gold1] → todos   [bold gold1]Enter[/bold gold1] → cancelar                 [bold deep_sky_blue1]║[/bold deep_sky_blue1]")
    console.print(f"[bold deep_sky_blue1]╚══════════════════════════════════════════════════╝[/bold deep_sky_blue1]")

    try:
        resp = input("  ❯ ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Cancelado.[/yellow]")
        return None

    if not resp:
        return None

    if resp == "a":
        console.print(f"  [green1]✓ Todos seleccionados ({len(items)})[/green1]")
        return list(items)

    selected = []
    for part in resp.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part) - 1
            if 0 <= idx < len(items):
                if items[idx] not in selected:
                    selected.append(items[idx])
            else:
                console.print(f"  [yellow]⚠ {part} fuera de rango, ignorado.[/yellow]")
        except ValueError:
            console.print(f"  [yellow]⚠ '{part}' no es válido, ignorado.[/yellow]")

    if not selected:
        console.print("[red]No se seleccionó ningún item.[/red]")
        return None

    console.print(f"  [green1]✓ {len(selected)} seleccionado(s)[/green1]")
    return selected

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

# ─── Auto-update ──────────────────────────────────────────────────────────────

_UPDATE_FLAG = Path.home() / ".musicdl" / ".just_updated"

def check_for_updates():
    """Verifica si hay nueva versión en GitHub y ofrece actualizar."""
    import requests as _requests
    import sys, shutil, subprocess, tempfile, textwrap

    if _UPDATE_FLAG.exists():
        _UPDATE_FLAG.unlink(missing_ok=True)
        return

    try:
        r = _requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=5
        )
        if r.status_code != 200:
            return

        data = r.json()
        tag_name = data.get("tag_name", "")
        latest = tag_name.lstrip("v")

        if not latest:
            return

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
                console.print("[cyan]  ⟳ Preparando actualización...[/cyan]")

                _UPDATE_FLAG.parent.mkdir(parents=True, exist_ok=True)
                _UPDATE_FLAG.touch()

                install_url = f"git+https://github.com/{GITHUB_REPO}.git@{tag_name}"
                fidelity_exe = shutil.which("fidelity") or "fidelity"

                updater_code = textwrap.dedent(f"""\
                    import subprocess, sys, time, os

                    time.sleep(2)

                    print("Actualizando Fidelity...")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--upgrade", "--no-cache-dir",
                         "{install_url}"]
                    )

                    if result.returncode == 0:
                        print("")
                        print("Actualización completada. Abre Fidelity de nuevo.")
                    else:
                        print("")
                        print("Error al actualizar. Intenta manualmente:")
                        print('  pip install --upgrade "git+https://github.com/{GITHUB_REPO}.git"')

                    input("\\nPresiona Enter para cerrar...")
                    try:
                        os.unlink(__file__)
                    except Exception:
                        pass
                """)

                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False, encoding="utf-8"
                )
                tmp.write(updater_code)
                tmp.close()

                subprocess.Popen(
                    [sys.executable, tmp.name],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    close_fds=True,
                )

                console.print("[green1]  ✓ Instalando en segundo plano — abre Fidelity de nuevo cuando termine.[/green1]")
                sys.exit(0)
    except Exception:
        pass
