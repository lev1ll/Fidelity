from pathlib import Path
from ui import console, menu_interactive, print_info_box, print_error_box, print_success_box
from utils import ensure_installed

# ─── Configuración ────────────────────────────────────────────────────────────

COOKIES_FILE = Path.home() / ".musicdl" / "apple_cookies.txt"

# Codecs disponibles (de más fácil a más difícil de configurar)
_CODEC_OPTIONS = [
    ("aac-legacy",    "AAC 256kbps  — sin .wvd, funciona siempre"),
    ("aac-he-legacy", "AAC-HE 64kbps — sin .wvd, menor calidad"),
    ("alac",          "ALAC Lossless — requiere device.wvd"),
    ("atmos",         "Dolby Atmos   — requiere device.wvd"),
]

# ─── Cookies ──────────────────────────────────────────────────────────────────

def _check_cookies():
    """Verifica que existe un cookies.txt válido. Retorna la ruta o None."""
    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
        return COOKIES_FILE
    return None

def _show_cookies_instructions():
    console.print("\n  [bold gold1]Cómo obtener cookies de Apple Music:[/bold gold1]")
    console.print()
    console.print("  [cyan]1.[/cyan] Abrí [bold]music.apple.com[/bold] en tu navegador y logueate")
    console.print("  [cyan]2.[/cyan] Instalá una extensión para exportar cookies:")
    console.print("       · Firefox  → [bold]'Export Cookies'[/bold]")
    console.print("       · Chrome   → [bold]'Get cookies.txt LOCALLY'[/bold]")
    console.print("  [cyan]3.[/cyan] Exportá las cookies de music.apple.com en formato [bold]Netscape[/bold]")
    console.print(f"  [cyan]4.[/cyan] Guardá el archivo en:")
    console.print(f"       [bold cyan]{COOKIES_FILE}[/bold cyan]")
    console.print()
    console.print("  [medium_purple]Nota: necesitás una suscripción activa de Apple Music.[/medium_purple]")
    console.print()

def setup_cookies():
    """Guía al usuario para configurar las cookies."""
    _show_cookies_instructions()
    ruta = input("  O pegá la ruta completa a tu cookies.txt (Enter para cancelar): ").strip()
    if not ruta:
        return False
    p = Path(ruta)
    if not p.exists():
        print_error_box("Archivo no encontrado", str(p))
        return False
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(str(p), str(COOKIES_FILE))
    print_success_box("Cookies guardadas", f"Copiadas a: {COOKIES_FILE}")
    return True

# ─── Widevine CDM (solo para ALAC/Atmos) ─────────────────────────────────────

def _check_wvd():
    """Verifica si existe device.wvd para codecs con DRM."""
    wvd = Path.home() / ".gamdl" / "device.wvd"
    return wvd if wvd.exists() else None

def _show_wvd_instructions():
    console.print("\n  [bold gold1]Cómo obtener device.wvd (Widevine CDM):[/bold gold1]")
    console.print()
    console.print("  El archivo device.wvd es necesario para descifrar ALAC y Atmos.")
    console.print("  Se extrae de un dispositivo Android usando herramientas como:")
    console.print("       · [bold]KeyDive[/bold] o [bold]Dumper[/bold] (buscar en GitHub)")
    console.print()
    console.print("  Una vez que tenés los archivos (private_key.pem + client_id.bin):")
    console.print("  [cyan]pip install pywidevine[/cyan]")
    console.print("  [cyan]pywidevine create-device --type ANDROID --level 3 \\[/cyan]")
    console.print("  [cyan]    --key private_key.pem --client_id client_id.bin \\[/cyan]")
    console.print("  [cyan]    --output device.wvd[/cyan]")
    console.print(f"\n  Después copiá el device.wvd a:")
    console.print(f"  [bold cyan]{Path.home() / '.gamdl' / 'device.wvd'}[/bold cyan]")
    console.print()
    console.print("  [yellow]Alternativa más fácil:[/yellow] usá AAC 256kbps que no necesita .wvd")
    console.print()

# ─── Descarga ─────────────────────────────────────────────────────────────────

