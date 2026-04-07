"""Módulo de barras de progreso mejoradas con Rich."""

from rich.console import Console
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TextColumn
from rich.text import Text

console = Console()

def create_progress_bar():
    """Crea una barra de progreso estilo Gemini."""
    return Progress(
        TextColumn("[bold deep_sky_blue1]⟳[/bold deep_sky_blue1] [cyan]{task.description}"),
        BarColumn(bar_width=30, style="hot_pink", complete_style="green1"),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "·",
        DownloadColumn(),
        "·",
        TransferSpeedColumn(),
        "·",
        TimeRemainingColumn(),
        console=console,
        transient=True
    )

def print_download_progress(filename, current, total, downloaded_bytes=None, total_bytes=None):
    """Muestra progreso de descarga con una línea simple."""
    percent = (current / total * 100) if total > 0 else 0
    bar_length = 30
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    
    # Información de tamaño si la tenemos
    size_info = ""
    if downloaded_bytes and total_bytes:
        downloaded_mb = downloaded_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        size_info = f"  {downloaded_mb:.1f}MB / {total_mb:.1f}MB"
    
    console.print(f"  [hot_pink]▶[/hot_pink] [{bar}] {percent:5.1f}%  [cyan]{filename[:40]:40}[/cyan]{size_info}")

def print_album_progress(album_name, current_track, total_tracks):
    """Muestra el progreso del álbum actual."""
    percent = (current_track / total_tracks * 100) if total_tracks > 0 else 0
    bar_length = 20
    filled = int(bar_length * current_track / total_tracks) if total_tracks > 0 else 0
    bar = "▮" * filled + "▯" * (bar_length - filled)
    
    console.print(f"\n[bold gold1]💿 {album_name}[/bold gold1]")
    console.print(f"  [{bar}] {current_track}/{total_tracks} tracks")

def print_track_downloading(track_num, total, artist, track_name, duration=""):
    """Muestra que se está descargando un track."""
    progress_text = f"  [hot_pink]⟳[/hot_pink] [{current_track}/{total}] [bold cyan]{artist}[/bold cyan] - [magenta]{track_name}[/magenta]"
    if duration:
        progress_text += f" [medium_purple]({duration})[/medium_purple]"
    console.print(progress_text)

def print_batch_progress(completed, total, current_item):
    """Muestra progreso de un lote de descargas."""
    percent = (completed / total * 100) if total > 0 else 0
    bar_length = 25
    filled = int(bar_length * completed / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    
    console.print(f"  [bold deep_sky_blue1]Descarga general:[/bold deep_sky_blue1] [{bar}] {percent:5.1f}% ({completed}/{total})")
    console.print(f"  [cyan]Descargando:[/cyan] {current_item}\n")

def show_download_summary(total_files, total_size_mb, duration_seconds, success_count, error_count):
    """Muestra un resumen final de descargas."""
    console.print("\n[bold deep_sky_blue1]╔═══════════════════════════════════════╗[/bold deep_sky_blue1]")
    console.print("[bold green1]✓ Descarga completada![/bold green1]")
    console.print("[bold deep_sky_blue1]╠═══════════════════════════════════════╣[/bold deep_sky_blue1]")
    console.print(f"  [bold cyan]📊 Total:[/bold cyan] {total_files} archivos")
    console.print(f"  [bold cyan]💾 Tamaño:[/bold cyan] {total_size_mb:.1f} MB")
    console.print(f"  [bold cyan]⏱️  Tiempo:[/bold cyan] {int(duration_seconds // 60):02d}:{int(duration_seconds % 60):02d}")
    
    if success_count > 0:
        console.print(f"  [bold green1]✓ Exitosos:[/bold green1] {success_count}")
    if error_count > 0:
        console.print(f"  [bold red]✗ Con error:[/bold red] {error_count}")
    
    if total_size_mb > 0:
        speed = total_size_mb / (duration_seconds / 60 / 60) if duration_seconds > 0 else 0
        console.print(f"  [bold gold1]⚡ Velocidad:[/bold gold1] {speed:.2f} MB/s")
    
    console.print("[bold deep_sky_blue1]╚═══════════════════════════════════════╝[/bold deep_sky_blue1]\n")
