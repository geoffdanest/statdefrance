"""statdefrance — slide finale des carrousels : la question du post + abonne-toi / partage.

Mise en page fixe ; seul le texte de la question change (champ « question » du post).
Chaque post est publié en carrousel : [visuel du jour, slide finale de la même palette].
python -m render.cta "Normal ou pas ?" [papier|nuit]  → aperçu cta/apercu-<palette>.jpg
"""
import sys
from pathlib import Path
from .templates import Post, LayoutError, M, W, H, typo
from .logo import draw_logo

ABOUT = "Chaque jour, deux chiffres tirés des données publiques de l’État."
ACTIONS = [("Abonne-toi", "pour ne rien rater."),
           ("Partage", "à quelqu’un qui doit voir ça.")]


def render_cta(palette, question):
    if not question or not question.strip().endswith("?"):
        raise LayoutError("« question » doit être une question courte, terminée par « ? ».")
    s = Post(palette); t = s.t
    draw_logo(s.d, M, M + 26, 30, t["ink"], t["acc"], 2)
    s.text((W - M, M + 26), "ET TOI ?", s.f("inter700", 20), t["acc"], "rs")
    s.text((M, H - M), typo("data.gouv.fr · Insee · portails publics"), s.f("inter500", 21), t["soft"], "ls")
    s.text((W - M, H - M), "@statdefrance", s.f("mono400", 20), t["soft"], "rs")

    fq, lq = s.f("inter900", 96), 104
    q = s.wrap(question.strip(), fq, W - 2 * M)
    if len(q) > 3:
        raise LayoutError(f"« question » fait {len(q)} lignes sur la slide finale (max 3). Raccourcir.")
    fr, lr = s.f("inter500", 36), 50
    fa, la = s.f("inter700", 46), 82
    fb, lb = s.f("inter500", 30), 42
    about = s.wrap(ABOUT, fb, W - 2 * M)
    r, g, n = 15.5, 43, 22

    # hauteur du bloc, pour le centrer verticalement entre l'en-tête et le pied de page
    block = len(q) * lq + 30 + lr + 90 + 2 * r + 96 + len(ACTIONS) * la + 40 + len(about) * lb
    top, bottom = 150, H - M - 80
    y = top + (bottom - top - block) / 2 + 76            # + hauteur de capitale

    for l in q:
        s.text((M, y), l, fq, t["ink"], "ls"); y += lq
    y += 30 - lq + lr
    s.text((M, y), typo("Réponds en commentaire."), fr, t["soft"], "ls")
    y += 90 + r
    for i in range(n):          # une rangée de points neutres, le dernier en rouge = toi
        s.dot(M + r + i * g, y, r, t["acc"] if i == n - 1 else t["mute"])
    y += r + 96
    for verb, rest in ACTIONS:
        s.dot(M + r, y - 15, r, t["acc"])
        x = M + 2 * r + 24
        s.text((x, y), typo(verb), fa, t["ink"], "ls")
        s.text((x + s.tw(verb + " ", fa), y), typo(rest), s.f("inter500", 46), t["ink"], "ls")
        y += la
    y += 40 - la + lb
    for l in about:
        s.text((M, y), l, fb, t["soft"], "ls"); y += lb
    s.check_bottom(y - lb, "La slide finale")
    return s.image()


def main(args):
    question = args[0] if args else "Normal ou pas ?"
    pals = [args[1]] if len(args) > 1 else ["papier", "nuit"]
    out = Path(__file__).resolve().parent.parent / "cta"
    out.mkdir(exist_ok=True)
    for pal in pals:
        f = out / f"apercu-{pal}.jpg"
        render_cta(pal, question).save(f, "JPEG", quality=94, optimize=True, progressive=True)
        print(f"OK      {f}")


if __name__ == "__main__":
    main(sys.argv[1:])
