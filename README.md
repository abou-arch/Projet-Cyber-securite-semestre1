# Classification de familles de malwares par analyse statique

Projet de cybersécurité (semestre 1) : classer des malwares par **famille** à partir de
caractéristiques statiques **déjà extraites**, sans jamais exécuter ni manipuler de binaire.

- **Features** : bibliothèques importées, taille du fichier, sections, chaînes de caractères,
  statistiques de fréquence des octets.
- **Outils** : Python, scikit-learn.
- **Dataset** : [EMBER 2018](https://github.com/elastic/ember), publié par Elastic.
- **Livrable** : un classifieur de familles de malwares, avec une analyse de l'importance des features.
- **Sécurité** : uniquement des features extraites, aucun échantillon exécutable.

Ce document explique comment **installer le dataset** et le préparer pour scikit-learn.

---

## 1. Le dataset EMBER 2018

EMBER 2018 décrit 1 million de fichiers PE Windows. Chaque fichier y est représenté par une
ligne JSON de caractéristiques calculées par Elastic. **Le dataset ne contient aucun
exécutable.**

| Sous-ensemble | Malveillants | Bénins | Non étiquetés |
|---------------|-------------:|-------:|--------------:|
| train         | 300 000      | 300 000 | 200 000      |
| test          | 100 000      | 100 000 | —            |

Le champ `avclass` donne la **famille** de chaque malware. Il est calculé par
[AVClass](https://github.com/malicialab/avclass) à partir des verdicts des antivirus.
C'est l'étiquette que nous cherchons à prédire. Le découpage train/test est **temporel** :
le test contient des fichiers plus récents que le train.

Correspondance entre les features demandées et les groupes EMBER :

| Feature du sujet               | Groupe EMBER                  | Exemples de colonnes                                        |
|--------------------------------|-------------------------------|-------------------------------------------------------------|
| Bibliothèques importées        | `imports`                     | `imports_library_hash…`, `imports_function_hash…`           |
| Taille du fichier              | `general`                     | `general_size`, `general_vsize`, `general_imports`          |
| Sections                       | `section`                     | `section_count`, `section_rx_count`, `section_entropy_hash…` |
| Chaînes de caractères          | `strings`                     | `strings_numstrings`, `strings_urls`, `strings_registry`    |
| Fréquence des octets           | `histogram`, `byteentropy`    | `histogram_byte_0x00` … `histogram_byte_0xff`               |
| En plus                        | `header`, `exports`, `datadirectories` | `header_coff_timestamp`, `exports_function_hash…`  |

Chaque échantillon devient un vecteur de **2381 features**. Les noms, les bibliothèques et
les fonctions sont regroupés par « hashing trick » : les colonnes `…_hashNN` rassemblent
plusieurs noms. Il faut en tenir compte au moment d'interpréter l'importance des features.

## 2. Prérequis

- **Python 3.10 ou plus récent**.
- **~15 Go d'espace disque libre** : l'archive fait environ 1,6 Go, les fichiers extraits
  environ 10 Go, et les données préparées environ 9,5 Ko par échantillon.
- Une connexion Internet pour le téléchargement.

Durées indicatives sur un ordinateur portable :

| Étape                               | Durée                       |
|-------------------------------------|-----------------------------|
| Téléchargement (1,6 Go)             | 5 à 30 min selon la connexion |
| Vérification SHA-256                | moins d'une minute          |
| Extraction (~10 Go)                 | environ 10 min              |
| Préparation des familles            | quelques minutes            |

## 3. Installation

### 3.1 Environnement Python

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

### 3.2 Télécharger, vérifier et extraire EMBER

```bash
python -m malware_family.download
```

Le script :

1. télécharge `ember_dataset_2018_2.tar.bz2` dans `data/raw/`. Si la connexion coupe, il
   suffit de relancer la commande : le téléchargement reprend où il s'était arrêté ;
2. vérifie la somme **SHA-256** publiée par Elastic
   (`b6052eb8d350a49a8d5a5396fbe7d16cf42848b86ff969b77464434cf2997812`) ;
3. extrait les fichiers dans `data/raw/ember2018/` : `train_features_0.jsonl` à
   `train_features_5.jsonl`, et `test_features.jsonl`.

Si le téléchargement échoue (proxy, réseau d'école…), téléchargez le fichier avec votre
navigateur à l'adresse <https://ember.elastic.co/ember_dataset_2018_2.tar.bz2>, puis :

```bash
python -m malware_family.download --archive chemin/vers/ember_dataset_2018_2.tar.bz2
```

Ajoutez `--delete-archive` pour supprimer l'archive après l'extraction (1,6 Go gagnés).

### 3.3 Préparer le jeu « familles de malwares »

```bash
python -m malware_family.prepare --top-families 10
```

Le script parcourt les fichiers JSONL et garde les malwares dont la famille AVClass est
connue. Il retient les **10 familles les plus fréquentes du train**, en ne regardant jamais
le test pour ce choix. Il vectorise ensuite ces échantillons dans
`data/processed/ember2018_top10/` :

| Fichier                         | Contenu                                                  |
|---------------------------------|----------------------------------------------------------|
| `X_train.npy`, `X_test.npy`     | matrices `(n, 2381)` en `float32`                        |
| `y_train.npy`, `y_test.npy`     | indice de la famille de chaque ligne                     |
| `families.txt`                  | nom de la famille pour chaque indice (ligne `i` ↔ `y = i`) |
| `feature_names.txt`             | nom des 2381 colonnes                                    |
| `meta_train.csv`, `meta_test.csv` | `sha256`, date d'apparition et famille de chaque ligne |
| `family_counts.csv`             | effectifs de **toutes** les familles, train et test      |
| `dataset_info.json`             | paramètres et statistiques, pour le rapport              |

Options utiles :

- `--top-families N` : nombre de familles à classer.
- `--max-per-family M` : au plus `M` échantillons par famille, tirés au hasard avec
  `--seed`. Ce plafond réduit la taille des données (utile si la RAM manque) et le
  déséquilibre entre classes.
- `--jobs K` : nombre de processus. Par défaut, tous les cœurs sont utilisés.

Les malwares du test qui appartiennent à d'autres familles sont écartés. Leur nombre est
indiqué dans `dataset_info.json`.

### 3.4 Vérifier l'installation

```bash
python -m malware_family.dataset data/processed/ember2018_top10
```

La commande affiche la taille des matrices et le nombre d'échantillons par famille. Si elle
se termine par « Installation vérifiée », le dataset est prêt.

## 4. Utiliser les données avec scikit-learn

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

from malware_family.dataset import load_dataset

data = load_dataset("data/processed/ember2018_top10")
print(data.X_train.shape, data.families)

clf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=0)
clf.fit(data.X_train, data.y_train)
print(classification_report(data.y_test, clf.predict(data.X_test), target_names=data.families))
```

Pour l'analyse d'importance, `data.feature_names[j]` donne le nom de la colonne `j`.
`malware_family.ember_features.feature_groups()` renvoie la position de chaque groupe
(`imports`, `section`, `strings`…), ce qui permet d'agréger l'importance par groupe.

## 5. Sécurité

- EMBER ne contient **que des caractéristiques extraites**. Aucun code malveillant n'est
  téléchargé, stocké ou exécuté.
- Le code du projet ne lit que du JSON. Il n'analyse jamais de fichier PE et n'utilise pas
  LIEF.
- Les `sha256` servent uniquement d'identifiants. Ne téléchargez pas les binaires
  correspondants depuis une plateforme d'analyse de malwares.
- Le dossier `data/` est exclu de git (`.gitignore`) : ne versionnez jamais les données.

## 6. Dépannage

| Problème | Solution |
|----------|----------|
| `Somme SHA-256 incorrecte` | Le fichier est corrompu ou incomplet. Supprimez-le, puis relancez la commande. |
| Téléchargement bloqué (proxy, pare-feu) | Téléchargez l'archive avec un navigateur, puis utilisez `--archive`. |
| `CERTIFICATE_VERIFY_FAILED` sous macOS | Lancez « Install Certificates.command » (dossier `Applications/Python 3.x`). |
| `Attention : … Go libres` | Libérez de l'espace ou choisissez un autre disque avec `--dest`, puis `prepare --data-dir`. |
| Manque de RAM pendant l'entraînement | Relancez `prepare` avec `--max-per-family 5000` (par exemple). |
| `Fichiers EMBER introuvables` | Lancez d'abord `python -m malware_family.download`, ou indiquez `--data-dir`. |
| Google Colab | Les mêmes commandes fonctionnent, préfixées par `!` (`!python -m malware_family.download`) ; changez de dossier avec `%cd`. |

**Pourquoi ne pas utiliser le paquet officiel `ember` ?** Il dépend de LightGBM et de
LIEF 0.9.0, qui n'est publié qu'en code source à compiler. Sa vectorisation échoue aussi avec
scikit-learn ≥ 1.2 (`ValueError: Samples can not be a single string`).
`malware_family/ember_features.py` reproduit exactement cette vectorisation, sans LIEF. Les
tests vérifient qu'elle donne des vecteurs identiques au bit près à ceux du code officiel.

## 7. Structure du dépôt

```
malware_family/
  download.py        téléchargement, vérification SHA-256 et extraction d'EMBER
  prepare.py         sélection des familles et vectorisation → data/processed/
  dataset.py         load_dataset() pour scikit-learn, et vérification de l'installation
  ember_features.py  vectorisation EMBER v2 (2381 features) et noms des features
tests/               tests hors ligne sur des données synthétiques
data/                (non versionné) raw/ = EMBER brut, processed/ = données préparées
```

## Références

- H. Anderson et P. Roth, *EMBER: An Open Dataset for Training Static PE Malware Machine
  Learning Models*, 2018. [arXiv:1804.04637](https://arxiv.org/abs/1804.04637)
- M. Sebastián, R. Rivera, P. Kotzias et J. Caballero, *AVClass: A Tool for Massive Malware
  Labeling*, RAID 2016.
