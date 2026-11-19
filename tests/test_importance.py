"""Tests de scripts/importance.py sur un petit jeu préparé synthétique (quelques secondes)."""
import json

import joblib
import lightgbm
import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier

from malware_family.dataset import load_dataset
from malware_family.ember_features import feature_groups, feature_names
from scripts import importance

FAMILIES = ["alpha", "beta", "gamma"]
# Deux colonnes par groupe ; seul « imports » distingue les familles.
NAMES = ["general_a", "general_b", "imports_a", "imports_b", "section_a", "section_b"]


def _write_dataset(path, n_train=240, n_test=90, seed=0):
    rng = np.random.default_rng(seed)
    path.mkdir()
    for split, n, start in (("train", n_train, 0), ("test", n_test, n_train)):
        y = rng.integers(0, len(FAMILIES), n)
        X = rng.normal(size=(n, len(NAMES))).astype(np.float32)
        X[:, 2] += 4 * y
        X[:, 3] += 4 * (y == 2)
        np.save(path / f"X_{split}.npy", X)
        np.save(path / f"y_{split}.npy", y)
        days = pd.Timestamp("2023-09-24") + pd.to_timedelta(np.arange(start, start + n), unit="D")
        pd.DataFrame({"sha256": [f"{i:064x}" for i in range(start, start + n)],
                      "first_seen": days.strftime("%Y-%m-%d"), "file_type": "Win32",
                      "family": np.array(FAMILIES)[y], "archive": f"Win32_{split}.zip",
                      "member": "semaine.jsonl", "line": np.arange(n)}).to_csv(path / f"meta_{split}.csv",
                                                                             index=False)
    (path / "families.txt").write_text("\n".join(FAMILIES) + "\n", encoding="utf-8")
    (path / "feature_names.txt").write_text("\n".join(NAMES) + "\n", encoding="utf-8")
    (path / "dataset_info.json").write_text(json.dumps({"created": "2026-01-01T00:00:00+00:00"}),
                                            encoding="utf-8")
    return path


@pytest.fixture
def trained(tmp_path):
    dataset = _write_dataset(tmp_path / "jeu")
    data = load_dataset(dataset)
    model = RandomForestClassifier(n_estimators=30, max_depth=6, random_state=0, n_jobs=1)
    model.fit(data.X_train, data.y_train)
    model_path = tmp_path / "models" / "best_model.joblib"
    model_path.parent.mkdir()
    joblib.dump(model, model_path)
    return dataset, data, model, model_path


def test_groups_follow_ember_feature_groups():
    groups = importance.feature_groups_of(feature_names())
    expected = feature_groups()
    assert list(groups) == list(expected)
    for name, columns in groups.items():
        np.testing.assert_array_equal(columns, np.arange(expected[name].start, expected[name].stop))


def test_permutation_drop_restores_data_and_finds_the_signal(trained):
    _, data, model, _ = trained
    X = np.array(data.X_test)
    before = X.copy()
    labels = list(range(len(FAMILIES)))
    useful, _ = importance.permutation_drop(model, X, data.y_test, [2, 3], labels, n_repeats=3)
    useless, family_drops = importance.permutation_drop(model, X, data.y_test, [0, 1], labels, n_repeats=3)
    np.testing.assert_array_equal(X, before)  # X remis en état
    assert useful.shape == (3,) and family_drops.shape == (3,)
    assert useful.mean() > 0.3 > abs(useless.mean())


def test_confusion_profile_measures_closeness():
    X = np.array([[0.0], [0.0], [1.0], [1.0], [0.9]])
    y_true = np.array([0, 0, 1, 1, 0])
    y_pred = np.array([0, 0, 1, 1, 1])  # le dernier « alpha » est classé « beta »
    assert importance.confused_pairs(y_true, y_pred, FAMILIES, min_count=1) == [("alpha", "beta", 1)]
    profile = importance.confusion_profile(X, y_true, y_pred, FAMILIES, "alpha", "beta", ["f"], ["f"])
    assert profile.n_confondus[0] == 1
    assert profile.rapprochement[0] == pytest.approx(0.9)


def test_main_writes_tables_and_figures(trained, tmp_path, capsys):
    dataset, data, model, model_path = trained
    results, figures = tmp_path / "results", tmp_path / "figures"
    importance.main(["--dataset", str(dataset), "--model", str(model_path), "--results-dir", str(results),
                     "--figures-dir", str(figures), "--n-repeats", "2", "--top", "4", "--pairs", "2",
                     "--ablation", "--ablation-trees", "10", "--shap-per-family", "0"])
    out = capsys.readouterr().out
    assert "Pas d'index des noms hachés" in out

    groups = pd.read_csv(results / "importances_groupes.csv")
    assert groups.group[0] == "imports"
    assert set(groups.group) == {"general", "imports", "section"}
    assert groups.mdi_sum.sum() == pytest.approx(1)
    assert {f"f1_drop_{family}" for family in FAMILIES} <= set(groups.columns)

    features = pd.read_csv(results / "importances.csv")
    assert len(features) == len(NAMES) and features.perm_f1_drop_mean.notna().sum() == 4
    assert features.feature[0] in ("imports_a", "imports_b")

    ablation = pd.read_csv(results / "ablation.csv")
    assert len(ablation) == 6
    scores = ablation.set_index(["group", "mode"]).test_f1_macro
    assert scores["imports", "seul"] > scores["general", "seul"]
    assert scores["imports", "sans"] < scores["general", "sans"]

    info = json.loads((results / "importance_info.json").read_text(encoding="utf-8"))
    assert info["n_test_rows"] == len(data.y_test) and not info["sampled"] and info["ablation"]
    assert (results / "confusions_features.csv").is_file()
    assert {path.name for path in figures.iterdir()} == {
        "C_importance_par_groupe.png", "C_top_features.png", "C_importance_groupes_par_famille.png",
        "C_ablation.png"}


