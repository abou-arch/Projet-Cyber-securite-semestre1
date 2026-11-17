"""Phase 3 du rôle B : évaluation approfondie du modèle final.

Le script part du modèle choisi en phase 2 par ``scripts/train.py``
(``models/best_model.joblib``) et du jeu préparé par ``malware_family.prepare``
(trouvé par ``find_dataset()`` : variable ``EMBER_DATASET`` ou dossiers conseillés).
Il ne choisit plus de modèle : il l'analyse. Écrit par Bryce (rôle B), intégré sur la
branche Abou. Étapes (plan/role_B_modeles_evaluation.txt, phase 3) :

* ``confusion``  : matrice de confusion normalisée (quelles familles sont confondues ?) ;
* ``effectifs``  : F1 par famille en fonction du nombre d'exemples d'entraînement ;
* ``derive``     : F1 macro semaine par semaine sur le test (dérive temporelle) ;
* ``bruit``      : réentraînement sur la variante ``--min-confidence 0.5`` (bruit des étiquettes) ;
* ``stabilite``  : 3 valeurs de random_state -> moyenne et écart-type des scores ;
* ``reduit``     : modèle réduit aux groupes / features les plus importants selon C ;
* ``rejet``      : (bonus) réponse « inconnu » sous un seuil de probabilité, précision / couverture.

Lancement, depuis la racine du projet (après ``python -m scripts.train``) :

    python -m scripts.evaluate                              # toutes les étapes
    python -m scripts.evaluate --etapes confusion derive    # seulement certaines étapes
    python -m scripts.evaluate --data-dir C:\\ember2024\\processed\\Win32_top10

Sorties (toutes préfixées B_ pour les figures) :

* ``results/evaluation.json``            : tous les chiffres de la phase 3 (mis à jour étape par étape) ;
* ``results/predictions_test_proba.csv`` : sha256, date, famille réelle / prédite, probabilité maximale ;
* ``results/f1_par_famille.csv``, ``results/score_par_semaine.csv``, ``results/stabilite.csv``,
  ``results/modele_reduit.csv``, ``results/rejet.csv`` ;
* ``results/figures/B_*.png``.

Les étapes ``bruit``, ``stabilite`` et ``reduit`` réentraînent le modèle (quelques minutes
chacune avec une forêt de 300 arbres). Le test n'est utilisé que pour mesurer : aucun
paramètre n'est réglé dessus.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import json
import time

import joblib
import matplotlib

matplotlib.use("Agg")  # figures enregistrées dans des fichiers, pas d'écran nécessaire

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, precision_recall_fscore_support)

from malware_family.dataset import find_dataset, load_dataset
from malware_family.ember_features import feature_groups
from malware_family.figures import CM, family_colors, new_figure, save_figure

# Variante à étiquettes sûres : par défaut, le dossier du jeu suivi de « _conf05 »
# (ex. C:\ember2024\processed\Win32_top10_conf05, commande de A dans le README, § 4.5).
VARIANT_SUFFIX = "_conf05"
RESULTS_DIR = ROOT / "results"
MODELS_DIR = ROOT / "models"

STEPS = ("confusion", "effectifs", "derive", "bruit", "stabilite", "reduit", "rejet")
MIN_TEST_SUPPORT = 30   # F1 macro « sans les petites familles » : au moins 30 fichiers du test
MIN_WEEK_SIZE = 50      # en dessous, le score d'une semaine est jugé peu fiable


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------

def log(message=""):
    print(message, flush=True)


def scores(y_true, y_pred, labels):
    """Les trois métriques du plan (F1 macro = métrique principale)."""
    return {
        "f1_macro": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
    }


def predict_with_proba(model, X):
    """Famille prédite et probabilité maximale de chaque ligne."""
    proba = model.predict_proba(X)
    classes = np.asarray(model.classes_)
    return classes[proba.argmax(axis=1)], proba.max(axis=1)


def with_random_state(model, seed):
    """Copie non entraînée du modèle, avec une autre graine si le modèle en a une."""
    model = clone(model)
    if "random_state" in model.get_params():
        model.set_params(random_state=seed)
    return model


def fit_timed(model, X, y):
    start = time.time()
    model.fit(X, y)
    return round(time.time() - start, 2)


def update_json(path, key, value):
    """Écrit ``value`` sous ``key`` dans le JSON, sans effacer les autres étapes déjà calculées."""
    content = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    content[key] = value
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_dates(data):
    dates = pd.to_datetime(data.meta_test["first_seen"], errors="coerce")
    if dates.isna().any():
        raise ValueError(f"{int(dates.isna().sum())} dates first_seen invalides dans meta_test.csv.")
    return dates


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------

def step_confusion(ctx):
    """Matrice de confusion normalisée par ligne (rappel de chaque famille sur la diagonale)."""
    data, families = ctx["data"], ctx["data"].families
    labels = np.arange(len(families))
    fig, ax = new_figure(height=14 * CM)
    ConfusionMatrixDisplay.from_predictions(
        data.y_test, ctx["y_pred"], labels=labels, display_labels=families,
        normalize="true", values_format=".2f", xticks_rotation=60, cmap="Blues",
        colorbar=False, ax=ax, text_kw={"fontsize": 7})
    ax.grid(False)
    ax.set_title("Matrice de confusion normalisée (test)")
    ax.set_xlabel("Famille prédite")
    ax.set_ylabel("Famille réelle")
    path = save_figure(fig, "B_matrice_confusion", directory=ctx["figures_dir"])

    # Paires les plus confondues (en nombre de fichiers), à expliquer avec C.
    counts = confusion_matrix(data.y_test, ctx["y_pred"], labels=labels)
    rates = counts / np.maximum(counts.sum(axis=1, keepdims=True), 1)
    pairs = [{"famille_reelle": families[i], "famille_predite": families[j],
              "n": int(counts[i, j]), "part_de_la_famille": round(float(rates[i, j]), 4)}
             for i in labels for j in labels if i != j and counts[i, j] > 0]
    pairs.sort(key=lambda p: -p["n"])
    log(f"  Figure : {path}")
    for p in pairs[:5]:
        log(f"  {p['famille_reelle']:>14} -> {p['famille_predite']:<14} "
            f"{p['n']:>5} fichiers ({100 * p['part_de_la_famille']:.1f} % de la famille)")
    return {"figure": path.name, "paires_confondues": pairs[:15]}


def step_effectifs(ctx):
    """F1 de chaque famille en fonction de son nombre d'exemples d'entraînement."""
    data, families = ctx["data"], ctx["data"].families
    labels = np.arange(len(families))
    precision, recall, f1, support = precision_recall_fscore_support(
        data.y_test, ctx["y_pred"], labels=labels, zero_division=0)
    table = pd.DataFrame({
        "famille": families,
        "n_train": np.bincount(data.y_train, minlength=len(families)),
        "n_test": support,
        "precision": precision, "rappel": recall, "f1": f1,
    })
    table.to_csv(ctx["results_dir"] / "f1_par_famille.csv", index=False, encoding="utf-8")

    colors = family_colors(families)
    fig, ax = new_figure()
    for row in table.itertuples():
        ax.scatter(row.n_train, row.f1, s=20 + 80 * np.sqrt(row.n_test / max(table.n_test.max(), 1)),
                   color=colors[row.famille], zorder=3)
        ax.annotate(row.famille, (row.n_train, row.f1), textcoords="offset points", xytext=(4, 3),
                    fontsize=8)
    ax.set_xscale("log")
    ax.set_ylim(min(0.0, table.f1.min() - 0.05), 1.05)
    ax.set_xlabel("Exemples d'entraînement (échelle log)")
    ax.set_ylabel("F1 sur le test")
    ax.set_title("F1 par famille selon la taille de son train (taille du point : effectif du test)")
    path = save_figure(fig, "B_f1_par_famille_effectifs", directory=ctx["figures_dir"])

    # Corrélation de rang : les familles plus fournies sont-elles mieux reconnues ?
    rho = table[["n_train", "f1"]].rank().corr().iloc[0, 1]
    small = table.n_test < MIN_TEST_SUPPORT
    kept = labels[~small.to_numpy()]
    f1_without_small = f1_score(data.y_test, ctx["y_pred"], labels=kept, average="macro",
                                zero_division=0) if len(kept) else float("nan")
    log(f"  Figure : {path}")
    log(f"  Corrélation de Spearman (n_train, F1) : {rho:.2f}")
    if small.any():
        log(f"  Familles de moins de {MIN_TEST_SUPPORT} fichiers du test : "
            + ", ".join(table.famille[small]) + f" ; F1 macro sans elles : {f1_without_small:.4f}")
    return {"figure": path.name, "fichier": "f1_par_famille.csv",
            "spearman_ntrain_f1": None if np.isnan(rho) else round(float(rho), 4),
            "familles_moins_de_30_test": list(table.famille[small]),
            "f1_macro_sans_petites_familles": round(float(f1_without_small), 4),
            "par_famille": table.round(4).to_dict(orient="records")}


def step_derive(ctx):
    """F1 macro semaine par semaine sur le test (dates first_seen)."""
    data = ctx["data"]
    dates = test_dates(data)
    weeks = dates.dt.to_period("W-SUN").dt.start_time  # semaines du lundi au dimanche
    rows = []
    for week in sorted(weeks.unique()):
        mask = (weeks == week).to_numpy()
        y_true, y_pred = data.y_test[mask], ctx["y_pred"][mask]
        present = np.unique(y_true)  # familles présentes cette semaine
        rows.append({
            "semaine": pd.Timestamp(week).strftime("%Y-%m-%d"),
            "n": int(mask.sum()),
            "n_familles": int(len(present)),
            "f1_macro": float(f1_score(y_true, y_pred, labels=present, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "fiable": bool(mask.sum() >= MIN_WEEK_SIZE),
        })
    table = pd.DataFrame(rows)
    table.to_csv(ctx["results_dir"] / "score_par_semaine.csv", index=False, encoding="utf-8")

    # Tendance : pente d'une droite ajustée sur les semaines fiables (points de F1 par semaine).
    reliable = table[table.fiable]
    slope = float(np.polyfit(np.arange(len(reliable)), reliable.f1_macro, 1)[0]) if len(reliable) >= 2 \
        else float("nan")

    fig, ax = new_figure()
    x = pd.to_datetime(table.semaine)
    ax.plot(x, table.f1_macro, marker="o", label="F1 macro")
    ax.plot(x, table.accuracy, marker="s", linestyle="--", label="Exactitude")
    unreliable = table[~table.fiable]
    if len(unreliable):
        ax.scatter(pd.to_datetime(unreliable.semaine), unreliable.f1_macro, s=80, facecolors="none",
                   edgecolors="red", zorder=4, label=f"< {MIN_WEEK_SIZE} fichiers")
    ax2 = ax.twinx()
    ax2.bar(x, table.n, width=5, alpha=0.15, color="grey")
    ax2.set_ylabel("Fichiers du test")
    ax2.grid(False)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Semaine de première soumission")
    ax.set_ylabel("Score")
    ax.set_title("Dérive temporelle : scores par semaine sur le test")
    ax.legend(loc="lower left")
    fig.autofmt_xdate()
    path = save_figure(fig, "B_score_par_semaine", directory=ctx["figures_dir"])
    log(f"  Figure : {path}")
    log(f"  {len(table)} semaines ; pente du F1 macro : {slope:+.4f} par semaine")
    return {"figure": path.name, "fichier": "score_par_semaine.csv",
            "pente_f1_macro_par_semaine": None if np.isnan(slope) else round(slope, 5),
            "premiere_semaine": rows[0] if rows else None, "derniere_semaine": rows[-1] if rows else None}


def step_bruit(ctx):
    """Même modèle, réentraîné sur la variante à étiquettes sûres (--min-confidence 0.5)."""
    data, variant_dir = ctx["data"], ctx["variant_dir"]
    if not (variant_dir / "dataset_info.json").is_file():
        log(f"  Variante introuvable : {variant_dir}")
        log("  Préparez-la avec la commande de A, par exemple :")
        log(f"    python -m malware_family.prepare --min-confidence 0.5 --out-dir {variant_dir}")
        return {"statut": "variante absente", "variante": str(variant_dir)}
    variant = load_dataset(variant_dir)
    log(f"  Variante : {variant_dir} (train {variant.X_train.shape[0]}, test {variant.X_test.shape[0]})")

    reference = ctx["reference_scores"]
    model = with_random_state(ctx["model"], ctx["base_seed"])
    duration = fit_timed(model, variant.X_train, variant.y_train)
    result = {
        "variante": str(variant_dir),
        "min_confidence": variant.info.get("min_confidence"),
        "n_train": {"base": int(len(data.y_train)), "variante": int(len(variant.y_train))},
        "familles_identiques": list(variant.families) == list(data.families),
        "duree_entrainement_s": duration,
        "base_sur_test_base": reference,
    }
    # 1) Sur le test de la variante (étiquettes sûres aussi dans le test).
    labels_v = np.arange(len(variant.families))
    result["variante_sur_test_variante"] = scores(variant.y_test, model.predict(variant.X_test), labels_v)
    # 2) Sur le test de base, même évaluation que le modèle de référence (si mêmes familles).
    if result["familles_identiques"]:
        labels = np.arange(len(data.families))
        result["variante_sur_test_base"] = scores(data.y_test, model.predict(data.X_test), labels)
        # 3) Et le modèle de base sur le test à étiquettes sûres.
        result["base_sur_test_variante"] = scores(variant.y_test, ctx["model"].predict(variant.X_test),
                                                  labels_v)
    else:
        log("  Attention : la variante ne retient pas les mêmes 10 familles ; "
            "seule la comparaison sur son propre test est faite.")

    table = pd.DataFrame({k: v for k, v in result.items() if k.endswith(("_base", "_variante"))
                          and isinstance(v, dict)}).T
    log(table.round(4).to_string())
    fig, ax = new_figure()
    table.rename(columns={"f1_macro": "F1 macro", "accuracy": "Exactitude",
                          "balanced_accuracy": "Exactitude équilibrée"}).plot(kind="bar", ax=ax, rot=0)
    ax.set_xticks(range(len(table)), [name.replace("_sur_", "\nsur ").replace("_", " ")
                                      for name in table.index])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Bruit des étiquettes : jeu de base et variante confiance ≥ 0,5")
    ax.legend(loc="lower right")
    path = save_figure(fig, "B_bruit_etiquettes", directory=ctx["figures_dir"])
    log(f"  Figure : {path}")
    result["figure"] = path.name
    return result


def step_stabilite(ctx):
    """Réentraîne le modèle avec plusieurs graines : les scores varient-ils ?"""
    data = ctx["data"]
    labels = np.arange(len(data.families))
    rows = []
    for seed in ctx["random_states"]:
        model = with_random_state(ctx["model"], seed)
        duration = fit_timed(model, data.X_train, data.y_train)
        row = {"random_state": seed, **scores(data.y_test, model.predict(data.X_test), labels),
               "duree_entrainement_s": duration}
        rows.append(row)
        log(f"  random_state={seed} : F1 macro {row['f1_macro']:.4f} ({duration:.0f} s)")
    table = pd.DataFrame(rows)
    table.to_csv(ctx["results_dir"] / "stabilite.csv", index=False, encoding="utf-8")
    summary = {metric: {"moyenne": float(table[metric].mean()),
                        "ecart_type": float(table[metric].std(ddof=1)) if len(table) > 1 else 0.0}
               for metric in ("f1_macro", "accuracy", "balanced_accuracy", "duree_entrainement_s")}
    log(f"  F1 macro : {summary['f1_macro']['moyenne']:.4f} ± {summary['f1_macro']['ecart_type']:.4f}")
    ctx["full_duration"] = summary["duree_entrainement_s"]["moyenne"]
    return {"fichier": "stabilite.csv", "par_graine": rows, "resume": summary}


def importance_ranking(ctx):
    """Classement des groupes et des features : résultats de C s'ils existent, sinon MDI du modèle.

    Fichiers de C (scripts/importance.py) : results/importances_groupes.csv (colonnes ``group``
    et ``perm_f1_drop_mean``) et results/importances.csv (``feature``, ``perm_f1_drop_mean``).
    """
    groups_csv = ctx["results_dir"] / "importances_groupes.csv"
    features_csv = ctx["results_dir"] / "importances.csv"
    names = list(ctx["data"].feature_names)
    if groups_csv.is_file():
        table = pd.read_csv(groups_csv)
        column = "perm_f1_drop_mean" if "perm_f1_drop_mean" in table else table.columns[-1]
        groups = list(table.sort_values(column, ascending=False)["group"])
        source = f"C ({groups_csv.name}, {column})"
    else:
        groups = None
        source = None
    features = None
    if features_csv.is_file():
        table = pd.read_csv(features_csv)
        # Permutation d'abord (calculée pour les 50 meilleures seulement), puis importance interne.
        columns = [c for c in ("perm_f1_drop_mean", "mdi") if c in table]
        if columns:
            order = table.sort_values(columns, ascending=False, na_position="last", kind="mergesort")
            features = [f for f in order["feature"] if f in names]
    if groups is None or features is None:
        importances = getattr(ctx["model"], "feature_importances_", None)
        if importances is None:
            raise SystemExit("Pas de résultats de C dans results/ et le modèle n'a pas de "
                             "feature_importances_ : indiquez les groupes avec --groupes.")
        if groups is None:
            by_group = {g: float(importances[s].sum()) for g, s in feature_groups().items()}
            groups = sorted(by_group, key=by_group.get, reverse=True)
            source = "MDI du modèle final (résultats de C absents de results/)"
        if features is None:
            features = [names[j] for j in np.argsort(importances)[::-1]]
    return groups, features, source


def step_reduit(ctx):
    """Modèles réduits aux groupes / features les plus importants : score et temps d'entraînement."""
    data = ctx["data"]
    labels = np.arange(len(data.families))
    names = list(data.feature_names)
    slices = feature_groups()
    ranked_groups, ranked_features, source = importance_ranking(ctx)
    log(f"  Classement utilisé : {source}")

    configs = []
    if ctx["groups"]:
        unknown = set(ctx["groups"]) - set(slices)
        if unknown:
            raise SystemExit(f"Groupes inconnus : {', '.join(sorted(unknown))} "
                             f"(groupes : {', '.join(slices)})")
        configs.append(("groupes : " + "+".join(ctx["groups"]), ctx["groups"], None))
    for k in ctx["top_groups"]:
        configs.append((f"top {k} groupe(s) : " + "+".join(ranked_groups[:k]), ranked_groups[:k], None))
    for n in ctx["top_features"]:
        configs.append((f"top {n} features", None, ranked_features[:n]))

    if ctx.get("full_duration") is None:  # temps du modèle complet, mesuré dans les mêmes conditions
        model = with_random_state(ctx["model"], ctx["base_seed"])
        ctx["full_duration"] = fit_timed(model, data.X_train, data.y_train)
    rows = [{"modele": "complet", "n_features": len(names), **ctx["reference_scores"],
             "duree_entrainement_s": ctx["full_duration"]}]
    for name, groups, features in configs:
        if groups is not None:
            columns = np.concatenate([np.arange(len(names))[slices[g]] for g in groups])
        else:
            columns = np.array([names.index(f) for f in features])
        columns = np.sort(columns)
        model = with_random_state(ctx["model"], ctx["base_seed"])
        if "categorical_features" in model.get_params():
            model.set_params(categorical_features=None)  # les indices ne correspondent plus
        X_train = np.asarray(data.X_train[:, columns])
        duration = fit_timed(model, X_train, data.y_train)
        del X_train
        row = {"modele": name, "n_features": int(len(columns)),
               **scores(data.y_test, model.predict(np.asarray(data.X_test[:, columns])), labels),
               "duree_entrainement_s": duration}
        rows.append(row)
        log(f"  {name:<55} {len(columns):>5} col. F1 macro {row['f1_macro']:.4f} ({duration:.0f} s)")
    table = pd.DataFrame(rows)
    table["perte_f1_macro"] = table.f1_macro.iloc[0] - table.f1_macro
    table["gain_temps"] = 1 - table.duree_entrainement_s / max(table.duree_entrainement_s.iloc[0], 1e-9)
    table.to_csv(ctx["results_dir"] / "modele_reduit.csv", index=False, encoding="utf-8")

    fig, (ax1, ax2) = new_figure(height=10 * CM, ncols=2, sharey=True)
    y = np.arange(len(table))
    ax1.barh(y, table.f1_macro, color="C0")
    ax1.set_xlim(0, 1.05)
    ax1.set_xlabel("F1 macro (test)")
    ax1.set_yticks(y, [f"{m} ({n} col.)" for m, n in zip(table.modele, table.n_features)], fontsize=7)
    ax1.invert_yaxis()
    ax2.barh(y, table.duree_entrainement_s, color="C1")
    ax2.set_xlabel("Entraînement (s)")
    fig.suptitle("Modèle réduit aux groupes ou features les plus importants")
    path = save_figure(fig, "B_modele_reduit", directory=ctx["figures_dir"])
    log(f"  Figure : {path}")
    return {"figure": path.name, "fichier": "modele_reduit.csv", "source_importance": source,
            "resultats": table.round(4).to_dict(orient="records")}


