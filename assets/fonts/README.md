# Fonts

Bundled TrueType fonts for the renderer live here.

TODO: add a real `.ttf` (e.g. `DejaVuSans.ttf` or an open-licensed UI font) and
point `launchpad.rendering.fonts.DEFAULT_FONT_FILE` at it. Until a font file is
present, the renderer falls back to `PIL.ImageFont.load_default()` so rendering
never crashes (legibility/quality will be limited).
