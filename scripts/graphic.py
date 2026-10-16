
from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report,
    ConfusionMatrixDisplay,
    confusion_matrix,
)

# Chemins du projet
ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

# Charger les prédictions et les noms des familles
df = pd.read_csv(RESULTS / "predictions_test.csv")

with open(RESULTS / "metrics.json", encoding="utf-8") as f:
    metrics = json.load(f)

families = metrics["families"]

y_true = df["y_true"].to_numpy()
y_pred = df["y_pred"].to_numpy()

# Rapport de classification par famille
report = classification_report(
    y_true,
    y_pred,
    labels=np.arange(len(families)),
    target_names=families,
    output_dict=True,
    zero_division=0,
)
report_df = pd.DataFrame(report).T.loc[families]


# FIGURE 1 — Matrice de confusion
cm = confusion_matrix(
    y_true,
    y_pred,
    labels=np.arange(len(families)),
)

fig, ax = plt.subplots(figsize=(12, 10))
ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=families,
).plot(
    ax=ax,
    xticks_rotation=45,
    values_format="d",
    colorbar=False,
)
ax.set_title("Matrice de confusion — test")
ax.set_xlabel("Famille prédite")
ax.set_ylabel("Famille réelle")
fig.tight_layout()
fig.savefig(FIGURES / "01_confusion_matrix.png", dpi=200)
plt.close(fig)


# FIGURE 2 — F1-score par famille
scores = report_df["f1-score"].sort_values()

fig, ax = plt.subplots(figsize=(10, 6))
scores.plot(kind="barh", ax=ax)
ax.set_title("F1-score par famille de malware")
ax.set_xlabel("F1-score")
ax.set_ylabel("Famille")
ax.set_xlim(0, 1)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(FIGURES / "02_f1_by_family.png", dpi=200)
plt.close(fig)


# FIGURE 3 — Nombre d'exemples réels par famille
real_counts = (
    pd.Series(y_true)
    .value_counts()
    .reindex(range(len(families)), fill_value=0)
)
real_counts.index = families

fig, ax = plt.subplots(figsize=(10, 6))
real_counts.sort_values().plot(kind="barh", ax=ax)
ax.set_title("Répartition des familles dans le jeu de test")
ax.set_xlabel("Nombre d'échantillons")
ax.set_ylabel("Famille réelle")
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(FIGURES / "03_test_family_distribution.png", dpi=200)
plt.close(fig)


# FIGURE 4 — Taux d'erreur par famille réelle
report_df["error_rate"] = 1 - report_df["recall"]
error_rates = report_df["error_rate"].sort_values()

fig, ax = plt.subplots(figsize=(10, 6))
error_rates.plot(kind="barh", ax=ax)
ax.set_title("Taux d'erreur par famille réelle")
ax.set_xlabel("Taux d'erreur (1 - recall)")
ax.set_ylabel("Famille")
ax.set_xlim(0, 1)
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig(FIGURES / "04_error_rate_by_family.png", dpi=200)
plt.close(fig)

print("Figures enregistrées dans :", FIGURES)
for path in sorted(FIGURES.glob("*.png")):
    print(path.name)
