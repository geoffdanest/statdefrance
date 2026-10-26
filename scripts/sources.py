"""Sources thématiques en plus de data.gouv et de l'Insee — toutes gratuites, sans clé.

Chaque source cherche d'abord des jeux liés aux mots-clés d'actu de la semaine,
puis complète avec ses propres thèmes, puis avec ses jeux les plus récents.

- Portails Opendatasoft (même API pour tous) : Éducation nationale, ODRÉ (RTE / éCO2mix, GRTgaz…),
  SNCF, Assurance Maladie (Ameli), DREES, Santé publique France (Odissé).
- ADEME (plateforme data-fair).
- Producteurs sans API ouverte (Agreste, France Travail, Banque de France, Hub'Eau…) :
  leurs jeux publiés sur data.gouv.fr, filtrés par organisation.

Un portail qui ne répond pas est ignoré : la collecte continue avec les autres.
"""
import json, re, time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

# Opendatasoft : (domaine, producteur affiché, thème, mots-clés propres)
ODS_PORTALS = {
    "education": ("data.education.gouv.fr", "Ministère de l'Éducation nationale", "Éducation",
                  ["baccalauréat", "brevet", "effectifs", "enseignants", "collèges", "lycées"]),
    "odre": ("odre.opendatasoft.com", "ODRÉ (RTE, GRTgaz, Enedis…)", "Énergie",
             ["éCO2mix", "consommation électricité", "production électricité", "gaz", "éolien", "solaire"]),
    "sncf": ("ressources.data.sncf.com", "SNCF", "Transports",
             ["régularité", "fréquentation gares", "TGV", "TER", "objets trouvés"]),
    "ameli": ("data.ameli.fr", "Assurance Maladie", "Santé",
              ["médicaments", "dépenses", "professionnels de santé", "pathologies", "arrêts de travail"]),
    "drees": ("data.drees.solidarites-sante.gouv.fr", "DREES", "Santé",
              ["hôpital", "urgences", "minima sociaux", "retraite", "médecins", "EHPAD"]),
    "odisse": ("odisse.santepubliquefrance.fr", "Santé publique France", "Santé",
               ["grippe", "vaccination", "canicule", "tabac", "alcool", "obésité"]),
}
ADEME = ("data.ademe.fr", "ADEME", "Environnement",
         ["déchets", "DPE", "rénovation", "émissions", "carbone", "véhicules"])
# Producteurs publiés sur data.gouv : (nom cherché dans les organisations, thème, mots-clés propres)
DATAGOUV_PRODUCERS = {
    "agreste": ("Agreste", "Agriculture", ["récoltes", "exploitations", "élevage", "prix agricoles"]),
    "france-travail": ("France Travail", "Emploi", ["demandeurs d'emploi", "offres", "embauches"]),
    "banque-de-france": ("Banque de France", "Économie", ["épargne", "crédit", "surendettement", "billets"]),
    "hubeau": ("Office français de la biodiversité", "Environnement", ["eau", "rivières", "nappes", "sécheresse"]),
}

PER_SOURCE = 4                 # jeux max par source
PER_KEYWORD = 1                # par source : un jeu max par mot-clé d'actu
MAX_FILE = 12 * 1024 * 1024
MAX_SOURCE_TOTAL = 40 * 1024 * 1024
DELAY = 0.4


def _get(url, ua, **kw):
    r = requests.get(url, headers=ua, timeout=kw.pop("timeout", 30), **kw)
    r.raise_for_status()
    return r


def _download(url, dest, ua):
    with requests.get(url, headers=ua, timeout=120, stream=True) as r:
        r.raise_for_status(); n = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                n += len(chunk)
                if n > MAX_FILE: raise ValueError("fichier trop gros")
                f.write(chunk)
    return n


