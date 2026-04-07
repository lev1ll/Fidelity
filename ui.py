"""UI estilo TRON con rich para terminal."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.table import Table
import pyfiglet

console = Console()

# Colores TRON
CYAN = "cyan1"
MAGENTA = "magenta"
PURPLE = "purple"
BLUE = "blue"
WHITE = "white"

def print_banner():
    """Banner épico estilo Gemini con ASCII art grande."""
    
    # Crear ASCII art grande con pyfiglet
    fig = pyfiglet.Figlet(font='slant', width=100)
    ascii_text = fig.renderText('FIDELITY')
    
    # Líneas decorativas
    banner_text = f"""
{ascii_text}
    ⚡  C Y B E R P U N K   M U S I C   D O W N L O A D E R  ⚡

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    Tidal Hi-Res 24-bit  •  YouTube Opus  •  Multi-Platform
    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    
    # Aplicar estilos de color - cada línea con color diferente
    lines = banner_text.split('\n')
    styled_lines = []
    
    for i, line in enumerate(lines):
        if 'FIDELITY' in line:
            styled_lines.append(f"[bold {MAGENTA}]{line}[/bold {MAGENTA}]")
        elif '⚡' in line:
            styled_lines.append(f"[bold {CYAN}]{line}[/bold {CYAN}]")
        elif '━' in line:
            styled_lines.append(f"[{PURPLE}]{line}[/{PURPLE}]")
        elif line.strip():
            styled_lines.append(f"[{CYAN}]{line}[/{CYAN}]")
        else:
            styled_lines.append(line)
    
    styled_banner = '\n'.join(styled_lines)
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
