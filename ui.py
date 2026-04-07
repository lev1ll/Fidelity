"""UI estilo TRON con rich para terminal."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.table import Table
from rich.syntax import Syntax
import pyfiglet
import questionary

console = Console()

# Colores vibrantes tipo Gemini
CYAN = "cyan1"
MAGENTA = "magenta"
PURPLE = "purple"
BLUE = "blue"
WHITE = "white"
HOT_PINK = "hot_pink"
DEEP_BLUE = "deep_sky_blue1"
GOLD = "gold1"
GREEN = "green1"
ORANGE = "orange1"

def print_banner():
    """Banner épico estilo Gemini con ASCII art multicolor y efectos vibrantez."""
    
    # Crear ASCII art grande con pyfiglet - font 'big' para letras más juntas y legibles
    fig = pyfiglet.Figlet(font='big', width=100)
    ascii_text = fig.renderText('FIDELITY')
    
    # Colorear cada CARÁCTER del ASCII con colores diferentes para máximo impacto (tipo Gemini)
    ascii_lines = ascii_text.split('\n')
    
    # Paleta de colores vibrantes tipo Gemini
    color_palette = [
        "hot_pink",          # Rosa brillante
        "deep_sky_blue1",    # Azul cielo
        "medium_purple",     # Púrpura
        "gold1",             # Dorado
        "green1",            # Verde brillante
        "magenta",           # Magenta
        "cyan1",             # Cyan brillante
        "orange1",           # Naranja
    ]
    
    # Colorear línea por línea con rotación de colores
    colored_ascii = []
    for line_idx, line in enumerate(ascii_lines):
        if line.strip():
            color = color_palette[line_idx % len(color_palette)]
            colored_ascii.append(f"[bold {color}]{line}[/bold {color}]")
        else:
            colored_ascii.append(line)
    
    colored_ascii_text = '\n'.join(colored_ascii)
    
    # Banner con máximo de decoración y colores vibrantes (sin la línea de Cyberpunk)
    banner_parts = [
        f"\n[bold deep_sky_blue1]▓▓▓▓▓[/bold deep_sky_blue1] " +
        f"[bold hot_pink]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold hot_pink] " +
        f"[bold deep_sky_blue1]▓▓▓▓▓[/bold deep_sky_blue1]\n",
        
        colored_ascii_text,
        
        f"\n[deep_sky_blue1]╔══════════════════════════════════════════════════════╗[/deep_sky_blue1]\n",
        
        f"  [bold green1]█[/bold green1] " +
        f"[bold orange1]Tidal Hi-Res 24-bit[/bold orange1] " +
        f"[cyan1]→[/cyan1] " +
        f"[bold hot_pink]YouTube Opus[/bold hot_pink] " +
        f"[cyan1]→[/cyan1] " +
        f"[bold medium_purple]Multi-Platform[/bold medium_purple]\n",
        
        f"[deep_sky_blue1]╚══════════════════════════════════════════════════════╝[/deep_sky_blue1]\n",
        
        f"[bold deep_sky_blue1]▓▓▓▓▓[/bold deep_sky_blue1] " +
        f"[bold hot_pink]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold hot_pink] " +
        f"[bold deep_sky_blue1]▓▓▓▓▓[/bold deep_sky_blue1]\n"
    ]
    
    styled_banner = ''.join(banner_parts)
    console.print(styled_banner)
    console.print()

def print_section(title, subtitle=""):
    """Panel de sección con título."""
    text = f"[bold {CYAN}]{title}[/bold {CYAN}]"
    if subtitle:
        text += f"\n[{PURPLE}]{subtitle}[/{PURPLE}]"
    
    console.print(f"\n[{MAGENTA}]{'━' * 50}[/{MAGENTA}]")
    console.print(text)
    console.print(f"[{MAGENTA}]{'━' * 50}[/{MAGENTA}]\n")

def print_status(message, status="info"):
    """Imprime mensaje con estado."""
    icons = {
        "success": "✓",
        "error": "✗",
        "warning": "⚠",
        "info": "ℹ",
        "loading": "⟳"
    }
    colors_map = {
        "success": "green",
        "error": "red",
        "warning": "yellow",
        "info": CYAN,
        "loading": MAGENTA
    }
    
    icon = icons.get(status, "→")
    color = colors_map.get(status, WHITE)
    console.print(f"  [{color}]{icon}[/{color}] {message}")

def print_download_header(title, artist="", tracks=0):
    """Header para descarga con estilo TRON."""
    text = f"[bold {CYAN}]▶ {title}[/bold {CYAN}]"
    if artist:
        text += f"\n[{PURPLE}]{artist}[/{PURPLE}]"
    if tracks:
        text += f" · [bold {MAGENTA}]{tracks} tracks[/bold {MAGENTA}]"
    
    panel = Panel(
        text,
        border_style=CYAN,
        padding=(0, 2),
        expand=False
    )
    console.print(panel)

def print_track_progress(num, total, artist, track, status="downloading"):
    """Muestra progreso de track con estilos TRON."""
    status_icons = {
        "downloading": "⟳",
        "completed": "✓",
        "error": "✗",
        "queued": "⏳"
    }
    status_colors = {
        "downloading": MAGENTA,
        "completed": "green",
        "error": "red",
        "queued": PURPLE
    }
    
    icon = status_icons.get(status, "→")
    color = status_colors.get(status, CYAN)
    
    track_text = f"{artist} - {track}"
    if len(track_text) > 45:
        track_text = track_text[:42] + "..."
    
    console.print(f"  [{color}]{icon}[/{color}] [{CYAN}]{num}/{total}[/{CYAN}]  {track_text}", soft_wrap=True)

def print_stats(downloaded, total, size_mb, speed_mbps=""):
    """Estadísticas finales."""
    stats_text = f"""