def step_rejet(ctx):
    """(Bonus) « inconnu » sous un seuil de probabilité : précision selon la couverture."""
    data = ctx["data"]
    y_true, y_pred, proba = data.y_test, ctx["y_pred"], ctx["proba_max"]
    labels = np.arange(len(data.families))
    rows = []
    for threshold in np.round(np.arange(0.0, 1.0, 0.05), 2).tolist() + [0.95, 0.99]:
        accepted = proba >= threshold
        n = int(accepted.sum())
        rows.append({
            "seuil": threshold,
            "couverture": n / len(y_true) if len(y_true) else 0.0,
            "precision": float(accuracy_score(y_true[accepted], y_pred[accepted])) if n else float("nan"),
            "f1_macro_acceptes": float(f1_score(y_true[accepted], y_pred[accepted], labels=labels,
                                                average="macro", zero_division=0)) if n else float("nan"),
            "n_acceptes": n,
        })
    table = pd.DataFrame(rows).drop_duplicates("seuil")
    table.to_csv(ctx["results_dir"] / "rejet.csv", index=False, encoding="utf-8")

    fig, ax = new_figure()
    ax.plot(table.couverture, table.precision, marker="o", markersize=3)
    for row in table[table.seuil.isin([0.5, 0.7, 0.9])].itertuples():
        ax.annotate(f"seuil {row.seuil:.1f}", (row.couverture, row.precision),
                    textcoords="offset points", xytext=(-10, -14), fontsize=8)
    ax.set_xlim(0, 1.02)
    ax.invert_xaxis()  # de gauche à droite : on rejette de plus en plus
    ax.set_xlabel("Couverture (part des fichiers auxquels le modèle répond)")
    ax.set_ylabel("Précision sur les réponses données")
    ax.set_title("Rejet des prédictions incertaines (« inconnu » sous le seuil)")
    path = save_figure(fig, "B_rejet_couverture", directory=ctx["figures_dir"])
    errors = y_true != y_pred
    log(f"  Figure : {path}")
    log(f"  Probabilité max. moyenne : {proba[~errors].mean():.3f} (justes) / "
        + (f"{proba[errors].mean():.3f} (erreurs)" if errors.any() else "aucune erreur"))
    return {"figure": path.name, "fichier": "rejet.csv",
            "proba_max_moyenne_justes": float(proba[~errors].mean()) if (~errors).any() else None,
            "proba_max_moyenne_erreurs": float(proba[errors].mean()) if errors.any() else None,
            "courbe": table.round(4).to_dict(orient="records")}


