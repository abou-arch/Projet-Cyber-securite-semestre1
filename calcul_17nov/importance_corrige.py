"""Importance des features du modèle final de B (rôle C).

Cinq mesures, toutes sur le test (le modèle final a vu tout le train) :

- **Importance interne** : ``model.feature_importances_``, normalisée à 1. C'est le MDI pour une
  forêt (baisse moyenne d'impureté), le gain pour LightGBM. Rapide, mais favorise les features
  continues aux nombreuses valeurs, et ne dit rien du test. Colonnes ``mdi`` des tableaux.
- **Permutation par groupe** : on mélange ensemble toutes les colonnes d'un groupe (imports,
  sections, chaînes…) et on mesure la baisse du F1 macro. ``permutation_importance`` de
  scikit-learn ne sait pas regrouper des colonnes, d'où la petite boucle ``permutation_drop``.
  La baisse est aussi mesurée famille par famille (F1 de chaque famille).
- **Permutation feature par feature**, pour les ``--top`` meilleures features du MDI seulement
  (sur les 2 568 colonnes, ce serait beaucoup trop long).
- **Ablation** (``--ablation``, optionnelle et longue) : le modèle de B réentraîné avec un seul
  groupe, puis avec tous les groupes sauf un.
- **SHAP par famille** (reprise de l'analyse de Kenneth) : pour des fichiers de chaque famille, la
  contribution de chaque feature à la décision « cette famille ». Exacte et rapide pour LightGBM
  (``pred_contrib``) ; pour une forêt, il faut le paquet ``shap`` (``pip install shap``), plus lent.

S'y ajoutent les **confusions** : pour les paires de familles les plus confondues, les features
sur lesquelles les fichiers mal classés ressemblent à la famille prédite.

Usage, depuis la racine du projet (après ``python -m scripts.train``) :

    python -m scripts.importance                    # jeu trouvé par find_dataset(), quelques minutes
    python -m scripts.importance --max-rows 5000    # essai rapide sur 5 000 lignes du test
    python -m scripts.importance --ablation         # ajoute l'ablation (environ 30 min)

Les colonnes hachées (``…_hashNN``) sont nommées avec l'index de ``scripts.hash_lookup`` s'il
existe (``python -m scripts.hash_lookup index <jeu>``). Écrit dans ``results/`` :
``importances.csv``, ``importances_groupes.csv``, ``confusions_features.csv``, ``ablation.csv``
(avec ``--ablation``), ``shap_top_par_famille.csv``, ``shap_groupes_par_famille.csv``,
``importance_info.json``, et les figures ``results/figures/C_*.png``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # lancé par « python scripts/importance.py »
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from tqdm import tqdm

from malware_family.dataset import find_dataset, load_dataset
from malware_family.ember_features import FEATURE_GROUPS
from malware_family.figures import FIGURES_DIR, FULL_WIDTH, CM, new_figure, save_figure
from scripts.hash_lookup import load_index, readable_name

ROOT = Path(__file__).resolve().parents[1]
RANDOM_STATE = 42


def feature_groups_of(names):
    """{groupe: indices des colonnes}, d'après le préfixe des noms (``imports_…`` -> imports).

    Sur les 2 568 colonnes d'EMBER2024, ce sont exactement les 12 groupes de FEATURE_GROUPS,
    dans le même ordre."""
    groups = {}
    for j, name in enumerate(names):
        groups.setdefault(name.split("_")[0], []).append(j)
    order = {group: i for i, group in enumerate(FEATURE_GROUPS)}
    return {group: np.array(columns) for group, columns in
            sorted(groups.items(), key=lambda item: order.get(item[0], len(order)))}


def native_importance(model):
    """(importance interne normalisée à 1, son nom) : MDI d'une forêt, gain de LightGBM."""
    values = getattr(model, "feature_importances_", None)
    if values is None:
        return None, None
    values = np.asarray(values, dtype=np.float64)
    label = "gain" if hasattr(model, "booster_") else "MDI"
    return (values / values.sum() if values.sum() > 0 else values), label


