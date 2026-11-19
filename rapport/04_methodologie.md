# 4. Méthodologie

*Rôle B. Section à rédiger : le plan ci-dessous est une proposition, à adapter.*

## 4.1 Modèles comparés

- Modèle de référence simple, pour situer les scores.
- Modèles retenus (forêt aléatoire, gradient boosting…) et pourquoi.
- Paramètres principaux et `random_state` fixé (reproductibilité, `scripts/train.py`).

## 4.2 Prétraitement

- Retrait des 43 features constantes (`VarianceThreshold`, voir section 2.8).
- Traitement des 7 colonnes catégorielles (section 3.2), si le modèle le demande.
- Mise à l'échelle éventuelle (inutile pour les arbres).

## 4.3 Validation et choix des hyperparamètres

- Validation temporelle plutôt qu'aléatoire (section 2.5) : par exemple, les dernières semaines
  du train comme jeu de validation, ou `TimeSeriesSplit`.
- Hyperparamètres testés et critère de choix.

## 4.4 Métriques

- Pourquoi le F1 macro plutôt que l'exactitude (test déséquilibré, section 2.2).
- Rappel et précision par famille, matrice de confusion normalisée par ligne.
- Prudence sur sinowal (9 fichiers de test), sfone (66) et grandoreiro (113).
