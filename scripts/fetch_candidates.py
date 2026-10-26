"""Collecte hebdomadaire (GitHub Action, dimanche 17h) — de quoi faire 14 posts.

1. Lit les gros titres français de la semaine (flux RSS publics) et en tire des mots-clés.
2. Cherche sur data.gouv.fr des jeux de données liés à ces mots-clés, puis complète
   avec les grands thèmes.
3. Fait de même dans le catalogue de l'Insee (API Melodi, gratuite et sans clé)
   et dans les portails thématiques (voir scripts/sources.py) — toujours l'actu d'abord.
4. Exclut tout jeu de données déjà utilisé dans posts/ (une donnée = un seul post).
5. Télécharge un fichier CSV léger par jeu retenu dans candidates/, avec ses métadonnées.

Aucune IA ici : le script collecte, Claude choisit ensuite.
"""
import io, json, re, sys, time, unicodedata, zipfile, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "candidates"
API = "https://www.data.gouv.fr/api/1"
UA = {"User-Agent": "statdefrance-bot/1.0 (+https://github.com)"}
MAX_DATASETS = 70            # 14 posts par semaine : large réserve
PER_THEME = 5                      # jeux max par thème
PER_KEYWORD = 2                    # jeux max par mot-clé d'actu
MAX_AGE_DAYS = 4 * 365             # données mises à jour depuis moins de 4 ans
TRUSTED_BADGES = {"public-service", "certified"}  # producteurs publics ou certifiés
MAX_FILE = 12 * 1024 * 1024        # 12 Mo par fichier
MAX_TOTAL = 250 * 1024 * 1024      # 250 Mo au total

# Insee — catalogue Melodi : accès libre, sans clé, 30 requêtes par minute
INSEE_API = "https://api.insee.fr/melodi"
INSEE_PAGE = "https://catalogue-donnees.insee.fr/fr/catalogue/recherche/{}"
MAX_INSEE = 20                     # jeux Insee en plus des jeux data.gouv
INSEE_PER_LABEL = 2                # jeux Insee max par mot-clé d'actu ou par thème
INSEE_MAX_ZIP = 40 * 1024 * 1024   # 40 Mo par archive téléchargée
INSEE_MAX_CSV = 25 * 1024 * 1024   # 25 Mo par CSV extrait
INSEE_MAX_TOTAL = 150 * 1024 * 1024
INSEE_DELAY = 2.5                  # secondes entre deux appels (reste sous 30/min)

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
    "Sport": ["sport", "licences sportives", "équipements sportifs"],
    "Environnement": ["déchets", "qualité de l'air", "eau"],
    "Économie": ["inflation", "entreprises", "épargne"],
}
STOP = set("""
alors aussi autre avant avec avoir bien cette comme dans depuis donc elle elles encore entre être fait faire
leur leurs mais même moins notre nous plus pour pourquoi quand quel quelle quels sans selon sera sont sous
tous tout toute toutes très vous votre après contre chez deux trois quatre cinq millions milliards euros
france français française françaises années année jour jours semaine mois heure heures selon direct vidéo
président gouvernement ministre premier nouvelle nouveau nouveaux grand grande petit petite fois point
monde politique article dernier dernière enfin hier demain aujourd ainsi pourrait doit veut quoi
lundi mardi mercredi jeudi vendredi samedi dimanche janvier février mars avril juin juillet août septembre
octobre novembre décembre images photos photo live info infos infographie témoignage témoignages explique
pourquoi comment combien voici après avant depuis pendant contre malgré lors face entre toujours encore
selon plusieurs certains certaines nouvelle nouvelles grands grandes petits petites premier première
annonce annonces affaire affaires question questions situation propos accord appel appels retour retours
victimes morts mort blessés enquête procès justice police polémique crise mobilisation
""".split())
STOP_N = {unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode() for w in STOP}


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


def keywords(items, n=12):
    """Mots présents dans au moins 2 titres différents, hors mots vides et noms propres."""
    c = Counter()
    for it in items:
        title = it["title"].replace("’", " ").replace("'", " ")
        seen = set()
        for m in re.finditer(r"[A-Za-zÀ-ÿ-]+", title):
            w = m.group(0)
            before = title[:m.start()].rstrip()
            starts = not before or before[-1] in ":-–—|«\"!?."   # majuscule de début de phrase : OK
            if len(w) < 5 or (w[:1].isupper() and not starts):    # noms propres (lieux, personnes) écartés
                continue
            k = w.lower()
            if norm(k) in STOP_N or k in seen:
                continue
            seen.add(k); c[k] += 1
    # un vrai mot commun apparaît au moins une fois en minuscules (élimine « Aubagne », « Riyad »…)
    lower = set(re.findall(r"\b[a-zà-ÿ][a-zà-ÿ-]{4,}\b", " ".join(it["title"] for it in items).replace("’", " ")))
    return [w for w, k in c.most_common(n * 2) if k >= 2 and w in lower][:n]


