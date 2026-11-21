"""Publication quotidienne (GitHub Action, 9h et 18h heure de Paris).

Deux créneaux par jour : posts/AAAA-MM-JJ.json (matin, 9h) et
posts/AAAA-MM-JJ-soir.json (soir, 18h). La publication est toujours lancée par les
tâches programmées Claude (9h02 et 18h02), qui déclenchent ce workflow ; GitHub n'a
aucun horaire propre. Chaque passage publie les créneaux du jour dont l'heure est
atteinte et pas encore publiés. Un post n'est publié que si son statut est
« validated » (validé par toi dans Claude). Après publication : statut
« published » + lien du post Instagram, enregistrés dans le JSON.
Si le post a une « question » et sa slide finale (<post>-fin.jpg), il est publié en
carrousel [visuel, slide finale]. Si Instagram refuse le carrousel, le visuel seul est
publié, pour ne jamais rater un créneau.

Variables d'environnement (secrets GitHub) :
  IG_USER_ID       identifiant du compte Instagram professionnel
  IG_ACCESS_TOKEN  clé de publication (jeton « utilisateur système », sans expiration)
  GITHUB_REPOSITORY fourni automatiquement par GitHub (pseudo/repo)
Options : --force (ignore l'heure), --date AAAA-MM-JJ, --slot matin|soir, --dry-run (n'appelle pas Instagram)
"""
import json, os, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parent.parent
GRAPH = os.environ.get("GRAPH_HOST", "https://graph.facebook.com") + "/" + os.environ.get("GRAPH_VERSION", "v21.0")


def log(msg): print(msg, flush=True)


def graph(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.request(method, f"{GRAPH}/{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Instagram {r.status_code} : {r.text[:400]}")
    return r.json()


def wait_ready(container):
    for _ in range(30):  # Instagram télécharge et traite l'image
        st = graph("GET", container, fields="status_code").get("status_code")
        if st == "FINISHED": return
        if st in ("ERROR", "EXPIRED"): raise RuntimeError(f"Conteneur Instagram en échec : {st}")
        time.sleep(4)
    raise RuntimeError("Conteneur Instagram pas prêt après 2 minutes.")


def publish(image_url, caption, extra_urls=()):
    """Publie une image, ou un carrousel si extra_urls contient d'autres images."""
    uid = os.environ["IG_USER_ID"]
    if extra_urls:
        children = []
        for url in (image_url, *extra_urls):
            c = graph("POST", f"{uid}/media", image_url=url, is_carousel_item="true")["id"]
            wait_ready(c); children.append(c)
        container = graph("POST", f"{uid}/media", media_type="CAROUSEL",
                          children=",".join(children), caption=caption)["id"]
    else:
        container = graph("POST", f"{uid}/media", image_url=image_url, caption=caption)["id"]
    wait_ready(container)
    media = graph("POST", f"{uid}/media_publish", creation_id=container)["id"]
    link = graph("GET", media, fields="permalink").get("permalink", "")
    return media, link


SLOTS = [("matin", "", 9), ("soir", "-soir", 18)]   # (nom, suffixe du fichier, heure de Paris)


def publish_slot(day, name, suffix, now, dry):
    f = ROOT / "posts" / f"{day}{suffix}.json"
    if not f.exists():
        log(f"[{name}] Aucun post prévu le {day}."); return 0
    post = json.loads(f.read_text(encoding="utf-8"))
    status = post.get("status", "draft")
    if status == "published":
        log(f"[{name}] Déjà publié : {post.get('ig_permalink')}"); return 0
    if status != "validated":
        log(f"[{name}] Post du {day} non validé (statut « {status} ») : rien n'est publié."); return 0
    img = f.with_suffix(".jpg")
    if not img.exists():
        log(f"[{name}] ERREUR : visuel manquant {img.name}"); return 1
    repo = os.environ.get("GITHUB_REPOSITORY", "pseudo/statdefrance")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    base = f"https://raw.githubusercontent.com/{repo}/{branch}/posts/"
    image_url = base + img.name
    fin = f.with_name(f.stem + "-fin.jpg")
    extra = [base + fin.name] if post.get("question") and fin.exists() else []
    kind = "carrousel" if extra else "image seule"
    log(f"[{name}] Publication du {day} ({post['template']}, {post['palette']}, {kind}) depuis {image_url}")
    if dry:
        log("[simulation] Instagram non appelé."); return 0
    try:
        media, link = publish(image_url, post["caption"], extra)
    except RuntimeError as e:
        if not extra: raise
        log(f"[{name}] Carrousel refusé ({e}) : publication du visuel seul.")
        media, link = publish(image_url, post["caption"])
    post.update(status="published", ig_media_id=media, ig_permalink=link, published_at=now.isoformat())
    f.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"[{name}] Publié : {link}")
    return 0


def main(args):
    now = datetime.now(ZoneInfo("Europe/Paris"))
    force, dry = "--force" in args, "--dry-run" in args
    day = args[args.index("--date") + 1] if "--date" in args else now.strftime("%Y-%m-%d")
    only = args[args.index("--slot") + 1] if "--slot" in args else None
    code = 0
    for name, suffix, hour in SLOTS:
        if only and name != only:
            continue
        if not force and now.hour < hour:
            log(f"[{name}] {now:%H:%M} à Paris : trop tôt, on attend {hour}h."); continue
        try:
            code |= publish_slot(day, name, suffix, now, dry)
        except Exception as e:   # un créneau en échec n'empêche pas l'autre
            log(f"[{name}] ERREUR : {e}"); code = 1
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
