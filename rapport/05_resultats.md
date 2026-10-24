# 5. Résultats

*Rôle B. Section à rédiger : le plan ci-dessous est une proposition, à adapter.*

## 5.1 Scores globaux

- Tableau comparatif des modèles : F1 macro, exactitude, temps d'entraînement.
- Modèle final retenu, et pourquoi.

## 5.2 Résultats par famille

- Précision, rappel et F1 par famille.
- Matrice de confusion normalisée (figure `B_matrice_confusion.png`).
- Familles les plus confondues, à relier aux profils de la section 3.4 et aux étiquettes peu
  sûres de la section 2.6 (wacatac).

## 5.3 Dérive temporelle

- Score sur la validation (fin du train) comparé au score sur le test.
- Score par semaine du test, si possible (figure `B_score_par_semaine.png`).

## 5.4 Variante : étiquettes plus sûres

- Résultats avec `--min-confidence 0.5`. Attention : la liste des 10 familles change
  (section 2.6), la comparaison doit le dire.
