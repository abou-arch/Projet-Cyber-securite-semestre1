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
