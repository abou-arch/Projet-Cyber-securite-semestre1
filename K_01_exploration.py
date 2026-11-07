"""Rôle A : exploration des données EMBER2024 (version de Kenneth).

À placer à la RACINE du projet (à côté de README.md), puis lancer :
    python K_01_exploration.py

Tout est enregistré dans results_kenneth/ (tableaux .csv + figures .png).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # enregistre les graphiques dans des fichiers, sans ouvrir de fenêtre
import matplotlib.pyplot as plt

from malware_family.dataset import load_dataset

DATA = Path.home() / "ember2024/processed/Win32_top10"
OUT = Path("results_kenneth")
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def titre(texte):
    print("\n" + "=" * 70 + "\n" + texte + "\n" + "=" * 70)


# ---------------------------------------------------------------- A.1 Charger
titre("A.1  Chargement et vérification")
data = load_dataset(DATA)
fam = list(data.families)
print("Train :", data.X_train.shape, "(fichiers, features)")
print("Test  :", data.X_test.shape)
print("Familles :", fam)
print("Colonnes des métadonnées :", data.meta_train.columns.tolist())

# ------------------------------------------------- A.2 Répartition des familles
titre("A.2  Nombre de fichiers par famille")
comptes = pd.DataFrame(
    {
        "train": np.bincount(data.y_train, minlength=len(fam)),
        "test": np.bincount(data.y_test, minlength=len(fam)),
    },
    index=fam,
)
comptes["part_test_%"] = (100 * comptes["test"] / comptes["test"].sum()).round(1)
print(comptes)
comptes.to_csv(OUT / "A_effectifs.csv")

ax = comptes[["train", "test"]].plot.barh(figsize=(9, 5))
ax.set_title("Nombre de fichiers par famille (train vs test)")
ax.set_xlabel("Nombre de fichiers")
plt.tight_layout()
plt.savefig(FIG / "A_effectifs.png", dpi=150)
plt.close()

# ------------------------------------ A.3 Temps et qualité des étiquettes
titre("A.3  Évolution dans le temps et confiance des étiquettes")
meta = pd.concat(
    [data.meta_train.assign(jeu="train"), data.meta_test.assign(jeu="test")],
    ignore_index=True,
)
col_date = next((c for c in meta.columns if "date" in c.lower()), None)
col_conf = next((c for c in meta.columns if "conf" in c.lower()), None)
col_fam = next((c for c in meta.columns if c.lower() in ("family", "famille")), None)
print("Colonne date :", col_date, "| confiance :", col_conf, "| famille :", col_fam)

if col_date and col_fam:
    d = meta[col_date]
    if np.issubdtype(d.dtype, np.number):
        meta["date"] = pd.to_datetime(d, unit="s")  # timestamp Unix -> date
    else:
        meta["date"] = pd.to_datetime(d)
    par_mois = meta.groupby([meta["date"].dt.to_period("M"), col_fam]).size().unstack(fill_value=0)
    print(par_mois)
    par_mois.to_csv(OUT / "A_par_mois.csv")
    ax = par_mois.plot(figsize=(11, 5), marker="o")
    ax.set_title("Fichiers par mois et par famille (train puis test)")
    ax.set_xlabel("Mois")
    ax.set_ylabel("Nombre de fichiers")
    plt.tight_layout()
    plt.savefig(FIG / "A_temps.png", dpi=150)
    plt.close()
else:
    print("Colonne de date ou de famille introuvable : étape sautée.")

if col_conf and col_fam:
    resume = meta.groupby(col_fam)[col_conf].describe().round(3)
    print(resume)
    resume.to_csv(OUT / "A_confiance.csv")
    meta.boxplot(column=col_conf, by=col_fam, rot=45, figsize=(11, 5))
    plt.suptitle("")
    plt.title("Confiance de ClarAVy dans le nom de famille")
    plt.tight_layout()
    plt.savefig(FIG / "A_confiance.png", dpi=150)
    plt.close()
else:
    print("Colonne de confiance introuvable : étape sautée.")

# ----------------------------------------------- A.4 Portrait de chaque famille
titre("A.4  Portrait médian de chaque famille (groupe 'general')")
noms = list(data.feature_names)
general = [n for n in noms if n.startswith("general")]
idx = [noms.index(n) for n in general]
df = pd.DataFrame(data.X_train[:, idx], columns=general)
df["famille"] = [fam[i] for i in data.y_train]
portrait = df.groupby("famille").median().round(2)
print(portrait.T)
portrait.to_csv(OUT / "A_portrait_general.csv")

titre("A.4 bis  Colonnes par groupe et colonnes constantes (inutiles)")
groupe = pd.Series([n.split("_")[0] for n in noms], name="groupe")
constantes = pd.Series(data.X_train.std(axis=0) == 0)
bilan = pd.DataFrame(
    {"colonnes": groupe.value_counts(), "constantes": constantes.groupby(groupe).sum()}
).sort_values("colonnes", ascending=False)
print(bilan)
print("Total colonnes constantes :", int(constantes.sum()), "sur", len(noms))
bilan.to_csv(OUT / "A_groupes_constantes.csv")

titre("Terminé")
print("Résultats enregistrés dans :", OUT.resolve())
for f in sorted(OUT.rglob("A_*")):
    print("  ", f)
