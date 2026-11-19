"""Logique de l'interface de démonstration (sans Streamlit, donc testable).

L'interface ne reçoit jamais d'exécutable : seulement des fichiers du jeu préparé ou des lignes
JSON de features EMBER2024. Tout reste en local, sans connexion à Internet.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from malware_family.dataset import find_dataset, load_dataset
from malware_family.ember_features import vectorize
from scripts.hash_lookup import load_index, readable_name
from scripts.importance import shap_for_class

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "tests" / "data" / "exemple_ember2024.jsonl"
MAX_UPLOAD_BYTES = 5_000_000      # même limite que .streamlit/config.toml (5 Mo)
DEFAULT_THRESHOLD = 0.5           # sous ce seuil de probabilité : « famille probablement inconnue »
REFUSED_BINARY = ("Ce fichier ressemble à un exécutable ou à un fichier binaire. L'interface n'accepte "
                  "que des lignes JSON de features EMBER2024 : elle n'analyse jamais de fichier "
                  "exécutable, et il ne faut jamais en télécharger un à partir de son empreinte.")
# Signatures de fichiers binaires refusés : PE (MZ), ELF, PDF, archives zip, gzip, 7z.
BINARY_MAGICS = (b"MZ", b"\x7fELF", b"%PDF", b"PK\x03\x04", b"\x1f\x8b", b"7z\xbc\xaf")


@dataclass
class Resources:
    """Tout ce que l'interface charge une seule fois."""
    model: object
    data: object                  # FamilyDataset (X_test reste sur le disque)
    index: pd.DataFrame | None    # index des noms hachés (scripts.hash_lookup), facultatif
    metrics: dict | None          # results/metrics.json (scripts.train)
    evaluation: dict | None       # results/evaluation.json (scripts.evaluate)
    dataset_path: Path
    model_path: Path
    results_dir: Path


def default_model_path():
    return Path(os.environ.get("EMBER_MODEL", ROOT / "models" / "best_model.joblib")).expanduser()


def default_results_dir():
    return Path(os.environ.get("EMBER_RESULTS", ROOT / "results")).expanduser()


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_resources(dataset=None, model_path=None, results_dir=None):
    """Charge le modèle final, le jeu préparé, l'index des noms et les résultats.

    Lève FileNotFoundError ou ValueError avec un message à afficher tel quel."""
    dataset = Path(dataset).expanduser() if dataset else find_dataset(ROOT)
    model_path = Path(model_path) if model_path else default_model_path()
    results_dir = Path(results_dir) if results_dir else default_results_dir()
    if not model_path.is_file():
        raise FileNotFoundError(f"Pas de modèle {model_path} : lancez d'abord "
                                "« python -m scripts.train ».")
    data = load_dataset(dataset)
    model = joblib.load(model_path)
    if getattr(model, "n_features_in_", data.X_test.shape[1]) != data.X_test.shape[1]:
        raise ValueError(f"{model_path} attend {model.n_features_in_} features, le jeu {dataset} en a "
                         f"{data.X_test.shape[1]} : relancez « python -m scripts.train » sur ce jeu.")
    try:
        index = load_index(dataset)
    except FileNotFoundError:
        index = None
    return Resources(model, data, index, _read_json(results_dir / "metrics.json"),
                     _read_json(results_dir / "evaluation.json"), dataset, model_path, results_dir)


# ---------------------------------------------------------------------------
# Prédiction
# ---------------------------------------------------------------------------

def predict_proba(model, X, n_families):
    """Probabilités (n, n_families), colonne k = famille k, même si le modèle n'a pas vu toutes
    les familles."""
    X = np.atleast_2d(np.asarray(X, dtype=np.float32))
    proba = np.zeros((len(X), n_families))
    proba[:, np.asarray(model.classes_, dtype=int)] = model.predict_proba(X)
    return proba


def ranking(proba_row, families):
    """Familles de la plus probable à la moins probable."""
    order = np.argsort(proba_row)[::-1]
    return pd.DataFrame({"famille": [families[k] for k in order], "probabilité": proba_row[order]})


def decision(proba_row, families, threshold=DEFAULT_THRESHOLD):
    """Famille prédite, sa probabilité, et si elle est sous le seuil (« probablement inconnue »)."""
    k = int(np.argmax(proba_row))
    return {"indice": k, "famille": families[k], "probabilité": float(proba_row[k]),
            "inconnue": bool(proba_row[k] < threshold)}


