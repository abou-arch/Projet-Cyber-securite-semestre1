"""Tests de l'interface de démonstration (app/), sur un petit jeu synthétique, hors ligne."""
import json
import sys

import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier

from app import core
from malware_family.dataset import load_dataset
from test_evaluate import FAMILIES, _write_dataset

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Jeu préparé (2 568 colonnes), modèle et dossier de résultats, désignés par les variables
    d'environnement que l'interface lit."""
    data_dir = tmp_path / "jeu"
    _write_dataset(data_dir, 240, 80, seed=0)
    data = load_dataset(data_dir)
    model = RandomForestClassifier(n_estimators=15, max_depth=6, random_state=0, n_jobs=1)
    model.fit(np.asarray(data.X_train), data.y_train)
    model_path = tmp_path / "best_model.joblib"
    joblib.dump(model, model_path)
    results = tmp_path / "results"
    (results / "figures").mkdir(parents=True)
    (results / "metrics.json").write_text(json.dumps({
        "selected_model": "rf_test", "test_f1_macro": 0.8, "test_accuracy": 0.9,
        "test_f1_macro_without_small_families": None,
        "test_per_family": {f: {"precision": 0.9, "recall": 0.8, "f1-score": 0.85, "support": 20}
                            for f in FAMILIES}}), encoding="utf-8")
    monkeypatch.setenv("EMBER_DATASET", str(data_dir))
    monkeypatch.setenv("EMBER_MODEL", str(model_path))
    monkeypatch.setenv("EMBER_RESULTS", str(results))
    return data, model


# --- Lignes de features : seules des lignes JSON EMBER2024 sont acceptées ---

def test_example_lines_are_read():
    rows, errors = core.read_feature_lines(core.EXAMPLE.read_bytes())
    assert len(rows) == 44 and not errors
    assert core.vectorize_rows(rows).shape == (44, 2568)
    assert core.describe_row(rows[0], 1)["n°"] == 1


@pytest.mark.parametrize("content", [b"MZ\x90\x00\x03" + bytes(200), b"\x7fELF\x02\x01", b"%PDF-1.7\n",
                                     b"PK\x03\x04zip", b"abc\x00def", b"\xff\xfe\xfa invalide"])
def test_binary_files_are_refused(content):
    with pytest.raises(ValueError, match="exécutable"):
        core.read_feature_lines(content)


def test_too_big_and_invalid_inputs_are_refused():
    with pytest.raises(ValueError, match="trop gros"):
        core.read_feature_lines(b"{}" * (core.MAX_UPLOAD_BYTES // 2 + 1))
    with pytest.raises(ValueError, match="Aucune ligne"):
        core.read_feature_lines('{"pas": "des features"}\n[1, 2]\npas du json')


def test_single_object_list_and_bad_lines():
    line = core.EXAMPLE.read_text(encoding="utf-8").splitlines()[0]
    one = json.dumps(json.loads(line), indent=2)  # un objet sur plusieurs lignes
    assert len(core.read_feature_lines(one)[0]) == 1
    assert len(core.read_feature_lines("[" + line + "," + line + "]")[0]) == 2
    rows, errors = core.read_feature_lines(line + "\n{cassé\n" + line)
    assert len(rows) == 2 and len(errors) == 1 and errors[0].startswith("ligne 2")


# --- Prédiction, seuil, explication ---

def test_predict_decision_and_rejection(project):
    data, model = project
    proba = core.predict_proba(model, np.asarray(data.X_test), len(FAMILIES))
    assert proba.shape == (80, len(FAMILIES)) and np.allclose(proba.sum(axis=1), 1)
    d = core.decision(np.array([0.1, 0.6, 0.2, 0.1]), FAMILIES, threshold=0.5)
    assert d == {"indice": 1, "famille": "beta", "probabilité": 0.6, "inconnue": False}
    assert core.decision(np.array([0.3, 0.3, 0.2, 0.2]), FAMILIES, 0.5)["inconnue"]
    table = core.rejection_table(proba.max(axis=1), proba.argmax(axis=1) == data.y_test)
    assert table.couverture.iloc[0] == 1 and table.couverture.is_monotonic_decreasing


def test_explainer_names_the_features(project):
    pytest.importorskip("shap")
    data, model = project
    top = core.Explainer(model).top(np.asarray(data.X_test[0]), int(data.y_test[0]), data.feature_names, n=5)
    assert len(top) == 5 and set(top.sens) <= {"pousse vers", "éloigne de"}


def test_pick_and_find_test_rows(project):
    data, _ = project
    row = core.pick_test_row(data, "gamma", seed=0)
    assert data.families[int(data.y_test[row])] == "gamma"
    # Empreintes hexadécimales qui commencent toutes par 20 zéros.
    data.meta_test["sha256"] = ["0" * 20 + f"{i:044x}" for i in range(len(data.meta_test))]
    assert core.find_test_row(data, data.meta_test.sha256[5]) == 5
    with pytest.raises(ValueError, match="plus de caractères"):
        core.find_test_row(data, "0" * 10)
    with pytest.raises(ValueError, match="8 caractères"):
        core.find_test_row(data, "abc")


def test_missing_model_message(tmp_path, monkeypatch, project):
    monkeypatch.setenv("EMBER_MODEL", str(tmp_path / "absent.joblib"))
    with pytest.raises(FileNotFoundError, match="scripts.train"):
        core.load_resources()


# --- L'application Streamlit elle-même ---

@pytest.fixture
def keep_main_module():
    """AppTest remplace sys.modules["__main__"] par le script testé et ne le remet pas : les
    processus lancés ensuite par multiprocessing (spawn) réexécuteraient l'interface. On le remet."""
    main = sys.modules["__main__"]
    yield
    sys.modules["__main__"] = main


def test_every_page_runs(project, keep_main_module):
    app = streamlit_testing.AppTest.from_file(str(core.ROOT / "app" / "demo.py"), default_timeout=120)
    app.run()
    assert not app.exception
    assert any("aide au tri" in info.value for info in app.sidebar.info)  # limites rappelées partout

    app.button[0].click().run()  # page 1 : tirer un fichier
    assert not app.exception and app.metric[0].label == "Famille prédite"

    for page in ("Analyser une ligne de features", "Résultats du modèle", "Famille inconnue ?"):
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
    assert any("sur" in md.value and "inconnue" in md.value for md in app.markdown)

    app.sidebar.radio[0].set_value("Analyser une ligne de features").run()
    app.button[0].click().run()  # charger l'exemple
    assert not app.exception
    assert any("ne fait pas partie" in w.value for w in app.warning)
