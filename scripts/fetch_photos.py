"""Cherche des photos libres pour le créneau actu (Openverse + Wikimedia Commons, sans clé).

python scripts/fetch_photos.py "carte bancaire;paiement carte"  → photos/<n>.jpg + photos/index.json
Licences acceptées : CC0, domaine public, CC BY (crédit affiché sur le visuel).
Pas de photo de personne identifiable : le choix final est fait par Claude, qui regarde les images.
"""
import json, sys, time
from pathlib import Path
import requests

OUT = Path(__file__).resolve().parent.parent / "photos"
UA = {"User-Agent": "statdefrance-bot/1.0 (+https://github.com/geoffdanest/statdefrance)"}
LICENSES = {"cc0", "pdm", "by"}
PER_QUERY, MAX = 6, 18


def openverse(q):
    r = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=30,
                     params={"q": q, "license": ",".join(LICENSES), "aspect_ratio": "tall,square",
                             "size": "large", "page_size": PER_QUERY, "mature": "false"})
    r.raise_for_status()
    for x in r.json().get("results", []):
        yield {"url": x["url"], "page": x.get("foreign_landing_url"), "title": x.get("title"),
               "author": x.get("creator") or "", "license": x.get("license"), "provider": x.get("provider")}


def commons(q):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:bitmap {q}",
        "gsrnamespace": 6, "gsrlimit": PER_QUERY, "prop": "imageinfo",
        "iiprop": "url|extmetadata|size", "iiurlwidth": 1600})
    r.raise_for_status()
    for p in (r.json().get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
        lic = (md.get("LicenseShortName", {}).get("value") or "").lower()
        code = "cc0" if "cc0" in lic else "pdm" if "public domain" in lic else "by" if lic.startswith("cc by ") and "sa" not in lic else None
        if code and ii.get("height", 0) >= 1000:
            yield {"url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"), "title": p.get("title"),
                   "author": md.get("Artist", {}).get("value", ""), "license": code, "provider": "wikimedia"}


def main(args):
    queries = [q.strip() for q in (args[0] if args else "").split(";") if q.strip()]
    OUT.mkdir(exist_ok=True); found = []
    for q in queries:
        for src in (openverse, commons):
            try:
                for x in src(q):
                    if len(found) >= MAX or any(f["url"] == x["url"] for f in found): continue
                    try:
                        r = requests.get(x["url"], headers=UA, timeout=60); r.raise_for_status()
                        f = OUT / f"{len(found) + 1:02d}.jpg"; f.write_bytes(r.content)
                        found.append(x | {"file": f.name, "query": q}); print(f"  + {f.name} [{x['license']}] {x['title']}")
                    except Exception as e:
                        print(f"  image ignorée : {e}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"  recherche « {q} » ignorée ({src.__name__}) : {e}")
    (OUT / "index.json").write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(found)} photos."); return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
