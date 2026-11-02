"""Version story (1080×1920) d'un post : python -m render.story posts/2026-11-03.json [autres.json …]

Le visuel du post est posé au centre, sur le fond de sa palette (avec le grain),
et le JPEG est écrit à côté du post : posts/AAAA-MM-JJ-story.jpg (ou -soir-story.jpg).
Option --missing : ne rend que les stories absentes.
"""
import json, random, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .templates import PALETTES
from .logo import ASSETS

SW, SH = 1080, 1920
CARD_W = 936                     # le post occupe 936 px de large (marges de 72 px)


def grain(im, mode, amount):
    random.seed(42)
    n = Image.effect_noise((im.width // 2, im.height // 2), 64).resize(im.size, Image.NEAREST)
    tint = Image.new("RGB", n.size, "#000000" if mode == "dark" else "#FFFFFF")
    if mode == "dark":
        mask = n.point(lambda v: int(max(0, 128 - v) * 2 * amount))
    else:
        mask = n.point(lambda v: int(max(0, v - 128) * 2 * amount))
    im.paste(tint, (0, 0), mask)


def story(post_path):
    post_path = Path(post_path)
    post = json.loads(post_path.read_text(encoding="utf-8"))
    t = PALETTES[post["palette"]]
    im = Image.new("RGB", (SW, SH), t["bg"])
    grain(im, *t["grain"])
    card = Image.open(post_path.with_suffix(".jpg")).convert("RGB")
    ch = round(card.height * CARD_W / card.width)
    card = card.resize((CARD_W, ch), Image.LANCZOS)
    x, y = (SW - CARD_W) // 2, (SH - ch) // 2 - 40
    d = ImageDraw.Draw(im)
    d.rectangle([x - 2, y - 2, x + CARD_W + 1, y + ch + 1], outline=t["mute"], width=2)
    im.paste(card, (x, y))
    # appel discret sous le post
    f = ImageFont.truetype(f"{ASSETS}/mono400.ttf", 26)
    d.text((SW // 2, y + ch + 74), "Nouveau post  ·  @statdefrance", font=f, fill=t["soft"], anchor="ms")
    out = post_path.with_name(post_path.stem + "-story.jpg")
    im.save(out, "JPEG", quality=92, optimize=True, progressive=True)
    return out


def main(args):
    missing = "--missing" in args
    code = 0
    for a in [a for a in args if not a.startswith("--")]:
        p = Path(a)
        if p.stem.endswith("-story") or not p.with_suffix(".jpg").exists():
            continue
        out = p.with_name(p.stem + "-story.jpg")
        if missing and out.exists():
            continue
        try:
            print(f"OK      {p.name} → {story(p).name}")
        except Exception as e:
            code = 1; print(f"ERREUR  {p.name} : {e}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
