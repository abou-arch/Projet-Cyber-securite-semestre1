# Avancement du projet

*État au 18/11/2026, d'après les branches `Abou`, `Bryce`, `phase3-evaluation`, `Kenneth` et `main`. Cochez les cases
au fil de l'eau (`- [x]`) et mettez la date ci-dessus à jour.*

Légende : ✅ terminé · 🔶 en cours ou à reprendre · ⬜ pas commencé.

## État des branches

| Branche | Dernier commit | État |
|---|---|---|
| `Abou` | 18/11 : démo en ligne (orbite 3D), correction de l'ablation | **branche de référence** : tout le travail commun y est |
| `main` | 26/09 : fichier d'exemple | ne contient rien du travail depuis le 26/09 ; la PR #3 (`Abou` → `main`) attend un relecteur |
| `phase3-evaluation` | 14/11 : `evaluate.py` (Bryce, compte `JimmyQuiRit`) | intégrée sur `Abou` ; **ne pas la fusionner** (partie d'un `Abou` du 24/10 : 9 conflits, `find_dataset` perdu, `.idea/` commité) |
| `Bryce` | 09/10 : premier `train.py` | dépassée : remplacée par `phase3-evaluation` |
| `Kenneth` | 17/11 : calcul complet sur les vraies données (`calcul_17nov/`) | chiffres repris ci-dessous et correction de l'ablation intégrée sur `Abou` ; **ne pas la fusionner** (`K_01_exploration.py` cassé, modèle et `.DS_Store` commités, figures dans l'ancienne palette) |

À faire par chacun pour repartir sur la même base : `git checkout Abou` puis `git pull`.

## Où en est-on ?

| Phase | État |
|---|---|
| 0. Installation (mêmes données sur les 3 machines) | ✅ |
| 1. Exploration, premiers modèles, outils | ✅ |
| 2. Variantes, modèle final, importance | ✅ HistGradientBoosting retenu (F1 macro 0,917) ; calcul refait sur `Abou`, dans `results/` |
| 3. Évaluation détaillée, interprétation | 🔶 calculs faits, dans `results/` (étape `bruit` comprise) ; interprétation et rédaction à faire |
| 4. Rapport et soutenance | 🔶 sections 1, 2, 3, 8 et diapositives 1 à 8 prêtes ; celles de B et C à rédiger |
| 5. Interface web de démonstration | 🔶 `docs/data/demo.json` réexporté avec le modèle final ; reste à publier |

### Chiffres du calcul complet (`results/`, 18/11)

