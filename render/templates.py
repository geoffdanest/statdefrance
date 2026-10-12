"""statdefrance — gabarits « Points ».

Chaque gabarit reçoit un post (dict) et renvoie une image 1080×1350.
Toute erreur de composition lève LayoutError avec un message en français :
le générateur doit alors raccourcir le texte, jamais réduire la typo.
"""
from PIL import Image, ImageDraw, ImageFont
import json, math, os, random, re

from .logo import draw_logo, ASSETS

W, H, M = 1080, 1350, 64          # format 4:5, marge de 64 px
SS = 2                             # suréchantillonnage : points parfaitement ronds
THIN = " "                    # espace fine (milliers, avant %)
NBSP = " "
FOOTER_TOP = H - M - 70            # rien ne doit descendre sous cette ligne (hors pied de page)

PALETTES = {
    "papier": dict(bg="#F7F4EC", ink="#0E1B3D", acc="#E4352B", sec="#2B4ACB",
                   mute="#DDD8CC", soft="#5E6577", grain=("dark", 0.09)),
    "nuit":   dict(bg="#0B1430", ink="#F5EFE3", acc="#FF5A4E", sec="#7FA2FF",
                   mute="#1F2C55", soft="#93A0BF", grain=("light", 0.10)),
}
FR_POLYS = json.load(open(f"{ASSETS}/france.json"))


class LayoutError(Exception):
    pass


def fmt(n):
    """34875 -> « 34 875 » avec espace fine ; 3.5 -> « 3,5 »."""
    if isinstance(n, float) and not n.is_integer():
        return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", THIN)
    return f"{int(n):,}".replace(",", THIN)


def typo(t):
    """Règles typographiques françaises appliquées à tout texte affiché."""
    t = t.replace("'", "’")
    t = re.sub(r"(\d) (\d{3})\b", rf"\1{THIN}\2", t)          # 34 875
    t = re.sub(r" (?=[%:;!?»])", THIN, t)                    # espace fine avant ponctuation haute
    t = re.sub(r"« ", "«" + THIN, t)
    t = re.sub(r" (?=\d)", NBSP, t)                           # un nombre reste avec le mot précédent
    t = re.sub(r"(\d) (?=[a-zA-Zéèàù%])", rf"\1{NBSP}", t)    # … et avec son unité
    return t


class Post:
    def __init__(self, palette):
        if palette not in PALETTES:
            raise LayoutError(f"Palette inconnue : {palette} (papier ou nuit)")
        self.t = PALETTES[palette]
        self.im = Image.new("RGB", (W * SS, H * SS), self.t["bg"])
        self._grain()
        self.d = ImageDraw.Draw(self.im)

    def _grain(self):
        """Bruit monochrome fin, posé uniquement sur le fond."""
        mode, amount = self.t["grain"]
        random.seed(42)
        n = Image.effect_noise((W * SS // 2, H * SS // 2), 64).resize((W * SS, H * SS), Image.NEAREST)
        tint = Image.new("RGB", n.size, "#000000" if mode == "dark" else "#FFFFFF")
        if mode == "dark":
            mask = n.point(lambda v: int(max(0, 128 - v) * 2 * amount))
        else:
            mask = n.point(lambda v: int(max(0, v - 128) * 2 * amount))
        self.im.paste(tint, (0, 0), mask)

    # primitives (coordonnées en px du post final)
    def f(self, name, s): return ImageFont.truetype(f"{ASSETS}/{name}.ttf", int(s * SS))
    def text(self, xy, t, font, fill, anchor="la"): self.d.text((xy[0] * SS, xy[1] * SS), t, font=font, fill=fill, anchor=anchor)
    def tw(self, t, font): return self.d.textlength(t, font=font) / SS
    def dot(self, cx, cy, r, fill): self.d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS], fill=fill)

    def wrap(self, t, font, maxw):
        out, line = [], ""
        for w in typo(t).split(" "):
            c = (line + " " + w).strip()
            if self.tw(c, font) > maxw and line:
                out.append(line); line = w
            else:
                line = c
        out.append(line)
        if any(self.tw(l, font) > maxw for l in out):
            raise LayoutError(f"Un mot est trop long pour la largeur : « {t[:40]}… »")
        # pas de mot seul en dernière ligne
        if len(out) > 1 and " " not in out[-1]:
            prev = out[-2].rsplit(" ", 1)
            if len(prev) == 2 and self.tw(prev[1] + " " + out[-1], font) <= maxw:
                out[-2], out[-1] = prev[0], prev[1] + " " + out[-1]
        return out

    def para(self, xy, t, font, fill, lh, maxw, max_lines, field, anchor="la"):
        ls = self.wrap(t, font, maxw)
        if len(ls) > max_lines:
            raise LayoutError(f"« {field} » fait {len(ls)} lignes (max {max_lines}). Raccourcir le texte.")
        for i, l in enumerate(ls):
            self.text((xy[0], xy[1] + i * lh), l, font, fill, anchor)
        return xy[1] + len(ls) * lh

    def chrome(self, p, right=None):
        t = self.t
        draw_logo(self.d, M, M + 26, 30, t["ink"], t["acc"], SS)
        self.text((W - M, M + 26), p["theme"].upper(), self.f("inter700", 20), t["acc"], "rs")
        src = typo(f"Source : {p['source']}")
        fn = self.f("inter500", 21)
        right = right or p.get("num", "")
        if self.tw(src, fn) > W - 2 * M - self.tw(right, self.f("mono400", 20)) - 40:
            raise LayoutError("« source » trop longue pour le pied de page. Abréger (ex. « Insee, COG 2026 »).")
        self.text((M, H - M), src, fn, t["soft"], "ls")
        self.text((W - M, H - M), right, self.f("mono400", 20), t["soft"], "rs")

    def check_bottom(self, y, what):
        if y > FOOTER_TOP:
            raise LayoutError(f"{what} descend dans le pied de page ({int(y)} > {FOOTER_TOP}). Raccourcir.")

    def image(self):
        return self.im.resize((W, H), Image.LANCZOS)


