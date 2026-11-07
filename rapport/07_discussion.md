# 7. Discussion et limites

*Rôle C, avec B. Section à rédiger : points à discuter, déjà repérés pendant l'exploration.*

- **Monde fermé** : 58 % des malwares du test appartiennent à d'autres familles (section 2.7).
  Le modèle les classerait à tort dans l'une des 10 qu'il connaît.
- **Étiquettes bruitées** : wacatac est une étiquette générique, et la confiance des étiquettes
  change entre le train et le test pour 4 familles (section 2.6).
- **Petites familles du test** : les scores de sinowal, sfone et grandoreiro reposent sur très
  peu de fichiers.
- **Dérive temporelle** : les familles évoluent par campagnes (section 2.5).
- **Limites de l'analyse statique** : packing et obfuscation (sfone, grandoreiro), et les virus
  qui infectent des programmes légitimes (expiro).
- **Hashing trick** : une colonne hachée peut regrouper plusieurs noms, ce qui rend son
  interprétation moins directe (section 3.3).
- **Plafond de 10 000 fichiers par famille** : il équilibre le train, mais ne reflète pas les
  proportions réelles.