def trusted(ds):
    org = ds.get("organization") or {}
    if not org:
        return False
    badges = {b.get("kind") for b in org.get("badges", []) or []}
    return bool(badges & TRUSTED_BADGES) if "badges" in org else True


def recent(ds):
    d = ds.get("last_update") or ds.get("last_modified") or ""
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(d.replace("Z", "+00:00"))
        return age.days <= MAX_AGE_DAYS
    except Exception:
        return True


def series_key(title):
    """« Carte des loyers 2023 » et « … 2024 » = même série : une seule retenue."""
    return re.sub(r"\s+", " ", re.sub(r"[\d\"«»()]", "", norm(title))).strip()


# ---------- Insee (Melodi) ----------

def _txt(v, lang="fr"):
    """Les textes du catalogue Insee sont des listes [{lang, content}] : garder le français."""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("content") or ""
    if isinstance(v, list):
        items = [x for x in v if isinstance(x, dict)]
        for x in items:
            if (x.get("lang") or "").lower().startswith(lang):
                return x.get("content") or ""
        return (items[0].get("content") or "") if items else ""
    return ""


def insee_catalog():
    try:
        r = requests.get(f"{INSEE_API}/catalog/all", headers=UA, timeout=60); r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        print(f"  catalogue Insee indisponible : {e}"); return []


def insee_csv_url(ds):
    for prod in ds.get("product") or []:
        fmt = (prod.get("format") or "").upper()
        lang = (prod.get("language") or "FR").upper()
        if "CSV" in fmt and lang.startswith("FR") and prod.get("accessURL"):
            return prod["accessURL"]
    return None


def insee_download(url, dest_dir):
    """Archive ZIP Insee → data.csv (observations) + labels.csv (libellés des codes)."""
    buf = io.BytesIO()
    with requests.get(url, headers=UA, timeout=120, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1 << 16):
            buf.write(chunk)
            if buf.tell() > INSEE_MAX_ZIP: raise ValueError("archive trop grosse")
    with zipfile.ZipFile(buf) as z:
        names = z.namelist()
        data = next((n for n in names if n.lower().endswith("_data.csv")), None) \
            or next((n for n in names if n.lower().endswith(".csv") and "metadata" not in n.lower()), None)
        labels = next((n for n in names if n.lower().endswith("_metadata.csv")), None)
        if not data: raise ValueError("pas de CSV dans l'archive")
        if z.getinfo(data).file_size > INSEE_MAX_CSV: raise ValueError("CSV trop gros")
        (dest_dir / "data.csv").write_bytes(z.read(data))
        n = z.getinfo(data).file_size
        if labels:
            (dest_dir / "labels.csv").write_bytes(z.read(labels))
            n += z.getinfo(labels).file_size
    return n


