import pyfiglet

fonts = ['slant', 'banner', 'big', 'block', 'digital', 'shadow', 'small', 'standard']

for font in fonts:
    print(f"\n{'='*60}")
    print(f"OPCIÓN: {font.upper()}")
    print(f"{'='*60}\n")
    try:
        fig = pyfiglet.Figlet(font=font)
        print(fig.renderText('FIDELITY'))
    except:
        print(f"Font {font} no disponible")
