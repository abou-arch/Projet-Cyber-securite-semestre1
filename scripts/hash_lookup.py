"""Retrouve les vrais noms derrière les colonnes hachées d'EMBER2024 (``…_hashNN``).

EMBER2024 range les noms de bibliothèques, de fonctions et de sections dans un
nombre fixe de cases, avec le « hashing trick » de scikit-learn (FeatureHasher) :

    case = abs(murmurhash3_32(texte, seed=0)) % n

Plusieurs noms peuvent tomber dans la même case : ce script les liste tous.

Usage, depuis la racine du projet :

    # Colonne d'un nom (aucune donnée nécessaire)
    python -m scripts.hash_lookup colonne imports_function "KERNEL32.dll:VirtualAlloc"

    # Index des noms présents dans un jeu préparé (relit une fois les archives du train)
    python -m scripts.hash_lookup index data/processed/ember2024_Win32_top10

    # Noms derrière des colonnes, d'après l'index
    python -m scripts.hash_lookup noms imports_function_hash0123 section_size_hash07

L'index est écrit dans le dossier du jeu préparé (``hash_lookup.csv``), donc hors
de git : chacun le régénère chez soi. Dans un notebook :

    from scripts.hash_lookup import load_index, names_for, readable_name
    index = load_index("data/processed/ember2024_Win32_top10")
    names_for("imports_function_hash0123", index)       # tous les noms de la case
    readable_name("imports_function_hash0123", index)   # libellé court pour une figure

Signe : pour les sections, les exports et le Rich header, scikit-learn ajoute la
valeur d'un nom avec le signe de son hash (``alternate_sign``). Un nom de signe -1
rend la colonne négative ; deux noms de signes opposés peuvent se compenser.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

if __package__ in (None, ""):  # lancé par « python scripts/hash_lookup.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sklearn.utils import murmurhash3_32
from tqdm import tqdm

from malware_family.dataset import DEFAULT_PATH
from malware_family.download import SPLITS
from malware_family.ember_features import feature_names
from malware_family.prepare import _open_lines, int_at_least

INDEX_NAME = "hash_lookup.csv"


def _sections(raw):
    return raw["section"]["sections"] if raw["section"] else []


def _section_values(key):
    return lambda raw: [(section["name"], section[key]) for section in _sections(raw)]


def _rich_header_values(raw):
    values = raw["richheader"] or []
    # Couples (comp.id, nombre d'objets) ; comp.id = (produit << 16) | build du compilateur.
    return [(str(values[i]), values[i + 1]) for i in range(0, len(values) - 1, 2)]


@dataclass(frozen=True)
class HashedGroup:
    """Colonnes ``<prefix>_hashNN`` : ``n_features`` cases remplies par ``FeatureHasher``."""
    prefix: str
    n_features: int
    alternate_sign: bool  # la valeur est ajoutée avec le signe du hash
    values: Callable      # ligne JSONL décodée -> [(texte haché, valeur ajoutée dans sa case)]
    example: str


# Mêmes textes et mêmes valeurs que malware_family.ember_features, dans l'ordre du vecteur.
HASHED_GROUPS = {group.prefix: group for group in (
    HashedGroup("section_size", 50, True, _section_values("size"), ".text"),
    HashedGroup("section_vsize", 50, True, _section_values("vsize"), ".text"),
    HashedGroup("section_entropy", 50, True, _section_values("entropy"), ".text"),
    HashedGroup("section_props", 50, True,
                lambda raw: [(f"{s['name']}:{prop}", 1) for s in _sections(raw) for prop in s["props"]],
                ".text:MEM_EXECUTE"),
    HashedGroup("section_entry_name", 10, True,
                lambda raw: [(raw["section"]["entry"], 1)] if raw["section"] else [], ".text"),
    HashedGroup("imports_library", 256, False,
                lambda raw: [(lib, 1) for lib in {lib.lower() for lib in raw["imports"] or {}}],
                "kernel32.dll"),
    HashedGroup("imports_function", 1024, False,
                lambda raw: [(lib.lower() + ":" + fn, 1)
                             for lib, fns in (raw["imports"] or {}).items() for fn in fns],
                "kernel32.dll:VirtualAlloc"),
    HashedGroup("exports_function", 128, True, lambda raw: [(fn, 1) for fn in raw["exports"] or []],
                "DllMain"),
    HashedGroup("richheader", 32, True, _rich_header_values, "6229955"),
)}
_COLUMN_RE = re.compile(r"(?P<prefix>\w+)_hash(?P<index>\d+)")


def bucket(text, n_features):
    """Case et signe de ``text`` dans un ``FeatureHasher`` à ``n_features`` cases."""
    h = murmurhash3_32(text, seed=0)  # texte encodé en UTF-8, comme dans FeatureHasher
    return abs(h) % n_features, 1 if h >= 0 else -1


def column_name(prefix, index):
    width = len(str(HASHED_GROUPS[prefix].n_features - 1))
    return f"{prefix}_hash{index:0{width}d}"


def parse_column(column):
    """(préfixe, case) d'une colonne hachée, ou None pour toute autre colonne."""
    match = _COLUMN_RE.fullmatch(column)
    if not match or match["prefix"] not in HASHED_GROUPS:
        return None
    prefix, index = match["prefix"], int(match["index"])
    if index >= HASHED_GROUPS[prefix].n_features or column_name(prefix, index) != column:
        return None
    return prefix, index


