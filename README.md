# statdefrance

Une stat surprenante par jour sur Instagram, tirée de l'open data officiel (data.gouv.fr)
et liée à l'actualité française. Tout est automatique, sauf **ta validation, une fois par semaine**.

## La semaine type

| Quand | Qui | Quoi |
|---|---|---|
| Dimanche ~17h | GitHub (gratuit) | Lit les titres de l'actu, collecte une quarantaine de jeux de données data.gouv jamais utilisés |
| Dimanche 18h | Claude (ton abonnement) | Choisit 7 stats, calcule, écrit, compose les visuels, te les présente dans une conversation |
| Quand tu veux | Toi | Tu réponds dans la conversation : « OK pour tout sauf le 3, refais le 5 » |
| Chaque jour 9h | GitHub (gratuit) | Publie le post validé du jour. Pas validé = pas publié |

## Ce que contient le repo

- `render/` — les 4 gabarits (grille, carte, hémicycle, comparaison), palettes Papier / Nuit,
  grain, logo, contrôles de composition. `python -m render posts/*.json --planche`
- `scripts/fetch_candidates.py` — collecte du dimanche (actu + data.gouv, sans doublon)
- `scripts/publish_daily.py` — publication Instagram du post validé du jour
- `GENERATION.md` — le cahier des charges que Claude suit chaque dimanche
- `posts/` — un fichier par jour (`AAAA-MM-JJ.json` + `.jpg`), avec son statut
- `examples/` — 4 posts d'exemple (chiffres de démonstration)

## Mise en route (une seule fois)

1. **GitHub → Settings → Actions → General → Workflow permissions** : cocher
   *Read and write permissions*, puis *Save*.
2. **Instagram** : passer le compte en *professionnel* (Créateur ou Entreprise) et le relier
   à une Page Facebook.
3. **Clé de publication Meta** (jeton sans expiration) — Claude te guide pas à pas :
   app Meta (type Business) → utilisateur système dans Meta Business Suite → jeton
   « Jamais » avec `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
4. **GitHub → Settings → Secrets and variables → Actions** : ajouter
   `IG_USER_ID` (identifiant du compte Instagram pro) et `IG_ACCESS_TOKEN` (la clé).
5. **Premier test** : onglet *Actions* → « Collecte hebdo » → *Run workflow*.

## Dépannage

- Rien n'a été publié ? Vérifier le statut dans `posts/<date>.json` (`validated` attendu) et
  l'onglet *Actions* → « Publication Instagram ».
- Republier un jour manqué : *Actions* → « Publication Instagram » → *Run workflow* avec la date.
