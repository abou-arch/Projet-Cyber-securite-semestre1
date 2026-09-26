"""Tests de bout en bout sur une fausse archive EMBER (données synthétiques, hors ligne)."""
import hashlib
import http.server
import json
import tarfile
import threading
from collections import Counter

import numpy as np
import pytest

from malware_family import download, prepare
from malware_family.dataset import load_dataset
from malware_family.ember_features import vectorize
from synthetic_ember import make_samples

PER_FILE = 40


@pytest.fixture
def fake_ember(tmp_path):
    """Dossier ember2018/ synthétique au format EMBER, et son archive .tar.bz2."""
    data_dir = tmp_path / "source" / "ember2018"
    data_dir.mkdir(parents=True)
    samples = make_samples(PER_FILE * len(download.EXPECTED_FILES), seed=0)
    by_file = {}
    for k, name in enumerate(download.EXPECTED_FILES):
        by_file[name] = samples[k * PER_FILE:(k + 1) * PER_FILE]
        with open(data_dir / name, "w", encoding="utf-8") as f:
            for i, sample in enumerate(by_file[name]):
                if i % 5 == 0:  # ordre de clés inhabituel : oblige à décoder toute la ligne
                    sample = dict(sample)
                    sample["avclass"] = sample.pop("avclass")
                f.write(json.dumps(sample) + "\n")
            f.write("\n")
    archive = tmp_path / "ember_dataset_2018_2.tar.bz2"
    with tarfile.open(archive, "w:bz2") as tar:
        tar.add(data_dir, arcname="ember2018")
    return data_dir, archive, by_file


def _trust_archive(monkeypatch, archive):
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setitem(download.DATASETS, "2018", dict(download.DATASETS["2018"], sha256=digest))


def test_download_verifies_and_extracts_archive(tmp_path, fake_ember, monkeypatch, capsys):
    _, archive, _ = fake_ember
    _trust_archive(monkeypatch, archive)
    raw = tmp_path / "raw"
    download.main(["--dest", str(raw), "--archive", str(archive)])
    for name in download.EXPECTED_FILES:
        assert (raw / "ember2018" / name).stat().st_size > 0
    capsys.readouterr()
    download.main(["--dest", str(raw), "--archive", str(archive)])
    assert "déjà installé" in capsys.readouterr().out


def test_download_rejects_corrupted_archive(tmp_path, fake_ember):
    _, archive, _ = fake_ember
    with pytest.raises(SystemExit, match="SHA-256 incorrecte"):
        download.main(["--dest", str(tmp_path / "raw"), "--archive", str(archive)])
    assert not (tmp_path / "raw" / "ember2018").exists()


def test_extract_refuses_path_traversal(tmp_path):
    evil = tmp_path / "evil.tar.bz2"
    payload = tmp_path / "payload.txt"
    payload.write_text("x")
    with tarfile.open(evil, "w:bz2") as tar:
        tar.add(payload, arcname="../payload.txt")
    with pytest.raises(SystemExit, match="Entrée inattendue"):
        download.extract(evil, tmp_path / "out")


class _FileServer(http.server.BaseHTTPRequestHandler):
    payload = b""
    honor_range = True
    ranges = []

    def do_GET(self):
        start, requested = 0, self.headers.get("Range")
        self.ranges.append(requested)
        if requested and self.honor_range:
            start = int(requested.split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(self.payload) - 1}/{len(self.payload)}")
        else:
            self.send_response(200)
        body = self.payload[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.mark.parametrize("honor_range", [True, False])
def test_download_resumes_partial_file(tmp_path, monkeypatch, honor_range):
    for variable in ("no_proxy", "NO_PROXY"):
        monkeypatch.setenv(variable, "*")
    payload = bytes(range(256)) * 5000
    handler = type("Handler", (_FileServer,), {"payload": payload, "honor_range": honor_range, "ranges": []})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        dest = tmp_path / "archive.tar.bz2"
        (tmp_path / "archive.tar.bz2.part").write_bytes(payload[:300_000])
        download.download(f"http://127.0.0.1:{server.server_port}/archive.tar.bz2", dest)
    finally:
        server.shutdown()
    assert dest.read_bytes() == payload
    assert handler.ranges == ["bytes=300000-"]
    assert not (tmp_path / "archive.tar.bz2.part").exists()


def _expected_selection(by_file, top):
    train = Counter(s["avclass"] for name, samples in by_file.items() if name.startswith("train")
                    for s in samples if s["label"] == 1 and s["avclass"])
    return sorted(train, key=lambda family: (-train[family], family))[:top]


@pytest.mark.parametrize("jobs", [1, 2])
def test_prepare_builds_family_dataset(tmp_path, fake_ember, monkeypatch, jobs):
    data_dir, _, by_file = fake_ember
    monkeypatch.setattr(prepare, "SCAN_CHUNK", 3000)  # coupe les fichiers au milieu des lignes
    monkeypatch.setattr(prepare, "VECTORIZE_CHUNK", 7)
    out = tmp_path / "processed"
    prepare.main(["--data-dir", str(data_dir), "--out-dir", str(out), "--top-families", "3",
                  "--jobs", str(jobs)])

    data = load_dataset(out)
    families = _expected_selection(by_file, 3)
    assert data.families == families
    for subset, X, y, meta in (("train", data.X_train, data.y_train, data.meta_train),
                               ("test", data.X_test, data.y_test, data.meta_test)):
        expected = [s for name, samples in by_file.items() if name.startswith(subset)
                    for s in samples if s["label"] == 1 and s["avclass"] in families]
        assert list(meta.sha256) == [s["sha256"] for s in expected]  # ordre des fichiers conservé
        assert [families[label] for label in y] == [s["avclass"] for s in expected]
        np.testing.assert_array_equal(X, np.stack([vectorize(s) for s in expected]))
    assert data.info["n_samples"] == {"train": len(data.y_train), "test": len(data.y_test)}
    assert len(data.feature_names) == data.X_train.shape[1] == 2381


def test_prepare_caps_samples_per_family(tmp_path, fake_ember):
    data_dir, _, by_file = fake_ember
    runs = []
    for run in ("a", "b"):
        out = tmp_path / run
        prepare.main(["--data-dir", str(data_dir), "--out-dir", str(out), "--top-families", "4",
                      "--max-per-family", "5", "--jobs", "1", "--seed", "7"])
        runs.append(load_dataset(out, mmap=False))
    assert np.bincount(runs[0].y_train).max() == 5
    assert np.bincount(runs[0].y_test).max() <= 5
    assert list(runs[0].meta_train.sha256) == list(runs[1].meta_train.sha256)  # tirage reproductible


def test_prepare_requires_downloaded_data(tmp_path):
    with pytest.raises(SystemExit, match="introuvables"):
        prepare.main(["--data-dir", str(tmp_path / "absent"), "--out-dir", str(tmp_path / "out")])
