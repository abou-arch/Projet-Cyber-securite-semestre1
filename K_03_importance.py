"""Rôle C : importance des features (version de Kenneth).
Lancer : python K_03_importance.py
"""
from pathlib import Path
import joblib
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("results_kenneth")
(OUT / "figures").mkdir(parents=True, exist_ok=True)

# --- C1 : charger le modèle entraîné en B ---
pack = joblib.load("models/K_lightgbm.joblib")
modele, noms, familles = pack["modele"], pack["features"], pack["familles"]
print("Modèle chargé :", len(noms), "features,", len(familles), "familles")
print("Exemples de noms :", noms[:10])
print("Exemples de noms :", noms[1000:1010])

# --- C2 : importance native (gain) ---
gain = modele.booster_.feature_importance(importance_type="gain")
imp = pd.DataFrame({"feature": noms, "gain": gain})
imp["gain_pct"] = 100 * imp["gain"] / imp["gain"].sum()
imp = imp.sort_values("gain", ascending=False)
imp.to_csv(OUT / "C_importance_gain.csv", index=False)

print(f"\nFeatures jamais utilisées : {(imp['gain'] == 0).sum()} sur {len(imp)}")
print(f"Part du gain des 20 premières : {imp['gain_pct'].head(20).sum():.1f} %")
print(imp.head(20).to_string(index=False))

top = imp.head(20).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(top["feature"], top["gain_pct"])
ax.set_xlabel("Part du gain total (%)")
ax.set_title("Top 20 des features (LightGBM, gain)")
fig.tight_layout()
fig.savefig(OUT / "figures/C_top20_gain.png", dpi=150)
# --- C3 : regrouper les features par type (préfixe du nom) ---
imp["groupe"] = imp["feature"].str.split("_").str[0]
groupes = (imp.groupby("groupe")
              .agg(nb_features=("feature", "size"),
                   inutilisees=("gain", lambda g: int((g == 0).sum())),
                   gain_pct=("gain_pct", "sum"))
              .sort_values("gain_pct", ascending=False).round(2))
groupes.to_csv(OUT / "C_importance_groupes.csv")
print("\n", groupes.to_string())

# --- C4 : importance par permutation de groupe (mesurée sur le TEST) ---
import numpy as np
from sklearn.metrics import f1_score

DATA = Path.home() / "ember2024/processed/Win32_top10"
X_te = np.load(DATA / "X_test.npy")[:, ~pack["constantes"]]
y_te = np.load(DATA / "y_test.npy")
ref = f1_score(y_te, modele.predict(X_te), average="macro")
print(f"\nF1 macro de référence : {ref:.3f}")

groupe_col = np.array([n.split("_")[0] for n in noms])
rng = np.random.default_rng(0)
lignes = []
for g in groupes.index:
    cols = np.where(groupe_col == g)[0]
    baisses = []
    for _ in range(3):
        Xp = X_te.copy()
        perm = rng.permutation(len(Xp))
        Xp[:, cols] = X_te[np.ix_(perm, cols)]
        baisses.append(ref - f1_score(y_te, modele.predict(Xp), average="macro"))
    lignes.append({"groupe": g, "baisse_f1_macro": round(float(np.mean(baisses)), 4)})
    print(f"{g:20s} -> baisse du F1 macro : {np.mean(baisses):.4f}")

perm_df = pd.DataFrame(lignes).sort_values("baisse_f1_macro", ascending=False)
perm_df.to_csv(OUT / "C_permutation_groupes.csv", index=False)

fig, ax = plt.subplots(figsize=(8, 5))
d = perm_df.iloc[::-1]
ax.barh(d["groupe"], d["baisse_f1_macro"])
ax.set_xlabel("Baisse du F1 macro quand le groupe est mélangé")
ax.set_title("Importance par permutation, par type de feature (test)")
fig.tight_layout()
fig.savefig(OUT / "figures/C_permutation_groupes.png", dpi=150)
# --- C5 : quels indices pour quelle famille ? (SHAP natif de LightGBM, sur le test) ---
F = len(noms)
lignes_fam, groupes_fam = [], {}
for k, fam in enumerate(familles):
    idx = np.where(y_te == k)[0][:300]          # 300 fichiers max par famille
    contrib = modele.predict(X_te[idx], pred_contrib=True)
    bloc = np.abs(contrib[:, k * (F + 1): k * (F + 1) + F]).mean(axis=0)
    top5 = np.argsort(bloc)[::-1][:5]
    for r, j in enumerate(top5, 1):
        lignes_fam.append({"famille": fam, "rang": r, "feature": noms[j],
                           "groupe": groupe_col[j],
                           "contribution": round(float(bloc[j]), 4)})
    parts = pd.Series(bloc, index=groupe_col).groupby(level=0).sum()
    groupes_fam[fam] = (100 * parts / parts.sum()).round(1)
    print(f"\n{fam} ({len(idx)} fichiers) : " + ", ".join(noms[j] for j in top5[:3]))

pd.DataFrame(lignes_fam).to_csv(OUT / "C_top5_par_famille.csv", index=False)

heat = pd.DataFrame(groupes_fam).T
heat = heat[heat.mean().sort_values(ascending=False).index]
heat.to_csv(OUT / "C_groupes_par_famille.csv")
print("\nPart de chaque groupe (%) par famille :\n", heat.to_string())

fig, ax = plt.subplots(figsize=(11, 6))
im = ax.imshow(heat.values, cmap="Blues")
ax.set_xticks(range(heat.shape[1]))
ax.set_xticklabels(heat.columns, rotation=45, ha="right")
ax.set_yticks(range(heat.shape[0]))
ax.set_yticklabels(heat.index)
for i in range(heat.shape[0]):
    for j in range(heat.shape[1]):
        ax.text(j, i, f"{heat.values[i, j]:.0f}", ha="center", va="center", fontsize=8)
fig.colorbar(im, label="% de la contribution")
ax.set_title("Quels types d'indices pour quelle famille ? (SHAP, test)")
fig.tight_layout()
fig.savefig(OUT / "figures/C_groupes_par_famille.png", dpi=150)