def normalize(prefix, text):
    """Texte tel qu'EMBER2024 le hache : nom de bibliothèque en minuscules pour les imports."""
    if prefix == "imports_library":
        return text.lower()
    if prefix == "imports_function":
        library, sep, function = text.partition(":")
        if not sep:
            raise ValueError(f"« {text} » : format attendu bibliotheque.dll:Fonction")
        return library.lower() + ":" + function
    return text


def column_for(prefix, text):
    """Colonne hachée et signe d'un nom, ex. ``column_for("imports_library", "KERNEL32.dll")``."""
    index, sign = bucket(normalize(prefix, text), HASHED_GROUPS[prefix].n_features)
    return column_name(prefix, index), sign if HASHED_GROUPS[prefix].alternate_sign else 1


def hashed_texts(raw):
    """Textes qui alimentent les colonnes hachées d'un échantillon : {préfixe: {textes}}.

    Comme dans FeatureHasher, un texte de valeur nulle (section de taille 0...) ne compte pas.
    """
    return {prefix: {text for text, value in group.values(raw) if value != 0}
            for prefix, group in HASHED_GROUPS.items()}


_SHA256_RE = re.compile(rb'"sha256"\s*:\s*"([0-9a-fA-F]{64})"')
_family_of = {}  # sha256 -> famille des échantillons du jeu préparé, partagé avec les processus


def _set_families(family_of):
    global _family_of
    _family_of = family_of


def _index_member(task):
    """Textes hachés des échantillons du jeu préparé présents dans un fichier JSONL."""
    zip_path, member = task
    counts, found = defaultdict(Counter), 0
    with zipfile.ZipFile(zip_path) as archive, _open_lines(archive, member) as lines:
        size = archive.getinfo(member).file_size
        for line in lines:
            match = _SHA256_RE.search(line)
            if not match or match.group(1).decode() not in _family_of:
                continue  # on ne décode que les lignes du jeu préparé
            raw = json.loads(line)
            family = _family_of.get(raw["sha256"])
            if family is None:
                continue
            found += 1
            for prefix, texts in hashed_texts(raw).items():
                for text in texts:
                    counts[prefix, text][family] += 1
    return size, found, counts


