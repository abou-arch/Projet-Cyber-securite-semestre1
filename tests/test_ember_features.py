import json
from pathlib import Path

import numpy as np
import pytest

from malware_family.ember_features import (CATEGORICAL_FEATURES, FEATURE_GROUPS, N_FEATURES,
                                           feature_groups, feature_names, vectorize)
from synthetic_ember import make_samples

REFERENCE = Path(__file__).parent / "data" / "ember2024_reference.json"
PE_GROUPS = ["header", "section", "imports", "exports", "datadirectories", "richheader",
             "authenticode", "pefilewarnings"]


def test_matches_official_thrember_implementation():
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    for sample in reference["samples"]:
        expected = np.zeros(N_FEATURES, dtype=np.float32)
        for index, value in sample["expected_nonzero"]:
            expected[index] = value
        vector = vectorize(sample["raw"])
        wrong_groups = [name for name, part in feature_groups().items()
                        if not np.array_equal(vector[part], expected[part])]
        assert not wrong_groups, f"{sample['raw']['sha256']} : groupes différents {wrong_groups}"


def test_dimensions_and_feature_names():
    names = feature_names()
    assert N_FEATURES == 2568
    assert len(names) == len(set(names)) == N_FEATURES
    for group, part in feature_groups().items():
        assert part.stop - part.start == FEATURE_GROUPS[group]
        assert all(name.startswith(group + "_") for name in names[part])
    # Mêmes colonnes catégorielles que les modèles officiels d'EMBER2024.
    assert CATEGORICAL_FEATURES == [2, 3, 4, 5, 6, 701, 702]


def test_vectors_are_finite_float32():
    X = np.stack([vectorize(sample) for sample in make_samples(200, seed=1)])
    assert X.shape == (200, N_FEATURES)
    assert X.dtype == np.float32
    assert np.isfinite(X).all()


def test_non_pe_file_has_empty_pe_groups():
    sample = next(s for s in make_samples(300, seed=2) if not s["header"])
    vector = vectorize(sample)
    assert vector[feature_groups()["histogram"]].any()
    for group in PE_GROUPS:
        assert not vector[feature_groups()[group]].any(), group


@pytest.mark.parametrize("group", ["histogram", "byteentropy"])
def test_empty_histogram_gives_zeros_instead_of_nan(group):
    sample = make_samples(1, seed=3)[0]
    sample[group] = [0] * 256
    assert not vectorize(sample)[feature_groups()[group]].any()


def test_real_ember2024_examples_are_vectorized():
    """44 vraies lignes d'EMBER2024 (tests/data/exemple_ember2024.jsonl), de 5 types de fichiers :
    toutes donnent un vecteur fini de la bonne taille. Ce fichier sert aussi d'exemple pour la démo."""
    path = Path(__file__).parent / "data" / "exemple_ember2024.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 44
    assert {row["file_type"] for row in rows} == {"Win32", "Win64", "Dot_Net", "ELF", "PDF"}
    X = np.array([vectorize(row) for row in rows])
    assert X.shape == (44, N_FEATURES) and np.isfinite(X).all()