def preselection_importance(X_train, y_train, random_state=RANDOM_STATE, max_rows=20_000):
    """Pour un modèle sans importance interne (HistGradientBoosting) : MDI d'une petite forêt
    entraînée sur au plus ``max_rows`` lignes du train, normalisée à 1. Elle sert seulement à
    choisir les features à permuter : les baisses de F1 sont toujours celles du vrai modèle."""
    rows = np.arange(len(y_train))
    if len(rows) > max_rows:
        rows = np.sort(np.random.default_rng(random_state).choice(rows, max_rows, replace=False))
    forest = RandomForestClassifier(n_estimators=100, max_depth=20, max_features="sqrt", n_jobs=-1,
                                    random_state=random_state)
    forest.fit(np.asarray(X_train[rows]), y_train[rows])
    return native_importance(forest)[0]


def f1_scores(model, X, y, labels):
    """(F1 macro, F1 de chaque famille) des prédictions de ``model`` sur X."""
    per_family = f1_score(y, model.predict(X), labels=labels, average=None, zero_division=0)
    return per_family.mean(), per_family


def permutation_drop(model, X, y, columns, labels, n_repeats=5, random_state=RANDOM_STATE,
                     baseline=None):
    """Baisse du F1 quand on mélange ensemble les lignes des colonnes ``columns``.

    Les colonnes d'un groupe sont mélangées avec la même permutation : leurs liens internes sont
    gardés, seul leur lien avec la famille est rompu. ``X`` est modifié puis remis en état.
    Renvoie (baisse du F1 macro à chaque répétition, baisse moyenne du F1 de chaque famille)."""
    if baseline is None:
        baseline = f1_scores(model, X, y, labels)
    base_macro, base_family = baseline
    rng = np.random.default_rng(random_state)
    saved = X[:, columns].copy()
    macro_drops, family_drops = [], []
    try:
        for _ in range(n_repeats):
            X[:, columns] = saved[rng.permutation(len(X))]
            macro, per_family = f1_scores(model, X, y, labels)
            macro_drops.append(base_macro - macro)
            family_drops.append(base_family - per_family)
    finally:
        X[:, columns] = saved
    return np.array(macro_drops), np.mean(family_drops, axis=0)


def group_importance(model, X, y, names, families, n_repeats=5, random_state=RANDOM_STATE,
                     native=None):
    """Une ligne par groupe : taille, somme de l'importance interne (``mdi_sum`` ; ``native`` si
    donnée, sinon celle du modèle), baisse du F1 macro et du F1 de chaque famille."""
    labels = list(range(len(families)))
    baseline = f1_scores(model, X, y, labels)
    mdi = native if native is not None else native_importance(model)[0]
    rows = []
    for group, columns in tqdm(feature_groups_of(names).items(), desc="Permutation par groupe"):
        drops, family_drops = permutation_drop(model, X, y, columns, labels, n_repeats,
                                               random_state, baseline)
        rows.append({"group": group, "n_features": len(columns),
                     "mdi_sum": float(mdi[columns].sum()) if mdi is not None else np.nan,
                     "perm_f1_drop_mean": drops.mean(), "perm_f1_drop_std": drops.std(),
                     **{f"f1_drop_{family}": drop for family, drop in zip(families, family_drops)}})
    table = pd.DataFrame(rows).sort_values("perm_f1_drop_mean", ascending=False, ignore_index=True)
    return table, baseline


