"""Modèle final du rôle B : choix sur une validation temporelle, puis une seule évaluation sur le test.

Reprend le protocole et les paramètres du premier modèle de B (forêt aléatoire de 300 arbres,
``class_weight="balanced_subsample"``, ``random_state=42``), cette fois sur le jeu dédoublonné :

- validation : les 15 % de lignes les plus récentes de X_train (lignes triées par date) ;
- candidats : DummyClassifier (plancher à battre), deux forêts aléatoires et LightGBM (paramètres
  de Kenneth) ; LightGBM s'arrête quand sa perte de validation ne baisse plus (arrêt anticipé),
  et garde ce nombre d'arbres pour la suite ;
- le meilleur F1 macro de validation est réentraîné sur tout le train, puis évalué sur le test.

Le F1 macro donne le même poids à chaque famille, même à sinowal (9 fichiers du test) : un seul
fichier de plus ou de moins le fait bouger de 0,01 à 0,03. ``metrics.json`` donne donc aussi le F1
macro sans les familles de moins de 30 fichiers dans le test.

Usage, depuis la racine du projet :

    python -m scripts.train                       # jeu trouvé par find_dataset()
    python -m scripts.train --dataset C:\\ember2024\\processed\\Win32_top10_conf05 --results-dir results/conf05
    python -m scripts.train --candidates lightgbm --model models/lightgbm.joblib \
        --results-dir results/lightgbm

Écrit le modèle dans ``models/best_model.joblib`` (hors de git), les scores dans
``results/metrics.json`` et les prédictions du test dans ``results/predictions_test.csv``
(une ligne par fichier, avec la probabilité de la famille prédite).
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # lancé par « python scripts/train.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import lightgbm
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
EARLY_STOPPING_ROUNDS = 50  # LightGBM s'arrête après 50 itérations sans progrès en validation
SMALL_FAMILY = 30           # familles de moins de 30 fichiers du test : F1 trop instable


def candidates(random_state=RANDOM_STATE):
    """Modèles comparés sur la validation : paramètres du premier modèle de B, et LightGBM avec ceux
    de Kenneth (``importance_type="gain"`` : feature_importances_ donne le gain de chaque feature)."""
    forest = dict(max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1,
                  random_state=random_state)
    return {
        "dummy": DummyClassifier(strategy="most_frequent"),
        "rf_200_depth20": RandomForestClassifier(n_estimators=200, max_depth=20, **forest),
        "rf_300_depth_none": RandomForestClassifier(n_estimators=300, max_depth=None, **forest),
        "lightgbm": lightgbm.LGBMClassifier(
            objective="multiclass", n_estimators=1000, learning_rate=0.1, num_leaves=63,
            colsample_bytree=0.5, subsample=0.8, subsample_freq=1, importance_type="gain",
            n_jobs=-1, random_state=random_state, verbose=-1),
    }


def fit_on_validation(model, X_fit, y_fit, X_val, y_val):
    """Entraîne ``model`` pour la sélection ; renvoie les paramètres à garder pour le modèle final.

    LightGBM s'arrête quand la perte de validation ne baisse plus : le nombre d'arbres atteint
    devient son ``n_estimators`` pour le réentraînement sur tout le train."""
    if isinstance(model, lightgbm.LGBMClassifier):
        # eval_X / eval_y depuis LightGBM 4.7, eval_set avant (encore accepté, mais déconseillé).
        validation = ({"eval_X": X_val, "eval_y": y_val}
                      if "eval_X" in inspect.signature(model.fit).parameters else {"eval_set": [(X_val, y_val)]})
        model.fit(X_fit, y_fit, **validation,
                  callbacks=[lightgbm.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)])
        return {"n_estimators": int(model.best_iteration_ or model.n_estimators)}
    model.fit(X_fit, y_fit)
    return {}


def scores(y_true, y_pred):
    """F1 macro (métrique principale : familles de tailles différentes), exactitude et exactitude équilibrée."""
    return {"f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
            "accuracy": accuracy_score(y_true, y_pred),
            "balanced_accuracy": balanced_accuracy_score(y_true, y_pred)}


def f1_macro_without_small(y_true, y_pred, n_families, min_support=SMALL_FAMILY):
    """F1 macro sur les seules familles d'au moins ``min_support`` fichiers dans ``y_true``,
    et la liste des indices de familles écartées."""
    support = np.bincount(y_true, minlength=n_families)
    kept = [k for k in range(n_families) if support[k] >= min_support]
    small = [k for k in range(n_families) if support[k] < min_support]
    per_family = f1_score(y_true, y_pred, labels=list(range(n_families)), average=None,
                          zero_division=0)
    return (float(per_family[kept].mean()) if kept else float("nan")), small


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
                        help=f"graine des modèles (défaut : {RANDOM_STATE})")
    parser.add_argument("--candidates", nargs="+", choices=list(candidates()), metavar="modele",
                        help="modèles comparés (défaut : tous) : " + ", ".join(candidates()))
    args = parser.parse_args(argv)
    names = args.candidates or list(candidates())

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
    for name in names:
        model = candidates(args.random_state)[name]
        start = time.perf_counter()
        final_params = fit_on_validation(model, X_fit, y_fit, X_val, y_val)
        duration = time.perf_counter() - start
        result = scores(y_val, model.predict(X_val))
        validation_results.append({"model": name,
                                   **{f"{metric}_validation": value for metric, value in result.items()},
                                   "final_params": final_params, "duration_seconds": round(duration, 2)})
        extra = "".join(f", {key} = {value}" for key, value in final_params.items())
        print(f"  {name:<20} F1 macro {result['f1_macro']:.4f}  exactitude {result['accuracy']:.4f}  "
              f"({duration:.0f} s{extra})")
        del model
    best = max(validation_results, key=lambda result: result["f1_macro_validation"])

    # Le modèle choisi est réentraîné sur tout le train, puis évalué une seule fois sur le test.
    model = candidates(args.random_state)[best["model"]].set_params(**best["final_params"])
    start = time.perf_counter()
    model.fit(data.X_train, data.y_train)
    training_seconds = time.perf_counter() - start
    proba = model.predict_proba(data.X_test)
    y_pred = model.classes_[proba.argmax(axis=1)]
    test = scores(data.y_test, y_pred)
    without_small, small = f1_macro_without_small(data.y_test, y_pred, len(data.families))
    small_names = [data.families[k] for k in small]
    print(f"Modèle retenu : {best['model']} (réentraîné en {training_seconds:.0f} s)\n"
          f"  test : F1 macro {test['f1_macro']:.4f}  exactitude {test['accuracy']:.4f}  "
          f"exactitude équilibrée {test['balanced_accuracy']:.4f}\n"
          f"  F1 macro sans les familles de moins de {SMALL_FAMILY} fichiers du test "
          f"({', '.join(small_names) or 'aucune'}) : {without_small:.4f}")

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
        "test_f1_macro_without_small_families": None if math.isnan(without_small) else without_small,
        "small_families": {"min_test_support": SMALL_FAMILY, "families": small_names},
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
