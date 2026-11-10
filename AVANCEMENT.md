# Avancement du projet

*État au 10/11/2026, d'après les branches `Abou`, `Bryce`, `Kenneth` et `main`. Cochez les cases
au fil de l'eau (`- [x]`) et mettez la date ci-dessus à jour.*

Légende : ✅ terminé · 🔶 en cours ou à reprendre · ⬜ pas commencé.

## État des branches

| Branche | Dernier commit | État |
|---|---|---|
| `Abou` | 10/11 : LightGBM et SHAP intégrés | **branche de référence** : tout le travail commun y est |
| `main` | 26/09 : fichier d'exemple | ne contient rien du travail depuis le 26/09 ; la PR #3 (`Abou` → `main`) attend un relecteur |
| `Bryce` | 09/10 : premier `train.py` | dépassée : son modèle a été repris et refait sur `Abou` (`scripts/train.py`) |
| `Kenneth` | 07/11 : LightGBM, SHAP | intégrée sur `Abou` ; **ne pas la fusionner** (`K_01_exploration.py` cassé, modèle et `.DS_Store` commités) |

À faire par chacun pour repartir sur la même base : `git checkout Abou` puis `git pull`.

## Où en est-on ?

| Phase | État |
|---|---|
| 0. Installation (mêmes données sur les 3 machines) | ✅ |
| 1. Exploration, premiers modèles, outils | ✅ |
| 2. Variantes, modèle final, importance | 🔶 modèle final à relancer avec LightGBM |
| 3. Évaluation détaillée, interprétation | 🔶 calculs faits, interprétation et figures de B à faire |
| 4. Rapport et soutenance | 🔶 sections de A en premier jet, celles de B et C à rédiger |
| 5. Interface web de démonstration | ⬜ à construire (voir plus bas) |

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
- [x] Relecture de B (`train.py`) et de C (branche `Kenneth`)

### Reste à faire
- [ ] Ajouter un relecteur à la PR #3 (C relit A), puis la fusionner
- [ ] Vider les sorties des notebooks 01 et 02 avant de les commiter
- [ ] Vérifier la licence d'EMBER2024 sur sa page Hugging Face (section 8.8)
- [ ] Décider du sort de `ExamplesJson1FilesdatasetChallenges` (1,7 Mo à la racine, ajouté sur `main` le 26/09) :
      le supprimer, ou le déplacer dans `tests/data/` s'il sert à la démo
- [ ] Remplir les cellules « À compléter » des notebooks 01 et 02
- [ ] Choisir le modèle de diapositives commun
- [ ] Assembler le rapport (`pandoc`), harmoniser les renvois et vérifier les chiffres contre `results/`

## Rôle B : modèles et évaluation

### Fait
- [x] Premier modèle (Bryce, 09/10), repris sur le jeu dédoublonné : `scripts/train.py`
- [x] Validation temporelle (15 % les plus récents du train), `random_state` fixé
- [x] Candidats : Dummy, 2 forêts aléatoires, LightGBM (paramètres de Kenneth, arrêt anticipé)
- [x] `results/metrics.json` et `results/predictions_test.csv` (forêt : F1 macro 0,883, exactitude 0,976)
- [x] F1 macro sans les familles de moins de 30 fichiers du test (sinowal : 9 fichiers)

### Reste à faire
- [ ] **Relancer `python -m scripts.train`** avec LightGBM, et noter le modèle retenu
      (forêt : 0,962 sans sinowal ; LightGBM chez Kenneth : 0,964)
- [ ] `scripts/evaluate.py` ou `notebooks/03_modeles.ipynb` :
  - [ ] matrice de confusion normalisée → `results/figures/B_matrice_confusion.png`
  - [ ] score par semaine du test → dérive temporelle (`B_score_par_semaine.png`)
  - [ ] seuil de confiance : que se passe-t-il si on refuse de répondre quand `proba_max` est faible ?
- [ ] Entraîner sur les variantes : `Win32_top10_conf05` (avec `class_weight`) et `Win32_top20`
- [ ] Tester un modèle réduit avec les seules colonnes `header` (74 colonnes : F1 macro 0,894 en ablation)
- [ ] Rédiger les sections 4 (méthodologie) et 5 (résultats) ; diapositives 9 à 12

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
- [ ] Rédiger la section 6 (importance) et la section 7 (discussion, avec B) ; diapositives 13 à 15

## Ensemble

- [ ] Section 9 (conclusion) : une réponse par question (performance, robustesse, interprétation)
- [ ] Relecture croisée : A relit B, B relit C, C relit A
- [ ] Tous les chiffres du rapport et des diapositives viennent de `results/` (même modèle final)
- [ ] Une répétition complète et chronométrée, avec la démo

---

## Interface web de démonstration (nouvelle partie)

**But** : montrer le classifieur en direct pendant la soutenance, et tester le modèle à la main.
**Responsable proposé** : A, avec B pour le chargement du modèle et C pour l'explication SHAP.
**Outil proposé** : [Streamlit](https://streamlit.io) : une page web en Python pur, sans HTML ni
JavaScript, lancée en local avec `streamlit run app/demo.py`.

### Règles de sécurité (à respecter strictement)
- L'interface ne reçoit **jamais d'exécutable** : uniquement des lignes du jeu préparé, ou une
  ligne JSON de features EMBER2024 (comme `ExamplesJson1FilesdatasetChallenges`). Un fichier
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
- [ ] Choisir l'outil (Streamlit proposé) et l'ajouter à `requirements.txt`
- [ ] `app/demo.py` : chargement du modèle, du jeu et de l'index des noms (mis en cache)
- [ ] Page 1 : tester un fichier du test
- [ ] Page 2 : analyser une ligne JSON (avec refus des fichiers binaires et limite de taille)
- [ ] Page 3 : résultats et figures
- [ ] Page 4 : seuil « famille inconnue » (seuil choisi avec B sur la validation)
- [ ] Tests automatiques (`streamlit.testing.v1.AppTest`) sur un petit jeu synthétique
- [ ] Section « Lancer la démo » dans le README
- [ ] Scénario de démo pour la soutenance (2 minutes) : un fichier bien classé, une confusion
      vers wacatac, un fichier à faible confiance ; diapositive « Démo » dans `rapport/diapositives.md`
- [ ] Copie d'écran de secours dans `results/figures/` si la démo ne marche pas le jour J

---

## Prochaines actions (par ordre)

1. **Tous** : `git checkout Abou` puis `git pull` ; `python -m pip install -r requirements.txt`.
2. **A** : relancer `scripts.train` puis `scripts.importance --ablation`, pousser `results/`.
3. **A** : ajouter C comme relecteur de la PR #3.
4. **B** : matrice de confusion et score par semaine ; sections 4 et 5.
5. **C** : interprétation dans le notebook 04 ; sections 6 et 7.
6. **A** : commencer l'interface web (pages 1 et 3 d'abord, les plus utiles pour la démo).