def apple_download(url, download_dir, codec="aac-legacy"):
    """Descarga desde Apple Music usando gamdl."""
    import subprocess, sys

    cookies = _check_cookies()
    if not cookies:
        print_error_box(
            "Cookies no configuradas",
            f"Guardá tu cookies.txt de music.apple.com en:\n  {COOKIES_FILE}"
        )
        return False

    needs_wvd = codec in ("alac", "atmos", "ac3")
    if needs_wvd and not _check_wvd():
        _show_wvd_instructions()
        opts = menu_interactive(
            "¿Qué hacer?",
            ["🔄 Usar AAC 256kbps (sin .wvd)", "❌ Cancelar"],
            ""
        )
        if opts == 1:
            return False
        codec = "aac-legacy"

    ensure_installed(["gamdl"])

    out_dir = download_dir / "Apple Music"
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "gamdl",
        "--cookies-path", str(cookies),
        "--output-path", str(out_dir),
        "--song-codec-priority", codec,
    ]

    wvd = _check_wvd()
    if wvd:
        cmd += ["--wvd-path", str(wvd)]

    cmd.append(url)

    console.print(f"\n  [cyan]⟳ Descargando con gamdl[/cyan]  [medium_purple]({codec})[/medium_purple]")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print_success_box("Descarga completada", f"Guardado en: {out_dir}")
        return True
    else:
        print_error_box("Error en descarga", "gamdl terminó con error. Revisá las cookies y el link.")
        return False

# ─── Menú ─────────────────────────────────────────────────────────────────────

def menu_apple_music(download_dir):
    codec_preferido = "aac-legacy"

    while True:
        cookies_ok = _check_cookies() is not None
        wvd_ok = _check_wvd() is not None
        cookies_status = "[green1]✓ configuradas[/green1]" if cookies_ok else "[red]✗ no configuradas[/red]"
        wvd_status     = "[green1]✓ encontrado[/green1]"   if wvd_ok   else "[yellow]— no encontrado (solo AAC)[/yellow]"

        console.print("\n[bold deep_sky_blue1]── Apple Music ────────────────────────[/bold deep_sky_blue1]")
        console.print(f"[gold1]Codec:[/gold1] [cyan]{codec_preferido}[/cyan]")
        console.print(f"[gold1]Cookies:[/gold1] {cookies_status}")
        console.print(f"[gold1]device.wvd:[/gold1] {wvd_status}\n")

        menu_options = [
            "🔗 Pegar URL de Apple Music",
            "🎵 Cambiar codec",
            "🍪 Configurar cookies",
            "❓ Cómo obtener device.wvd",
            "⬅️  Volver"
        ]

        choice = menu_interactive(
            "MENÚ APPLE MUSIC",
            menu_options,
            "Selecciona una opción"
        )

        if choice == 4:
            break

        elif choice == 3:  # Instrucciones .wvd
            _show_wvd_instructions()
            input("  Presioná Enter para continuar...")

        elif choice == 2:  # Configurar cookies
            if not cookies_ok:
                _show_cookies_instructions()
            ruta = input("  Ruta a tu cookies.txt (Enter para cancelar): ").strip()
            if ruta:
                p = Path(ruta)
                if p.exists():
                    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(str(p), str(COOKIES_FILE))
                    print_success_box("Cookies guardadas", f"Copiadas a: {COOKIES_FILE}")
                else:
                    print_error_box("Archivo no encontrado", str(p))

        elif choice == 1:  # Cambiar codec
            codec_labels = [f"{c}  —  {desc}" for c, desc in _CODEC_OPTIONS]
            codec_labels.append("⬅️  Cancelar")
            sel = menu_interactive("Codec de audio:", codec_labels, "")
            if sel < len(_CODEC_OPTIONS):
                codec_preferido = _CODEC_OPTIONS[sel][0]
                console.print(f"  [green1]✓ Codec: {codec_preferido}[/green1]")

        elif choice == 0:  # Pegar URL
            if not cookies_ok:
                print_error_box(
                    "Cookies no configuradas",
                    "Primero configurá tus cookies de music.apple.com"
                )
                _show_cookies_instructions()
                continue

            url = input("\n  🔗 Pegá el link de Apple Music: ").strip()
            if not url:
                continue

            apple_download(url, download_dir, codec_preferido)
