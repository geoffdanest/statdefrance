"""Vérification de la connexion Instagram, sans rien publier.

- Liste les Pages et comptes Instagram accessibles avec IG_ACCESS_TOKEN
  (pour trouver la valeur de IG_USER_ID).
- Si IG_USER_ID est renseigné : vérifie le compte et le quota de publication.
"""
import os, sys
import requests


def note(level, msg):
    """Affiche le message dans le journal et dans les Annotations de la page du passage."""
    print(msg)
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level}::{msg}")

GRAPH = "https://graph.facebook.com/" + os.environ.get("GRAPH_VERSION", "v21.0")


def get(path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=30)
    return r.ok, r.json()


def main():
    if not os.environ.get("IG_ACCESS_TOKEN"):
        note("error", "❌ Secret IG_ACCESS_TOKEN absent."); return 1
    ok, me = get("me", fields="id,name")
    if not ok:
        note("error", f"❌ La clé est refusée par Meta : {me.get('error', {}).get('message')}"); return 1
    print(f"✅ Clé valide (utilisateur : {me.get('name')})")

    ok, data = get("me/accounts", fields="name,instagram_business_account{id,username}")
    found = []
    for page in data.get("data", []) if ok else []:
        ig = page.get("instagram_business_account")
        if ig:
            found.append(ig)
            note("notice", f"Page « {page['name']} » → Instagram @{ig.get('username')} : IG_USER_ID = {ig['id']}")
        else:
            print(f"   Page « {page['name']} » → aucun compte Instagram pro relié")
    if not found:
        note("warning", "⚠️ Aucun compte Instagram trouvé : vérifier que l'utilisateur système a bien accès à la Page"
              " et au compte Instagram, et que le compte est relié à la Page.")

    uid = os.environ.get("IG_USER_ID")
    if not uid:
        note("notice", "➡️ Secret IG_USER_ID absent : copie le nombre ci-dessus dans les secrets GitHub, puis relance ce contrôle.")
        return 0 if found else 1
    ok, acc = get(uid, fields="username,media_count")
    if not ok:
        note("error", f"❌ IG_USER_ID {uid} refusé : {acc.get('error', {}).get('message')}"); return 1
    print(f"✅ Compte de publication : @{acc['username']} ({acc.get('media_count', 0)} publications)")
    ok, lim = get(f"{uid}/content_publishing_limit", fields="config,quota_usage")
    if ok and lim.get("data"):
        d = lim["data"][0]
        print(f"✅ Quota : {d.get('quota_usage', 0)} publication(s) sur {d.get('config', {}).get('quota_total', '?')} par 24 h")
    else:
        note("warning", "⚠️ Quota illisible : vérifier l'autorisation instagram_content_publish sur la clé.")
    note("notice", f"🎉 Tout est prêt : la publication de 9h postera sur @{acc['username']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
