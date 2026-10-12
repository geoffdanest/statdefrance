"""Logo stat•de•france : Inter Black, approche « Très serré », points rapprochés."""
from PIL import ImageFont
import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TRACK = -0.07      # approche des lettres, en fraction du corps
DOT_GAP = 0.02     # espace entre un point et les lettres, en fraction du corps
DOT_R = 0.12       # rayon du point, en fraction du corps


def draw_logo(d, x, y, size, ink, acc, ss=1):
    """Dessine le logo. (x, y) = ligne de base à gauche, en px non suréchantillonnés."""
    f = ImageFont.truetype(f"{ASSETS}/inter900.ttf", int(size * ss))
    cx = x
    for i, word in enumerate(["stat", "de", "france"]):
        for j, ch in enumerate(word):
            pos = f.getlength(word[:j]) / ss + j * TRACK * size
            d.text(((cx + pos) * ss, y * ss), ch, font=f, fill=ink, anchor="ls")
        cx += f.getlength(word) / ss + (len(word) - 1) * TRACK * size
        if i < 2:
            r, g = size * DOT_R, size * DOT_GAP
            dx, dy = cx + g + r, y - size * 0.30
            d.ellipse([(dx - r) * ss, (dy - r) * ss, (dx + r) * ss, (dy + r) * ss], fill=acc)
            cx = dx + r + g
    return cx