def rejection_table(proba_max, correct, thresholds=None):
    """Pour chaque seuil : part des fichiers auxquels le modèle répond, et justesse de ces réponses."""
    proba_max, correct = np.asarray(proba_max), np.asarray(correct, dtype=bool)
    thresholds = np.round(np.arange(0, 1.0001, 0.05), 2) if thresholds is None else thresholds
    rows = []
    for t in thresholds:
        kept = proba_max >= t
        rows.append({"seuil": float(t), "couverture": float(kept.mean()) if len(kept) else np.nan,
                     "justesse": float(correct[kept].mean()) if kept.any() else np.nan,
                     "n_reponses": int(kept.sum())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Explication (SHAP)
# ---------------------------------------------------------------------------

class Explainer:
    """Contributions SHAP d'un fichier à la décision « famille k ».

    LightGBM les calcule lui-même ; pour une forêt ou HistGradientBoosting, il faut le paquet
    ``shap`` (créé une seule fois, puis réutilisé). ``available`` est faux si rien ne marche."""

    def __init__(self, model):
        self.model = model
        self._tree = None
        self.error = None

    def _shap_values(self, X, k):
        if hasattr(self.model, "booster_"):
            return shap_for_class(self.model, X, k)
        if self._tree is None:
            import shap  # ImportError géré par contributions()
            self._tree = shap.TreeExplainer(self.model)
        values = self._tree.shap_values(X, check_additivity=False)
        position = list(self.model.classes_).index(k)
        if isinstance(values, list):
            return np.asarray(values[position])
        return np.asarray(values)[:, :, position]

    def contributions(self, x, k):
        """Vecteur (n_features,) ou None si l'explication n'est pas disponible."""
        try:
            values = self._shap_values(np.atleast_2d(np.asarray(x, dtype=np.float32)), k)
        except ImportError:
            self.error = "le paquet shap n'est pas installé (python -m pip install shap)"
            return None
        except Exception as error:  # modèle non pris en charge par shap
            self.error = f"{type(error).__name__} : {error}"
            return None
        return None if values is None else np.asarray(values)[0]

    def top(self, x, k, names, index=None, n=10):
        """Les ``n`` features qui pèsent le plus, avec leur vrai nom et leur sens."""
        values = self.contributions(x, k)
        if values is None:
            return None
        order = np.argsort(np.abs(values))[::-1][:n]
        x = np.asarray(x).ravel()
        return pd.DataFrame({
            "feature": [readable_name(names[j], index) if index is not None else names[j] for j in order],
            "valeur": x[order],
            "contribution": values[order],
            "sens": ["pousse vers" if values[j] > 0 else "éloigne de" for j in order],
        })


# ---------------------------------------------------------------------------
# Lignes JSON de features
# ---------------------------------------------------------------------------

def read_feature_lines(raw):
    """Lignes EMBER2024 d'un texte ou d'un fichier déposé : renvoie (lignes valides, erreurs).

    Refuse tout fichier binaire (exécutable, archive, PDF) et tout fichier de plus de 5 Mo.
    Accepte une ligne JSON par fichier analysé, un seul objet JSON, ou une liste d'objets."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(f"Fichier trop gros ({len(raw) / 1e6:.1f} Mo) : 5 Mo au plus.")
    head = raw.lstrip()[:8]
    if raw.startswith(BINARY_MAGICS) or head.startswith(BINARY_MAGICS) or b"\x00" in raw[:4096]:
        raise ValueError(REFUSED_BINARY)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(REFUSED_BINARY) from None
    try:
        whole = json.loads(text)
        candidates = whole if isinstance(whole, list) else [whole]
        numbered = list(enumerate(candidates, 1))
    except json.JSONDecodeError:
        numbered = [(i, line) for i, line in enumerate(text.splitlines(), 1) if line.strip()]
    rows, errors = [], []
    for number, item in numbered:
        try:
            row = json.loads(item) if isinstance(item, str) else item
            if not isinstance(row, dict):
                raise ValueError("ce n'est pas un objet JSON")
            vectorize(row)  # vérifie que toutes les features sont là
        except Exception as error:
            errors.append(f"ligne {number} : {type(error).__name__} ({str(error)[:80]})")
            continue
        rows.append(row)
    if not rows:
        raise ValueError("Aucune ligne de features EMBER2024 valide. " + "; ".join(errors[:3]))
    return rows, errors


def vectorize_rows(rows):
    return np.vstack([vectorize(row) for row in rows]).astype(np.float32)


def describe_row(row, number):
    """Résumé lisible d'une ligne : identifiant, type, famille connue, date."""
    date = row.get("first_submission_date")
    when = (datetime.fromtimestamp(date, tz=timezone.utc).strftime("%d/%m/%Y")
            if isinstance(date, (int, float)) else "?")
    return {"n°": number, "sha256": str(row.get("sha256", "?"))[:16] + "…",
            "type": row.get("file_type", "?"), "famille (étiquette)": row.get("family") or "aucune",
            "confiance": (f"{row['family_confidence']:.2f}".replace(".", ",")
                          if isinstance(row.get("family_confidence"), (int, float)) else "—"),
            "première soumission": when}


# ---------------------------------------------------------------------------
# Fichiers du test
# ---------------------------------------------------------------------------

def pick_test_row(data, family=None, seed=None):
    """Indice d'un fichier du test, tiré au hasard (dans une famille si ``family`` est donnée)."""
    rng = np.random.default_rng(seed)
    rows = (np.arange(len(data.y_test)) if family is None
            else np.flatnonzero(data.y_test == data.families.index(family)))
    if not len(rows):
        raise ValueError(f"Aucun fichier de la famille {family} dans le test.")
    return int(rng.choice(rows))


def find_test_row(data, sha256_prefix):
    """Indice du fichier du test dont l'empreinte commence par ``sha256_prefix`` (au moins 8 caractères)."""
    prefix = sha256_prefix.strip().lower()
    if len(prefix) < 8 or any(c not in "0123456789abcdef" for c in prefix):
        raise ValueError("Donnez au moins 8 caractères hexadécimaux de l'empreinte sha256.")
    matches = np.flatnonzero(data.meta_test.sha256.str.startswith(prefix).to_numpy())
    if not len(matches):
        raise ValueError("Aucun fichier du test avec cette empreinte.")
    if len(matches) > 1:
        raise ValueError(f"{len(matches)} fichiers commencent ainsi : donnez plus de caractères.")
    return int(matches[0])
