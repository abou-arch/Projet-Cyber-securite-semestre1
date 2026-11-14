# Rôle B – Phase 3 : évaluation approfondie

Ce qui a été ajouté pour la phase 3 du plan `plan/role_B_modeles_evaluation.txt` :

| Fichier | Rôle |
|---|---|
| `scripts/evaluate.py` | script de la phase 3 (nom prévu par le plan et par `scripts/__init__.py`) |
| `tests/test_evaluate.py` | tests hors ligne sur un petit jeu synthétique (4 tests) |
| `README_phase3.md` | ce fichier |

Aucun autre fichier du projet n'a été modifié.

## Point de départ

Le script reprend la sortie de la phase 2 (`scripts/optimize.py`) :

- le modèle final `models/best_model.joblib` (forêt `rf_300_depth_none` d'après `results/metrics.json`) ;
- le jeu préparé `data/processed/ember2024_Win32_top10` (même chemin que `optimize.py`).

Il ne choisit plus de modèle : il l'analyse. Le test sert seulement à mesurer, aucun paramètre n'est réglé dessus.

## Lancer

Depuis la racine du projet, une fois le dossier `data/` remis en place :

```bash
python scripts/optimize.py          # phase 2, si models/best_model.joblib n'existe pas
python -m scripts.evaluate          # phase 3 : toutes les étapes
```

Options utiles :

- `--etapes confusion effectifs derive rejet` : seulement les étapes rapides, sans réentraînement.
- `--data-dir C:\ember2024\processed\Win32_top10` : jeu préparé ailleurs. La variable `EMBER_DATASET` marche aussi.
- `--variante-dir ...` : variante pour l'étape bruit. Par défaut : `data/processed/ember2024_Win32_top10_conf05`.
- `--random-states 0 1 2` : graines de l'étape stabilité.
- `--groupes header section` : un modèle réduit choisi à la main.
- `--top-groupes 1 3` : modèles réduits aux k meilleurs groupes.
- `--top-features 100` : modèle réduit aux n meilleures features.

La variante à étiquettes sûres se prépare avec la commande de A :

```bash
python -m malware_family.prepare --min-confidence 0.5 --out-dir data/processed/ember2024_Win32_top10_conf05
```

Si elle est absente, l'étape `bruit` est sautée avec un message ; les autres étapes tournent quand même.

## Les étapes (cases de la phase 3 du plan)

| Étape | Case du plan | Sorties |
|---|---|---|
| `confusion` | Matrice de confusion normalisée (`normalize="true"`) | `B_matrice_confusion.png` ; paires les plus confondues dans `evaluation.json` (à expliquer avec C) |
| `effectifs` | F1 par famille selon le nombre d'exemples d'entraînement | `B_f1_par_famille_effectifs.png`, `f1_par_famille.csv` ; corrélation de Spearman ; F1 macro sans les familles de moins de 30 fichiers du test |
| `derive` | F1 macro semaine par semaine sur le test (`first_seen`) | `B_score_par_semaine.png`, `score_par_semaine.csv` ; pente du F1 par semaine. Les semaines de moins de 50 fichiers sont signalées. |
| `bruit` | Réentraînement sur la variante `--min-confidence 0.5` | `B_bruit_etiquettes.png` ; scores croisés base / variante sur les deux tests |
| `stabilite` | 3 valeurs de `random_state` : moyenne et écart-type | `stabilite.csv` |
| `reduit` | Modèle réduit aux groupes ou features les plus importants selon C | `B_modele_reduit.png`, `modele_reduit.csv` ; F1, perte de F1 et temps d'entraînement par rapport au modèle complet |
| `rejet` | (Bonus) « inconnu » sous un seuil de probabilité | `B_rejet_couverture.png`, `rejet.csv` (précision selon la couverture) |

Toutes les figures vont dans `results/figures/` et suivent les conventions de `malware_family/figures.py` : préfixe `B_`, 16 cm, 200 dpi, couleurs des familles.

Tous les chiffres vont dans `results/evaluation.json`. Ce fichier est mis à jour étape par étape : relancer une seule étape ne fait pas perdre les autres.

`results/predictions_test_proba.csv` ajoute la date et la probabilité maximale à chaque prédiction. Le plan les demandait pour la phase 2 ; ce fichier est utile à C et à la démo.

## Modèle réduit et résultats de C

- Si `results/importances_groupes.csv` est présent (sortie de `scripts/importance.py` de C, branche `Abou`), les groupes sont classés selon `perm_f1_drop_mean`. De même, `results/importances.csv` sert pour les features.
- Sinon, le script se rabat sur l'importance MDI du modèle final, en somme par groupe. Cette somme favorise les grands groupes, comme `imports` avec 1 282 colonnes. La source utilisée est écrite dans `evaluation.json`.

## Durée (estimation)

`confusion`, `effectifs`, `derive` et `rejet` ne réentraînent rien : quelques secondes à une minute.

`bruit`, `stabilite` et `reduit` réentraînent la forêt de 300 arbres. En phase 2, elle a mis environ 1 min sur 85 % du train. Il faut donc compter de l'ordre de 10 à 15 min pour ces trois étapes.

## Tests

```bash
python -m pytest tests/test_evaluate.py
```

Les tests construisent un faux jeu préparé et un petit modèle dans un dossier temporaire, puis vérifient toutes les sorties.

**Les résultats sur les vraies données ne sont pas encore calculés** : le dossier `data/` (15 Go) n'était pas dans l'archive.
