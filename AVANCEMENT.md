# Avancement du projet

*État au 17/11/2026, d'après les branches `Abou`, `Bryce`, `phase3-evaluation`, `Kenneth` et `main`. Cochez les cases
au fil de l'eau (`- [x]`) et mettez la date ci-dessus à jour.*

Légende : ✅ terminé · 🔶 en cours ou à reprendre · ⬜ pas commencé.

## État des branches

| Branche | Dernier commit | État |
|---|---|---|
| `Abou` | 17/11 : évaluation de Bryce intégrée | **branche de référence** : tout le travail commun y est |
| `main` | 26/09 : fichier d'exemple | ne contient rien du travail depuis le 26/09 ; la PR #3 (`Abou` → `main`) attend un relecteur |
| `phase3-evaluation` | 14/11 : `evaluate.py` (Bryce, compte `JimmyQuiRit`) | intégrée sur `Abou` ; **ne pas la fusionner** (partie d'un `Abou` du 24/10 : 9 conflits, `find_dataset` perdu, `.idea/` commité) |
| `Bryce` | 09/10 : premier `train.py` | dépassée : remplacée par `phase3-evaluation` |
| `Kenneth` | 07/11 : LightGBM, SHAP | intégrée sur `Abou` ; **ne pas la fusionner** (`K_01_exploration.py` cassé, modèle et `.DS_Store` commités) |

À faire par chacun pour repartir sur la même base : `git checkout Abou` puis `git pull`.

## Où en est-on ?

| Phase | État |
|---|---|
| 0. Installation (mêmes données sur les 3 machines) | ✅ |
| 1. Exploration, premiers modèles, outils | ✅ |
| 2. Variantes, modèle final, importance | 🔶 code prêt (6 candidats) ; modèle final à relancer sur les vraies données |
| 3. Évaluation détaillée, interprétation | 🔶 code prêt (`evaluate.py`, `importance.py`) ; calculs et interprétation à faire |
| 4. Rapport et soutenance | 🔶 sections et diapositives de A prêtes ; celles de B et C à rédiger |
| 5. Interface web de démonstration | 🔶 prête et testée ; à lancer sur le modèle final (voir plus bas) |

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
- [ ] Assembler le rapport (`pandoc`), harmoniser les renvois et vérifier les chiffres contre `results/`

## Rôle B : modèles et évaluation

### Fait
- [x] Premier modèle (Bryce, 09/10), repris sur le jeu dédoublonné : `scripts/train.py`
- [x] Validation temporelle (15 % les plus récents du train), `random_state` fixé
- [x] Candidats : Dummy, 2 forêts aléatoires, 2 HistGradientBoosting (Bryce, colonnes
      catégorielles déclarées sans décalage d'indices ; sans `class_weight`, qui le rendait
      des centaines de fois plus lent avec scikit-learn 1.9), LightGBM (Kenneth, arrêt anticipé)
- [x] `results/metrics.json` et `results/predictions_test.csv` (forêt : F1 macro 0,883, exactitude 0,976)
- [x] F1 macro sans les familles de moins de 30 fichiers du test (sinowal : 9 fichiers)
- [x] `scripts/evaluate.py` (Bryce, 14/11, intégré le 17/11), 7 étapes : matrice de confusion,
      F1 selon les effectifs, dérive par semaine, bruit des étiquettes, stabilité (3 graines),
      modèle réduit (d'après C), rejet « inconnu » sous un seuil ; 7 tests

### Reste à faire
- [ ] **Relancer `python -m scripts.train`** (6 candidats, 20 à 40 min) et noter le modèle retenu
      (forêt : 0,962 sans sinowal ; LightGBM chez Kenneth : 0,964)
- [ ] **Lancer `python -m scripts.evaluate`** sur les vraies données (après `scripts.importance`,
      pour que le modèle réduit suive le classement de C) et pousser `results/`
- [ ] Préparer la variante `Win32_top10_conf05` sur sa machine si l'étape `bruit` la demande
- [ ] Entraîner sur la variante `Win32_top20` (20 familles) : ce qui change
- [ ] Interpréter : dérive (pente par semaine), confusions vers wacatac (avec C), seuil de rejet
      à proposer pour la démo
- [ ] Rédiger les sections 4 (méthodologie) et 5 (résultats) ; diapositives 9 à 12, dans la présentation
      commune (même style que les diapositives 1 à 8)

## Rôle C : importance des features et interprétation

### Fait
- [x] `scripts/importance.py` : importance interne (MDI/gain), permutation par groupe et par
      famille, top 50 features, ablation, confusions, SHAP par famille
- [x] Calcul complet sur la forêt (30 948 fichiers, 43 min) ; résultats et figures `C_*` poussés
- [x] Analyse de Kenneth (LightGBM, gain, SHAP) intégrée sur `Abou`
- [x] Notebook `04_importance` (lit les résultats, cellules d'interprétation)

### Reste à faire
- [ ] Relancer `python -m scripts.importance --ablation` **sur le modèle final** retenu par B
      (+ SHAP : rapide pour LightGBM ; pour une forêt, `pip install shap` et `--shap-per-family 20`)
- [ ] Confirmer les noms : `python -m scripts.hash_lookup noms imports_library_hash003 imports_library_hash218`
      (probablement `mfc42.dll` pour cosmu et `mpr.dll` pour sfone)
- [ ] Remplir les cellules « À compléter » du notebook 04 (groupes, features, familles, confusions vers wacatac)
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
référence choisie par A (fond noir, accent bleu-cyan, cartes à bord fin, halo bleu).

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
- [ ] `python -m scripts.export_demo` sur le modèle final, commiter `docs/data/demo.json`, puis
      activer GitHub Pages (*Settings → Pages*, dossier `/docs`) après la fusion dans `main`
- [ ] Scénario de démo pour la soutenance (2 minutes) : un fichier bien classé, une confusion
      vers wacatac, un fichier à faible confiance ; diapositive « Démo » dans `rapport/diapositives.md`
- [ ] Copie d'écran de secours dans `results/figures/` si la démo ne marche pas le jour J

---

## Prochaines actions (par ordre)

1. **Tous** : `git checkout Abou` puis `git pull` ; `python -m pip install -r requirements.txt`.
   Ne plus travailler sur `Bryce`, `phase3-evaluation` ni `Kenneth` : tout est sur `Abou`.
2. **A** : ajouter C comme relecteur de la PR #3.
3. **B** : `python -m scripts.train`, puis `python -m scripts.importance --ablation` (ou A),
   puis `python -m scripts.evaluate` ; pousser `results/` et les figures `B_` et `C_`, qui sortiront
   directement dans la nouvelle palette.
4. **B** : sections 4 et 5, avec les chiffres de `results/metrics.json` et `results/evaluation.json`.
5. **C** : interprétation dans le notebook 04 ; sections 6 et 7.
6. **A** : lancer l'interface sur les vraies données (`python -m streamlit run app/demo.py`) une fois
   le modèle final entraîné, puis préparer le scénario de démo.