def build_index(dataset, data_dir=None, splits=("train",), jobs=1):
    """Pour chaque nom haché, nombre d'échantillons du jeu préparé qui le contiennent, par famille.

    Renvoie (familles, lignes [colonne, texte, signe, n_samples, effectif par famille...],
    échantillons trouvés, échantillons attendus).
    """
    dataset = Path(dataset)
    info = json.loads((dataset / "dataset_info.json").read_text(encoding="utf-8"))
    families = (dataset / "families.txt").read_text(encoding="utf-8").splitlines()
    data_dir = Path(data_dir or info["source"])
    family_of, tasks, total = {}, [], 0
    for split in splits:
        meta = pd.read_csv(dataset / f"meta_{split}.csv", usecols=["sha256", "family"], dtype=str,
                           keep_default_na=False)
        family_of.update(zip(meta.sha256, meta.family))
        for name in info["archives"]:
            if not name.endswith(f"_{split}.zip"):
                continue
            path = data_dir / name
            if not path.is_file():
                raise SystemExit(f"Archive introuvable : {path}\n"
                                 "Indiquez le dossier des archives EMBER2024 avec --data-dir.")
            with zipfile.ZipFile(path) as archive:
                members = sorted((m for m in archive.infolist() if m.filename.endswith(".jsonl")),
                                 key=lambda m: m.filename)
            tasks += [(path, member.filename) for member in members]
            total += sum(member.file_size for member in members)

    counts, found = defaultdict(Counter), 0
    context = multiprocessing.get_context("spawn")  # comme prepare : même comportement partout
    with (context.Pool(jobs, initializer=_set_families, initargs=(family_of,)) if jobs > 1
          else nullcontext()) as pool:
        if pool is None:
            _set_families(family_of)
        results = pool.imap_unordered(_index_member, tasks) if pool else map(_index_member, tasks)
        with tqdm(total=total, unit="B", unit_scale=True, desc="Lecture des archives") as bar:
            for size, n_found, member_counts in results:
                found += n_found
                for key, by_family in member_counts.items():
                    counts[key].update(by_family)
                bar.update(size)

    order = {name: j for j, name in enumerate(feature_names())}
    rows = []
    for (prefix, text), by_family in counts.items():
        column, sign = column_for(prefix, text)
        rows.append([column, text, sign, sum(by_family.values()), *(by_family[f] for f in families)])
    rows.sort(key=lambda row: (order[row[0]], -row[3], row[1]))
    return families, rows, found, len(family_of)


def load_index(path=DEFAULT_PATH):
    """Index écrit par la commande ``index`` ; ``path`` : jeu préparé ou fichier CSV."""
    path = Path(path)
    if path.is_dir():
        path = path / INDEX_NAME
    if not path.is_file():
        raise FileNotFoundError(f"Pas d'index {path} : lancez "
                                f"« python -m scripts.hash_lookup index {path.parent} ».")
    # keep_default_na=False : un nom de section vide ou « NA » reste un texte.
    return pd.read_csv(path, dtype={"column": str, "text": str}, keep_default_na=False)


def names_for(column, index):
    """Tous les noms de la case ``column``, du plus fréquent au plus rare."""
    if parse_column(column) is None:
        raise ValueError(f"{column} n'est pas une colonne hachée")
    return index[index.column == column].reset_index(drop=True)


def _display(text):
    return text if text else '""'


def readable_name(column, index, max_names=2):
    """Libellé d'une colonne pour une figure, ex. « imports_function_hash0123 (kernel32.dll:Sleep, +4) »."""
    if parse_column(column) is None:
        return column
    names = names_for(column, index)
    if names.empty:
        return f"{column} (aucun nom)"
    shown = ", ".join(_display(text) for text in names.text[:max_names])
    more = f", +{len(names) - max_names}" if len(names) > max_names else ""
    return f"{column} ({shown}{more})"


