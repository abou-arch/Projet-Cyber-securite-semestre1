"""Échantillons EMBER synthétiques (aucun vrai malware) pour les tests.

Les enregistrements respectent le schéma des lignes JSONL d'EMBER 2018 avec
des valeurs aléatoires, et couvrent quelques cas limites (aucune chaîne,
aucune section, section d'entrée introuvable, imports par ordinal, noms non ASCII...).
"""
from __future__ import annotations

import random

SECTION_NAMES = [".text", ".data", ".rdata", ".rsrc", ".reloc", "UPX0", "UPX1", "", ".tls", "sécu"]
SECTION_PROPS = ["CNT_CODE", "CNT_INITIALIZED_DATA", "MEM_EXECUTE", "MEM_READ", "MEM_WRITE",
                 "MEM_DISCARDABLE"]
LIBRARIES = {
    "KERNEL32.dll": ["CreateFileA", "VirtualAlloc", "GetProcAddress", "LoadLibraryA", "WriteFile"],
    "kernel32.dll": ["ExitProcess", "Sleep"],
    "USER32.dll": ["MessageBoxA", "GetWindowTextW"],
    "ADVAPI32.dll": ["RegOpenKeyExA", "RegSetValueExA", "CryptAcquireContextA"],
    "WS2_32.dll": ["ordinal23", "ordinal115", "connect"],
    "MSVBVM60.DLL": ["ordinal100", "__vbaFreeStr"],
}
DATA_DIRECTORIES = [
    "EXPORT_TABLE", "IMPORT_TABLE", "RESOURCE_TABLE", "EXCEPTION_TABLE", "CERTIFICATE_TABLE",
    "BASE_RELOCATION_TABLE", "DEBUG", "ARCHITECTURE", "GLOBAL_PTR", "TLS_TABLE",
    "LOAD_CONFIG_TABLE", "BOUND_IMPORT", "IAT", "DELAY_IMPORT_DESCRIPTOR", "CLR_RUNTIME_HEADER",
]


def make_raw_sample(rng, sha256, label=1, avclass="", appeared="2018-01"):
    """Retourne un dict au format d'une ligne JSONL d'EMBER 2018."""
    size = rng.randint(512, 3_000_000)
    has_strings = rng.random() > 0.1
    printabledist = [rng.randint(0, 400) if has_strings and rng.random() < 0.7 else 0 for _ in range(96)]
    printables = sum(printabledist)

    sections = []
    for _ in range(rng.choice([0, 1, 3, 5, 8])):
        sections.append({
            "name": rng.choice(SECTION_NAMES),
            "size": rng.choice([0, rng.randint(512, 400_000)]),
            "entropy": rng.uniform(0, 8),
            "vsize": rng.randint(0, 500_000),
            "props": rng.sample(SECTION_PROPS, rng.randint(0, 4)),
        })
    if sections and rng.random() < 0.8:
        entry = rng.choice(sections)["name"]
    else:
        entry = rng.choice(["", ".text", "absente"])

    imports = {lib: rng.sample(fns, rng.randint(1, len(fns)))
               for lib, fns in LIBRARIES.items() if rng.random() < 0.5}

    return {
        "sha256": sha256,
        "md5": sha256[:32],
        "appeared": appeared,
        "label": label,
        "avclass": avclass,
        "histogram": [rng.randint(0, size // 64) for _ in range(256)],
        "byteentropy": [rng.randint(0, 3000) if rng.random() < 0.3 else 0 for _ in range(256)],
        "strings": {
            "numstrings": rng.randint(0, 5000) if has_strings else 0,
            "avlength": rng.uniform(5, 40) if has_strings else 0,
            "printabledist": printabledist,
            "printables": printables,
            "entropy": rng.uniform(3, 6.5) if has_strings else 0.0,
            "paths": rng.randint(0, 5),
            "urls": rng.randint(0, 10),
            "registry": rng.randint(0, 20),
            "MZ": rng.randint(0, 50),
        },
        "general": {
            "size": size,
            "vsize": rng.randint(4096, 4_000_000),
            "has_debug": rng.randint(0, 1),
            "exports": rng.randint(0, 20),
            "imports": sum(len(fns) for fns in imports.values()),
            "has_relocations": rng.randint(0, 1),
            "has_resources": rng.randint(0, 1),
            "has_signature": rng.randint(0, 1),
            "has_tls": rng.randint(0, 1),
            "symbols": rng.randint(0, 100),
        },
        "header": {
            "coff": {
                "timestamp": rng.randint(0, 2**32 - 1),
                "machine": rng.choice(["I386", "AMD64", "ARM", ""]),
                "characteristics": rng.sample(
                    ["CHARA_32BIT_MACHINE", "EXECUTABLE_IMAGE", "DLL", "RELOCS_STRIPPED",
                     "LINE_NUMS_STRIPPED"],
                    rng.randint(0, 3)),
            },
            "optional": {
                "subsystem": rng.choice(["WINDOWS_GUI", "WINDOWS_CUI", "NATIVE", ""]),
                "dll_characteristics": rng.sample(
                    ["DYNAMIC_BASE", "NX_COMPAT", "TERMINAL_SERVER_AWARE", "NO_SEH"], rng.randint(0, 3)),
                "magic": rng.choice(["PE32", "PE32_PLUS", ""]),
                "major_image_version": rng.randint(0, 10),
                "minor_image_version": rng.randint(0, 10),
                "major_linker_version": rng.randint(0, 14),
                "minor_linker_version": rng.randint(0, 40),
                "major_operating_system_version": rng.randint(4, 10),
                "minor_operating_system_version": rng.randint(0, 3),
                "major_subsystem_version": rng.randint(4, 10),
                "minor_subsystem_version": rng.randint(0, 3),
                "sizeof_code": rng.randint(0, 2_000_000),
                "sizeof_headers": rng.choice([512, 1024, 4096]),
                "sizeof_heap_commit": rng.choice([4096, 8192]),
            },
        },
        "section": {"entry": entry, "sections": sections},
        "imports": imports,
        "exports": rng.sample(["DllMain", "ServiceMain", "Install", "run", "Exporté"], rng.randint(0, 3)),
        "datadirectories": [
            {"name": name, "size": rng.randint(0, 10_000), "virtual_address": rng.randint(0, 2_000_000)}
            for name in (DATA_DIRECTORIES + ["RESERVED"])[:rng.choice([0, 5, 15, 16])]
        ],
    }


def make_samples(n, seed=0):
    rng = random.Random(seed)
    families = ["alpha", "beta", "gamma", "delta"]
    samples = []
    for i in range(n):
        label = rng.choice([-1, 0, 1, 1])
        avclass = rng.choice(families + [""]) if label == 1 else ""
        samples.append(make_raw_sample(rng, f"{i:064x}", label, avclass, f"2018-{rng.randint(1, 12):02d}"))
    return samples