def feature_importance(model, X, y, names, families, top=50, n_repeats=5, random_state=RANDOM_STATE,
                       index=None, native=None):
    """Une ligne par feature : importance interne (``mdi`` ; ``native`` si donnée, sinon celle du
    modèle) et rang ; permutation pour les ``top`` meilleures selon cette importance."""
    mdi = native if native is not None else native_importance(model)[0]
    if mdi is None:
        raise SystemExit(f"{type(model).__name__} n'a pas de feature_importances_ : donnez une "
                         "importance de présélection (preselection_importance).")
    labels = list(range(len(families)))
    baseline = f1_scores(model, X, y, labels)
    table = pd.DataFrame({"feature": names, "group": [name.split("_")[0] for name in names],
                          "mdi": mdi})
    table["mdi_rank"] = table.mdi.rank(ascending=False, method="first").astype(int)
    table["perm_f1_drop_mean"] = np.nan
    table["perm_f1_drop_std"] = np.nan
    candidates = table.nsmallest(top, "mdi_rank").index
    for j in tqdm(candidates, desc=f"Permutation des {len(candidates)} meilleures features"):
        drops, _ = permutation_drop(model, X, y, [j], labels, n_repeats, random_state, baseline)
        table.loc[j, ["perm_f1_drop_mean", "perm_f1_drop_std"]] = drops.mean(), drops.std()
    table["name"] = [readable_name(name, index) if index is not None else name for name in names]
    return table.sort_values(["perm_f1_drop_mean", "mdi"], ascending=False, na_position="last",
                             ignore_index=True)


def confused_pairs(y_true, y_pred, families, n_pairs=3, min_count=5):
    """Les paires (famille réelle, famille prédite) les plus fréquentes parmi les erreurs."""
    errors = pd.DataFrame({"true": y_true, "pred": y_pred})
    errors = errors[errors.true != errors.pred]
    counts = errors.groupby(["true", "pred"]).size().sort_values(ascending=False)
    return [(families[a], families[b], int(n)) for (a, b), n in counts.items() if n >= min_count][:n_pairs]


def confusion_profile(X, y_true, y_pred, families, real, predicted, features, names):
    """Pour les fichiers de ``real`` classés ``predicted`` : de quelle famille sont-ils proches ?

    Pour chaque feature, compare la moyenne des fichiers confondus à celle des fichiers bien
    classés des deux familles. ``rapprochement`` vaut 1 si les confondus ont la valeur de la
    famille prédite, 0 s'ils ont celle de leur vraie famille (NaN si les deux familles ont la
    même moyenne)."""
    a, b = families.index(real), families.index(predicted)
    groups = {"moyenne_reelle_ok": (y_true == a) & (y_pred == a),
              "moyenne_confondus": (y_true == a) & (y_pred == b),
              "moyenne_predite_ok": (y_true == b) & (y_pred == b)}
    columns = [names.index(feature) for feature in features]
    means = {key: np.asarray(X[mask][:, columns], dtype=np.float64).mean(axis=0) if mask.any()
             else np.full(len(columns), np.nan) for key, mask in groups.items()}
    to_real = np.abs(means["moyenne_confondus"] - means["moyenne_reelle_ok"])
    to_predicted = np.abs(means["moyenne_confondus"] - means["moyenne_predite_ok"])
    with np.errstate(invalid="ignore", divide="ignore"):
        closeness = np.where(to_real + to_predicted > 0, to_real / (to_real + to_predicted), np.nan)
    return pd.DataFrame({"famille_reelle": real, "famille_predite": predicted,
                         "n_confondus": int(groups["moyenne_confondus"].sum()), "feature": features,
                         **means, "rapprochement": closeness})


