"""Collecte hebdomadaire (GitHub Action, dimanche 17h).

1. Lit les gros titres français de la semaine (flux RSS publics) et en tire des mots-clés.
2. Cherche sur data.gouv.fr des jeux de données liés à ces mots-clés, puis complète
   avec les grands thèmes.
3. Exclut tout jeu de données déjà utilisé dans posts/ (une donnée = un seul post).
4. Télécharge un fichier CSV léger par jeu retenu dans candidates/, avec ses métadonnées.

Aucune IA ici : le script collecte, Claude choisit ensuite.
"""
import json, re, sys, time, unicodedata, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "candidates"
API = "https://www.data.gouv.fr/api/1"
UA = {"User-Agent": "statdefrance-bot/1.0 (+https://github.com)"}
MAX_DATASETS = 40
MAX_FILE = 12 * 1024 * 1024        # 12 Mo par fichier
MAX_TOTAL = 160 * 1024 * 1024      # 160 Mo au total

FEEDS = [  # titres d'actualité publics, utilisés uniquement comme mots-clés
    "https://www.francetvinfo.fr/titres.rss",
    "https://www.lemonde.fr/rss/une.xml",
    "https://www.vie-publique.fr/rss/actualites.xml",
    "https://www.20minutes.fr/feeds/rss-une.xml",
]
THEMES = {
    "Santé": ["santé", "hôpital", "médecins"],
    "Emploi": ["emploi", "chômage", "salaires"],
    "Logement": ["logement", "loyers", "immobilier"],
    "Éducation": ["école", "baccalauréat", "étudiants"],
    "Énergie": ["énergie", "électricité", "carburants"],
    "Agriculture": ["agriculture", "exploitations agricoles", "vin"],
    "Sécurité": ["sécurité routière", "accidents", "pompiers"],
    "Culture": ["musées", "cinéma", "bibliothèques"],
    "Transports": ["trains", "vélo", "aéroports"],
    "Territoires": ["communes", "population", "prénoms"],
}
STOP = set("""
alors aussi autre avant avec avoir bien cette comme dans depuis donc elle elles encore entre être fait faire
leur leurs mais même moins notre nous plus pour pourquoi quand quel quelle quels sans selon sera sont sous
tous tout toute toutes très vous votre après contre chez deux trois quatre cinq millions milliards euros
france français française françaises années année jour jours semaine mois heure heures selon direct vidéo
président gouvernement ministre premier nouvelle nouveau nouveaux grand grande petit petite fois point
monde politique article dernier dernière enfin hier demain aujourd ainsi pourrait doit veut quoi
""".split())


def norm(s):
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def used_datasets():
    used = set()
    for f in (ROOT / "posts").glob("*.json"):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            if p.get("status") != "rejected" and p.get("dataset_id"):
                used.add(p["dataset_id"])
        except Exception:
            pass
    return used


def headlines():
    items = []
    for url in FEEDS:
        try:
            r = requests.get(url, headers=UA, timeout=20); r.raise_for_status()
            root = ET.fromstring(r.content)
            for it in root.iter("item"):
                t = (it.findtext("title") or "").strip(); l = (it.findtext("link") or "").strip()
                if t: items.append({"title": t, "link": l, "feed": url})
        except Exception as e:
            print(f"  flux ignoré {url} : {e}")
    return items


def keywords(items, n=14):
    c = Counter()
    for it in items:
        words = re.findall(r"[A-Za-zÀ-ÿ’'-]{5,}", it["title"])
        for w in {w.lower().strip("’'-") for w in words}:
            if norm(w) not in {norm(s) for s in STOP}:
                c[w] += 1
    return [w for w, k in c.most_common(n) if k >= 2] or [w for w, _ in c.most_common(n)]


def search(q, sort="-reuses", size=8):
    try:
        r = requests.get(f"{API}/datasets/", params={"q": q, "page_size": size, "sort": sort}, headers=UA, timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"  recherche ignorée « {q} » : {e}"); return []


def pick_resource(ds):
    best = None
    for res in ds.get("resources", []):
        fmt = (res.get("format") or "").lower()
        size = res.get("filesize") or 0
        if fmt in ("csv",) and 0 < size <= MAX_FILE:
            if best is None or (res.get("last_modified") or "") > (best.get("last_modified") or ""):
                best = res
    return best


def download(url, dest):
    with requests.get(url, headers=UA, timeout=60, stream=True) as r:
        r.raise_for_status(); n = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                n += len(chunk)
                if n > MAX_FILE: raise ValueError("fichier trop gros")
                f.write(chunk)
    return n


def main():
    OUT.mkdir(exist_ok=True)
    used = used_datasets(); print(f"{len(used)} jeux déjà utilisés, exclus.")
    news = headlines(); kws = keywords(news)
    print(f"{len(news)} titres lus. Mots-clés d'actu : {', '.join(kws)}")

    queue = []  # (origine, thème/mot-clé, requête, tri)
    for kw in kws:
        queue.append(("actu", kw, kw, "-reuses"))
    for theme, qs in THEMES.items():
        for q in qs:
            queue.append(("theme", theme, q, "-reuses"))
            queue.append(("theme", theme, q, "-created"))

    seen, picked, total = set(), [], 0
    for origin, label, q, sort in queue:
        if len(picked) >= MAX_DATASETS or total >= MAX_TOTAL: break
        for ds in search(q, sort):
            if len(picked) >= MAX_DATASETS: break
            if ds["id"] in used or ds["id"] in seen: continue
            if not ds.get("organization"): continue      # producteurs identifiés uniquement
            if ds.get("archived") or ds.get("deleted"): continue
            res = pick_resource(ds)
            if not res: continue
            seen.add(ds["id"])
            slug = ds["slug"][:80]; d = OUT / slug; d.mkdir(exist_ok=True)
            try:
                size = download(res["url"], d / "data.csv")
            except Exception as e:
                print(f"  téléchargement raté {slug} : {e}"); continue
            total += size
            related = [h for h in news if origin == "actu" and norm(label) in norm(h["title"])][:3]
            meta = {
                "dataset_id": ds["id"], "title": ds["title"], "page": ds.get("page") or f"https://www.data.gouv.fr/fr/datasets/{ds['slug']}/",
                "organization": ds["organization"]["name"], "description": (ds.get("description") or "")[:1500],
                "resource_title": res.get("title"), "resource_url": res["url"], "last_modified": res.get("last_modified"),
                "license": ds.get("license"), "origin": origin, "label": label, "query": q, "news": related,
            }
            (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            picked.append({k: meta[k] for k in ("dataset_id", "title", "organization", "origin", "label")} | {"dir": slug})
            print(f"  + [{origin}:{label}] {ds['title'][:70]}")
            time.sleep(0.3)

    index = {"generated_at": datetime.now(timezone.utc).isoformat(), "keywords": kws,
             "headlines": news[:60], "datasets": picked}
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(picked)} jeux retenus, {total / 1e6:.1f} Mo.")
    return 0 if picked else 1


if __name__ == "__main__":
    sys.exit(main())
