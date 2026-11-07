"""Rôle B : classifieur de familles de malwares (version de Kenneth).
Lancer : python K_02_modele.py
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

DATA = Path.home() / "ember2024/processed/Win32_top10"
OUT = Path("results_kenneth")
OUT.mkdir(exist_ok=True)

# --- B1 : chargement ---
X_train = np.load(DATA / "X_train.npy")
X_test = np.load(DATA / "X_test.npy")
y_train = np.load(DATA / "y_train.npy")
y_test = np.load(DATA / "y_test.npy")
families = [l for l in (DATA / "families.txt").read_text().splitlines() if l.strip()]
feature_names = [l for l in (DATA / "feature_names.txt").read_text().splitlines() if l.strip()]
meta_train = pd.read_csv(DATA / "meta_train.csv")
meta_test = pd.read_csv(DATA / "meta_test.csv")

print("X_train :", X_train.shape, "| X_test :", X_test.shape)
print("Nb features :", len(feature_names))
print("Familles :", families)
print("Effectifs train :", np.bincount(y_train))
print("Effectifs test  :", np.bincount(y_test))
print("Colonnes meta :", list(meta_train.columns))

# --- B2 : retirer les features constantes (calculé sur le TRAIN seulement) ---
constantes = X_train.max(axis=0) == X_train.min(axis=0)
X_tr = X_train[:, ~constantes]
X_te = X_test[:, ~constantes]
noms = [n for n, c in zip(feature_names, constantes) if not c]
print(f"\nFeatures constantes retirées : {constantes.sum()} -> il en reste {X_tr.shape[1]}")

# --- B3 : baseline (le modèle « idiot » à battre) ---
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score

base = DummyClassifier(strategy="most_frequent").fit(X_tr, y_train)
p = base.predict(X_te)
print(f"Baseline : accuracy = {accuracy_score(y_test, p):.3f} | "
      f"F1 macro = {f1_score(y_test, p, average='macro'):.3f}")
# --- B4 : LightGBM ---
import time
import lightgbm as lgb

# Validation = les 10 % les plus RÉCENTS du train (on ne touche jamais au test)
dates = pd.to_datetime(meta_train["first_seen"], utc=True, errors="coerce")
val = (dates >= dates.quantile(0.9)).to_numpy()
print(f"\nTrain interne : {(~val).sum()} | Validation : {val.sum()}")

modele = lgb.LGBMClassifier(
objective="multiclass", n_estimators=1000, learning_rate=0.1,
num_leaves=63, colsample_bytree=0.5, subsample=0.8, subsample_freq=1,
n_jobs=-1, random_state=0, verbose=-1)

t0 = time.time()
modele.fit(X_tr[~val], y_train[~val],
eval_set=[(X_tr[val], y_train[val])],
callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)])
print(f"Entraînement : {time.time() - t0:.0f} s | meilleur nb d'arbres : {modele.best_iteration_}")

p = modele.predict(X_te)
print(f"LightGBM : accuracy = {accuracy_score(y_test, p):.3f} | "
f"F1 macro = {f1_score(y_test, p, average='macro'):.3f}")
# --- B5 : évaluation détaillée + sauvegardes ---
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, ConfusionMatrixDisplay

labels = list(range(len(families)))
print(classification_report(y_test, p, labels=labels, target_names=families,
                            digits=3, zero_division=0))
rapport = classification_report(y_test, p, labels=labels, target_names=families,
                                output_dict=True, zero_division=0)
pd.DataFrame(rapport).T.round(3).to_csv(OUT / "B_rapport_par_famille.csv")

(OUT / "figures").mkdir(exist_ok=True)
fig, ax = plt.subplots(figsize=(9, 8))
ConfusionMatrixDisplay.from_predictions(
    y_test, p, labels=labels, display_labels=families, normalize="true",
    values_format=".2f", cmap="Blues", ax=ax, xticks_rotation=45)
ax.set_title("LightGBM : matrice de confusion (normalisée par ligne)")
fig.tight_layout()
fig.savefig(OUT / "figures/B_confusion.png", dpi=150)

p_base = base.predict(X_te)
pd.DataFrame([
    {"modele": "Baseline", "accuracy": accuracy_score(y_test, p_base),
     "f1_macro": f1_score(y_test, p_base, average="macro")},
    {"modele": "LightGBM", "accuracy": accuracy_score(y_test, p),
     "f1_macro": f1_score(y_test, p, average="macro")},
]).round(3).to_csv(OUT / "B_scores.csv", index=False)

Path("models").mkdir(exist_ok=True)
joblib.dump({"modele": modele, "features": noms, "familles": families,
             "constantes": constantes}, "models/K_lightgbm.joblib")
print("Résultats B enregistrés dans results_kenneth/ et models/")
# --- B6 : comparaison avec une Random Forest ---
from sklearn.ensemble import RandomForestClassifier

t0 = time.time()
rf = RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=0)
rf.fit(X_tr, y_train)
p_rf = rf.predict(X_te)
print(f"\nRandom Forest ({time.time() - t0:.0f} s) : "
      f"accuracy = {accuracy_score(y_test, p_rf):.3f} | "
      f"F1 macro = {f1_score(y_test, p_rf, average='macro'):.3f}")

scores = pd.read_csv(OUT / "B_scores.csv")
scores.loc[len(scores)] = ["Random Forest",
                           round(accuracy_score(y_test, p_rf), 3),
                           round(f1_score(y_test, p_rf, average="macro"), 3)]
scores.to_csv(OUT / "B_scores.csv", index=False)
print(scores)