def ablation(model, data, groups, n_estimators=None):
    """F1 macro du test pour le modèle de B réentraîné avec un seul groupe, puis sans un groupe."""
    labels = list(range(len(data.families)))
    all_columns = np.arange(data.X_train.shape[1])
    rows = []
    settings = [(group, mode) for group in groups for mode in ("seul", "sans")]
    for group, mode in tqdm(settings, desc="Ablation"):
        columns = groups[group] if mode == "seul" else np.setdiff1d(all_columns, groups[group])
        estimator = clone(model)
        cat = estimator.get_params().get("categorical_features")
        if cat is not None and not isinstance(cat, str):
                    cat = np.asarray(cat)
                    if cat.dtype == bool:
                        cat = cat[columns]
                    else:
                        pos = {int(c): i for i, c in enumerate(columns)}
                        cat = [pos[int(c)] for c in cat if int(c) in pos]
                    estimator.set_params(categorical_features=cat if len(cat) else None)
        if n_estimators and "n_estimators" in estimator.get_params():
            estimator.set_params(n_estimators=n_estimators)
        start = time.perf_counter()
        estimator.fit(np.asarray(data.X_train[:, columns]), data.y_train)
        macro, _ = f1_scores(estimator, np.asarray(data.X_test[:, columns]), data.y_test, labels)
        rows.append({"group": group, "mode": mode, "n_features": len(columns), "test_f1_macro": macro,
                     "duration_seconds": round(time.perf_counter() - start, 2)})
        del estimator
    return pd.DataFrame(rows)


def shap_for_class(model, X, k):
    """Contributions SHAP (n, F) de chaque feature au score de la classe ``k``.

    LightGBM les calcule lui-même, exactement (``pred_contrib`` : TreeSHAP, en log-odds). Pour un
    autre modèle d'arbres (forêt), on passe par le paquet ``shap`` (en probabilité). Renvoie None
    si ``shap`` n'est pas installé."""
    position = list(model.classes_).index(k)
    n_features = X.shape[1]
    if hasattr(model, "booster_"):
        contrib = np.asarray(model.predict(X, pred_contrib=True))
        if contrib.shape[1] == n_features + 1:  # deux classes : une seule colonne de score
            return contrib[:, :n_features] * (1 if position == 1 else -1)
        start = position * (n_features + 1)
        return contrib[:, start:start + n_features]
    try:
        import shap
    except ImportError:
        return None
    values = shap.TreeExplainer(model).shap_values(X, check_additivity=False)
    if isinstance(values, list):  # anciennes versions de shap : une matrice par classe
        return np.asarray(values[position])
    return np.asarray(values)[:, :, position]


def shap_by_family(model, X, y, names, families, per_family=200, top=5, index=None,
                   random_state=RANDOM_STATE):
    """SHAP sur au plus ``per_family`` fichiers (tirés au hasard) de chaque famille, pour la décision
    « cette famille ». Renvoie (top ``top`` features par famille, part de chaque groupe en %),
    ou (None, None) si le modèle ne le permet pas.

    ``shap_mean`` > 0 : la feature pousse vers la famille ; < 0 : elle en éloigne."""
    rng = np.random.default_rng(random_state)
    groups = feature_groups_of(names)
    top_rows, shares = [], {}
    for k, family in enumerate(tqdm(families, desc="SHAP par famille")):
        rows = np.flatnonzero(y == k)
        if not len(rows):
            continue
        rows = np.sort(rng.choice(rows, min(per_family, len(rows)), replace=False))
        values = shap_for_class(model, X[rows], k)
        if values is None:
            return None, None
        mean_abs, mean = np.abs(values).mean(axis=0), values.mean(axis=0)
        total = mean_abs.sum()
        for rank, j in enumerate(np.argsort(mean_abs)[::-1][:top], 1):
            top_rows.append({"famille": family, "n_fichiers": len(rows), "rang": rank, "feature": names[j],
                             "group": names[j].split("_")[0],
                             "name": readable_name(names[j], index) if index is not None else names[j],
                             "shap_abs_mean": mean_abs[j], "shap_mean": mean[j],
                             "part_pct": 100 * mean_abs[j] / total if total else np.nan})
        shares[family] = {group: 100 * mean_abs[columns].sum() / total if total else np.nan
                          for group, columns in groups.items()}
    table = pd.DataFrame.from_dict(shares, orient="index")
    table = table[table.mean().sort_values(ascending=False).index]
    table.index.name = "famille"
    return pd.DataFrame(top_rows), table


