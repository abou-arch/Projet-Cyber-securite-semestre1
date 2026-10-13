"""Tests de scripts/hash_lookup.py : noms réels derrière les colonnes hachées (hors ligne)."""
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from malware_family import prepare
from malware_family.ember_features import N_FEATURES, feature_names, vectorize
from scripts import hash_lookup
from synthetic_ember import make_samples

REFERENCE = Path(__file__).parent / "data" / "ember2024_reference.json"


def test_hashed_columns_match_feature_names():
    names = feature_names()
    ours = [hash_lookup.column_name(prefix, i)
            for prefix, group in hash_lookup.HASHED_GROUPS.items() for i in range(group.n_features)]
    assert ours == [name for name in names if "_hash" in name]  # mêmes colonnes, même ordre
    assert all(hash_lookup.parse_column(name) is not None for name in ours)
    for name in ("general_size", "imports_library_hash256", "imports_library_hash7", "section_hash01"):
        assert hash_lookup.parse_column(name) is None


def _rebuild_hashed_columns(raw):
    """Valeurs des colonnes hachées recalculées avec bucket() et les textes de HASHED_GROUPS."""
    names = {name: j for j, name in enumerate(feature_names())}
    vector = np.zeros(N_FEATURES, dtype=np.float64)
    for prefix, group in hash_lookup.HASHED_GROUPS.items():
        for text, value in group.values(raw):
            index, sign = hash_lookup.bucket(text, group.n_features)
            column = names[hash_lookup.column_name(prefix, index)]
            vector[column] += value * (sign if group.alternate_sign else 1)
    return vector.astype(np.float32)


def test_bucket_reproduces_ember_vectorization_exactly():
    reference = [sample["raw"] for sample in json.loads(REFERENCE.read_text(encoding="utf-8"))["samples"]]
    hashed = np.array(["_hash" in name for name in feature_names()])
    for raw in reference + make_samples(300, seed=5):
        np.testing.assert_array_equal(_rebuild_hashed_columns(raw)[hashed], vectorize(raw)[hashed])


def test_column_for_normalizes_library_names():
    column, sign = hash_lookup.column_for("imports_function", "KERNEL32.dll:VirtualAlloc")
    assert (column, sign) == hash_lookup.column_for("imports_function", "kernel32.dll:VirtualAlloc")
    assert column != hash_lookup.column_for("imports_function", "kernel32.dll:virtualalloc")[0]
    assert sign == 1  # pas de signe alterné pour les imports
    sample = {**make_samples(1, seed=6)[0], "imports": {"KERNEL32.dll": ["VirtualAlloc"]}}
    assert vectorize(sample)[feature_names().index(column)] == 1
    with pytest.raises(ValueError, match="bibliotheque.dll:Fonction"):
        hash_lookup.normalize("imports_function", "VirtualAlloc")


def _write_archives(directory, samples):
    """Archives Win32_train.zip et Win32_test.zip ; chaque ligne y figure deux fois, comme dans EMBER2024."""
    directory.mkdir()
    cut = int(len(samples) * 0.8)
    for split, part in (("train", samples[:cut]), ("test", samples[cut:])):
        with zipfile.ZipFile(directory / f"Win32_{split}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("all.jsonl", "".join(2 * (json.dumps(s) + "\n") for s in part))
    return {"train": samples[:cut], "test": samples[cut:]}


@pytest.mark.parametrize("jobs", [1, 2])
def test_index_lists_every_name_of_the_prepared_dataset(tmp_path, jobs, capsys):
    splits = _write_archives(tmp_path / "raw", make_samples(250, seed=7))
    dataset = tmp_path / "processed"
    prepare.main(["--data-dir", str(tmp_path / "raw"), "--out-dir", str(dataset), "--top-families", "3",
                  "--max-per-family", "30", "--jobs", "1"])
    hash_lookup.main(["index", str(dataset), "--jobs", str(jobs)])
    meta = pd.read_csv(dataset / "meta_train.csv", dtype=str)
    assert f"{len(meta)} échantillons (train)" in capsys.readouterr().out  # doublons comptés une fois

    kept = [s for s in splits["train"] if s["sha256"] in set(meta.sha256)]  # échantillons de X_train
    expected = Counter()
    for sample in kept:
        for prefix, texts in hash_lookup.hashed_texts(sample).items():
            expected.update((hash_lookup.column_for(prefix, text)[0], text, sample["family"])
                            for text in texts)

    index = hash_lookup.load_index(dataset)
    families = (dataset / "families.txt").read_text(encoding="utf-8").splitlines()
    assert list(index.columns) == ["column", "text", "sign", "n_samples", *families]
    found = Counter({(row.column, row.text, family): getattr(row, family)
                     for row in index.itertuples() for family in families if getattr(row, family)})
    assert found == expected
    assert (index.n_samples == index[families].sum(axis=1)).all()
    assert {"", "sécu"} <= set(index.text)  # nom de section vide et non ASCII conservés

    column, sign = hash_lookup.column_for("imports_function", "KERNEL32.dll:VirtualAlloc")
    names = hash_lookup.names_for(column, index)
    assert "kernel32.dll:VirtualAlloc" in set(names.text)
    assert list(names.n_samples) == sorted(names.n_samples, reverse=True)
    assert hash_lookup.readable_name(column, index, max_names=len(names)).count(",") == len(names) - 1
    assert hash_lookup.readable_name("general_size", index) == "general_size"

    hash_lookup.main(["noms", column, "general_size", "--index", str(dataset)])
    out = capsys.readouterr().out
    assert f"{column} : {len(names)} nom(s)" in out
    assert "kernel32.dll:VirtualAlloc" in out
    assert "general_size : pas une colonne hachée" in out


def test_index_requires_sample_positions(tmp_path):
    _write_archives(tmp_path / "raw", make_samples(100, seed=8))
    dataset = tmp_path / "processed"
    prepare.main(["--data-dir", str(tmp_path / "raw"), "--out-dir", str(dataset), "--jobs", "1"])
    meta = pd.read_csv(dataset / "meta_train.csv")
    meta.drop(columns=["archive", "member", "line"]).to_csv(dataset / "meta_train.csv", index=False)
    with pytest.raises(SystemExit, match="ancienne version"):
        hash_lookup.main(["index", str(dataset), "--jobs", "1"])


def test_lookup_requires_an_index(tmp_path):
    with pytest.raises(SystemExit, match="scripts.hash_lookup index"):
        hash_lookup.main(["noms", "imports_library_hash001", "--index", str(tmp_path)])