Refait sur `Abou` : identique au calcul de Kenneth du 17/11 (mêmes 30 948 prédictions). L'ablation
vient de son calcul (relancée sur le PC d'Abou, elle manque de mémoire).

| Mesure | Résultat |
|---|---|
| Modèle retenu (validation) | `hgb_lr0.1_leaves31` : F1 macro 0,962 (LightGBM 0,960 ; forêt 0,957) |
| Test (30 948 fichiers) | F1 macro **0,917**, exactitude **0,982**, exactitude équilibrée 0,918 |
| Sans sinowal (9 fichiers du test) | F1 macro **0,966** ; sinowal seule : 0,476 |
| Familles les plus faibles | grandoreiro 0,909, flystudio 0,941, wacatac 0,956, sfone 0,961 |
| Confusions principales | expiro → wacatac (91), glupteba → wacatac (65), flystudio → wacatac (59) |
| Dérive | F1 macro de 0,975 (semaine du 16/09/2024) à 0,944 (semaine du 09/12/2024) : −0,005 par semaine |
| Stabilité (3 graines) | F1 macro entre 0,913 et 0,922 |
| Modèle réduit | 100 features : F1 0,917 (autant que les 2 568), entraînement 16 fois plus court |
| Bruit des étiquettes (`conf05`) | entraîné sur les seules étiquettes sûres (60 732 fichiers) : F1 macro 0,807 sur son test, 0,691 sur le test complet ; pas mieux que le jeu complet |
| Rejet « inconnu » | seuil 0,9 : répond à 97,2 % des fichiers, 99,1 % de réponses justes |
| Groupes les plus utiles (permutation) | header (baisse de F1 0,315), imports (0,101), datadirectories (0,078) |

---

## Rôle A : données, outils communs, coordination

### Fait
- [x] Téléchargement vérifié (SHA-256) et préparation du jeu `Win32_top10`
- [x] Dédoublonnage : chaque ligne figurait deux fois dans les archives ; aucun fichier du test dans le train
- [x] `load_dataset`, `find_dataset` (variable `EMBER_DATASET` ou dossiers conseillés), vérification et comparaison de jeux
- [x] Notebooks `01_exploration` et `02_features`, figures `A_*`
- [x] `scripts/hash_lookup.py` : vrais noms derrière les colonnes hachées (index construit : 277 258 noms)
- [x] Conventions de figures (`malware_family/figures.py`)
- [x] Variantes préparées et comparées : étiquettes sûres (A et B), 20 familles
- [x] Rapport, premier jet : sections 1, 2, 3 et 8 ; squelette des autres sections ; bibliographie
- [x] Trame des diapositives (18 diapositives, minutage)
- [x] PR #3 ouverte (`Abou` → `main`)
- [x] Relecture et intégration sur `Abou` : B (`train.py`, puis `phase3-evaluation` le 17/11) et C (branche `Kenneth`)
- [x] Interface web : application Streamlit locale (4 pages) et démo en ligne sur GitHub Pages, avec une
      orbite en 3D (voir « Interface web » plus bas)
- [x] Relecture du calcul complet de Kenneth (17/11) : chiffres repris ci-dessus, correction de
      l'ablation intégrée sur `Abou` le 18/11

### Reste à faire
- [ ] Ajouter un relecteur à la PR #3 (C relit A), puis la fusionner
- [x] Sorties des notebooks 01 et 02 vidées
- [x] Licence d'EMBER2024 vérifiée sur Hugging Face : Apache 2.0, accès libre, citation demandée (section 8.8)
- [x] `ExamplesJson1FilesdatasetChallenges` déplacé dans `tests/data/exemple_ember2024.jsonl` (44 vraies
      lignes, familles hors des 10 : exemple pour la démo et pour un test)
- [x] Conclusions des notebooks 01 et 02 rédigées (cellules « À compléter »)
- [x] Modèle de diapositives commun choisi (style sobre, Space Grotesk + Inter) et diapositives 1 à 8
      préparées, avec les notes d'oral : présentation Slides sur claude.ai (lien privé, à partager à B et C)
- [ ] Diapositive 1 : compléter « [Formation] — [date de soutenance] » ; relire les notes d'oral
- [x] Palette commune des figures (violets, ors, beiges, gris) dans `malware_family/figures.py`,
      appliquée aux scripts de B et C et aux notebooks
- [ ] Régénérer les figures `A_` avec la nouvelle palette (notebooks 01 et 02 : *Restart Kernel and
      Run All*), puis les remplacer dans la présentation (diapositives 4, 6, 7 et 8)
- [x] Refaire le calcul final sur `Abou` et pousser `results/` et `docs/data/demo.json`
      (voir « Prochaines actions », étape 2)
- [ ] Assembler le rapport (`pandoc`), harmoniser les renvois et vérifier les chiffres contre `results/`

## Rôle B : modèles et évaluation

### Fait
- [x] Premier modèle (Bryce, 09/10), repris sur le jeu dédoublonné : `scripts/train.py`
- [x] Validation temporelle (15 % les plus récents du train), `random_state` fixé
- [x] Candidats : Dummy, 2 forêts aléatoires, 2 HistGradientBoosting (Bryce, colonnes
      catégorielles déclarées sans décalage d'indices ; sans `class_weight`, qui le rendait
      des centaines de fois plus lent avec scikit-learn 1.9), LightGBM (Kenneth, arrêt anticipé)
- [x] Premier calcul dans `results/` (forêt seule, avant les 6 candidats : F1 macro 0,883, exactitude 0,976)
- [x] Calcul complet sur les vraies données (Kenneth, 17/11) : 6 candidats, HistGradientBoosting
      retenu, F1 macro 0,917 sur le test (chiffres en haut de ce document)
- [x] F1 macro sans les familles de moins de 30 fichiers du test (sinowal : 9 fichiers)
- [x] `scripts/evaluate.py` (Bryce, 14/11, intégré le 17/11), 7 étapes : matrice de confusion,
      F1 selon les effectifs, dérive par semaine, bruit des étiquettes, stabilité (3 graines),
      modèle réduit (d'après C), rejet « inconnu » sous un seuil ; 7 tests
- [x] `evaluate.py` lancé sur le modèle final (Kenneth, 17/11) : toutes les étapes sauf `bruit`
      (variante `Win32_top10_conf05` absente de sa machine)

### Reste à faire
- [ ] Étape `bruit` : lancer `python -m scripts.evaluate` sur une machine qui a la variante
      `Win32_top10_conf05` (celle de A), ou la préparer sur la sienne
- [ ] Entraîner sur la variante `Win32_top20` (20 familles) : ce qui change
- [ ] Interpréter : dérive (−0,005 par semaine), confusions vers wacatac (avec C), stabilité,
      modèle réduit (100 features suffisent), et proposer le seuil de rejet de la démo (0,9 ?)
- [ ] Rédiger les sections 4 (méthodologie) et 5 (résultats) ; diapositives 9 à 12, dans la présentation
      commune (même style que les diapositives 1 à 8)

## Rôle C : importance des features et interprétation

### Fait
- [x] `scripts/importance.py` : importance interne (MDI/gain), permutation par groupe et par
      famille, top 50 features, ablation, confusions, SHAP par famille
- [x] Calcul complet sur la forêt (30 948 fichiers, 43 min) ; résultats et figures `C_*` poussés
- [x] Analyse de Kenneth (LightGBM, gain, SHAP) intégrée sur `Abou`
- [x] Notebook `04_importance` (lit les résultats, cellules d'interprétation)
- [x] Calcul complet sur le modèle final (Kenneth, 17/11, 31 min) : importance, ablation, SHAP
      (200 fichiers par famille)
- [x] Bug trouvé par Kenneth : l'ablation plantait avec HistGradientBoosting (indices des colonnes
      catégorielles non recalés) ; corrigé sur `Abou` le 18/11, avec un test

### Reste à faire
- [ ] Refaire `python -m scripts.importance --ablation` sur `Abou` (figures `C_` dans la nouvelle
      palette ; voir « Prochaines actions », étape 2)
- [ ] Confirmer les noms : `python -m scripts.hash_lookup noms imports_library_hash003 imports_library_hash218`
      (probablement `mfc42.dll` pour cosmu et `mpr.dll` pour sfone)
- [ ] Remplir les cellules « À compléter » du notebook 04 (groupes, features, familles, confusions vers
      wacatac) ; pistes du calcul : `header` compte pour presque toutes les familles (surtout glupteba, berbew
      et sfone ; très peu pour cosmu), `imports` pour sfone et grandoreiro, `datadirectories`
      presque seulement pour grandoreiro
- [ ] Relier les indices aux descriptions publiques des familles (Malpedia, éditeurs), sans télécharger d'échantillon
- [ ] Transmettre à B : groupes et features utiles pour un modèle réduit
- [ ] Rédiger la section 6 (importance) et la section 7 (discussion, avec B) ; diapositives 13 à 15, dans
      la présentation commune

## Ensemble

- [ ] Section 9 (conclusion) : une réponse par question (performance, robustesse, interprétation)
- [ ] Relecture croisée : A relit B, B relit C, C relit A
- [ ] Tous les chiffres du rapport et des diapositives viennent de `results/` (même modèle final)
- [ ] Une répétition complète et chronométrée, avec la démo

---

## Interface web de démonstration

**But** : montrer le classifieur en direct pendant la soutenance, et tester le modèle à la main.
**Responsable** : A, avec B pour le chargement du modèle et C pour l'explication SHAP.
**Outil** : [Streamlit](https://streamlit.io) : une page web en Python pur, lancée en local avec
`python -m streamlit run app/demo.py` (README, § 6.6). Style sombre inspiré de la page de
référence choisie par A (fond noir, cartes à bord fin), graphiques dans la palette du projet.
**Démo en ligne** : <https://abou-arch.github.io/Projet-Cyber-securite-semestre1/> (README, § 6.7).

### Règles de sécurité (à respecter strictement)
- L'interface ne reçoit **jamais d'exécutable** : uniquement des lignes du jeu préparé, ou une
  ligne JSON de features EMBER2024 (comme `tests/data/exemple_ember2024.jsonl`). Un fichier
  `.exe`, `.dll` ou binaire est refusé avec un message qui explique pourquoi.
- Elle tourne **en local seulement** (`localhost`), sans connexion à Internet ni à VirusTotal.
- Les `sha256` sont affichés comme identifiants, jamais comme liens de téléchargement.
- Un avertissement rappelle les limites : 10 familles seulement, outil d'aide et pas de décision.

### Pages
1. **Tester un fichier du test**
   - choisir une famille, un fichier au hasard ou un `sha256` ;
   - afficher la famille prédite, la vraie famille, juste ou faux ;
   - les probabilités des 10 familles (barres, couleurs de `family_colors`) ;
   - les 10 features qui ont le plus pesé (SHAP), avec leurs vrais noms (`hash_lookup`).
2. **Analyser une ligne EMBER2024**
   - coller ou déposer une ligne JSON de features ;
   - vectorisation avec `malware_family.ember_features.vectorize`, puis prédiction et explication.
3. **Résultats du modèle** : scores (`metrics.json`), matrice de confusion, figures `B_` et `C_`.
4. **Famille inconnue ?** : si la probabilité maximale est sous un seuil, afficher « famille
   probablement inconnue » plutôt qu'une des 10 (illustre la limite du monde fermé : 58 % des
   malwares du test sont d'autres familles).

### Tâches
- [x] Outil choisi (Streamlit) et ajouté à `requirements.txt`, avec `shap` pour les explications
- [x] `app/demo.py` (pages) et `app/core.py` (logique) : modèle, jeu et index des noms mis en cache ;
      fonctionne avec une forêt, HistGradientBoosting ou LightGBM
- [x] Page 1 : tester un fichier du test (au hasard, par famille ou par empreinte)
- [x] Page 2 : analyser des lignes JSON (fichiers binaires refusés, 5 Mo au plus, exemple de 44 lignes)
- [x] Page 3 : résultats et figures `A_`, `B_`, `C_`
- [x] Page 4 : seuil « famille inconnue » réglable, sur le test et sur des familles jamais vues
- [x] Tests automatiques (`streamlit.testing.v1.AppTest`) sur un petit jeu synthétique : 14 tests
- [x] Section « Interface web de démonstration » dans le README (§ 6.6)
- [ ] La lancer sur les vraies données avec le modèle final, et choisir le seuil par défaut avec B
      (`results/rejet.csv`)
- [x] Version en ligne pour GitHub Pages (`docs/`) : page statique animée, dans le même style, qui
      lit des résultats exportés à l'avance (`scripts/export_demo.py`, README § 6.7)
- [x] `python -m scripts.export_demo` (forêt du premier calcul), `docs/data/demo.json` poussé et
      GitHub Pages activé (branche `Abou`, dossier `/docs`)
- [x] Animations proches de la page de référence (apparitions, compteurs, curseur, sections qui
      s'estompent) et orbite en 3D (Three.js, WebGL), avec un repli en 2D
- [ ] Réexporter `docs/data/demo.json` avec le modèle final (HistGradientBoosting), puis le pousser
- [ ] Après la fusion de la PR #3 : faire servir GitHub Pages depuis `main` (facultatif)
- [ ] Scénario de démo pour la soutenance (2 minutes) : un fichier bien classé, une confusion
      vers wacatac, un fichier à faible confiance ; diapositive « Démo » dans `rapport/diapositives.md`
- [ ] Copie d'écran de secours dans `results/figures/` si la démo ne marche pas le jour J

---

## Prochaines actions (par ordre)

1. **Tous** : `git checkout Abou` puis `git pull` ; `python -m pip install -r requirements.txt`.
   Ne plus travailler sur `Bryce`, `phase3-evaluation` ni `Kenneth` : tout est sur `Abou`.
2. **A** (qui a la variante `conf05`), ou Kenneth : refaire le calcul final sur `Abou` à jour et
   comparer aux chiffres du 17/11 (F1 macro 0,917) :
   `python -m scripts.train` (≈ 10 min), `python -m scripts.importance --ablation` (≈ 30 min),
   `python -m scripts.evaluate`, puis `python -m scripts.export_demo` ; pousser `results/` et
   `docs/data/demo.json`. Les figures `B_` et `C_` sortiront dans la nouvelle palette.
3. **A** : régénérer les figures `A_` (notebooks 01 et 02) et les mettre dans les diapositives 4, 6, 7
   et 8 ; compléter la diapositive 1 ; ajouter C comme relecteur de la PR #3.
4. **B** : sections 4 et 5 avec les chiffres de `results/metrics.json` et `results/evaluation.json` ;
   choisir avec A le seuil « inconnu » de la démo.
5. **C** : interprétation dans le notebook 04 ; sections 6 et 7 ; diapositives 13 à 15.
6. **A** : scénario de démo (2 minutes) et copie d'écran de secours ; puis assemblage du rapport.