def _save(fig, name, figures_dir):
    """Enregistre la figure puis la ferme (un calcul complet en crée plusieurs)."""
    path = save_figure(fig, name, figures_dir)
    plt.close(fig)
    return path


def _fr(value, digits=3):
    """Nombre avec une virgule décimale, comme dans le rapport (0,883)."""
    return f"{value:.{digits}f}".replace(".", ",")


def _short(text, width=58):
    return text if len(text) <= width else text[:width - 1] + "…"


def plot_groups(groups, baseline_f1, figures_dir, native_label="MDI"):
    """Deux barres par groupe : baisse du F1 macro par permutation, et importance interne."""
    table = groups.iloc[::-1]
    fig, (left, right) = new_figure(FULL_WIDTH, 9 * CM, ncols=2, sharey=True)
    left.barh(table.group, table.perm_f1_drop_mean, xerr=table.perm_f1_drop_std, color="tab:blue")
    left.set_xlabel("Baisse du F1 macro (permutation)")
    left.set_title(f"Sur le test (F1 macro {_fr(baseline_f1)})")
    right.barh(table.group, table.mdi_sum, color="tab:gray")
    right.set_xlabel(f"Somme du {native_label}")
    right.set_title(f"Dans le modèle ({native_label})")
    for ax in (left, right):
        ax.grid(axis="y", visible=False)
    left.set_yticks(range(len(table)), [f"{g} ({n})" for g, n in zip(table.group, table.n_features)])
    fig.tight_layout()
    return _save(fig, "C_importance_par_groupe", figures_dir)


def plot_top_features(features, figures_dir, n=20):
    """Les ``n`` features dont la permutation fait le plus baisser le F1, colorées par groupe."""
    table = features.dropna(subset=["perm_f1_drop_mean"]).head(n).iloc[::-1]
    palette = dict(zip(FEATURE_GROUPS, matplotlib.colormaps["tab20"].colors))
    fig, ax = new_figure(FULL_WIDTH, (3 + 0.45 * len(table)) * CM)
    ax.barh(range(len(table)), table.perm_f1_drop_mean, xerr=table.perm_f1_drop_std,
            color=[palette.get(group, "tab:gray") for group in table.group])
    ax.set_yticks(range(len(table)), [_short(name) for name in table.name], fontsize=8)
    ax.set_xlabel("Baisse du F1 macro (permutation, test)")
    ax.grid(axis="y", visible=False)
    shown = list(dict.fromkeys(table.group[::-1]))
    handles = [Patch(color=palette.get(g, "tab:gray"), label=g)
               for g in shown]
    ax.legend(handles=handles, title="Groupe", loc="lower right", frameon=False)
    fig.tight_layout()
    return _save(fig, "C_top_features", figures_dir)


def plot_groups_by_family(groups, families, test_counts, figures_dir):
    """Carte de chaleur : baisse du F1 de chaque famille quand on permute chaque groupe."""
    values = groups[[f"f1_drop_{family}" for family in families]].to_numpy()
    fig, ax = new_figure(FULL_WIDTH, 10 * CM)
    limit = max(np.abs(values).max(), 1e-6)
    image = ax.imshow(values, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(range(len(families)), [f"{f}\n(n={n})" for f, n in zip(families, test_counts)],
                  rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(groups)), groups.group)
    ax.grid(False)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            if abs(values[i, j]) >= 0.01:
                ax.text(j, i, _fr(values[i, j], 2), ha="center", va="center",
                        fontsize=6, color="white" if abs(values[i, j]) > 0.6 * limit else "black")
    fig.colorbar(image, ax=ax, label="Baisse du F1 de la famille")
    ax.set_title("Groupes permutés (lignes) et familles touchées (colonnes)")
    fig.tight_layout()
    return _save(fig, "C_importance_groupes_par_famille", figures_dir)


