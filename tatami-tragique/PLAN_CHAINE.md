# TATAMI TRAGIQUE : plan de chaîne

## Positionnement
Chaîne Shorts francophone « arts martiaux + humour ». Deux formats qui se complètent :
1. **Combats de boules armées** (100 % original, zéro droits) : le format principal, publiable tous les jours.
2. **Classements de fails** avec vannes : le format secondaire, avec des clips dont tu as les droits (idéalement).

## Épisodes prêts à poster (dossier `combats/`)
| # | Fichier | Titre | Issue |
|---|---|---|---|
| 1 | EP1_KATANA_vs_NUNCHAKU.mp4 | KATANA vs NUNCHAKU ⚔️ Qui gagne ? | Le Nunchaku gagne avec 10 PV (2 renversements) |
| 2 | EP2_BO_vs_SHURIKENS.mp4 | BÔ vs SHURIKENS 🥷 Qui gagne ? | Les Shurikens gagnent avec 2 PV |
| 3 | EP3_1_NOIRE_vs_10_BLANCHES.mp4 | 1 CEINTURE NOIRE vs 10 CEINTURES BLANCHES 🥋 | Les blanches gagnent, la dernière avec 4 PV |

Description type :
```
Chaque touche le rend plus fort… Qui gagne ? 👇 Commente AVANT la fin !
Épisode suivant demain 🥋
#shorts #simulation #combat #katana #satisfying #quivagagner
```
Épingle un commentaire : « Team KATANA ou team NUNCHAKU ? 👇 »

## Calendrier conseillé
1 Short par jour à heure fixe (18 h ou 19 h). Alterner : combat, combat, fail, combat…

## Prochains épisodes (le moteur les génère ; il suffit d'ajouter un `ep_EX` dans fight.py)
- **Le Grand Tournoi** : 8 armes, bracket, 1 Short par match puis une finale (série = abonnements).
- **Ceinture blanche qui grossit à chaque touche** vs Ceinture noire.
- **Maître Shaolin** (0 arme, 1 PV mais esquive) vs Katana.
- **100 ceintures blanches vs 1 Maître** (la suite de l'épisode 3).
- **Tes abonnés choisissent** : « commente 2 armes, je fais le combat » (boucle d'engagement).
- **Revanche** : Katana vs Nunchaku, round 2 (les perdants reviennent).
- Armes à ajouter : saï, kama (faucille), tonfa, éventail de fer, corde à sauter 😅.

## Refaire / créer un épisode
```
python3 combats/fight.py search E4        # liste les graines donnant un combat serré
python3 combats/fight.py render E4 SEED   # rend la vidéo
python3 combats/tune.py E4                # grille d'équilibrage (si un camp gagne toujours)
```
Critères de sélection d'une graine : 18-36 s, le vainqueur finit à ≤ 20 % de PV, au moins 1 renversement.
Le script attend `assets/` (polices et emojis) à côté de lui, comme `render.py`.
