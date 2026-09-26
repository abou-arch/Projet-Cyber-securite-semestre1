import json
from pathlib import Path

import numpy as np
import pytest

from malware_family.ember_features import (FEATURE_GROUPS, N_FEATURES, feature_groups,
                                           feature_names, vectorize)
from synthetic_ember import make_samples

REFERENCE = Path(__file__).parent / "data" / "ember_v2_reference.json"


def test_matches_official_ember_implementation():
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
    assert N_FEATURES == 2381
    assert len(names) == len(set(names)) == N_FEATURES
    for group, part in feature_groups().items():
        assert part.stop - part.start == FEATURE_GROUPS[group]
        assert all(name.startswith(group + "_") for name in names[part])


def test_vectors_are_finite_float32():
    X = np.stack([vectorize(sample) for sample in make_samples(200, seed=1)])
    assert X.shape == (200, N_FEATURES)
    assert X.dtype == np.float32
    assert np.isfinite(X).all()


def test_entry_section_name_is_hashed_character_by_character():
    # Comportement d'EMBER v2 : ".text" et son anagramme "txet." donnent le même vecteur.
    sample = make_samples(1, seed=2)[0]
    columns = [i for i, name in enumerate(feature_names()) if name.startswith("section_entry_name_")]
    vectors = []
    for entry in (".text", "txet."):
        sample["section"] = {"entry": entry, "sections": []}
        vectors.append(vectorize(sample)[columns])
    assert len(columns) == 50 and vectors[0].any()
    np.testing.assert_array_equal(vectors[0], vectors[1])


@pytest.mark.parametrize("group", ["histogram", "byteentropy"])
def test_empty_histogram_gives_zeros_instead_of_nan(group):
    sample = make_samples(1, seed=3)[0]
    sample[group] = [0] * 256
    assert not vectorize(sample)[feature_groups()[group]].any()