def plot_ablation(table, full_f1, figures_dir):
    """F1 macro avec un seul groupe et sans un groupe, par rapport au modèle complet."""
    pivot = table.pivot(index="group", columns="mode", values="test_f1_macro")
    pivot = pivot.sort_values("seul")
    fig, ax = new_figure(FULL_WIDTH, 9 * CM)
    positions = np.arange(len(pivot))
    ax.barh(positions - 0.2, pivot["seul"], height=0.4, label="ce groupe seul", color="tab:blue")
    ax.barh(positions + 0.2, pivot["sans"], height=0.4, label="tous sauf ce groupe", color="tab:orange")
    ax.axvline(full_f1, color="black", linestyle="--", linewidth=1, label=f"modèle complet ({_fr(full_f1)})")
    ax.set_yticks(positions, pivot.index)
    ax.set_xlabel("F1 macro (test)")
    ax.set_xlim(0, 1)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False)
    fig.tight_layout()
    return _save(fig, "C_ablation", figures_dir)


def plot_shap_groups(shares, test_counts, figures_dir):
    """Carte de chaleur : part de chaque groupe (colonnes) dans les décisions de chaque famille."""
    fig, ax = new_figure(FULL_WIDTH, 10 * CM)
    image = ax.imshow(shares.to_numpy(), cmap="Blues", vmin=0, aspect="auto")
    ax.set_xticks(range(shares.shape[1]), shares.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(shares)), [f"{family} (n={test_counts.get(family, 0)})"
                                       for family in shares.index], fontsize=8)
    ax.grid(False)
    limit = np.nanmax(shares.to_numpy())
    for i in range(shares.shape[0]):
        for j in range(shares.shape[1]):
            value = shares.iat[i, j]
            if value >= 1:
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if value > 0.6 * limit else "black")
    fig.colorbar(image, ax=ax, label="Part de la contribution (%)")
    ax.set_title("Quels groupes de features décident de chaque famille ? (SHAP, test)")
    fig.tight_layout()
    return _save(fig, "C_shap_groupes_par_famille", figures_dir)


