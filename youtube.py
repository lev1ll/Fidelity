from ui import (
    console, menu_interactive, print_info_box, print_error_box, print_success_box,
)
from utils import ensure_installed, check_ffmpeg, fmt_duration, pick, pick_multi

_VIDEO_CODEC_NAMES = {
    "av01": "AV1", "vp09": "VP9", "vp9": "VP9",
    "avc1": "H.264", "hvc1": "H.265", "dvh1": "H.265",
}

def yt_search(query, limit=10):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        return info.get("entries", [])

def yt_get_all_formats(url):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

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
            continue
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
            {"key": "EmbedThumbnail"},
        ]
    opts = {
        "format": fmt,
        "outtmpl": str(dest_dir / "%(title)s.%(ext)s"),
        "postprocessors": postprocessors,
        "writethumbnail": has_ffmpeg,
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

        if choice == 2:
            break

        url = None
        dest = download_dir / "YouTube"

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
            dest.mkdir(parents=True, exist_ok=True)
            for entry in selected:
                url = f"https://www.youtube.com/watch?v={entry['id']}"
                yt_download(url, dest)
            print_success_box("Descarga completada", f"Guardado en: {dest}")

        elif choice == 1:  # Pegar URL
            url = input("\n  🔗 Pegá el link de YouTube: ").strip()
            if not url:
                continue

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

            if mode == 2:
                continue

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