def test_main_requires_a_model(trained, tmp_path):
    dataset = trained[0]
    with pytest.raises(SystemExit, match="scripts.train"):
        importance.main(["--dataset", str(dataset), "--model", str(tmp_path / "absent.joblib")])


def _lightgbm(data):
    model = lightgbm.LGBMClassifier(n_estimators=30, num_leaves=7, min_child_samples=5,
                                    importance_type="gain", random_state=0, verbose=-1)
    return model.fit(data.X_train, data.y_train)


def test_shap_of_lightgbm_adds_up_to_its_raw_score(trained):
    _, data, _, _ = trained
    model = _lightgbm(data)
    X = np.asarray(data.X_test[:20])
    raw = model.predict(X, raw_score=True)
    bias = model.predict(X, pred_contrib=True)[:, len(NAMES)::len(NAMES) + 1]
    for k in range(len(FAMILIES)):
        np.testing.assert_allclose(importance.shap_for_class(model, X, k).sum(axis=1) + bias[:, k],
                                   raw[:, k], rtol=1e-5, atol=1e-5)


@pytest.mark.parametrize("kind", ["lightgbm", "forest"])
def test_shap_by_family_finds_the_signal(trained, kind):
    _, data, forest, _ = trained
    if kind == "forest":
        pytest.importorskip("shap")
    model = _lightgbm(data) if kind == "lightgbm" else forest
    top, shares = importance.shap_by_family(model, np.asarray(data.X_test), data.y_test, NAMES, FAMILIES,
                                            per_family=10, top=2)
    assert list(shares.index) == FAMILIES and shares.columns[0] == "imports"
    np.testing.assert_allclose(shares.sum(axis=1), 100)
    assert (shares["imports"] > 50).all()  # seul « imports » distingue les familles
    assert len(top) == 2 * len(FAMILIES) and set(top.n_fichiers) == {10}
    assert set(top[top.rang == 1].group) == {"imports"}


def test_main_with_lightgbm_writes_shap_and_gain(trained, tmp_path, capsys):
    dataset, data, _, _ = trained
    model_path = tmp_path / "lgbm.joblib"
    joblib.dump(_lightgbm(data), model_path)
    results, figures = tmp_path / "results", tmp_path / "figures"
    importance.main(["--dataset", str(dataset), "--model", str(model_path), "--results-dir", str(results),
                     "--figures-dir", str(figures), "--n-repeats", "2", "--top", "3",
                     "--shap-per-family", "15"])
    info = json.loads((results / "importance_info.json").read_text(encoding="utf-8"))
    assert info["native_importance"] == "gain" and info["shap_per_family"] == 15
    groups = pd.read_csv(results / "importances_groupes.csv")
    assert groups.mdi_sum.sum() == pytest.approx(1)  # gain normalisé
    shares = pd.read_csv(results / "shap_groupes_par_famille.csv", index_col="famille")
    assert list(shares.index) == FAMILIES
    assert (figures / "C_shap_groupes_par_famille.png").is_file()
    assert "SHAP, indice principal" in capsys.readouterr().out


def test_main_with_histgradientboosting_uses_a_preselection_forest(trained, tmp_path, capsys):
    """HistGradientBoosting n'a pas de feature_importances_ : une petite forêt choisit les features
    à permuter, mais les baisses de F1 sont celles du vrai modèle."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    dataset, data, _, _ = trained
    model = HistGradientBoostingClassifier(max_iter=30, random_state=0).fit(data.X_train, data.y_train)
    model_path = tmp_path / "hgb.joblib"
    joblib.dump(model, model_path)
    results = tmp_path / "results"
    importance.main(["--dataset", str(dataset), "--model", str(model_path), "--results-dir", str(results),
                     "--figures-dir", str(tmp_path / "figures"), "--n-repeats", "2", "--top", "3",
                     "--shap-per-family", "0"])
    assert "petite forêt" in capsys.readouterr().out
    info = json.loads((results / "importance_info.json").read_text(encoding="utf-8"))
    assert info["native_importance"] == "MDI de présélection"
    features = pd.read_csv(results / "importances.csv")
    assert features.perm_f1_drop_mean.notna().sum() == 3
    assert features.feature[0] in ("imports_a", "imports_b")


def test_ablation_recale_les_colonnes_categorielles():
    """Les colonnes catégorielles de HistGradientBoosting sont des indices de toutes les colonnes :
    réentraîné sur un groupe, le modèle doit les retrouver à leur nouvelle place (ou ne plus en avoir)."""
    from types import SimpleNamespace

    from sklearn.ensemble import HistGradientBoostingClassifier
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 300)
    X = np.column_stack([y + rng.normal(scale=0.3, size=300), rng.normal(size=300),
                         (y + rng.integers(0, 2, 300)) % 4, rng.normal(size=300)]).astype(np.float32)
    data = SimpleNamespace(X_train=X[:200], y_train=y[:200], X_test=X[200:], y_test=y[200:],
                           families=FAMILIES)
    groups = {"a": np.array([0, 1]), "b": np.array([2, 3])}
    for categorical in ([2], [False, False, True, False]):
        model = HistGradientBoostingClassifier(max_iter=10, categorical_features=categorical, random_state=0)
        assert importance.restrict_categorical(clone(model), groups["b"]).get_params()[
            "categorical_features"] == [0]
        assert importance.restrict_categorical(clone(model), groups["a"]).get_params()[
            "categorical_features"] is None
        table = importance.ablation(model, data, groups)
        assert len(table) == 4 and table.test_f1_macro.notna().all()