def _check_predictions(y_pred, data, path):
    """Part des prédictions identiques à results/predictions_test.csv (même modèle que B ?)."""
    if not path.is_file():
        return None
    saved = pd.read_csv(path, dtype={"sha256": str})
    same_files = len(saved) == len(data.y_test) and (saved.sha256 == data.meta_test.sha256).all()
    if not same_files:
        return None
    return float((saved.y_pred.to_numpy() == y_pred).mean())


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m scripts.importance",
                                     description="Importance des features du modèle final, sur le test.")
    parser.add_argument("--dataset", type=Path, help="jeu préparé (défaut : find_dataset())")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "best_model.joblib",
                        help="modèle de scripts.train (défaut : models/best_model.joblib)")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results",
                        help="dossier des tableaux (défaut : results/)")
    parser.add_argument("--figures-dir", type=Path, default=FIGURES_DIR,
                        help="dossier des figures (défaut : results/figures/)")
    parser.add_argument("--n-repeats", type=int, default=5,
                        help="permutations par groupe ou feature (défaut : 5)")
    parser.add_argument("--top", type=int, default=50,
                        help="features du MDI évaluées une par une par permutation (défaut : 50)")
    parser.add_argument("--max-rows", type=int,
                        help="tirage de lignes du test, pour un essai rapide (défaut : tout le test)")
    parser.add_argument("--pairs", type=int, default=3,
                        help="paires de familles confondues étudiées (défaut : 3)")
    parser.add_argument("--ablation", action="store_true",
                        help="réentraîne le modèle avec un seul groupe, puis sans un groupe (long)")
    parser.add_argument("--ablation-trees", type=int,
                        help="nombre d'arbres pour l'ablation (défaut : celui du modèle)")
    parser.add_argument("--shap-per-family", type=int, default=200,
                        help="fichiers du test par famille pour SHAP (défaut : 200 ; 0 : pas de SHAP). "
                             "Pour une forêt, SHAP est lent : commencer par 50")
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE,
                        help=f"graine (défaut : {RANDOM_STATE})")
    args = parser.parse_args(argv)

    path = args.dataset.expanduser() if args.dataset else find_dataset(ROOT)
    try:
        data = load_dataset(path)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error))
    if not args.model.is_file():
        raise SystemExit(f"Pas de modèle {args.model} : lancez « python -m scripts.train » "
                         "(même jeu de données, random_state fixé : même modèle que B).")
    model = joblib.load(args.model)
    if getattr(model, "n_features_in_", data.X_test.shape[1]) != data.X_test.shape[1]:
        raise SystemExit(f"{args.model} attend {model.n_features_in_} features, le jeu {path} en a "
                         f"{data.X_test.shape[1]}.")
    try:
        index = load_index(path)
    except FileNotFoundError:
        index = None
        print(f"Pas d'index des noms hachés dans {path} : les colonnes …_hashNN gardent leur numéro.\n"
              f"  Pour les noms réels : python -m scripts.hash_lookup index {path}")

    start = time.perf_counter()
    rows = np.arange(len(data.y_test))
    if args.max_rows and args.max_rows < len(rows):
        rows = np.sort(np.random.default_rng(args.random_state).choice(rows, args.max_rows, replace=False))
    X = np.array(data.X_test[rows], dtype=np.float32)  # copie modifiable : les permutations s'y font
    y = data.y_test[rows]
    names, families = data.feature_names, data.families
    print(f"Jeu : {path}\nModèle : {args.model} ({type(model).__name__})\n"
          f"Test : {len(y)} lignes{' (tirage)' if len(rows) < len(data.y_test) else ''}, "
          f"{args.n_repeats} permutations par groupe ou feature")

    y_pred = model.predict(X)
    agreement = (_check_predictions(model.predict(np.asarray(data.X_test)) if len(rows) < len(data.y_test)
                                    else y_pred, data, args.results_dir / "predictions_test.csv"))
    if agreement is not None and agreement < 1:
        print(f"Attention : {agreement:.1%} seulement des prédictions sont celles de "
              "results/predictions_test.csv. Le modèle n'est pas celui de B : relancez scripts.train.")

    native, native_label = native_importance(model)
    if native is None:  # ex. HistGradientBoosting
        print(f"{type(model).__name__} n'a pas d'importance interne : une petite forêt entraînée sur "
              "le train choisit les features à permuter (les baisses de F1 restent celles du modèle).")
        native, native_label = preselection_importance(data.X_train, data.y_train, args.random_state), \
            "MDI de présélection"
    groups, (baseline_f1, baseline_family) = group_importance(model, X, y, names, families,
                                                              args.n_repeats, args.random_state, native)
    features = feature_importance(model, X, y, names, families, args.top, args.n_repeats,
                                  args.random_state, index, native)

    top_features = list(features.dropna(subset=["perm_f1_drop_mean"]).feature[:30])
    pairs = confused_pairs(y, y_pred, families, args.pairs)
    profiles = [confusion_profile(X, y, y_pred, families, real, predicted, top_features, names)
                for real, predicted, _ in pairs]
    confusions = pd.concat(profiles, ignore_index=True) if profiles else pd.DataFrame()
    if len(confusions):
        confusions["name"] = confusions.feature.map(dict(zip(features.feature, features.name)))

    args.results_dir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.results_dir / "importances.csv", index=False)
    groups.to_csv(args.results_dir / "importances_groupes.csv", index=False)
    confusions.to_csv(args.results_dir / "confusions_features.csv", index=False)
    figures = [plot_groups(groups, baseline_f1, args.figures_dir, native_label),
               plot_top_features(features, args.figures_dir),
               plot_groups_by_family(groups, families, np.bincount(y, minlength=len(families)),
                                     args.figures_dir)]

    shap_top = shap_shares = None
    if args.shap_per_family > 0:
        shap_top, shap_shares = shap_by_family(model, X, y, names, families, args.shap_per_family,
                                               index=index, random_state=args.random_state)
        if shap_top is None:
            print(f"SHAP sauté : pour un modèle {type(model).__name__}, installez le paquet shap "
                  "(python -m pip install shap), puis relancez.")
        else:
            shap_top.to_csv(args.results_dir / "shap_top_par_famille.csv", index=False)
            shap_shares.round(2).to_csv(args.results_dir / "shap_groupes_par_famille.csv")
            counts = dict(zip(families, np.bincount(y, minlength=len(families)).tolist()))
            figures.append(plot_shap_groups(shap_shares, counts, args.figures_dir))

    ablation_table = None
    if args.ablation:
        ablation_table = ablation(model, data, feature_groups_of(names), args.ablation_trees)
        ablation_table.to_csv(args.results_dir / "ablation.csv", index=False)
        full_f1 = f1_scores(model, np.asarray(data.X_test), data.y_test, list(range(len(families))))[0]
        figures.append(plot_ablation(ablation_table, full_f1, args.figures_dir))

    info = {"dataset": str(path), "dataset_created": data.info.get("created"), "model": str(args.model),
            "model_type": type(model).__name__, "n_test_rows": int(len(y)),
            "sampled": bool(len(rows) < len(data.y_test)), "n_repeats": args.n_repeats, "top": args.top,
            "random_state": args.random_state, "scoring": "f1_macro",
            "baseline_f1_macro": float(baseline_f1),
            "baseline_f1_per_family": dict(zip(families, map(float, baseline_family))),
            "agreement_with_predictions_test": agreement, "hash_index": index is not None,
            "confused_pairs": [{"famille_reelle": a, "famille_predite": b, "n": n} for a, b, n in pairs],
            "native_importance": native_label,
            "shap_per_family": args.shap_per_family if shap_top is not None else 0,
            "ablation": args.ablation, "ablation_trees": args.ablation_trees,
            "duration_seconds": round(time.perf_counter() - start, 1)}
    (args.results_dir / "importance_info.json").write_text(
        json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nF1 macro de référence : {baseline_f1:.4f}\nGroupes (baisse du F1 macro par permutation) :")
    for row in groups.itertuples():
        print(f"  {row.group:<16}{row.n_features:>5} col.  {row.perm_f1_drop_mean:+.4f} "
              f"± {row.perm_f1_drop_std:.4f}   {native_label} {row.mdi_sum:.3f}")
    print("Features les plus importantes :")
    for row in features.dropna(subset=["perm_f1_drop_mean"]).head(10).itertuples():
        print(f"  {row.perm_f1_drop_mean:+.4f}  {row.name}")
    if shap_top is not None:
        print("SHAP, indice principal de chaque famille :")
        for row in shap_top[shap_top.rang == 1].itertuples():
            print(f"  {row.famille:<14} {row.name}  ({row.part_pct:.0f} % de la contribution, "
                  f"{'pousse vers' if row.shap_mean > 0 else 'éloigne de'} la famille)")
    if ablation_table is not None:
        print("Ablation (F1 macro du test) :")
        print(ablation_table.pivot(index="group", columns="mode", values="test_f1_macro")
              .round(4).to_string())
    written = ["importances.csv", "importances_groupes.csv", "confusions_features.csv",
               "importance_info.json"] + (["ablation.csv"] if args.ablation else []) + (
        ["shap_top_par_famille.csv", "shap_groupes_par_famille.csv"] if shap_top is not None else [])
    print(f"\nÉcrits dans {args.results_dir} : {', '.join(written)}\nFigures : "
          + ", ".join(figure.name for figure in figures)
          + f"\n({info['duration_seconds']:.0f} s)")


if __name__ == "__main__":
    main()
