# 6. Importance des features

*Rôle C. Section à rédiger : le plan ci-dessous est une proposition, à adapter.*

## 6.1 Méthodes

- Importance intrinsèque du modèle (réduction d'impureté) et ses biais.
- Importance par permutation, sur le test [permutation-importance].
- Agrégation par groupe de features (`malware_family.ember_features.feature_groups()`).

## 6.2 Groupes de features les plus utiles

- Importance cumulée par groupe (figure `C_importance_par_groupe.png`).

## 6.3 Features individuelles

- Les features les plus importantes, nommées avec `scripts/hash_lookup.py` pour les colonnes
  hachées (`readable_name`).
- Comparaison avec les pistes de la section 3.5.

## 6.4 Explication des confusions

- Pour les paires de familles les plus confondues (section 5.2), les features qui les
  rapprochent.

## 6.5 Modèle réduit (optionnel)

- Performance du modèle avec les seules features les plus importantes.