def parse_args(argv=None):
    groups = "\n".join(f"  {g.prefix:<20}{g.n_features:>5} cases   ex. {g.example}"
                       for g in HASHED_GROUPS.values())
    parser = argparse.ArgumentParser(
        prog="python -m scripts.hash_lookup", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Vrais noms derrière les colonnes hachées (…_hashNN) d'EMBER2024.",
        epilog=f"Colonnes hachées :\n{groups}\n"
               "section_size, section_vsize et section_entropy hachent le même nom de section.")
    commands = parser.add_subparsers(dest="command", required=True)

    colonne = commands.add_parser("colonne", help="colonne d'un ou plusieurs noms (sans données)")
    colonne.add_argument("prefix", choices=list(HASHED_GROUPS), help="groupe de colonnes hachées")
    colonne.add_argument("texts", nargs="+", metavar="nom", help="ex. KERNEL32.dll:VirtualAlloc")

    index = commands.add_parser("index", help="index des noms présents dans un jeu préparé")
    index.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_PATH,
                       help=f"dossier créé par malware_family.prepare (défaut : {DEFAULT_PATH})")
    index.add_argument("--data-dir", type=Path,
                       help="dossier des archives EMBER2024 (défaut : celui utilisé par prepare)")
    index.add_argument("--splits", nargs="+", choices=SPLITS, default=["train"],
                       help="parties à indexer (défaut : train, les données vues par le modèle)")
    index.add_argument("--out", type=Path, help=f"fichier CSV (défaut : <dataset>/{INDEX_NAME})")
    index.add_argument("--jobs", type=int_at_least(1), default=os.cpu_count() or 1,
                       help="nombre de processus (défaut : nombre de cœurs)")

    noms = commands.add_parser("noms", help="noms derrière une ou plusieurs colonnes (d'après l'index)")
    noms.add_argument("columns", nargs="+", metavar="colonne", help="ex. imports_function_hash0123")
    noms.add_argument("--index", type=Path, default=DEFAULT_PATH,
                      help=f"jeu préparé ou fichier {INDEX_NAME} (défaut : {DEFAULT_PATH})")
    noms.add_argument("--max", type=int_at_least(0), default=0,
                      help="nombre de noms affichés par colonne (défaut : 0 = tous)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.command == "colonne":
        for text in args.texts:
            try:
                column, sign = column_for(args.prefix, text)
            except ValueError as error:
                raise SystemExit(str(error))
            print(f"{column}  (signe {sign:+d})  <- {_display(normalize(args.prefix, text))}")

    elif args.command == "index":
        if not (args.dataset / "dataset_info.json").is_file():
            raise SystemExit(f"Pas de jeu préparé dans {args.dataset} : "
                             "lancez « python -m malware_family.prepare ».")
        families, rows, found, expected = build_index(args.dataset, args.data_dir, args.splits, args.jobs)
        out = args.out or args.dataset / INDEX_NAME
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["column", "text", "sign", "n_samples", *families])
            writer.writerows(rows)
        if found != expected:
            print(f"Attention : {found} échantillons retrouvés dans les archives sur {expected}.")
        print(f"{len(rows)} noms, {len({row[0] for row in rows})} colonnes hachées, "
              f"{found} échantillons ({' + '.join(args.splits)}) -> {out}")

    else:
        try:
            index = load_index(args.index)
        except FileNotFoundError as error:
            raise SystemExit(str(error))
        families = list(index.columns[4:])
        for column in args.columns:
            if parse_column(column) is None:
                print(f"\n{column} : pas une colonne hachée")
                continue
            names = names_for(column, index)
            print(f"\n{column} : {len(names)} nom(s)")
            if len(names):
                print(f"  {'éch.':>7} {'signe':>5}  nom   [familles principales]")
            for _, row in (names.head(args.max) if args.max else names).iterrows():
                top = sorted(((row[f], f) for f in families if row[f]), reverse=True)[:3]
                print(f"  {row['n_samples']:>7} {row['sign']:>+5d}  {_display(row['text'])}   ["
                      + ", ".join(f"{f} {n}" for n, f in top) + "]")


if __name__ == "__main__":
    main()
