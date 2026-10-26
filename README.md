# statdefrance

Deux stats surprenantes par jour sur Instagram (9h et 18h), tirées de l'open data officiel (data.gouv.fr, Insee et une dizaine de portails publics)
et liées à l'actualité française. Tout est automatique, sauf **ta validation, une fois par semaine**.

## La semaine type

| Quand | Qui | Quoi |
|---|---|---|
| Dimanche ~17h | GitHub (gratuit) | Lit les titres de l'actu, collecte des jeux jamais utilisés : 70 data.gouv, 20 Insee, ~45 portails thématiques — liés à l'actu en priorité |
| Dimanche 18h | Claude (ton abonnement) | Choisit 14 stats (2 par jour), calcule, écrit, compose les visuels, te les présente dans une conversation |
| Quand tu veux | Toi | Tu réponds dans la conversation : « OK pour tout sauf le 3, refais le 5 » |
| Chaque jour 9h et 18h | Claude (tâches programmées), GitHub en secours | Publie le post validé du créneau. Pas validé = pas publié |

## Ce que contient le repo

- `render/` — les 4 gabarits (grille, carte, hémicycle, comparaison), palettes Papier / Nuit,
  grain, logo, contrôles de composition. `python -m render posts/*.json --planche`
- `scripts/fetch_candidates.py` — collecte du dimanche (actu + data.gouv + Insee, sans doublon).
  L'Insee passe par son catalogue Melodi : gratuit, sans clé ni inscription.
- `scripts/sources.py` — portails thématiques, tous gratuits et sans clé : Éducation nationale,
  ODRÉ (énergie, RTE éCO2mix), SNCF, Assurance Maladie, DREES, Santé publique France (Odissé),
  ADEME, et les jeux d'Agreste, France Travail, Banque de France et Hub'Eau publiés sur data.gouv.
- `scripts/publish_daily.py` — publication Instagram des posts validés du jour (9h et 18h)
- `GENERATION.md` — le cahier des charges que Claude suit chaque dimanche
- `posts/` — deux fichiers par jour (`AAAA-MM-JJ.json` à 9h, `AAAA-MM-JJ-soir.json` à 18h, + `.jpg`), avec son statut
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
