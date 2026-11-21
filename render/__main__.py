"""Rendu des posts : python -m render posts/2026-10-20.json [autres.json …]

Pour chaque post : vérifie le contenu, compose le visuel, écrit le JPEG à côté
du JSON (Instagram n'accepte que le JPEG). Code de sortie 1 si un post échoue.
Si le post a un champ « question », écrit aussi la slide finale du carrousel
(<post>-fin.jpg : la question + abonne-toi / partage, même palette).
Si le post a un champ « une » (créneaux actu), écrit aussi la slide d'ouverture
(<post>-une.jpg : photo plein cadre + titre), à partir de la photo du champ « photo ».
Si « template » vaut « une » (créneau actu sans donnée pertinente), seule la une est rendue,
dans <post>.jpg : le post est publié en image seule, sans visuel ni slide finale.
Option --planche : écrit aussi posts/_planche.jpg avec tous les visuels rendus.
"""
import json, sys, re
from pathlib import Path
from PIL import Image
from .templates import render, LayoutError, W, H
from .cta import render_cta
from .une import render_une

ROOT = Path(__file__).resolve().parent.parent


def check_caption(post):
    cap = post["caption"]
    if len(cap) > 2200:
        raise LayoutError(f"Légende trop longue ({len(cap)} caractères, max 2200).")
    tags = re.findall(r"#\w+", cap)
    if len(tags) > 30:
        raise LayoutError(f"{len(tags)} hashtags (max 30).")
    if post["source_url"] not in cap:
        raise LayoutError("La légende doit citer l'URL de la source (source_url).")
    q = post.get("question")
    if q and q.strip() not in cap:
        raise LayoutError("La légende doit reprendre la « question » (seule sur sa ligne, avant la source).")


def main(args):
    planche = "--planche" in args
    paths = [Path(a) for a in args if not a.startswith("--")]
    ok, rendered = True, []
    for p in paths:
        try:
            post = json.loads(p.read_text(encoding="utf-8"))
            check_caption(post)
            seule = post.get("template") == "une"   # créneau actu sans donnée : la une seule, sans carrousel
            if seule and post.get("question"):
                raise LayoutError("Post « une » seule : pas de « question » (pas de carrousel).")
            im = None if seule else render(post)
            if post.get("une"):
                photo = ROOT / post.get("photo", "")
                if not post.get("photo") or not photo.is_file():
                    raise LayoutError("« photo » manquante : chemin du fichier depuis la racine du repo (ex. posts/photos/AAAA-MM-JJ-actu-20h.jpg).")
                if not post.get("photo_credit"):
                    raise LayoutError("« photo_credit » manquant (ex. « Photo : Nom, CC0 »).")
                if post["photo_credit"] not in post.get("caption", ""):
                    raise LayoutError("La légende doit reprendre « photo_credit » (ligne après la source).")
                une = p.with_suffix(".jpg") if seule else p.with_name(p.stem + "-une.jpg")
                render_une(post, photo).save(une, "JPEG", quality=94, optimize=True, progressive=True)
                rendered.append(une)
                print(f"OK      {p.name} → {une.name} (une{' seule' if seule else ''})")
                if seule:
                    continue
            elif seule:
                raise LayoutError("Post « une » seule : champs « une » et « photo » obligatoires.")
            out = p.with_suffix(".jpg")
            im.save(out, "JPEG", quality=94, optimize=True, progressive=True)
            rendered.append(out)
            print(f"OK      {p.name} → {out.name}")
            if post.get("question"):
                fin = p.with_name(p.stem + "-fin.jpg")
                render_cta(post["palette"], post["question"]).save(fin, "JPEG", quality=94, optimize=True, progressive=True)
                rendered.append(fin)
                print(f"OK      {p.name} → {fin.name} (slide finale)")
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
