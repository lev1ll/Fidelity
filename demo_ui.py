#!/usr/bin/env python3
"""Demo de la nueva interfaz interactiva con menús por flechas."""

from ui import print_banner, menu_interactive, print_info_box, print_success_box, print_error_box

# Mostrar banner
print_banner()

# Mostrar demostración del menú
print("\n" + "="*60)
print("DEMOSTRACIÓN: Menú interactivo con navegación por flechas")
print("="*60 + "\n")

print("[bold yellow]→ Menú principal con ↑↓ para navegar:[/bold yellow]\n")

# Opciones del menú
demo_options = [
    "🎵 Tidal - FLAC / Video (Hi-Res 24-bit)",
    "▶️  YouTube - Opus / AAC / Video",
    "⚙️  Configuración",
    "🚪 Salir"
]

print("[cyan]Prueba escribiendo números 1-4 y presiona ENTER[/cyan]\n")
print("Opciones disponibles:")
for i, opt in enumerate(demo_options, 1):
    print(f"  {i}. {opt}")

print("\n" + "="*60)

# Demostraciones de otros elementos de UI
print_success_box("Descarga Completada", "Se descargaron 13 canciones en 2:45 minutos\n→ Tamaño: 850 MB\n→ Velocidad promedio: 5.2 MB/s")

print_info_box("Información", "Fidelity v1.8.0 - Menús interactivos con navegación por flechas ↑↓")

print_error_box("Ejemplo de Error", "Archivo no encontrado: config.json\n→ Solución: Ejecuta el setup nuevamente")

print("\n[bold green]✓ Demo completada[/bold green]\n")
