"""Exporte les données de la démo statique (docs/, publiable sur GitHub Pages).

GitHub Pages ne sert que des fichiers statiques : ni Python, ni le modèle, ni les données (1 Go,
hors de git) n'y tournent. Ce script calcule donc à l'avance, avec le modèle final, ce que la
page montre, et l'écrit dans un petit fichier JSON :

- un échantillon de fichiers du test (``--per-family`` par famille) : vraie famille, probabilités
  de chaque famille et les features qui ont le plus pesé (SHAP), avec leurs vrais noms ;
- la courbe « famille inconnue » (part des fichiers auxquels le modèle répond et justesse, pour
  chaque seuil), calculée sur tout le test ;
- les 32 fichiers Win32 de ``tests/data/exemple_ember2024.jsonl``, de familles hors des 10 ;
- les scores (``results/metrics.json``) et l'importance des groupes de features.

Aucune donnée sensible : pas d'exécutable, seulement le début des empreintes (12 caractères),
qui sert d'identifiant.

Usage, depuis la racine du projet (après ``python -m scripts.train`` et, pour l'importance,
``python -m scripts.importance``) :

    python -m scripts.export_demo            # -> docs/data/demo.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):  # lancé par « python scripts/export_demo.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from tqdm import tqdm

from app import core

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "data" / "demo.json"
HASH_PREFIX = 12  # caractères de l'empreinte gardés comme identifiant


def _round(values, digits=4):
    return [round(float(v), digits) for v in values]


def sample_rows(y, n_families, per_family, seed):
    """Indices tirés au hasard, au plus ``per_family`` par famille, dans l'ordre du test."""
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(n_families):
        candidates = np.flatnonzero(y == k)
        if len(candidates):
            rows.extend(rng.choice(candidates, min(per_family, len(candidates)), replace=False).tolist())
    return sorted(rows)


def export(res, per_family=20, top=8, seed=0):
    """Contenu du fichier de la démo, sous forme de dictionnaire."""
    data, families = res.data, res.data.families
    X_test = np.asarray(data.X_test)
    proba = core.predict_proba(res.model, X_test, len(families))
    pmax, pred = proba.max(axis=1), proba.argmax(axis=1)
    correct = pred == data.y_test

    explainer = core.Explainer(res.model)
    samples = []
    for row in tqdm(sample_rows(data.y_test, len(families), per_family, seed), desc="Explications"):
        top_features = explainer.top(X_test[row], int(pred[row]), data.feature_names, res.index, n=top)
        meta = data.meta_test.iloc[row]
        samples.append({
            "id": int(row),
            "sha256": str(meta.sha256)[:HASH_PREFIX],
            "date": str(meta.first_seen)[:10],
            "famille": families[int(data.y_test[row])],
            "confiance": round(float(meta.family_confidence), 3) if "family_confidence" in meta else None,
            "proba": _round(proba[row]),
            "explication": [] if top_features is None else [
                {"feature": f, "contribution": round(float(c), 4)}
                for f, c in zip(top_features.feature, top_features.contribution)],
        })

    lines = core.read_feature_lines(core.EXAMPLE.read_bytes())[0]
    examples = [r for r in lines if r.get("file_type") == "Win32"]
    unknown_proba = core.predict_proba(res.model, core.vectorize_rows(examples), len(families))
    unknown = [{"famille": r.get("family") or "aucune", "proba": _round(p)}
               for r, p in zip(examples, unknown_proba)]

    rejection = core.rejection_table(pmax, correct)
    m = res.metrics or {}
    per_family_scores = m.get("test_per_family", {})
    groups_csv = res.results_dir / "importances_groupes.csv"
    groups = (pd.read_csv(groups_csv)[["group", "n_features", "perm_f1_drop_mean"]]
              .round(4).to_dict(orient="records") if groups_csv.is_file() else [])
    shap_csv = res.results_dir / "shap_groupes_par_famille.csv"
    shap_groups = (pd.read_csv(shap_csv, index_col=0).round(1).to_dict(orient="index")
                   if shap_csv.is_file() else {})

    return {
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "jeu": res.dataset_path.name,
        "modele": {"type": type(res.model).__name__, "nom": m.get("selected_model")},
        "familles": list(families),
        "n_train": int(len(data.y_train)),
        "n_test": int(len(data.y_test)),
        "scores": {key: (round(float(m[key]), 4) if m.get(key) is not None else None)
                   for key in ("test_f1_macro", "test_f1_macro_without_small_families", "test_accuracy",
                               "test_balanced_accuracy", "validation_f1_macro")},
        "par_famille": {f: {"f1": round(float(per_family_scores[f]["f1-score"]), 3),
                            "precision": round(float(per_family_scores[f]["precision"]), 3),
                            "rappel": round(float(per_family_scores[f]["recall"]), 3),
                            "fichiers": int(per_family_scores[f]["support"])}
                        for f in families if f in per_family_scores},
        "rejet": [{"seuil": r.seuil, "couverture": round(r.couverture, 4),
                   "justesse": None if np.isnan(r.justesse) else round(r.justesse, 4)}
                  for r in rejection.itertuples()],
        "echantillon": samples,
        "inconnues": unknown,
        "groupes": groups,
        "shap_groupes": shap_groups,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.export_demo",
                                     description="Données de la démo statique (docs/, GitHub Pages).")
    parser.add_argument("--dataset", type=Path, help="jeu préparé (défaut : find_dataset())")
    parser.add_argument("--model", type=Path, help="modèle (défaut : models/best_model.joblib)")
    parser.add_argument("--results-dir", type=Path, help="dossier des résultats (défaut : results/)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="fichier écrit (défaut : docs/data/demo.json)")
    parser.add_argument("--per-family", type=int, default=20,
                        help="fichiers du test par famille (défaut : 20)")
    parser.add_argument("--top", type=int, default=8, help="features expliquées par fichier (défaut : 8)")
    parser.add_argument("--seed", type=int, default=0, help="graine du tirage (défaut : 0)")
    args = parser.parse_args(argv)
    try:
        res = core.load_resources(args.dataset, args.model, args.results_dir)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error))
    content = export(res, args.per_family, args.top, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(content, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(content['echantillon'])} fichiers du test, {len(content['inconnues'])} de familles "
          f"inconnues -> {args.out} ({args.out.stat().st_size / 1e3:.0f} Ko)\n"
          "Publiez le dossier docs/ avec GitHub Pages (README, § 6.7).")


if __name__ == "__main__":
    main()