[bold {CYAN}]═══════════════════════════════════[/bold {CYAN}]
[bold {MAGENTA}]Download Complete[/bold {MAGENTA}]
[bold {CYAN}]═══════════════════════════════════[/bold {CYAN}]

  [{CYAN}]✓[/{CYAN}] {downloaded}/{total} tracks descargados
  [{CYAN}]📦[/{CYAN}] Tamaño: {size_mb:.1f} MB
"""
    if speed_mbps:
        stats_text += f"  [{CYAN}]⚡[/{CYAN}] Velocidad: {speed_mbps} MB/s\n"
    
    stats_text += f"[bold {CYAN}]═══════════════════════════════════[/bold {CYAN}]"
    
    console.print(stats_text)

def print_welcome():
    """Pantalla de bienvenida."""
    print_banner()
    console.print(f"[{PURPLE}]Iniciando sesión...[/{PURPLE}]")
    console.print()

def menu_interactive(title, options, subtitle=""):
    """Menú interactivo con navegación por flechas ↑↓.
    
    Args:
        title: Título del menú
        options: Lista de opciones (strings)
        subtitle: Subtítulo opcional
        
    Returns:
        El índice de la opción seleccionada (0-based)
    """
    console.print(f"\n[bold {HOT_PINK}]{'━' * 60}[/bold {HOT_PINK}]")
    console.print(f"[bold {GOLD}]▶ {title}[/bold {GOLD}]")
    if subtitle:
        console.print(f"[{DEEP_BLUE}]{subtitle}[/{DEEP_BLUE}]")
    console.print(f"[bold {HOT_PINK}]{'━' * 60}[/bold {HOT_PINK}]\n")
    
    # Usar questionary para menú con flechas
    answer = questionary.select(
        "Selecciona con ↑↓ y presiona ENTER:",
        choices=options,
        pointer="→ ►",
        style=questionary.Style([
            ('pointer', 'fg:#ff69b4 bold'),
            ('highlighted', 'fg:#00d4ff bold'),
            ('selected', 'fg:#00ff00 bold'),
        ])
    ).ask()
    
    if answer:
        return options.index(answer)
    return 0

def print_menu_table(title, items, columns=None):
    """Imprime un menú como tabla estilo retro.
    
    Args:
        title: Título de la tabla
        items: Lista de items [{"label": "...", "description": "...", "icon": "..."}, ...]
        columns: Lista de nombres de columnas
    """
    console.print(f"\n[bold {DEEP_BLUE}]╔════════════════════════════════════════╗[/bold {DEEP_BLUE}]")
    console.print(f"[bold {GOLD}]║ {title:<38} ║[/bold {GOLD}]")
    console.print(f"[bold {DEEP_BLUE}]╠════════════════════════════════════════╣[/bold {DEEP_BLUE}]")
    
    for item in items:
        icon = item.get("icon", "  ")
        label = item.get("label", "")
        desc = item.get("description", "")
        
        line = f"║ {icon} [bold {HOT_PINK}]{label:<12}[/bold {HOT_PINK}] [cyan]{desc:<20}[/cyan] ║"
        console.print(line)
    
    console.print(f"[bold {DEEP_BLUE}]╚════════════════════════════════════════╝[/bold {DEEP_BLUE}]\n")

def print_loading_animation(text="Cargando"):
    """Muestra animación de carga estilo retro."""
    import time
    frames = ["◰", "◳", "◲", "◱"]
    for i in range(4):
        console.print(f"[bold {MAGENTA}]{frames[i]}[/bold {MAGENTA}] {text}...", end="\r")
        time.sleep(0.2)
    console.print(f"[bold {GREEN}]✓[/bold {GREEN}] {text} completo!", end="\r")
    console.print()

def print_error_box(title, message):
    """Imprime un cuadro de error estilo retro."""
    panel_text = f"[bold red]⚠ {title}[/bold red]\n\n{message}"
    panel = Panel(
        panel_text,
        border_style="red",
        title="[bold red]ERROR[/bold red]",
        padding=(1, 2)
    )
    console.print(panel)

def print_success_box(title, message):
    """Imprime un cuadro de éxito estilo retro."""
    panel_text = f"[bold green]✓ {title}[/bold green]\n\n{message}"
    panel = Panel(
        panel_text,
        border_style="green",
        title="[bold green]ÉXITO[/bold green]",
        padding=(1, 2)
    )
    console.print(panel)

def print_info_box(title, message):
    """Imprime un cuadro de información estilo retro."""
    panel_text = f"[bold {CYAN}]ℹ {title}[/bold {CYAN}]\n\n{message}"
    panel = Panel(
        panel_text,
        border_style=CYAN,
        title=f"[bold {CYAN}]INFO[/bold {CYAN}]",
        padding=(1, 2)
    )
    console.print(panel)

def print_download_progress(filename, current, total, downloaded_bytes=None, total_bytes=None):
    """Muestra progreso de descarga con una línea mejorada."""
    percent = (current / total * 100) if total > 0 else 0
    bar_length = 25
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    
    # Información de tamaño si la tenemos
    size_info = ""
    if downloaded_bytes and total_bytes:
        downloaded_mb = downloaded_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        size_info = f" {downloaded_mb:.1f}MB / {total_mb:.1f}MB"
    
    filename_short = filename[:35] if len(filename) > 35 else filename
    console.print(f"  [hot_pink]▶[/hot_pink] [{bar}] {percent:5.1f}%  [cyan]{filename_short}{size_info}[/cyan]")

def print_album_progress(album_name, current_track, total_tracks):
    """Muestra el progreso del álbum actual."""
    percent = (current_track / total_tracks * 100) if total_tracks > 0 else 0
    bar_length = 20
    filled = int(bar_length * current_track / total_tracks) if total_tracks > 0 else 0
    bar = "▮" * filled + "▯" * (bar_length - filled)
    
    console.print(f"\n[bold gold1]💿 {album_name}[/bold gold1]")
    console.print(f"  [{bar}] {current_track}/{total_tracks} tracks\n")

def print_track_downloading(track_num, total, artist, track_name, duration=""):
    """Muestra que se está descargando un track."""
    progress_text = f"  [hot_pink]⟳[/hot_pink] [{track_num}/{total}] [bold cyan]{artist}[/bold cyan] - [magenta]{track_name}[/magenta]"
    if duration:
        progress_text += f" [medium_purple]({duration})[/medium_purple]"
    console.print(progress_text)

def print_batch_progress(completed, total, current_item=""):
    """Muestra progreso de un lote de descargas."""
    percent = (completed / total * 100) if total > 0 else 0
    bar_length = 20
    filled = int(bar_length * completed / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    
    console.print(f"  [bold deep_sky_blue1]General:[/bold deep_sky_blue1] [{bar}] {percent:5.1f}% ({completed}/{total})")
    if current_item:
        console.print(f"  [cyan]→ {current_item}[/cyan]")

def show_download_summary(total_files, total_size_mb, duration_seconds, success_count=None, error_count=0):
    """Muestra un resumen final de descargas."""
    import time
    
    console.print(f"\n[bold deep_sky_blue1]╔═══════════════════════════════════════╗[/bold deep_sky_blue1]")
    console.print(f"[bold green1]✓ Descarga completada![/bold green1]")
    console.print(f"[bold deep_sky_blue1]╠═══════════════════════════════════════╣[/bold deep_sky_blue1]")
    console.print(f"  [bold cyan]📊 Total:[/bold cyan] {total_files} archivos")
    console.print(f"  [bold cyan]💾 Tamaño:[/bold cyan] {total_size_mb:.1f} MB")
    
    if duration_seconds:
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        console.print(f"  [bold cyan]⏱️  Tiempo:[/bold cyan] {minutes:02d}:{seconds:02d}")
    
    if success_count is not None and success_count > 0:
        console.print(f"  [bold green1]✓ Exitosos:[/bold green1] {success_count}")
    if error_count > 0:
        console.print(f"  [bold red]✗ Con error:[/bold red] {error_count}")
    
    if total_size_mb > 0 and duration_seconds and duration_seconds > 0:
        speed = total_size_mb / (duration_seconds / 3600)
        console.print(f"  [bold gold1]⚡ Velocidad:[/bold gold1] {speed:.2f} MB/s")
    
    console.print(f"[bold deep_sky_blue1]╚═══════════════════════════════════════╝[/bold deep_sky_blue1]\n")
