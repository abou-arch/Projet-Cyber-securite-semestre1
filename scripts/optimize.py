from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("Script optimize.py démarré", flush=True)

import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from malware_family.dataset import load_dataset

DATA_DIR = ROOT / "data" / "processed" / "ember2024_Win32_top10"
RESULTS_DIR = ROOT / "results"
MODELS_DIR = ROOT / "models"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

print(f"Chargement du dataset : {DATA_DIR}", flush=True)
data = load_dataset(DATA_DIR)

print(f"Train : {data.X_train.shape}", flush=True)
print(f"Test  : {data.X_test.shape}", flush=True)

dates = pd.to_datetime(data.meta_train["first_seen"], errors="coerce", utc=True)
if dates.isna().any():
    raise ValueError(f"{dates.isna().sum()} dates first_seen invalides.")

order = np.argsort(dates.to_numpy(), kind="stable")
split = int(len(order) * 0.85)
fit_idx, val_idx = order[:split], order[split:]

y_train = np.asarray(data.y_train)
y_fit, y_val = y_train[fit_idx], y_train[val_idx]

if len(np.unique(y_fit)) != len(data.families):
    raise ValueError(
        "Au moins une famille est absente de la partie d'entraînement temporelle."
    )

print(f"Entraînement : {len(fit_idx)} ; validation : {len(val_idx)}", flush=True)

X_fit = np.asarray(data.X_train)[fit_idx]
X_val = np.asarray(data.X_train)[val_idx]

candidates = [
    ("dummy", DummyClassifier(strategy="prior")),
    ("rf_200_depth20", RandomForestClassifier(
        n_estimators=200, max_depth=20, min_samples_leaf=2,
        max_features="sqrt", class_weight="balanced_subsample",
        n_jobs=-1, random_state=42
    )),
    ("rf_300_depth_none", RandomForestClassifier(
        n_estimators=300, max_depth=None, min_samples_leaf=2,
        max_features="sqrt", class_weight="balanced_subsample",
        n_jobs=-1, random_state=42
    )),
]

scores = []
best_name, best_score, best_params = None, -1.0, None

for name, model in candidates:
    print(f"\nÉvaluation de {name}...", flush=True)
    start = time.time()
    model.fit(X_fit, y_fit)
    pred = model.predict(X_val)
    score = f1_score(y_val, pred, average="macro", zero_division=0)

    row = {
        "model": name,
        "f1_macro_validation": float(score),
        "accuracy_validation": float(accuracy_score(y_val, pred)),
        "balanced_accuracy_validation": float(
            balanced_accuracy_score(y_val, pred)
        ),
        "duration_seconds": round(time.time() - start, 2),
    }
    scores.append(row)
    print(row, flush=True)

    if score > best_score:
        best_name, best_score = name, score
        best_params = model.get_params()

print(f"\nMeilleur modèle en validation : {best_name}", flush=True)

if best_name == "dummy":
    final_model = DummyClassifier(strategy="prior")
else:
    final_model = RandomForestClassifier(**best_params)

print("Réentraînement sur tout le train...", flush=True)
start = time.time()
final_model.fit(data.X_train, data.y_train)
print(f"Réentraînement terminé en {time.time() - start:.1f} s", flush=True)

print("Évaluation finale sur le test...", flush=True)
test_pred = final_model.predict(data.X_test)
test_f1 = f1_score(data.y_test, test_pred, average="macro", zero_division=0)

metrics = {
    "selected_model": best_name,
    "validation_f1_macro": float(best_score),
    "test_f1_macro": float(test_f1),
    "test_accuracy": float(accuracy_score(data.y_test, test_pred)),
    "test_balanced_accuracy": float(
        balanced_accuracy_score(data.y_test, test_pred)
    ),
    "validation_results": scores,
    "families": list(data.families),
}

joblib.dump(final_model, MODELS_DIR / "best_model.joblib")
with open(RESULTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)

predictions = pd.DataFrame({
    "y_true": np.asarray(data.y_test),
    "y_pred": np.asarray(test_pred),
    "famille_reelle": [data.families[int(i)] for i in data.y_test],
    "famille_predite": [data.families[int(i)] for i in test_pred],
})
if "sha256" in data.meta_test.columns:
    predictions.insert(0, "sha256", data.meta_test["sha256"].to_numpy())

predictions.to_csv(
    RESULTS_DIR / "predictions_test.csv", index=False, encoding="utf-8"
)

print("\nTerminé. Fichiers générés :", flush=True)
print(MODELS_DIR / "best_model.joblib", flush=True)
print(RESULTS_DIR / "metrics.json", flush=True)
print(RESULTS_DIR / "predictions_test.csv", flush=True)
print(f"F1 macro test : {test_f1:.4f}", flush=True)
