# Soutenance : trame des diapositives

*A coordonne ; chacun prépare et présente sa partie. Durée proposée : **15 minutes** et
questions. À ajuster dès que la durée officielle est connue.*

## Répartition et minutage

| Partie | Diapositives | Présente | Durée |
|---|---|---|---:|
| Introduction et données | 1 à 8 | A | 5 min |
| Modèles et résultats | 9 à 12 | B | 5 min |
| Importance des features | 13 à 15 | C | 4 min |
| Limites, éthique, conclusion | 16 à 18 | A, B et C | 1 min |

## Règles communes

- **Une idée par diapositive**, dite dans son titre : « Le test est 1 000 fois plus déséquilibré
  que le train », plutôt que « Effectifs ».
- **Au plus 5 lignes de texte.** Le détail va à l'oral et dans le rapport.
- **Figures** prises dans `results/figures/` (style commun, une couleur fixe par famille).
- **Chiffres** identiques à ceux du rapport, sur le jeu `Win32_top10` dédoublonné.
- **Même modèle de diapositives pour tous.** A le fournit avant la répétition.
- **Transitions** : chacun annonce la partie suivante et la personne qui la présente.

---

## Partie A : introduction et données (5 min)

### 1. Titre
- Classification de familles de malwares par analyse statique (EMBER2024).
- Noms de A, B et C, formation, date.

### 2. Pourquoi reconnaître la famille d'un malware ?
- La plupart des malwares sont des variantes de quelques familles.
- La famille indique quoi faire : réagir, prioriser, suivre une campagne.
- *Oral* : les antivirus ne s'accordent pas sur les noms, d'où ClarAVy.

### 3. Notre approche : l'analyse statique, sans exécuter le fichier
- Statique = examiner sans exécuter (en-têtes, imports, sections, octets). Rapide et sans danger.
- EMBER2024 : 3,2 millions de fichiers, déjà réduits à des features. **Aucun exécutable.**
- Question : prédire la famille avec scikit-learn, et expliquer ce qui compte.

### 4. Le jeu : 10 familles, 100 000 fichiers en train
- Win32, 10 familles les plus fréquentes du train, 10 000 fichiers au plus par famille.
- **Figure** : `A_effectifs_familles.png`.
- Message : le train est équilibré, mais le test va de 10 000 berbew à **9 sinowal** (×1 111).

### 5. Un défaut des données, détecté et corrigé
- Chaque ligne des archives figurait **deux fois** : 49 658 lignes de test pour 30 190 fichiers.
- Correction : une ligne par `sha256`, et aucun fichier du test présent dans le train.
- *Oral* : sans cela, les petites familles auraient compté double (18 sinowal au lieu de 9).

### 6. Les malwares arrivent par vagues
- **Figure** : `A_echantillons_par_semaine.png`.
- sfone, grandoreiro et sinowal actives dans le train, presque absentes du test.
- Message : dérive temporelle, d'où une **validation temporelle** (transition vers B).

### 7. Toutes les étiquettes ne se valent pas
- **Figure** : `A_confiance_etiquettes.png`.
- wacatac : étiquette générique (confiance médiane 0,13). Des confusions sont à prévoir.
- Garder les étiquettes sûres vide wacatac, sinowal et grandoreiro (variante A : 148 wacatac).

### 8. 2 568 features, et des familles aux profils distincts
- 12 groupes : en-têtes, sections, imports, chaînes, octets… dont 1 650 colonnes hachées.
- **Figure** : `A_part_non_nulle_features.png` (ou `A_boxplots_features.png`).
- Exemples : grandoreiro, minuscule et sans imports ; glupteba et berbew, sans Rich header ;
  expiro, qui ressemble à un programme normal.
- *Transition* : « Ces différences, B va montrer jusqu'où un modèle les exploite. »

---

## Partie B : modèles et résultats (5 min)

*À compléter par B, avec ses figures préfixées `B_`.*

### 9. Méthode
- Modèles comparés, et pourquoi ce choix.
- Validation temporelle (dernières semaines du train).
- Métrique principale : F1 macro (test déséquilibré), et rappel par famille.

### 10. Résultats globaux
- Tableau : F1 macro et exactitude par modèle. Modèle retenu.

### 11. Familles bien reconnues, familles confondues
- **Figure** : matrice de confusion normalisée (`B_matrice_confusion.png`).
- Les confusions principales, et leur lien avec les profils (diapositive 8) et wacatac (diapositive 7).
- Rappeler que sinowal (9 fichiers) n'est pas interprétable.

### 12. Robustesse : dans le temps et selon les variantes
- Score en validation contre score sur le test : effet de la dérive.
- Variante à étiquettes sûres (A) et variante à 20 familles : ce qui change.
- *Transition* : « Mais sur quoi le modèle s'appuie-t-il ? C va le montrer. »

---

## Partie C : importance des features (4 min)

*À compléter par C, avec ses figures préfixées `C_`.*

### 13. Quels groupes de features comptent le plus ?
- **Figure** : importance par groupe (`C_importance_par_groupe.png`).
- Méthode en une phrase : importance par permutation sur le test.

### 14. Les features les plus importantes, avec leurs vrais noms
- Top 10 des features, avec les noms des colonnes hachées retrouvés par `hash_lookup`
  (ex. `imports_function_hash0581` = `kernel32.dll:VirtualAlloc`).
- Comparaison avec les pistes de l'exploration : sections, Rich header, entropie, imports.

### 15. Pourquoi le modèle se trompe
- Pour une ou deux paires de familles confondues (diapositive 11), les features qui les
  rapprochent.

---

## Ensemble : limites, éthique et conclusion (1 min)

### 16. Limites (C, avec B)
- Monde fermé : 58 % des malwares du test sont d'autres familles.
- Étiquettes bruitées, petites familles du test, packing et obfuscation.

### 17. Éthique et sécurité (A)
- Aucun code malveillant téléchargé ni exécuté ; EMBER2024-capa exclu.
- Le classifieur aide l'analyste, il ne décide pas à sa place.

### 18. Conclusion et perspectives (A, B et C)
- Réponse en une phrase à chacune des 3 questions : performance, robustesse, interprétation.
- Perspectives : familles inconnues, Win64 et .NET, mise à jour du modèle dans le temps.
- « Merci, place aux questions. »

---

## Diapositives de réserve (questions possibles)

- **Le hashing trick** en détail : formule, collisions, signe des valeurs.
- **Les variantes** : tableau 2.5 du rapport (étiquettes sûres) et tableau 2.3 (20 familles).
- **La chaîne de préparation** : download, prepare, vérification ; vectorisation identique au bit
  près à celle du code officiel.
- **Les 43 features constantes** et `VarianceThreshold`.

Questions à préparer :

- Pourquoi ne pas avoir exécuté les fichiers (analyse dynamique) ?
- Pourquoi plafonner à 10 000 fichiers par famille ?
- Que ferait le modèle face à une famille inconnue ?
- Le modèle résisterait-il à un malware packé ou modifié volontairement ?

## Avant la répétition

- [ ] Durée officielle connue, et minutage ajusté.
- [ ] Modèle de diapositives commun choisi (A).
- [ ] Figures de B et C dans `results/figures/`.
- [ ] Chiffres vérifiés contre le rapport (A).
- [ ] Une répétition complète, chronométrée, avec les transitions.
