"""Tests de scripts/export_demo.py : données de la démo statique (docs/, GitHub Pages)."""
import json

from scripts import export_demo
from test_demo import FAMILIES, project  # noqa: F401  (fixture : jeu, modèle et résultats synthétiques)


def test_export_writes_a_small_self_contained_file(project, tmp_path):  # noqa: F811
    out = tmp_path / "docs" / "data" / "demo.json"
    export_demo.main(["--out", str(out), "--per-family", "3", "--top", "4"])
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["familles"] == FAMILIES and data["n_test"] == 80
    assert len(data["echantillon"]) == 3 * len(FAMILIES)
    for sample in data["echantillon"]:
        # identifiant raccourci, jamais l'empreinte entière
        assert len(sample["sha256"]) == export_demo.HASH_PREFIX
        assert len(sample["proba"]) == len(FAMILIES) and abs(sum(sample["proba"]) - 1) < 1e-3
        assert sample["famille"] in FAMILIES
        assert len(sample["explication"]) in (0, 4)
    assert len(data["inconnues"]) == 32  # fichiers Win32 de l'exemple, familles hors des 10
    assert data["rejet"][0]["seuil"] == 0 and data["rejet"][0]["couverture"] == 1
    assert data["scores"]["test_f1_macro"] == 0.8
    assert out.stat().st_size < 200_000


def test_sample_rows_respects_the_cap():
    import numpy as np
    y = np.array([0] * 10 + [1] * 2 + [2] * 5)
    rows = export_demo.sample_rows(y, 3, 3, seed=0)
    assert rows == sorted(rows) and len(rows) == 3 + 2 + 3