def _recent(date_str, max_age_days):
    try:
        d = datetime.fromisoformat(str(date_str)[:10]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days <= max_age_days
    except Exception:
        return True


def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------- Opendatasoft ----------

def ods_search(domain, q, ua, limit=10):
    params = {"limit": limit, "order_by": "modified desc"}
    if q:
        params["where"] = '"' + q.replace('"', " ") + '"'   # recherche plein texte
    r = _get(f"https://{domain}/api/explore/v2.1/catalog/datasets", ua, params=params)
    out = []
    for ds in r.json().get("results", []):
        m = (ds.get("metas") or {}).get("default") or {}
        out.append({
            "id": ds.get("dataset_id"), "title": m.get("title") or ds.get("dataset_id"),
            "description": _strip_html(m.get("description"))[:1500],
            "modified": m.get("modified") or m.get("data_processed") or "",
            "records": m.get("records_count") or 0,
            "page": f"https://{domain}/explore/dataset/{ds.get('dataset_id')}/",
            "csv": f"https://{domain}/api/explore/v2.1/catalog/datasets/{quote(str(ds.get('dataset_id')))}"
                   f"/exports/csv?delimiter=%3B&limit=200000",
        })
    return [d for d in out if d["id"] and d["records"]]


# ---------- ADEME (data-fair) ----------

def ademe_search(q, ua, limit=10):
    params = {"size": limit, "sort": "updatedAt:-1"}
    if q: params["q"] = q
    r = _get(f"https://{ADEME[0]}/data-fair/api/v1/datasets", ua, params=params)
    out = []
    for ds in r.json().get("results", []):
        i = ds.get("id")
        out.append({
            "id": i, "title": ds.get("title") or i, "description": _strip_html(ds.get("description"))[:1500],
            "modified": ds.get("dataUpdatedAt") or ds.get("updatedAt") or "", "records": ds.get("count") or 0,
            "page": f"https://{ADEME[0]}/datasets/{i}",
            "csv": f"https://{ADEME[0]}/data-fair/api/v1/datasets/{i}/lines?format=csv&size=10000",
        })
    return [d for d in out if d["id"] and d["records"]]


# ---------- Producteurs via data.gouv ----------

def datagouv_org_id(api, name, ua):
    r = _get(f"{api}/organizations/", ua, params={"q": name, "page_size": 5})
    for org in r.json().get("data", []):
        if name.lower() in (org.get("name") or "").lower():
            return org["id"], org["name"]
    return None, None


def datagouv_org_search(api, org_id, q, ua, pick_resource, limit=10):
    params = {"organization": org_id, "page_size": limit, "sort": "-last_update"}
    if q: params["q"] = q
    r = _get(f"{api}/datasets/", ua, params=params)
    out = []
    for ds in r.json().get("data", []):
        if ds.get("archived") or ds.get("deleted"): continue
        res = pick_resource(ds)
        if not res: continue
        out.append({
            "id": ds["id"], "title": ds["title"], "description": (ds.get("description") or "")[:1500],
            "modified": ds.get("last_update") or "", "records": 1,
            "page": ds.get("page") or f"https://www.data.gouv.fr/fr/datasets/{ds['slug']}/", "csv": res["url"],
            "datagouv": True,
        })
    return out


# ---------- Collecte commune ----------

def collect_source(key, producer, theme, own_kws, search, *, kws, themes, used, news, out_dir,
                   ua, norm, max_age_days, id_prefix):
    """Actu d'abord (un jeu par mot-clé), puis thèmes, puis plus récents. Renvoie les jeux retenus."""
    queue = [("actu", kw, kw) for kw in kws]
    queue += [("theme", theme, q) for q in own_kws + themes.get(theme, [])]
    queue += [("theme", theme, "")]                       # les plus récents du portail
    picked, seen, total, failures = [], set(), 0, 0
    for origin, label, q in queue:
        if len(picked) >= PER_SOURCE or total >= MAX_SOURCE_TOTAL or failures >= 3: break
        try:
            cands = search(q)
        except Exception as e:
            failures += 1
            print(f"  [{key}] recherche ignorée « {q} » : {e}"); continue
        n = 0
        for c in cands:
            if len(picked) >= PER_SOURCE: break
            if origin == "actu" and n >= PER_KEYWORD: break
            did = c["id"] if c.get("datagouv") else f"{id_prefix}:{c['id']}"
            if did in used or did in seen: continue
            if not _recent(c["modified"], max_age_days): continue
            if origin == "actu" and norm(label) not in norm(f"{c['title']} {c['description']}"):
                continue                                   # lien avec l'actu trop faible
            seen.add(did)
            slug = re.sub(r"[^a-z0-9-]+", "-", norm(f"{key}-{c['id']}"))[:80].strip("-")
            d = out_dir / slug; d.mkdir(exist_ok=True)
            try:
                size = _download(c["csv"], d / "data.csv", ua)
            except Exception as e:
                print(f"  [{key}] téléchargement raté {c['id']} : {e}"); continue
            total += size; n += 1
            related = [h for h in news if origin == "actu" and norm(label) in norm(h["title"])][:3]
            meta = {
                "source": key, "dataset_id": did, "title": c["title"], "page": c["page"],
                "organization": producer, "description": c["description"], "resource_title": c["title"],
                "resource_url": c["csv"], "last_modified": c["modified"], "license": "Licence ouverte",
                "origin": origin, "label": label, "query": q, "news": related,
                "lecture": "CSV séparé par « ; »." if not c.get("datagouv") else "CSV d'origine (séparateur à vérifier).",
            }
            (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            picked.append({k: meta[k] for k in ("dataset_id", "title", "organization", "origin", "label", "source")}
                          | {"dir": slug})
            print(f"  + [{key}:{origin}:{label}] {c['title'][:70]}")
            time.sleep(DELAY)
    return picked


def collect_all(*, kws, themes, used, news, out_dir, ua, norm, max_age_days, api, pick_resource, trusted_ids=None):
    common = dict(kws=kws, themes=themes, used=used, news=news, out_dir=out_dir, ua=ua, norm=norm,
                  max_age_days=max_age_days)
    picked = []
    for key, (domain, producer, theme, own) in ODS_PORTALS.items():
        picked += collect_source(key, producer, theme, own, lambda q, d=domain: ods_search(d, q, ua),
                                 id_prefix=key, **common)
    picked += collect_source("ademe", ADEME[1], ADEME[2], ADEME[3], lambda q: ademe_search(q, ua),
                             id_prefix="ademe", **common)
    for key, (name, theme, own) in DATAGOUV_PRODUCERS.items():
        try:
            org_id, org_name = datagouv_org_id(api, name, ua)
        except Exception as e:
            print(f"  [{key}] organisation introuvable : {e}"); continue
        if not org_id:
            print(f"  [{key}] organisation « {name} » introuvable sur data.gouv"); continue
        picked += collect_source(key, org_name, theme, own,
                                 lambda q, o=org_id: datagouv_org_search(api, o, q, ua, pick_resource),
                                 id_prefix=key, **common)
    return picked
