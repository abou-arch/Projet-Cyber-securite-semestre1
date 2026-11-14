"""Tests de scripts/evaluate.py (phase 3 du rôle B) sur un petit jeu synthétique, hors ligne."""
import json

import joblib
import matplotlib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

matplotlib.use("Agg")  # pas d'écran pendant les tests

from malware_family.ember_features import N_FEATURES, feature_groups, feature_names  # noqa: E402
from scripts import evaluate  # noqa: E402

FAMILIES = ["alpha", "beta", "gamma", "delta"]


def _write_dataset(path, n_train, n_test, seed, min_confidence=None):
    """Jeu au format de malware_family.prepare : quelques colonnes séparent les familles."""
    rng = np.random.default_rng(seed)
    path.mkdir(parents=True)
    start = {"train": pd.Timestamp("2023-09-25"), "test": pd.Timestamp("2024-10-01")}
    for split, n in (("train", n_train), ("test", n_test)):
        y = rng.integers(0, len(FAMILIES), n)
        X = rng.random((n, N_FEATURES), dtype=np.float32)
        X[:, 0] += y              # general : très informatif
        X[:, 300] += 0.5 * y      # histogram : un peu informatif
        np.save(path / f"X_{split}.npy", X)
        np.save(path / f"y_{split}.npy", y)
        days = np.sort(rng.integers(0, 70, n))  # lignes triées par date, environ 10 semaines
        pd.DataFrame({
            "sha256": [f"{seed:02x}{split}{i:055x}" for i in range(n)],  # uniques
            "first_seen": [(start[split] + pd.Timedelta(days=int(d))).strftime("%Y-%m-%d") for d in days],
            "file_type": "Win32", "family": [FAMILIES[i] for i in y],
            "family_confidence": rng.random(n), "y": y,
        }).to_csv(path / f"meta_{split}.csv", index=False)
    (path / "families.txt").write_text("\n".join(FAMILIES) + "\n", encoding="utf-8")
    (path / "feature_names.txt").write_text("\n".join(feature_names()) + "\n", encoding="utf-8")
    (path / "dataset_info.json").write_text(json.dumps(
        {"source": "synthétique", "created": "2026-11-13", "min_confidence": min_confidence}),
        encoding="utf-8")


@pytest.fixture
def project(tmp_path):
    data_dir, variant_dir = tmp_path / "data", tmp_path / "data_conf05"
    _write_dataset(data_dir, 240, 160, seed=0)
    _write_dataset(variant_dir, 180, 120, seed=1, min_confidence=0.5)
    model = RandomForestClassifier(n_estimators=10, random_state=42, n_jobs=1)
    from malware_family.dataset import load_dataset
    data = load_dataset(data_dir)
    model.fit(data.X_train, data.y_train)
    model_path = tmp_path / "models" / "best_model.joblib"
    model_path.parent.mkdir()
    joblib.dump(model, model_path)
    return tmp_path, data_dir, variant_dir, model_path


def test_all_steps_write_results_and_figures(project):
    tmp_path, data_dir, variant_dir, model_path = project
    results = tmp_path / "results"
    evaluate.main(["--data-dir", str(data_dir), "--variante-dir", str(variant_dir),
                   "--modele", str(model_path), "--results-dir", str(results),
                   "--random-states", "0", "1", "2", "--top-groupes", "1", "2", "--top-features", "20",
                   "--groupes", "general", "header"])

    content = json.loads((results / "evaluation.json").read_text(encoding="utf-8"))
    assert set(evaluate.STEPS) <= set(content)
    assert content["contexte"]["n_test"] == 160
    for name in ("matrice_confusion", "f1_par_famille_effectifs", "score_par_semaine",
                 "bruit_etiquettes", "modele_reduit", "rejet_couverture"):
        assert (results / "figures" / f"B_{name}.png").read_bytes().startswith(b"\x89PNG")

    f1 = pd.read_csv(results / "f1_par_famille.csv")
    assert list(f1.famille) == FAMILIES and f1.n_train.sum() == 240

    weeks = pd.read_csv(results / "score_par_semaine.csv")
    assert weeks.n.sum() == 160 and weeks.f1_macro.between(0, 1).all()

    stability = content["stabilite"]["resume"]["f1_macro"]
    assert len(content["stabilite"]["par_graine"]) == 3 and stability["ecart_type"] >= 0

    noise = content["bruit"]
    assert noise["familles_identiques"] and "variante_sur_test_base" in noise

    reduced = pd.read_csv(results / "modele_reduit.csv")
    assert reduced.modele.iloc[0] == "complet" and reduced.n_features.iloc[0] == N_FEATURES
    assert "groupes : general+header" in set(reduced.modele)
    assert (reduced.n_features.iloc[1:] < N_FEATURES).all()
    # Sans les fichiers de C, le classement vient de la MDI du modèle (somme par groupe).
    assert "MDI" in content["reduit"]["source_importance"]
    model = joblib.load(model_path)
    by_group = {g: model.feature_importances_[s].sum() for g, s in feature_groups().items()}
    top1 = reduced.loc[reduced.modele.str.startswith("top 1 groupe"), "modele"].iloc[0]
    assert top1.endswith(": " + max(by_group, key=by_group.get))
    # Les 20 features les plus importantes contiennent les colonnes informatives.
    assert reduced.loc[reduced.modele == "top 20 features", "f1_macro"].iloc[0] > 0.8

    rejection = pd.read_csv(results / "rejet.csv")
    assert rejection.couverture.iloc[0] == 1.0 and rejection.couverture.is_monotonic_decreasing

    predictions = pd.read_csv(results / "predictions_test_proba.csv")
    assert len(predictions) == 160 and predictions.proba_max.between(0, 1).all()


def test_uses_importance_from_role_c_when_available(project):
    tmp_path, data_dir, _, model_path = project
    results = tmp_path / "results"
    results.mkdir()
    pd.DataFrame({"group": ["histogram", "general", "header"],
                  "perm_f1_drop_mean": [0.3, 0.2, 0.1]}).to_csv(results / "importances_groupes.csv",
                                                               index=False)
    evaluate.main(["--data-dir", str(data_dir), "--modele", str(model_path),
                   "--results-dir", str(results), "--etapes", "reduit",
                   "--top-groupes", "1", "--top-features"])
    content = json.loads((results / "evaluation.json").read_text(encoding="utf-8"))
    assert content["reduit"]["source_importance"].startswith("C")
    assert content["reduit"]["resultats"][1]["modele"] == "top 1 groupe(s) : histogram"
    assert content["reduit"]["resultats"][1]["n_features"] == 256


def test_missing_variant_is_reported_not_fatal(project, capsys):
    tmp_path, data_dir, _, model_path = project
    results = tmp_path / "results"
    evaluate.main(["--data-dir", str(data_dir), "--modele", str(model_path),
                   "--variante-dir", str(tmp_path / "absente"), "--results-dir", str(results),
                   "--etapes", "bruit"])
    content = json.loads((results / "evaluation.json").read_text(encoding="utf-8"))
    assert content["bruit"]["statut"] == "variante absente"
    assert "--min-confidence 0.5" in capsys.readouterr().out


def test_missing_model_gives_clear_message(tmp_path):
    with pytest.raises(SystemExit, match="optimize.py"):
        evaluate.main(["--modele", str(tmp_path / "rien.joblib"), "--results-dir", str(tmp_path)])
