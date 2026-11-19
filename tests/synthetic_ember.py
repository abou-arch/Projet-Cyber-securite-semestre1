"""Échantillons EMBER2024 synthétiques (aucun vrai malware) pour les tests.

Les enregistrements respectent le schéma des lignes JSONL d'EMBER2024
(métadonnées + features version 3) avec des valeurs aléatoires, et couvrent
quelques cas limites : fichier non PE, aucune chaîne, aucune section, exports,
imports par ordinal, avertissements pefile, noms non ASCII, ordre des clés variable...
"""
from __future__ import annotations

import random

from malware_family.ember_features import (DATA_DIRECTORY_NAMES, DLL_CHARACTERISTICS, DOS_MEMBERS,
                                           IMAGE_CHARACTERISTICS, MACHINE_TYPES, OPTIONAL_FIELDS,
                                           PEFILE_WARNINGS, STRING_PATTERNS, SUBSYSTEM_TYPES)

SECTION_NAMES = [".text", ".data", ".rdata", ".rsrc", ".reloc", "UPX0", "UPX1", "", ".tls", "sécu"]
SECTION_PROPS = ["CNT_CODE", "CNT_INITIALIZED_DATA", "MEM_EXECUTE", "MEM_READ", "MEM_WRITE",
                 "MEM_DISCARDABLE"]
LIBRARIES = {
    "KERNEL32.dll": ["CreateFileA", "VirtualAlloc", "GetProcAddress", "LoadLibraryA", "WriteFile"],
    "kernel32.dll": ["ExitProcess", "Sleep"],
    "USER32.dll": ["MessageBoxA", "GetWindowTextW"],
    "ADVAPI32.dll": ["RegOpenKeyExA", "RegSetValueExA", "CryptAcquireContextA"],
    "WS2_32.dll": ["WS2_32.dll:ordinal23", "WS2_32.dll:ordinal115", "connect"],
    "mscoree.dll": ["_CorExeMain"],
}


def _pe_features(rng, size):
    sections = []
    for _ in range(rng.choice([0, 1, 3, 5, 8])):
        sections.append({
            "name": rng.choice(SECTION_NAMES),
            "size": rng.choice([0, rng.randint(512, 400_000)]),
            "entropy": rng.uniform(0, 8),
            "vsize": rng.randint(0, 500_000),
            "size_ratio": rng.uniform(0, 1),
            "vsize_ratio": rng.uniform(0, 3),
            "props": rng.sample(SECTION_PROPS, rng.randint(0, 4)),
        })
    entry = rng.choice(sections)["name"] if sections and rng.random() < 0.8 else rng.choice(["", ".text"])
    image_base = rng.choice([0x400000, 0x10000000, 0x140000000, rng.randint(0, 2**63)])
    return {
        "header": {
            "coff": {
                "timestamp": rng.randint(0, 2**32 - 1),
                "machine": "IMAGE_FILE_MACHINE_" + rng.choice(MACHINE_TYPES + ("INCONNU",)),
                "number_of_sections": len(sections),
                "number_of_symbols": rng.randint(0, 50),
                "sizeof_optional_header": rng.choice([224, 240]),
                "pointer_to_symbol_table": rng.randint(0, 5000),
                "characteristics": rng.sample(IMAGE_CHARACTERISTICS, rng.randint(0, 4)),
            },
            "optional": {
                "magic": rng.choice([267, 523]),
                "subsystem": "IMAGE_SUBSYSTEM_" + rng.choice(SUBSYSTEM_TYPES),
                **{field: rng.randint(0, 2_000_000) for field in OPTIONAL_FIELDS},
                "image_base": image_base,
                "base_of_data": rng.randint(0, 100_000),
                "dll_characteristics": rng.sample(DLL_CHARACTERISTICS, rng.randint(0, 4)),
            },
            "dos": {member: rng.randint(0, 65535) for member in DOS_MEMBERS},
        },
        "section": {
            "entry": entry,
            "sections": sections,
            "overlay": {"size": rng.choice([0, rng.randint(1, size)]),
                        "size_ratio": rng.uniform(0, 0.5), "entropy": rng.uniform(0, 8)},
        },
        "imports": {lib: rng.sample(fns, rng.randint(1, len(fns)))
                    for lib, fns in LIBRARIES.items() if rng.random() < 0.5},
        "exports": rng.sample(["DllMain", "ServiceMain", "Install", "ordinal7", "Exporté"],
                              rng.randint(0, 3)),
        "datadirectories": [{"has_relocs": rng.randint(0, 1), "has_dynamic_relocs": rng.randint(0, 1)}] + [
            {"name": name, "size": rng.randint(0, 10_000), "virtual_address": rng.randint(0, 2_000_000)}
            for name in DATA_DIRECTORY_NAMES[:rng.choice([0, 5, 16])]
        ],
        "richheader": [rng.randint(0, 2**24) for _ in range(2 * rng.randint(0, 9))],
        "authenticode": {
            "num_certs": rng.randint(0, 3), "self_signed": rng.randint(0, 1),
            "empty_program_name": rng.randint(0, 1), "no_countersigner": rng.randint(0, 1),
            "parse_error": rng.randint(0, 1), "chain_max_depth": rng.randint(0, 4),
            "latest_signing_time": rng.choice([0, rng.uniform(1.4e9, 1.75e9)]),
            "signing_time_diff": rng.choice([0, rng.uniform(-1e8, 1e8)]),
        },
        "pefilewarnings": sorted(rng.sample(PEFILE_WARNINGS, rng.choice([0, 0, 1, 3]))),
    }


