"""Tests de bout en bout sur de fausses archives EMBER2024 (données synthétiques, hors ligne)."""
import hashlib
import json
import math
import shutil
import zipfile
from collections import Counter, defaultdict

import numpy as np
import pytest

from malware_family import download, prepare
from malware_family.dataset import load_dataset
from malware_family.ember_features import vectorize
from synthetic_ember import make_samples

START, WEEK = 1_695_513_600, 604_800  # 24/09/2023, début d'EMBER2024


def _write_archive(path, samples):
    """Archive au format EMBER2024 (un fichier JSONL par semaine) ; renvoie ses lignes."""
    by_week = defaultdict(list)
    for sample in samples:
        by_week[(sample["first_submission_date"] - START) // WEEK].append(sample)
    lines = {}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for week, week_samples in sorted(by_week.items()):
            member = f"week{week:02d}_{path.stem}.jsonl"
            archive.writestr(member, "".join(json.dumps(s) + "\n" for s in week_samples) + "\n")
            lines.update({s["sha256"]: (member, line_no) for line_no, s in enumerate(week_samples)})
    return lines


@pytest.fixture
def fake_ember(tmp_path):
    """Archives Win32 et Win64 synthétiques, rangées comme sur Hugging Face."""
    remote = tmp_path / "hub"
    remote.mkdir()
    samples, lines = {}, {}
    for file_type, n, seed in (("Win32", 300, 0), ("Win64", 100, 1)):
        all_samples = make_samples(n, seed=seed, file_type=file_type)
        cut = int(n * 0.8)  # comme EMBER2024 : les semaines les plus récentes forment le test
        for split, part in (("train", all_samples[:cut]), ("test", all_samples[cut:])):
            samples[file_type, split] = part
            lines.update(_write_archive(remote / f"{file_type}_{split}.zip", part))
    return remote, samples, lines


@pytest.fixture
def fake_hub(fake_ember, monkeypatch):
    """Remplace Hugging Face par le dossier local des fausses archives."""
    remote, _, _ = fake_ember
    calls = {"info": [], "fetch": []}

    def remote_info(names):
        calls["info"].append(list(names))
        return {name: ((remote / name).stat().st_size,
                       hashlib.sha256((remote / name).read_bytes()).hexdigest()) for name in names}

    def fetch(name, dest):
        calls["fetch"].append(name)
        shutil.copy(remote / name, dest / name)

    monkeypatch.setattr(download, "remote_info", remote_info)
    monkeypatch.setattr(download, "fetch", fetch)
    return calls


def test_download_fetches_only_needed_archives(tmp_path, fake_hub, capsys):
    raw = tmp_path / "raw"
    download.main(["--dest", str(raw)])
    assert fake_hub["info"] == [["Win32_train.zip", "Win32_test.zip"]]
    assert fake_hub["fetch"] == ["Win32_train.zip", "Win32_test.zip"]
    assert sorted(p.name for p in raw.glob("*.zip")) == ["Win32_test.zip", "Win32_train.zip"]
    capsys.readouterr()
    download.main(["--dest", str(raw)])  # deuxième lancement : rien à retélécharger
    assert fake_hub["fetch"] == ["Win32_train.zip", "Win32_test.zip"]
    assert capsys.readouterr().out.count("déjà téléchargé et vérifié") == 2


def test_download_verifies_manual_download_without_refetching(tmp_path, fake_ember, fake_hub):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(fake_ember[0] / "Win64_train.zip", raw)
    download.main(["--dest", str(raw), "--file-types", "Win64"])
    assert fake_hub["fetch"] == ["Win64_test.zip"]


def test_download_rejects_corrupted_archive(tmp_path, fake_hub, monkeypatch):
    def corrupted_fetch(name, dest):
        (dest / name).write_bytes(b"x" * 10)

    monkeypatch.setattr(download, "fetch", corrupted_fetch)
    raw = tmp_path / "raw"
    with pytest.raises(SystemExit, match="corrompu"):
        download.main(["--dest", str(raw)])
    assert not (raw / "Win32_train.zip").exists()


def test_hugging_face_calls(tmp_path, monkeypatch):
    huggingface_hub = pytest.importorskip("huggingface_hub")
    from huggingface_hub.hf_api import RepoFile

    def get_paths_info(self, repo_id, paths, repo_type=None, **kwargs):
        assert (repo_id, repo_type) == ("joyce8/EMBER2024", "dataset")
        return [RepoFile(path=path, size=10 + i, oid="0" * 40,
                         lfs={"size": 10 + i, "oid": f"{i:064x}", "pointerSize": 134})
                for i, path in enumerate(paths)]

    downloads = []
    monkeypatch.setattr(huggingface_hub.HfApi, "get_paths_info", get_paths_info)
    monkeypatch.setattr(huggingface_hub, "hf_hub_download",
                        lambda *args, **kwargs: downloads.append((args, kwargs)))
    assert download.remote_info(["Win32_train.zip", "Win32_test.zip"]) == {
        "Win32_train.zip": (10, "0" * 64), "Win32_test.zip": (11, f"{1:064x}")}
    download.fetch("Win32_train.zip", tmp_path)
    assert downloads == [(("joyce8/EMBER2024", "Win32_train.zip"),
                          {"repo_type": "dataset", "local_dir": tmp_path})]


def test_read_metadata_fast_path_and_fallback():
    sample = make_samples(1, seed=4)[0]
    sample.update(label=1, family="berbew", family_confidence=0.75)
    # Une DLL importée nommée « family » ne doit pas être prise pour la métadonnée.
    sample["imports"] = {"family": ["label"], **sample.get("imports", {})}
    expected = {"sha256": sample["sha256"], "label": 1, "family": "berbew", "family_confidence": 0.75,
                "first_submission_date": sample["first_submission_date"]}
    line = json.dumps({"imports": sample.pop("imports"), **sample}).encode()
    assert prepare._read_metadata(line) == expected
    # Valeur inattendue (NaN) : repli sur le décodage complet de la ligne.
    nan_line = json.dumps(dict(sample, family_confidence=float("nan"))).encode()
    assert math.isnan(prepare._read_metadata(nan_line)["family_confidence"])


def _expected(samples, lines, split, file_types, families=None, top=None):
    """Lignes attendues : malwares avec famille, dans l'ordre chronologique de prepare."""
    rows = [s for t in file_types for s in samples[t, split] if s["label"] == 1 and s["family"]]
    if top:
        train = Counter(s["family"] for t in file_types for s in samples[t, "train"]
                        if s["label"] == 1 and s["family"])
        families = sorted(train, key=lambda family: (-train[family], family))[:top]
    rows = [s for s in rows if s["family"] in families]
    rows.sort(key=lambda s: (s["first_submission_date"], file_types.index(s["file_type"]),
                             *lines[s["sha256"]]))
    return rows, families


@pytest.mark.parametrize("jobs", [1, 3])
def test_prepare_builds_family_dataset(tmp_path, fake_ember, jobs):
    remote, samples, lines = fake_ember
    out = tmp_path / "processed"
    prepare.main(["--data-dir", str(remote), "--out-dir", str(out), "--file-types", "Win32",
                  "--top-families", "3", "--jobs", str(jobs)])

    data = load_dataset(out)
    _, families = _expected(samples, lines, "train", ["Win32"], top=3)
    assert data.families == families
    for split, X, y, meta in (("train", data.X_train, data.y_train, data.meta_train),
                              ("test", data.X_test, data.y_test, data.meta_test)):
        expected, _ = _expected(samples, lines, split, ["Win32"], families)
        assert list(meta.sha256) == [s["sha256"] for s in expected]  # ordre chronologique
        assert [families[label] for label in y] == [s["family"] for s in expected]
        assert set(meta.file_type) == {"Win32"}
        assert meta.first_seen.str.match(r"^20\d\d-\d\d-\d\d$").all()
        np.testing.assert_array_equal(X, np.stack([vectorize(s) for s in expected]))
    assert data.info["n_samples"] == {"train": len(data.y_train), "test": len(data.y_test)}
    assert len(data.feature_names) == data.X_train.shape[1] == 2568


def test_prepare_shares_a_single_jsonl_between_processes(tmp_path, fake_ember):
    _, samples, _ = fake_ember
    single = tmp_path / "single"
    single.mkdir()
    lines = {}
    for split in ("train", "test"):  # un seul gros fichier JSONL par archive
        with zipfile.ZipFile(single / f"Win32_{split}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("all.jsonl", "".join(json.dumps(s) + "\n" for s in samples["Win32", split]))
        lines.update({s["sha256"]: ("all.jsonl", i) for i, s in enumerate(samples["Win32", split])})
    out = tmp_path / "processed"
    prepare.main(["--data-dir", str(single), "--out-dir", str(out), "--top-families", "3", "--jobs", "3"])
    data = load_dataset(out)
    expected, _ = _expected(samples, lines, "train", ["Win32"], top=3)
    np.testing.assert_array_equal(data.X_train, np.stack([vectorize(s) for s in expected]))


def test_prepare_uses_all_downloaded_types(tmp_path, fake_ember, monkeypatch):
    remote, samples, lines = fake_ember
    monkeypatch.chdir(tmp_path)
    prepare.main(["--data-dir", str(remote), "--top-families", "4", "--jobs", "1"])
    data = load_dataset(tmp_path / "data" / "processed" / "hub_Win32-Win64_top4")
    expected, _ = _expected(samples, lines, "train", ["Win32", "Win64"], top=4)
    assert list(data.meta_train.sha256) == [s["sha256"] for s in expected]
    assert set(data.meta_train.file_type) == {"Win32", "Win64"}
    # Sans plafond, le nom du dossier le signale.
    prepare.main(["--data-dir", str(remote), "--top-families", "4", "--max-per-family", "0", "--jobs", "1"])
    no_cap = load_dataset(tmp_path / "data" / "processed" / "hub_Win32-Win64_top4_all")
    assert list(no_cap.meta_train.sha256) == list(data.meta_train.sha256)


def test_prepare_filters_confidence_and_caps_families(tmp_path, fake_ember):
    remote, _, _ = fake_ember
    runs = []
    for run in ("a", "b"):
        out = tmp_path / run
        prepare.main(["--data-dir", str(remote), "--out-dir", str(out), "--file-types", "Win32",
                      "--top-families", "4", "--min-confidence", "0.3", "--max-per-family", "8",
                      "--jobs", "1", "--seed", "7"])
        runs.append(load_dataset(out, mmap=False))
    data = runs[0]
    assert (data.meta_train.family_confidence >= 0.3).all()
    assert np.bincount(data.y_train).max() == 8
    assert np.bincount(data.y_test).max() <= 8
    assert list(data.meta_train.sha256) == list(runs[1].meta_train.sha256)  # tirage reproductible


def test_tilde_paths_are_expanded(tmp_path, fake_ember, monkeypatch):
    # Entre guillemets, « ~ » n'est pas remplacé par le terminal : nos scripts le font.
    for variable in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(variable, str(tmp_path))
    prepare.main(["--data-dir", "~/hub", "--out-dir", "~/out", "--file-types", "Win32",
                  "--top-families", "2", "--jobs", "1"])
    assert (tmp_path / "out" / "dataset_info.json").is_file()
    assert len(load_dataset("~/out").families) == 2


def test_prepare_requires_downloaded_archives(tmp_path):
    with pytest.raises(SystemExit, match="introuvables"):
        prepare.main(["--data-dir", str(tmp_path / "absent"), "--out-dir", str(tmp_path / "out")])


def test_prepare_keeps_each_file_once_and_removes_train_files_from_test(tmp_path, fake_ember):
    _, samples, _ = fake_ember
    train = samples["Win32", "train"]
    leaked = [s for s in train if s["label"] == 1 and s["family"]][:3]  # aussi dans le test
    test = samples["Win32", "test"] + leaked
    raw = tmp_path / "raw"
    raw.mkdir()
    for split, part in (("train", train), ("test", test)):
        with zipfile.ZipFile(raw / f"Win32_{split}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            lines = "".join(json.dumps(s) + "\n" for s in part)
            archive.writestr("a.jsonl", lines)
            archive.writestr("b.jsonl", lines)  # chaque ligne deux fois, comme dans EMBER2024
    out = tmp_path / "processed"
    prepare.main(["--data-dir", str(raw), "--out-dir", str(out), "--top-families", "4",
                  "--max-per-family", "0", "--jobs", "1"])

    data = load_dataset(out)
    with_family = {split: {s["sha256"] for s in part if s["label"] == 1 and s["family"]}
                   for split, part in (("train", train), ("test", test))}
    assert set(data.meta_train.sha256) == with_family["train"]
    assert set(data.meta_test.sha256) == with_family["test"] - with_family["train"]
    assert data.meta_train.sha256.is_unique and data.meta_test.sha256.is_unique
    assert set(data.meta_train.member) == {"a.jsonl"}  # la première occurrence est gardée
    by_sha256 = {s["sha256"]: s for s in train}
    expected = np.stack([vectorize(by_sha256[sha]) for sha in data.meta_train.sha256])
    np.testing.assert_array_equal(data.X_train, expected)
    assert data.info["duplicate_lines"] == {"train": len(train), "test": len(test)}
    assert data.info["test_malware_seen_in_train"] == len(leaked)
    labels = Counter(s["label"] for s in train)
    assert data.info["ember_label_counts"]["train"] == {"benign": labels[0], "malicious": labels[1]}


def test_load_dataset_rejects_duplicated_samples(tmp_path, fake_ember):
    remote, _, _ = fake_ember
    out = tmp_path / "processed"
    prepare.main(["--data-dir", str(remote), "--out-dir", str(out), "--file-types", "Win32", "--jobs", "1"])
    meta = (out / "meta_test.csv").read_text(encoding="utf-8").splitlines()
    (out / "meta_test.csv").write_text("\n".join(meta[:-1] + [meta[1]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="en double"):
        load_dataset(out)


def test_find_dataset_uses_variable_then_standard_folders(tmp_path, fake_ember, monkeypatch):
    from malware_family.dataset import find_dataset

    remote, _, _ = fake_ember
    home, project = tmp_path / "home", tmp_path / "projet"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("EMBER_DATASET", raising=False)
    with pytest.raises(FileNotFoundError, match="EMBER_DATASET"):
        find_dataset(project)
    in_home = home / "ember2024" / "processed" / "Win32_top10"
    prepare.main(["--data-dir", str(remote), "--out-dir", str(in_home), "--file-types", "Win32",
                  "--jobs", "1"])
    assert find_dataset(project) == in_home
    in_project = project / "data" / "processed" / "ember2024_Win32_top10"
    shutil.copytree(in_home, in_project)
    assert find_dataset(project) == in_project  # le dossier du projet passe en premier
    monkeypatch.setenv("EMBER_DATASET", "~/ailleurs")
    assert find_dataset(project) == home / "ailleurs"  # la variable passe avant tout