def collect_insee(kws, used, news):
    """Jeux Insee : d'abord ceux liés aux mots-clés d'actu, puis par thème, puis les plus récents."""
    catalog = insee_catalog()
    print(f"{len(catalog)} jeux au catalogue Insee.")
    rows = []
    for ds in catalog:
        ident = ds.get("identifier")
        if not ident or f"insee:{ident}" in used: continue
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(str(ds.get("modified", ""))[:10]).replace(tzinfo=timezone.utc)
            if age.days > MAX_AGE_DAYS: continue
        except Exception:
            pass
        url = insee_csv_url(ds)
        if not url: continue
        title = _txt(ds.get("title")); desc = _txt(ds.get("description")) or _txt(ds.get("abstract"))
        rows.append({"ds": ds, "id": ident, "url": url, "title": title, "desc": desc,
                     "text": f" {norm(title)} {norm(desc)} ", "modified": str(ds.get("modified", ""))})
    rows.sort(key=lambda x: x["modified"], reverse=True)

    def match(word):
        w = norm(word)
        return [x for x in rows if re.search(rf"\b{re.escape(w)}", x["text"])]

    queue = [("actu", kw, match(kw)) for kw in kws]
    queue += [("theme", theme, [x for q in qs for x in match(q)]) for theme, qs in THEMES.items()]
    queue += [("recent", "Récents", rows)]

    picked, seen, total = [], set(), 0
    for origin, label, cands in queue:
        n = 0
        for x in cands:
            if len(picked) >= MAX_INSEE or total >= INSEE_MAX_TOTAL: break
            if n >= INSEE_PER_LABEL or x["id"] in seen: continue
            seen.add(x["id"])
            d = OUT / f"insee-{x['id'].lower()}"; d.mkdir(exist_ok=True)
            try:
                size = insee_download(x["url"], d)
            except Exception as e:
                print(f"  téléchargement Insee raté {x['id']} : {e}"); time.sleep(INSEE_DELAY); continue
            total += size; n += 1
            related = [h for h in news if origin == "actu" and norm(label) in norm(h["title"])][:3]
            meta = {
                "source": "insee", "dataset_id": f"insee:{x['id']}", "title": x["title"],
                "page": INSEE_PAGE.format(x["id"]), "organization": "Insee",
                "description": x["desc"][:1500], "resource_title": x["id"], "resource_url": x["url"],
                "last_modified": x["modified"], "license": "Licence ouverte Etalab",
                "num_observations": x["ds"].get("numObservations"),
                "origin": "theme" if origin == "recent" else origin, "label": label,
                "query": label, "news": related,
                "lecture": "CSV séparé par « ; ». Valeur = OBS_VALUE. Les colonnes contiennent des codes : "
                           "leurs libellés sont dans labels.csv (COD_VAR/LIB_VAR pour les colonnes, COD_MOD/LIB_MOD pour les valeurs).",
            }
            (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            picked.append({k: meta[k] for k in ("dataset_id", "title", "organization", "origin", "label", "source")} | {"dir": d.name})
            print(f"  + [insee:{origin}:{label}] {x['title'][:70]}")
            time.sleep(INSEE_DELAY)
    print(f"{len(picked)} jeux Insee retenus, {total / 1e6:.1f} Mo.")
    return picked


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

    # file d'attente : actu d'abord, puis thèmes en tourniquet (tous les thèmes représentés)
    queue = [("actu", kw, kw, "-reuses") for kw in kws]
    rounds = max(len(q) for q in THEMES.values())
    for i in range(rounds):
        for theme, qs in THEMES.items():
            if i < len(qs):
                queue.append(("theme", theme, qs[i], "-reuses"))
                queue.append(("theme", theme, qs[i], "-created"))

    seen, series, picked, total = set(), set(), [], 0
    count = Counter()
    for origin, label, q, sort in queue:
        if len(picked) >= MAX_DATASETS or total >= MAX_TOTAL: break
        cap = PER_KEYWORD if origin == "actu" else PER_THEME
        for ds in search(q, sort, size=12):
            if count[label] >= cap or len(picked) >= MAX_DATASETS: break
            if ds["id"] in used or ds["id"] in seen: continue
            if ds.get("archived") or ds.get("deleted"): continue
            if not trusted(ds) or not recent(ds): continue
            sk = series_key(ds["title"])
            if sk in series: continue
            res = pick_resource(ds)
            if not res: continue
            seen.add(ds["id"])
            slug = ds["slug"][:80]; d = OUT / slug; d.mkdir(exist_ok=True)
            try:
                size = download(res["url"], d / "data.csv")
            except Exception as e:
                print(f"  téléchargement raté {slug} : {e}"); continue
            total += size; series.add(sk); count[label] += 1
            related = [h for h in news if origin == "actu" and norm(label) in norm(h["title"])][:3]
            meta = {
                "source": "data.gouv", "dataset_id": ds["id"], "title": ds["title"], "page": ds.get("page") or f"https://www.data.gouv.fr/fr/datasets/{ds['slug']}/",
                "organization": ds["organization"]["name"], "description": (ds.get("description") or "")[:1500],
                "resource_title": res.get("title"), "resource_url": res["url"], "last_modified": res.get("last_modified"),
                "license": ds.get("license"), "origin": origin, "label": label, "query": q, "news": related,
            }
            (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            picked.append({k: meta[k] for k in ("dataset_id", "title", "organization", "origin", "label", "source")} | {"dir": slug})
            print(f"  + [{origin}:{label}] {ds['title'][:70]}")
            time.sleep(0.3)

    print(f"{len(picked)} jeux data.gouv retenus, {total / 1e6:.1f} Mo.")
    picked += collect_insee(kws, used, news)

    taken = used | {p["dataset_id"] for p in picked}
    extra = sources.collect_all(kws=kws, themes=THEMES, used=taken, news=news, out_dir=OUT, ua=UA, norm=norm,
                                max_age_days=MAX_AGE_DAYS, api=API, pick_resource=pick_resource)
    print(f"{len(extra)} jeux des portails thématiques retenus.")
    picked += extra

    by_source = Counter(p.get("source", "data.gouv") for p in picked)
    actu = Counter(p.get("source", "data.gouv") for p in picked if p.get("origin") == "actu")
    index = {"generated_at": datetime.now(timezone.utc).isoformat(), "keywords": kws,
             "by_source": dict(by_source), "actu_by_source": dict(actu),
             "headlines": news[:60], "datasets": picked}
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(picked)} jeux retenus au total.")
    return 0 if picked else 1


if __name__ == "__main__":
    sys.exit(main())