# ── 1. GRILLE 100 : 1 point = 1 % ───────────────────────────────────────────
def grille(p):
    pct = int(round(float(p["pct"])))
    if not 1 <= pct <= 99:
        raise LayoutError("« pct » doit être entre 1 et 99 pour la grille.")
    s = Post(p["palette"]); t = s.t
    s.chrome(p, "1 point = 1 %".replace(" %", THIN + "%"))
    g, r = 84, 31
    x0 = M + r + (W - 2 * M - 2 * r - 9 * g) / 2; y0 = 196
    for i in range(100):
        s.dot(x0 + (i % 10) * g, y0 + (i // 10) * g, r, t["acc"] if i < pct else t["mute"])
    by = y0 + 9 * g + r + 150
    big = s.f("inter900", 128); lab = f"{pct}{THIN}%"
    s.text((M - 4, by), lab, big, t["ink"], "ls")
    lx = M + s.tw(lab, big) + 36
    fn = s.f("inter500", 32)
    ls = s.wrap(p["label"], fn, W - M - lx)
    if len(ls) > 3:
        raise LayoutError(f"« label » fait {len(ls)} lignes à côté du chiffre (max 3). Raccourcir.")
    for i, l in enumerate(ls):  # légende calée sur la ligne de base du chiffre
        s.text((lx, by - (len(ls) - 1 - i) * 42), l, fn, t["ink"], "ls")
    return s.image()


# ── 2. CARTE EN POINTS : vrai tracé de la France, trame hexagonale ──────────
def _inside(x, y, poly):
    c, j = False, len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def carte(p):
    s = Post(p["palette"]); t = s.t; s.chrome(p)
    lon0, lon1, lat0, lat1 = -5.3, 9.7, 41.25, 51.2
    k = math.cos(math.radians(46.5)); mw = 800
    sc = mw / ((lon1 - lon0) * k); mh = (lat1 - lat0) * sc
    ox, oy, step = (W - mw) / 2, 150, 19
    for gy in range(int(mh / (step * 0.866)) + 1):
        for gx in range(int(mw / step) + 1):
            x = ox + gx * step + (step / 2 if gy % 2 else 0); y = oy + gy * step * 0.866
            lon = lon0 + (x - ox) / (sc * k); lat = lat1 - (y - oy) / sc
            on = any(_inside(lon, lat, poly) for poly in FR_POLYS)
            s.dot(x, y, 6.6 if on else 1.9, t["acc"] if on else t["mute"])
    by = oy + mh + 40
    big = s.f("inter900", 148); num = fmt(p["number"]) if not isinstance(p["number"], str) else typo(p["number"])
    unit = s.f("inter500", 44)
    if s.tw(num, big) + 22 + s.tw(typo(p["unit"]), unit) > W - 2 * M:
        raise LayoutError("Chiffre + unité trop larges. Utiliser une unité plus courte ou « 1,2 million ».")
    s.text((M - 4, by + 128), num, big, t["ink"], "ls")
    s.text((M + s.tw(num, big) + 22, by + 128), typo(p["unit"]), unit, t["ink"], "ls")
    y = s.para((M, by + 200), p["hook"], s.f("inter500", 32), t["soft"], 44, W - 2 * M, 2, "hook")
    s.check_bottom(y, "Le texte sous la carte")
    return s.image()


# ── 3. HÉMICYCLE : une part d'un tout, remplie de gauche à droite ──────────
def hemicycle(p):
    pct = float(p["pct"])
    if not 1 <= pct <= 99:
        raise LayoutError("« pct » doit être entre 1 et 99 pour l’hémicycle.")
    s = Post(p["palette"]); t = s.t; s.chrome(p)
    s.para((M, 196), p["title"], s.f("inter700", 64), t["ink"], 74, W - 2 * M, 3, "title")
    cx, cy, rows, r0, r1, rd = W / 2, 1010, 8, 250, 470, 15.5
    seats = []
    for k in range(rows):
        rr = r0 + k * (r1 - r0) / (rows - 1); n = round(math.pi * rr / (2 * rd + 13))
        for j in range(n):
            seats.append((math.pi - j * math.pi / (n - 1), rr))
    seats.sort(key=lambda a: (-round(a[0], 4), a[1]))
    filled = round(len(seats) * pct / 100)
    for i, (a, rr) in enumerate(seats):
        s.dot(cx + rr * math.cos(a), cy - rr * math.sin(a), rd, t["acc"] if i < filled else t["mute"])
    lab = (fmt(pct) if pct != int(pct) else str(int(pct))) + THIN + "%"
    s.text((cx, cy - 6), lab, s.f("inter900", 128), t["ink"], "ms")
    lf = s.f("inter500", 28)
    if s.tw(typo(p["label"]), lf) > 2 * r0 + 60:
        raise LayoutError("« label » trop long pour le centre de l’hémicycle (une ligne courte).")
    s.text((cx, cy + 46), typo(p["label"]), lf, t["soft"], "ms")
    return s.image()


# ── 4. COMPARAISON : 1 point = N unités ─────────────────────────────────────
def _per_dot(vmax, cap=44):
    for base in [1, 2, 5]:
        for e in range(0, 10):
            u = base * 10 ** e
            if vmax / u <= cap:
                return u
    raise LayoutError("Valeurs trop grandes pour la comparaison.")


def compare(p):
    rows = p["rows"]
    if not 2 <= len(rows) <= 5:
        raise LayoutError("La comparaison prend 2 à 5 lignes.")
    per = p.get("per_dot") or _per_dot(max(r["value"] for r in rows))
    unit = p.get("dot_unit", "")
    s = Post(p["palette"]); t = s.t
    s.chrome(p, typo(f"1 point = {fmt(per)} {unit}".strip()))
    y = s.para((M, 196), p["title"], s.f("inter700", 58), t["ink"], 68, W - 2 * M, 3, "title") + 80
    r, g, perrow = 15.5, 43, 22
    for row in rows:
        col = t["acc"] if row.get("highlight") else t["sec"]
        s.text((M, y), typo(row["name"]), s.f("inter700", 30), t["ink"], "ls")
        s.text((W - M, y), fmt(row["value"]), s.f("inter700", 30), t["ink"], "rs")
        n = max(1, round(row["value"] / per))
        for i in range(n):
            s.dot(M + r + (i % perrow) * g, y + 44 + (i // perrow) * g, r, col)
        y += 44 + ((n - 1) // perrow + 1) * g + 64
    s.check_bottom(y - 64, "La comparaison")
    if not any(r.get("highlight") for r in rows):
        raise LayoutError("Marquer une ligne avec \"highlight\": true (en rouge).")
    return s.image()


TEMPLATES = {"grille": grille, "carte": carte, "hemicycle": hemicycle, "compare": compare}
REQUIRED = {
    "grille": ["pct", "label"],
    "carte": ["number", "unit", "hook"],
    "hemicycle": ["pct", "title", "label"],
    "compare": ["title", "rows"],
}
COMMON = ["date", "theme", "palette", "template", "num", "source", "source_url", "dataset_id", "caption"]


def render(post):
    missing = [k for k in COMMON + REQUIRED.get(post.get("template"), []) if k not in post]
    if post.get("template") not in TEMPLATES:
        raise LayoutError(f"Gabarit inconnu : {post.get('template')} ({', '.join(TEMPLATES)})")
    if missing:
        raise LayoutError(f"Champs manquants : {', '.join(missing)}")
    if not str(post["source_url"]).startswith("https://www.data.gouv.fr/"):
        raise LayoutError("« source_url » doit pointer vers une page data.gouv.fr.")
    return TEMPLATES[post["template"]](post)
