"""Rendu des posts : python -m render posts/2026-10-20.json [autres.json …]

Pour chaque post : vérifie le contenu, compose le visuel, écrit le JPEG à côté
du JSON (Instagram n'accepte que le JPEG). Code de sortie 1 si un post échoue.
Option --planche : écrit aussi posts/_planche.jpg avec tous les visuels rendus.
"""
import json, sys, re
from pathlib import Path
from PIL import Image
from .templates import render, LayoutError, W, H


def check_caption(post):
    cap = post["caption"]
    if len(cap) > 2200:
        raise LayoutError(f"Légende trop longue ({len(cap)} caractères, max 2200).")
    tags = re.findall(r"#\w+", cap)
    if len(tags) > 30:
        raise LayoutError(f"{len(tags)} hashtags (max 30).")
    if post["source_url"] not in cap and "data.gouv.fr" not in cap:
        raise LayoutError("La légende doit citer la source (data.gouv.fr).")


def main(args):
    planche = "--planche" in args
    paths = [Path(a) for a in args if not a.startswith("--")]
    ok, rendered = True, []
    for p in paths:
        try:
            post = json.loads(p.read_text(encoding="utf-8"))
            check_caption(post)
            im = render(post)
            out = p.with_suffix(".jpg")
            im.save(out, "JPEG", quality=94, optimize=True, progressive=True)
            rendered.append(out)
            print(f"OK      {p.name} → {out.name}")
        except LayoutError as e:
            ok = False; print(f"ERREUR  {p.name} : {e}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            ok = False; print(f"ERREUR  {p.name} : contenu invalide ({e})")
    if planche and rendered:
        cols = min(4, len(rendered)); rows = (len(rendered) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (W + 40) - 40, rows * (H + 40) - 40), "#D6D6D6")
        for i, f in enumerate(rendered):
            sheet.paste(Image.open(f), ((i % cols) * (W + 40), (i // cols) * (H + 40)))
        out = rendered[0].parent / "_planche.jpg"
        sheet.resize((sheet.width // 3, sheet.height // 3), Image.LANCZOS).save(out, quality=88)
        print(f"Planche : {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