STEP_FUNCTIONS = {
    "confusion": step_confusion, "effectifs": step_effectifs, "derive": step_derive,
    "bruit": step_bruit, "stabilite": step_stabilite, "reduit": step_reduit, "rejet": step_rejet,
}


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m scripts.evaluate",
        description="Phase 3 (rôle B) : évaluation approfondie du modèle final.")
    parser.add_argument("--data-dir", type=Path, default=None,
                        help="jeu préparé (défaut : find_dataset(), variable EMBER_DATASET ou dossiers "
                             "conseillés)")
    parser.add_argument("--variante-dir", type=Path, default=None,
                        help="variante --min-confidence 0.5 pour l'étape bruit "
                             f"(défaut : dossier du jeu suivi de {VARIANT_SUFFIX})")
    parser.add_argument("--modele", type=Path, default=MODELS_DIR / "best_model.joblib",
                        help="modèle final de la phase 2 (défaut : models/best_model.joblib)")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR,
                        help="dossier des résultats (défaut : results/)")
    parser.add_argument("--figures-dir", type=Path, default=None,
                        help="dossier des figures (défaut : <results-dir>/figures)")
    parser.add_argument("--etapes", nargs="+", choices=STEPS, default=list(STEPS),
                        help="étapes à lancer (défaut : toutes)")
    parser.add_argument("--random-states", nargs="+", type=int, default=[0, 1, 2],
                        help="graines pour l'étape stabilite (défaut : 0 1 2)")
    parser.add_argument("--groupes", nargs="+", default=None,
                        help="groupes de features d'un modèle réduit choisi à la main (ex. header section)")
    parser.add_argument("--top-groupes", nargs="*", type=int, default=[1, 3],
                        help="modèles réduits aux k groupes les plus importants (défaut : 1 3)")
    parser.add_argument("--top-features", nargs="*", type=int, default=[100],
                        help="modèles réduits aux n features les plus importantes (défaut : 100)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    results_dir = args.results_dir.expanduser()
    figures_dir = (args.figures_dir or results_dir / "figures").expanduser()
    results_dir.mkdir(parents=True, exist_ok=True)

    log("Script evaluate.py (phase 3, rôle B) démarré")
    if not args.modele.is_file():
        raise SystemExit(f"Modèle introuvable : {args.modele}\n"
                         "Lancez d'abord la phase 2 : python -m scripts.train")
    try:
        data_dir = args.data_dir.expanduser() if args.data_dir else find_dataset(ROOT)
    except FileNotFoundError as error:
        raise SystemExit(str(error))
    variant_dir = (args.variante_dir.expanduser() if args.variante_dir
                   else data_dir.parent / f"{data_dir.name}{VARIANT_SUFFIX}")
    log(f"Chargement du dataset : {data_dir}")
    try:
        data = load_dataset(data_dir)
    except (FileNotFoundError, ValueError) as error:
        raise SystemExit(str(error))
    log(f"Train : {data.X_train.shape} ; test : {data.X_test.shape}")
    log(f"Chargement du modèle : {args.modele}")
    model = joblib.load(args.modele)
    log(f"Modèle : {type(model).__name__}")

    labels = np.arange(len(data.families))
    y_pred, proba_max = predict_with_proba(model, data.X_test)
    reference = scores(data.y_test, y_pred, labels)
    log(f"Scores du modèle final sur le test : {reference}")

    # Prédictions détaillées (probabilité maximale), utiles à C et à la démo.
    predictions = pd.DataFrame({
        "sha256": data.meta_test["sha256"].to_numpy(),
        "first_seen": data.meta_test["first_seen"].to_numpy(),
        "y_true": data.y_test, "y_pred": y_pred,
        "famille_reelle": [data.families[int(i)] for i in data.y_test],
        "famille_predite": [data.families[int(i)] for i in y_pred],
        "proba_max": np.round(proba_max, 5),
    })
    predictions.to_csv(results_dir / "predictions_test_proba.csv", index=False, encoding="utf-8")

    # Cohérence avec la phase 2 : mêmes prédictions que results/predictions_test.csv ?
    agreement = None
    previous = results_dir / "predictions_test.csv"
    if previous.is_file():
        old = pd.read_csv(previous)
        if len(old) == len(predictions) and "y_pred" in old:
            agreement = float((old["y_pred"].to_numpy() == y_pred).mean())
            log(f"Accord avec predictions_test.csv (phase 2) : {100 * agreement:.2f} %")
            if agreement < 0.99:
                log("  Attention : le modèle ou le jeu de données ne sont pas ceux de la phase 2.")

    evaluation_json = results_dir / "evaluation.json"
    update_json(evaluation_json, "contexte", {
        "dataset": str(data_dir), "dataset_cree": data.info.get("created"),
        "modele": str(args.modele), "type_modele": type(model).__name__,
        "familles": list(data.families), "n_train": int(len(data.y_train)),
        "n_test": int(len(data.y_test)), "scores_test": reference,
        "accord_avec_predictions_test": agreement,
    })

    base_seed = model.get_params().get("random_state", 0)
    ctx = {
        "data": data, "model": model, "y_pred": y_pred, "proba_max": proba_max,
        "reference_scores": reference, "base_seed": base_seed if base_seed is not None else 0,
        "results_dir": results_dir, "figures_dir": figures_dir, "variant_dir": variant_dir,
        "random_states": args.random_states, "groups": args.groupes,
        "top_groups": args.top_groupes, "top_features": args.top_features, "full_duration": None,
    }
    for step in STEPS:  # toujours le même ordre (stabilite mesure le temps utilisé par reduit)
        if step not in args.etapes:
            continue
        log(f"\n=== Étape {step} ===")
        start = time.time()
        result = STEP_FUNCTIONS[step](ctx)
        result["duree_etape_s"] = round(time.time() - start, 2)
        update_json(evaluation_json, step, result)

    log(f"\nTerminé. Résultats : {evaluation_json}")
    log(f"Figures : {figures_dir}")


if __name__ == "__main__":
    main()
