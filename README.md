# Classification de familles de malwares par analyse statique

Projet de cybersécurité (semestre 1) : classer des malwares par **famille** à partir de
caractéristiques statiques **déjà extraites**, sans jamais exécuter ni manipuler de binaire.

- **Features** : bibliothèques importées, taille du fichier, sections, chaînes de caractères,
  statistiques de fréquence des octets.
- **Outils** : Python, scikit-learn.
- **Dataset** : [EMBER2024](https://github.com/FutureComputing4AI/EMBER2024), hébergé sur
  [Hugging Face](https://huggingface.co/datasets/joyce8/EMBER2024).
- **Livrable** : un classifieur de familles de malwares, avec une analyse de l'importance des features.
- **Sécurité** : uniquement des features extraites, aucun échantillon exécutable.

Ce document explique comment **installer le dataset** et le préparer pour scikit-learn.

---

## 1. Le dataset EMBER2024

EMBER2024 décrit 3,2 millions de fichiers soumis à VirusTotal entre septembre 2023 et
décembre 2024. Chaque fichier y est représenté par une ligne JSON de caractéristiques.
**Le dataset ne contient aucun exécutable.** Le projet n'utilise que les exécutables Windows
(PE), car ses features (imports, sections…) n'existent que pour eux :

| Type    | Train     | Test    | Taille annoncée (train + test) |
|---------|----------:|--------:|-------------------------------:|
| Win32   | 1 560 000 | 360 000 | 28,6 Go                        |
| Win64   |   520 000 | 120 000 | 15,4 Go                        |
| .NET    |   260 000 |  60 000 |  2,2 Go                        |

Chiffres du [README officiel](https://github.com/FutureComputing4AI/EMBER2024). Chaque type
contient des fichiers bénins et malveillants.

- **Étiquette de famille** : le champ `family` est calculé par
  [ClarAVy](https://github.com/FutureComputing4AI/ClarAVy) à partir des verdicts des
  antivirus. Il est accompagné d'un score de confiance, `family_confidence`.
- **Découpage temporel** : le train couvre les 52 premières semaines, le test les 12
  dernières. On évalue donc le classifieur sur des malwares plus récents que ceux de
  l'apprentissage.
- **Familles les plus fréquentes** (tous types confondus, d'après le notebook officiel) :
  berbew, wacatac, expiro, cosmu, xmrig, upatre, sfone, glupteba, grandoreiro, flystudio.

Correspondance entre les features demandées et les groupes EMBER2024 (format « version 3 ») :

| Feature du sujet         | Groupe EMBER2024           | Exemples de colonnes                                          |
|--------------------------|----------------------------|---------------------------------------------------------------|
| Bibliothèques importées  | `imports`                  | `imports_library_count`, `imports_library_hash…`, `imports_function_hash…` |
| Taille du fichier        | `general`, `header`        | `general_size`, `header_optional_sizeof_image`                |
| Sections                 | `section`                  | `section_count`, `section_entropy_max`, `section_rx_count`   |
| Chaînes de caractères    | `strings`                  | `strings_numstrings`, `strings_pattern_url`, `strings_pattern_powershell` |
| Fréquence des octets     | `histogram`, `byteentropy` | `histogram_byte_0x00` … `histogram_byte_0xff`                 |
| En plus                  | `header`, `exports`, `datadirectories`, `richheader`, `authenticode`, `pefilewarnings` | `authenticode_num_certs`, `richheader_pairs` |

Chaque échantillon devient un vecteur de **2568 features**. Les noms de bibliothèques, de
fonctions et de sections sont regroupés par « hashing trick » : une colonne `…_hashNN`
rassemble plusieurs noms. Il faut en tenir compte pour interpréter l'importance des features.

## 2. Ce qui est téléchargé, et ce qui ne l'est pas

Seules les données nécessaires au projet sont récupérées :

- **Téléchargé** : `Win32_train.zip` et `Win32_test.zip` par défaut, ou les archives des types
  choisis avec `--file-types`.
- **Jamais téléchargé** :
  - les fichiers APK, ELF et PDF ;
  - le « challenge set » ;
  - les modèles de référence ;
  - le jeu complémentaire **EMBER2024-capa**, qui contient du code malveillant désassemblé et
    sort du cadre de sécurité du projet.
- **Pas de décompression** : les archives restent compressées sur le disque, et
  `prepare` lit directement leur contenu.
- **Données préparées** : seuls les malwares des familles retenues sont vectorisés, à
  raison d'environ 10 Ko par échantillon.

## 3. Prérequis

- **Python 3.10 ou plus récent**.
- **De l'espace disque pour les archives.** Leur taille réelle est affichée par le script
  avant le téléchargement. Win32 est le type le plus volumineux (voir le tableau ci-dessus).
- Un accès à `huggingface.co`.

## 4. Installation

### 4.1 Environnement Python

```bash
git clone https://github.com/abou-arch/Projet-Cyber-securite-semestre1.git
cd Projet-Cyber-securite-semestre1
git checkout Abou

python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r requirements.txt

python -m pytest                   # optionnel : ~10 s, hors ligne, vérifie que tout fonctionne
```

Toutes les commandes suivantes se lancent **depuis la racine du projet**.

### 4.2 Télécharger les archives nécessaires

```bash
python -m malware_family.download                          # exécutables Win32 (défaut)
python -m malware_family.download --file-types Win32 Win64 # plusieurs types
```

Les archives arrivent dans `data/raw/ember2024/`. Le script :

- vérifie chacune avec la **somme SHA-256** publiée par Hugging Face ;
- reprend un téléchargement interrompu là où il s'était arrêté : il suffit de relancer la commande ;
- ne retélécharge pas une archive déjà vérifiée.

Si le téléchargement est impossible par ce script (réseau d'école, proxy…), passe par ton
navigateur :

1. Va sur la page [Files and versions](https://huggingface.co/datasets/joyce8/EMBER2024/tree/main)
   du dataset.
2. Télécharge `Win32_train.zip` et `Win32_test.zip`.
3. Place-les dans `data/raw/ember2024/`.
4. Relance `python -m malware_family.download` : il les vérifie sans les retélécharger.

### 4.3 Préparer le jeu « familles de malwares »

```bash
python -m malware_family.prepare --top-families 10
```

Le script lit les archives et garde les malwares dont la famille est connue. Il retient les
**10 familles les plus fréquentes du train**, sans jamais regarder le test pour ce choix. Il
vectorise ensuite ces échantillons dans `data/processed/ember2024_Win32_top10/` :

| Fichier                           | Contenu                                                     |
|-----------------------------------|-------------------------------------------------------------|
| `X_train.npy`, `X_test.npy`       | matrices `(n, 2568)` en `float32`, lignes triées par date   |
| `y_train.npy`, `y_test.npy`       | indice de la famille de chaque ligne                        |
| `families.txt`                    | nom de la famille pour chaque indice (ligne `i` ↔ `y = i`)  |
| `feature_names.txt`               | nom des 2568 colonnes                                       |
| `meta_train.csv`, `meta_test.csv` | `sha256`, date de première soumission, type, famille et confiance de chaque ligne |
| `family_counts.csv`               | effectifs de **toutes** les familles, train et test         |
| `dataset_info.json`               | paramètres et statistiques, pour le rapport                 |

Options utiles :

- `--top-families N` : nombre de familles à classer.
- `--max-per-family M` : au plus `M` échantillons par famille et par split, tirés au hasard
  (graine `--seed`). La valeur par défaut, 10 000, limite `X_train` à environ 1 Go pour
  10 familles et réduit le déséquilibre entre familles. `0` garde tout, mais les familles
  les plus fréquentes comptent des dizaines de milliers d'échantillons.
- `--min-confidence 0.5` : ignore les étiquettes de famille peu sûres.
- `--file-types Win32` : restreint la préparation à certains types téléchargés.
- `--jobs K` : nombre de processus. Par défaut, tous les cœurs sont utilisés.

Les malwares du test qui appartiennent à d'autres familles sont écartés. Leur nombre est
indiqué dans `dataset_info.json`.

### 4.4 Vérifier l'installation

```bash
python -m malware_family.dataset data/processed/ember2024_Win32_top10
```

La commande affiche la taille des matrices et le nombre d'échantillons par famille. Elle
vérifie aussi qu'aucune valeur n'est aberrante (infinie ou manquante). Si elle se termine par
« Installation vérifiée », le dataset est prêt.

## 5. Utiliser les données avec scikit-learn

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

from malware_family.dataset import load_dataset

data = load_dataset("data/processed/ember2024_Win32_top10")
print(data.X_train.shape, data.families)

clf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=0)
clf.fit(data.X_train, data.y_train)
print(classification_report(data.y_test, clf.predict(data.X_test), target_names=data.families))
```

Pour l'analyse d'importance, `data.feature_names[j]` donne le nom de la colonne `j`.
`malware_family.ember_features.feature_groups()` renvoie la position de chaque groupe
(`imports`, `section`, `strings`…), pour agréger l'importance par groupe.
`CATEGORICAL_FEATURES` liste les colonnes qui sont des codes et non des quantités : type de
machine, sous-système, premiers octets.

## 6. Sécurité

- EMBER2024 ne contient **que des caractéristiques extraites**. Aucun code malveillant n'est
  téléchargé, stocké ou exécuté.
- Le jeu complémentaire EMBER2024-capa, qui contient du code malveillant désassemblé, n'est
  jamais téléchargé.
- Le code du projet ne lit que du JSON. Il n'analyse jamais de fichier exécutable.
- Les `sha256` servent uniquement d'identifiants. Ne télécharge pas les binaires
  correspondants depuis une plateforme d'analyse de malwares.
- Le dossier `data/` est exclu de git (`.gitignore`) : ne versionne jamais les données.

## 7. Dépannage

| Problème | Solution |
|----------|----------|
| `Impossible d'interroger Hugging Face` | Vérifie ta connexion et un éventuel proxy, ou télécharge les archives avec ton navigateur (§ 4.2). |
| `… est corrompu` | L'archive a été supprimée : relance la commande. |
| `Attention : il faut … Go` | Libère de l'espace, ou choisis un autre disque avec `--dest`, puis utilise `prepare --data-dir`. |
| Manque de RAM pendant l'entraînement | Relance `prepare` avec un plafond plus bas, par exemple `--max-per-family 3000`. |
| `Archives EMBER2024 introuvables` | Lance d'abord `python -m malware_family.download`, ou indique `--data-dir`. |
| Google Colab | Les mêmes commandes fonctionnent, préfixées par `!` (`!python -m malware_family.download`). Change de dossier avec `%cd`. |

**Pourquoi ne pas utiliser le paquet officiel `thrember` ?**

- **Son installation échoue aujourd'hui.** Avec `signify` ≥ 0.9, `import thrember` plante.
  Sous Linux avec un OpenSSL récent, `oscrypto` ne trouve pas la bibliothèque.
- **Sa préparation ne passe pas sur un portable.** Il vectorise tous les fichiers, bénins
  compris (environ 24 Go pour le train PE), puis charge tout en mémoire.

`malware_family/ember_features.py` reproduit exactement sa vectorisation, sans ces
dépendances. Les tests vérifient qu'elle donne des vecteurs identiques au bit près.

## 8. Structure du dépôt

```
malware_family/
  download.py        téléchargement et vérification des archives EMBER2024 utiles
  prepare.py         sélection des familles et vectorisation → data/processed/
  dataset.py         load_dataset() pour scikit-learn, et vérification de l'installation
  ember_features.py  vectorisation EMBER2024 (2568 features) et noms des features
plan/                répartition du travail à trois : A (données), B (modèles), C (importance)
tests/               tests hors ligne sur des données synthétiques
data/                (non versionné) raw/ = archives EMBER2024, processed/ = données préparées
```

## Références

- R. J. Joyce, G. Miller, P. Roth, R. Zak, E. Zaresky-Williams, H. Anderson, E. Raff et J. Holt,
  *EMBER2024 – A Benchmark Dataset for Holistic Evaluation of Malware Classifiers*, KDD 2025.
  [arXiv:2506.05074](https://arxiv.org/abs/2506.05074)
- Code d'origine de la vectorisation : [thrember](https://github.com/FutureComputing4AI/EMBER2024)
  (licence Apache 2.0).
