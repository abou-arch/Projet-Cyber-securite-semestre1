"""Modèle final du rôle B : choix sur une validation temporelle, puis une seule évaluation sur le test.

Reprend le protocole et les paramètres du premier modèle de B (forêt aléatoire de 300 arbres,
``class_weight="balanced_subsample"``, ``random_state=42``), cette fois sur le jeu dédoublonné :

- validation : les 15 % de lignes les plus récentes de X_train (lignes triées par date) ;
- candidats : DummyClassifier (plancher à battre) et deux forêts aléatoires ;
- le meilleur F1 macro de validation est réentraîné sur tout le train, puis évalué sur le test.

Usage, depuis la racine du projet :

    python -m scripts.train                       # jeu trouvé par find_dataset()
    python -m scripts.train --dataset C:\\ember2024\\processed\\Win32_top10_conf05 --results-dir results/conf05

Écrit le modèle dans ``models/best_model.joblib`` (hors de git), les scores dans
``results/metrics.json`` et les prédictions du test dans ``results/predictions_test.csv``
(une ligne par fichier, avec la probabilité de la famille prédite).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # lancé par « python scripts/train.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score

from malware_family.dataset import find_dataset, load_dataset

ROOT = Path(__file__).resolve().parents[1]
VALIDATION_FRACTION = 0.15
RANDOM_STATE = 42


def candidates(random_state=RANDOM_STATE):
    """Modèles comparés sur la validation, avec les paramètres du premier modèle de B."""
    forest = dict(max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1,
                  random_state=random_state)
    return {
        "dummy": DummyClassifier(strategy="most_frequent"),
        "rf_200_depth20": RandomForestClassifier(n_estimators=200, max_depth=20, **forest),
        "rf_300_depth_none": RandomForestClassifier(n_estimators=300, max_depth=None, **forest),
    }


def scores(y_true, y_pred):
    """F1 macro (métrique principale : familles de tailles différentes), exactitude et exactitude équilibrée."""
    return {"f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
            "accuracy": accuracy_score(y_true, y_pred),
            "balanced_accuracy": balanced_accuracy_score(y_true, y_pred)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.train",
                                     description="Choisit un modèle sur la validation temporelle, "
                                                 "le réentraîne sur tout le train et l'évalue sur le test.")
    parser.add_argument("--dataset", type=Path,
                        help="dossier créé par malware_family.prepare (défaut : find_dataset())")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "best_model.joblib",
                        help="fichier du modèle final (défaut : models/best_model.joblib)")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results",
                        help="dossier de metrics.json et predictions_test.csv (défaut : results/)")
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE,
                        help=f"graine des forêts (défaut : {RANDOM_STATE})")
    args = parser.parse_args(argv)

    path = args.dataset.expanduser() if args.dataset else find_dataset(ROOT)
    try:
        data = load_dataset(path)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error))
    if not data.meta_train.first_seen.is_monotonic_increasing:
        raise SystemExit(f"{path} : les lignes du train ne sont pas triées par date.")

    n_train = len(data.y_train)
    cut = n_train - max(1, round(n_train * VALIDATION_FRACTION))
    X_fit, y_fit = data.X_train[:cut], data.y_train[:cut]
    X_val, y_val = data.X_train[cut:], data.y_train[cut:]
    print(f"Jeu : {path}\n  entraînement {cut} lignes, validation {n_train - cut} lignes "
          f"(à partir du {data.meta_train.first_seen.iloc[cut]}), test {len(data.y_test)} lignes")

    validation_results = []
    for name, model in candidates(args.random_state).items():
        start = time.perf_counter()
        model.fit(X_fit, y_fit)
        duration = time.perf_counter() - start
        result = scores(y_val, model.predict(X_val))
        validation_results.append({"model": name,
                                   **{f"{metric}_validation": value for metric, value in result.items()},
                                   "duration_seconds": round(duration, 2)})
        print(f"  {name:<20} F1 macro {result['f1_macro']:.4f}  exactitude {result['accuracy']:.4f}  "
              f"({duration:.0f} s)")
        del model
    best = max(validation_results, key=lambda result: result["f1_macro_validation"])

    # Le modèle choisi est réentraîné sur tout le train, puis évalué une seule fois sur le test.
    model = candidates(args.random_state)[best["model"]]
    start = time.perf_counter()
    model.fit(data.X_train, data.y_train)
    training_seconds = time.perf_counter() - start
    proba = model.predict_proba(data.X_test)
    y_pred = model.classes_[proba.argmax(axis=1)]
    test = scores(data.y_test, y_pred)
    print(f"Modèle retenu : {best['model']} (réentraîné en {training_seconds:.0f} s)\n"
          f"  test : F1 macro {test['f1_macro']:.4f}  exactitude {test['accuracy']:.4f}  "
          f"exactitude équilibrée {test['balanced_accuracy']:.4f}")

    args.model.parent.mkdir(parents=True, exist_ok=True)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model)
    families = np.array(data.families)
    pd.DataFrame({"sha256": data.meta_test.sha256, "y_true": data.y_test, "y_pred": y_pred,
                  "famille_reelle": families[data.y_test], "famille_predite": families[y_pred],
                  "proba_max": proba.max(axis=1).round(4)}).to_csv(
        args.results_dir / "predictions_test.csv", index=False)
    labels = list(range(len(families)))
    metrics = {
        "dataset": str(path),
        "dataset_created": data.info["created"],
        "n_samples": {"fit": cut, "validation": n_train - cut, "train": n_train, "test": len(data.y_test)},
        "selected_model": best["model"],
        "selected_params": model.get_params(),
        "validation_f1_macro": best["f1_macro_validation"],
        **{f"test_{metric}": value for metric, value in test.items()},
        "final_training_seconds": round(training_seconds, 2),
        "sklearn_version": sklearn.__version__,
        "validation_results": validation_results,
        "test_per_family": classification_report(data.y_test, y_pred, labels=labels, target_names=families,
                                                 output_dict=True, zero_division=0),
        "families": data.families,
    }
    (args.results_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=lambda value: value.item()) + "\n",
        encoding="utf-8")
    print(f"Écrits : {args.model}, {args.results_dir / 'metrics.json'}, "
          f"{args.results_dir / 'predictions_test.csv'}")


if __name__ == "__main__":
    main()
