"""Tests de scripts/train.py sur un petit jeu préparé synthétique (quelques secondes)."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score

from malware_family.dataset import load_dataset
from scripts import train


def _write_dataset(path, n_train=120, n_test=45, n_features=6, seed=0):
    """Jeu au format de malware_family.prepare : 3 familles, séparables par la première colonne."""
    rng = np.random.default_rng(seed)
    families = ["alpha", "beta", "gamma"]
    path.mkdir()
    for split, n, start in (("train", n_train, 0), ("test", n_test, n_train)):
        y = rng.integers(0, len(families), n)
        X = rng.normal(size=(n, n_features)).astype(np.float32)
        X[:, 0] += 5 * y
        np.save(path / f"X_{split}.npy", X)
        np.save(path / f"y_{split}.npy", y)
        days = pd.Timestamp("2023-09-24") + pd.to_timedelta(np.arange(start, start + n), unit="D")
        pd.DataFrame({"sha256": [f"{i:064x}" for i in range(start, start + n)],
                      "first_seen": days.strftime("%Y-%m-%d"), "file_type": "Win32",
                      "family": np.array(families)[y], "archive": f"Win32_{split}.zip",
                      "member": "semaine.jsonl", "line": np.arange(n)}).to_csv(path / f"meta_{split}.csv",
                                                                             index=False)
    (path / "families.txt").write_text("\n".join(families) + "\n", encoding="utf-8")
    (path / "feature_names.txt").write_text("\n".join(f"f{j}" for j in range(n_features)) + "\n",
                                            encoding="utf-8")
    (path / "dataset_info.json").write_text(json.dumps({"created": "2026-01-01T00:00:00+00:00"}),
                                            encoding="utf-8")
    return path


def test_train_selects_on_validation_and_writes_results(tmp_path):
    dataset = _write_dataset(tmp_path / "jeu")
    model_path, results = tmp_path / "models" / "best.joblib", tmp_path / "results"
    train.main(["--dataset", str(dataset), "--model", str(model_path), "--results-dir", str(results)])

    metrics = json.loads((results / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["n_samples"] == {"fit": 102, "validation": 18, "train": 120, "test": 45}
    assert [result["model"] for result in metrics["validation_results"]] == list(train.candidates())
    assert metrics["selected_model"] != "dummy"
    assert metrics["validation_f1_macro"] == max(result["f1_macro_validation"]
                                                 for result in metrics["validation_results"])
    assert metrics["selected_params"]["random_state"] == train.RANDOM_STATE

    data = load_dataset(dataset)
    predictions = pd.read_csv(results / "predictions_test.csv", dtype={"sha256": str})
    assert list(predictions.sha256) == list(data.meta_test.sha256)  # une ligne par fichier du test
    assert (predictions.famille_predite == np.array(data.families)[predictions.y_pred]).all()
    model = joblib.load(model_path)
    np.testing.assert_array_equal(predictions.y_pred, model.predict(data.X_test))
    np.testing.assert_allclose(predictions.proba_max, model.predict_proba(data.X_test).max(axis=1), atol=1e-4)
    assert metrics["test_f1_macro"] == pytest.approx(
        f1_score(predictions.y_true, predictions.y_pred, average="macro"))
    assert set(metrics["test_per_family"]) >= set(data.families)


def test_lightgbm_keeps_the_number_of_trees_found_by_early_stopping(tmp_path):
    dataset = _write_dataset(tmp_path / "jeu")
    model_path, results = tmp_path / "models" / "lgbm.joblib", tmp_path / "results"
    train.main(["--dataset", str(dataset), "--model", str(model_path), "--results-dir", str(results),
                "--candidates", "lightgbm"])

    metrics = json.loads((results / "metrics.json").read_text(encoding="utf-8"))
    assert [result["model"] for result in metrics["validation_results"]] == ["lightgbm"]
    n_trees = metrics["validation_results"][0]["final_params"]["n_estimators"]
    assert 1 <= n_trees < 1000  # arrêt anticipé sur un jeu aussi simple
    model = joblib.load(model_path)
    assert model.n_estimators == n_trees == metrics["selected_params"]["n_estimators"]
    assert model.get_params()["importance_type"] == "gain"
    assert metrics["small_families"] == {"min_test_support": train.SMALL_FAMILY,
                                         "families": ["alpha", "beta", "gamma"]}  # moins de 30 fichiers


def test_f1_macro_without_small_families():
    y_true = np.array([0] * 40 + [1] * 40 + [2] * 3)
    y_pred = np.array([0] * 40 + [1] * 40 + [0] * 3)  # la petite famille 2 est toujours ratée
    without_small, small = train.f1_macro_without_small(y_true, y_pred, 3)
    assert small == [2]
    assert without_small == pytest.approx(f1_score(y_true, y_pred, labels=[0, 1], average="macro"))
    assert without_small > f1_score(y_true, y_pred, average="macro")


def test_categorical_columns_for_histgradientboosting():
    X = np.zeros((4, 8), dtype=np.float32)
    X[:, 2] = [0, 3, 3, 77]       # codes entiers de 0 à 254 : catégorielle
    X[:, 3] = [0, 255, 1, 2]      # 255 dépasse la limite : reste numérique
    X[:, 5] = [0.5, 1, 2, 3]      # pas un entier : reste numérique
    assert train.usable_categorical(X, columns=[2, 3, 5, 40]) == [2]  # 40 : colonne absente

    models = train.candidates(categorical=[2])
    assert {name for name in models if name.startswith("hgb_")} == {"hgb_lr0.1_leaves31",
                                                                    "hgb_lr0.05_leaves63"}
    for name in ("hgb_lr0.1_leaves31", "hgb_lr0.05_leaves63"):
        params = models[name].get_params()
        assert params["categorical_features"] == [2]
        assert params["class_weight"] is None  # avec des poids, scikit-learn 1.9 est des heures plus lent
    assert train.candidates()["hgb_lr0.1_leaves31"].get_params()["categorical_features"] is None
