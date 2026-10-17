"""Publie en Reel les vidéos de reels/ dont le .json a le statut « validated ».

Envoi direct du fichier à Instagram (upload « resumable »), sans dépendre d'une URL publique.
Après publication : statut « published », identifiant et lien enregistrés dans le .json.
"""
import json, os, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
VER = os.environ.get("GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{VER}"


def log(msg): print(msg, flush=True)


def graph(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.request(method, f"{GRAPH}/{path}", params=params if method == "GET" else None,
                         data=params if method == "POST" else None, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Instagram {r.status_code} : {r.text[:400]}")
    return r.json()


def publish_reel(video: Path, caption: str, share_to_feed=True):
    uid = os.environ["IG_USER_ID"]
    container = graph("POST", f"{uid}/media", media_type="REELS", upload_type="resumable",
                      caption=caption, share_to_feed="true" if share_to_feed else "false")["id"]
    log(f"Conteneur créé : {container}. Envoi de la vidéo ({video.stat().st_size // 1024} Ko)…")
    with open(video, "rb") as fh:
        r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{VER}/{container}",
                          headers={"Authorization": f"OAuth {os.environ['IG_ACCESS_TOKEN']}",
                                   "offset": "0", "file_size": str(video.stat().st_size)},
                          data=fh, timeout=300)
    if not r.ok:
        raise RuntimeError(f"Envoi vidéo {r.status_code} : {r.text[:400]}")
    for _ in range(60):  # Instagram traite la vidéo (souvent 30 s à 2 min)
        st = graph("GET", container, fields="status_code,status")
        code = st.get("status_code")
        if code == "FINISHED": break
        if code in ("ERROR", "EXPIRED"): raise RuntimeError(f"Traitement en échec : {st}")
        time.sleep(5)
    else:
        raise RuntimeError("Traitement trop long, réessayer plus tard.")
    media = graph("POST", f"{uid}/media_publish", creation_id=container)["id"]
    link = graph("GET", media, fields="permalink").get("permalink", "")
    return media, link


def main():
    done = 0
    for meta in sorted((ROOT / "reels").glob("*.json")):
        post = json.loads(meta.read_text())
        if post.get("status") != "validated":
            continue
        video = meta.with_suffix(".mp4")
        log(f"Publication du Reel {video.name}")
        media, link = publish_reel(video, post["caption"], post.get("share_to_feed", True))
        post.update(status="published", ig_media_id=media, permalink=link,
                    published_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        meta.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n")
        log(f"Publié : {link}")
        done += 1
    log(f"{done} Reel(s) publié(s).")


if __name__ == "__main__":
    sys.exit(main())