def make_raw_sample(rng, sha256, label=1, family=None, first_seen=1_700_000_000, file_type="Win32"):
    """Retourne un dict au format d'une ligne JSONL d'EMBER2024."""
    size = rng.randint(512, 3_000_000)
    is_pe = rng.random() > 0.05
    has_strings = rng.random() > 0.1
    printabledist = [rng.randint(0, 400) if has_strings and rng.random() < 0.7 else 0 for _ in range(96)]
    features = {
        "general": {"size": size, "entropy": rng.uniform(0, 8), "is_pe": int(is_pe),
                    "start_bytes": [77, 90, rng.randint(0, 255), rng.randint(0, 255)]},
        "histogram": [rng.randint(0, size // 64) for _ in range(256)],
        "byteentropy": [rng.randint(0, 3000) if rng.random() < 0.3 else 0 for _ in range(256)],
        "strings": {
            "numstrings": rng.randint(0, 5000) if has_strings else 0,
            "avlength": rng.uniform(5, 40) if has_strings else 0,
            "printabledist": printabledist,
            "printables": sum(printabledist),
            "entropy": rng.uniform(3, 6.5) if has_strings else 0.0,
            "string_counts": {p: rng.randint(1, 50) for p in rng.sample(STRING_PATTERNS, rng.randint(0, 12))},
        },
    }
    if is_pe:
        features.update(_pe_features(rng, size))
    else:  # thrember produit des groupes vides pour un fichier non PE
        features.update(header={}, section={}, imports={}, exports=[], datadirectories=[],
                        richheader=[], authenticode={}, pefilewarnings=[])
    metadata = {
        "sha256": sha256, "tlsh": "T1" + sha256[:70].upper(),
        "first_submission_date": first_seen, "last_analysis_date": first_seen + 86_400,
        "detection_ratio": rng.random(), "label": label, "file_type": file_type,
        "family": family, "family_confidence": rng.random() if family else None,
        "behavior": ["backdoor"] if family else [], "file_property": [], "packer": [],
        "exploit": [], "group": [],
    }
    # L'ordre des clés du JSONL officiel n'est pas documenté : on le fait varier.
    order = rng.random()
    if order < 0.4:
        return {**metadata, **features}
    if order < 0.8:
        return {**features, **metadata}
    return {"sha256": sha256, **features, **metadata}


def make_samples(n, seed=0, file_type="Win32", start=1_695_513_600, week=604_800):
    """n échantillons étalés chronologiquement à partir de ``start`` (une semaine tous les 5)."""
    rng = random.Random(seed)
    families = ["alpha", "beta", "gamma", "delta"]
    samples = []
    for i in range(n):
        label = rng.choice([0, 1, 1])
        family = rng.choice(families + [None]) if label == 1 else None
        first_seen = start + (i // 5) * week + rng.randint(0, week - 1)
        samples.append(make_raw_sample(rng, f"{seed:08x}{i:056x}", label, family, first_seen, file_type))
    return samples
