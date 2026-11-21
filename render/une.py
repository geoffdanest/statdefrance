"""statdefrance — slide « une » du créneau actu : photo plein cadre + titre en capitales.

Mise en page inspirée des médias d'actu : photo pleine page, dégradé sombre en bas, titre en
capitales (1re partie en crème, 2e partie en corail), ligne « stat·de·france · date », crédit photo.
La photo est recadrée pour remplir le 4:5 ; `focus` (0–1, défaut 0.5) choisit le point vertical gardé.
"""
import numpy as np
from PIL import Image, ImageDraw
from .templates import Post, LayoutError, M, W, H, SS, PALETTES, typo
from .logo import draw_logo

NUIT = PALETTES["nuit"]
GRAIN = 10          # écart-type du bruit, en niveaux (0–255)


def _cover(path, focus=0.5):
    im = Image.open(path).convert("RGB")
    r = max(W * SS / im.width, H * SS / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x = (im.width - W * SS) // 2
    y = round((im.height - H * SS) * focus)
    return im.crop((x, y, x + W * SS, y + H * SS))


def _gradient(start, color):
    """Dégradé vertical : transparent à `start` (0–1 de la hauteur) → couleur pleine en bas."""
    g = Image.new("L", (1, H * SS))
    y0 = int(start * H * SS)
    for y in range(H * SS):
        t = 0 if y < y0 else (y - y0) / (H * SS * 0.80 - y0)        # opaque dès 80 % de la hauteur
        g.putpixel((0, y), int(255 * min(1, max(0, t) ** 1.4)))
    g = g.resize((W * SS, H * SS))
    return Image.new("RGB", (W * SS, H * SS), color), g


def _film_grain(im, amount=GRAIN, seed=42):
    """Grain monochrome type argentique, posé sur toute l'image (photo comprise)."""
    rng = np.random.default_rng(seed)
    h, w = im.height // 2, im.width // 2                      # grain à l'échelle du post final
    n = rng.normal(0, amount, (h, w)).astype(np.float32)
    n = np.asarray(Image.fromarray(n, mode="F").resize((im.width, im.height), Image.NEAREST))
    a = np.asarray(im).astype(np.float32)
    lum = a.mean(axis=2, keepdims=True) / 255
    weight = 0.6 + 0.8 * lum * (1 - lum) * 4 / 1.6            # plus visible dans les tons moyens
    out = np.clip(a + n[..., None] * weight, 0, 255).astype(np.uint8)
    return Image.fromarray(out)


def render_une(p, photo_path):
    t = NUIT
    s = Post("nuit")                         # fond + grain, remplacés par la photo puis le grain re-posé
    photo = _cover(photo_path, p.get("photo_focus", 0.5))
    shade, mask = _gradient(0.30, t["bg"])
    photo.paste(shade, (0, 0), mask)
    top = Image.new("L", (1, H * SS))        # léger voile en haut pour lire le logo
    for y in range(H * SS):
        top.putpixel((0, y), int(140 * max(0, 1 - y / (260 * SS))))
    photo.paste(Image.new("RGB", (W * SS, H * SS), t["bg"]), (0, 0), top.resize((W * SS, H * SS)))
    s.im = _film_grain(photo)
    s.d = ImageDraw.Draw(s.im)

    draw_logo(s.d, M, M + 26, 30, t["ink"], t["acc"], SS)
    s.text((W - M, M + 26), ("Actu · " + p["theme"]).upper(), s.f("inter700", 20), t["acc"], "rs")

    fh, lh = s.f("inter900", 58), 66
    a = s.wrap(p["une"][0].upper(), fh, W - 2 * M)
    b = s.wrap(p["une"][1].upper(), fh, W - 2 * M) if len(p["une"]) > 1 else []
    if len(a) + len(b) > 5:
        raise LayoutError(f"« une » fait {len(a) + len(b)} lignes (max 5). Raccourcir.")
    meta = typo(f"stat·de·france  ·  {p['date'][8:10]}/{p['date'][5:7]}/{p['date'][:4]}")
    credit = typo(p.get("photo_credit", ""))
    y = H - M - 70 - 40 - (len(a) + len(b)) * lh + lh      # ligne de base de la 1re ligne
    for l in a:
        s.text((M, y), l, fh, t["ink"], "ls"); y += lh
    for l in b:
        s.text((M, y), l, fh, t["acc"], "ls"); y += lh
    s.text((M, H - M - 18), meta, s.f("inter500", 24), t["soft"], "ls")
    if credit:
        s.text((W - M, H - M - 18), credit, s.f("mono400", 16), t["soft"], "rs")
    return s.image()
