# Fonts

Bundled TrueType fonts for the renderer live here.

## Add these files manually

The renderer prefers these exact filenames:

- `DejaVuSans.ttf` — regular weight (body / detail text)
- `DejaVuSans-Bold.ttf` — bold weight (section titles, header)

DejaVu Sans is a good 1-bit e-ink choice (clear at small sizes, wide glyph
coverage including `°` and accents) and is freely redistributable. On most
Linux systems the files are at `/usr/share/fonts/truetype/dejavu/`.

Do not commit fonts you are not licensed to redistribute.

## Fallback behaviour

If these files are absent, `launchpad.rendering.fonts.load_font(size)` falls
back to `PIL.ImageFont.load_default(size=size)`, which still scales with the
requested size so the typographic hierarchy is preserved. Quality/legibility
improves once the real TTFs are added.
