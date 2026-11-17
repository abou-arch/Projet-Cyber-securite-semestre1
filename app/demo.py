"""Interface web de démonstration du classifieur de familles de malwares (EMBER2024).

Lancement, depuis la racine du projet (après ``python -m scripts.train``) :

    python -m streamlit run app/demo.py

La page s'ouvre sur http://localhost:8501, en local seulement (.streamlit/config.toml).
Elle n'accepte jamais d'exécutable : uniquement des fichiers du jeu préparé ou des lignes JSON
de features EMBER2024.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import core  # noqa: E402
from malware_family.figures import new_figure  # noqa: E402

PAGES = ("Tester un fichier du test", "Analyser une ligne de features", "Résultats du modèle",
         "Famille inconnue ?")
LIMITS = ("**Outil d'aide au tri, pas de décision automatique.** Le modèle ne connaît que 10 familles "
          "de fichiers Win32 : dans le test réel, 58 % des malwares appartiennent à d'autres familles. "
          "Aucun exécutable n'est accepté, téléchargé ni exécuté.")

# Style sombre : fond noir, titres blancs avec un mot en bleu-cyan, cartes presque noires à bord fin,
# badges « pilule » et halo bleu en pur CSS (aucune image ni police téléchargée : tout reste local).
ACCENT, ACCENT_DEEP, MUTED = "#1CC2FF", "#0099FF", "#8F8F8F"
# Graphiques presque monochromes : nuances de gris, une touche de violet (ce qui compte), d'or (le
# seuil) et de beige (le texte des graphiques).
CHART_GREY, VIOLET, GOLD, BEIGE = "#3F3F46", "#9B7BEA", "#D4AF37", "#E8DCC4"
STYLE = f"""
<style>
html, body, [class*="css"], .stApp {{
  font-family: Inter, "Segoe UI", -apple-system, Roboto, Helvetica, Arial, sans-serif;
}}
.stApp {{ background: #000000; }}
[data-testid="stSidebar"] {{ background: #050505; border-right: 1px solid #1C1C1C; }}
[data-testid="stHeader"] {{ background: transparent; }}
h1, h2, h3 {{ letter-spacing: -0.02em; font-weight: 600 !important; }}

.hero {{ position: relative; padding: 28px 0 18px 0; margin-bottom: 8px; overflow: visible; }}
.hero .ring {{
  position: absolute; right: 2%; top: -40px; width: 300px; height: 300px; border-radius: 50%;
  background: radial-gradient(circle, rgba(0,0,0,0) 38%, rgba(28,194,255,0.55) 47%,
              rgba(0,153,255,0.25) 56%, rgba(0,0,0,0) 68%);
  filter: blur(6px); pointer-events: none;
}}
.hero .ring::after {{
  content: ""; position: absolute; inset: 34%; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #3a4a5a 0%, #0b0f14 55%, #000 100%);
  box-shadow: 0 0 40px rgba(28,194,255,0.25);
}}
.pill {{
  display: inline-flex; align-items: center; gap: 8px; padding: 4px 12px; border-radius: 999px;
  background: #0E0E0E; border: 1px solid #1C1C1C; color: #D9D9D9; font-size: 12px;
  letter-spacing: 0.06em; text-transform: uppercase;
}}
.pill .dot {{ width: 8px; height: 8px; border-radius: 50%; background: {ACCENT_DEEP};
  box-shadow: 0 0 8px {ACCENT}; }}
.hero h1 {{ font-size: 46px; line-height: 1.08; margin: 14px 0 10px 0; color: #FFFFFF; max-width: 760px; }}
.hero h1 .accent {{ color: {ACCENT}; }}
.hero p {{ color: {MUTED}; font-size: 17px; max-width: 640px; margin: 0; }}

[data-testid="stMetric"] {{
  background: #080808; border: 1px solid #1C1C1C; border-radius: 12px; padding: 16px 18px;
}}
[data-testid="stMetricLabel"] p {{ color: {MUTED} !important; }}
[data-testid="stMetricValue"] {{ color: #FFFFFF; }}
[data-testid="stAlert"] {{ border-radius: 12px; border: 1px solid #1C1C1C; }}
.stButton > button, .stDownloadButton > button {{ border-radius: 8px; border: 1px solid #2A2A2A; }}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
  background: {ACCENT}; color: #000000; border: none; font-weight: 600;
}}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
  background: {ACCENT_DEEP}; color: #000000;
}}
[data-testid="stDataFrame"], [data-testid="stFileUploaderDropzone"], .stTextArea textarea,
.stTextInput input {{ border-radius: 12px; }}
[data-testid="stImage"] img {{ border-radius: 12px; }}
.section-title {{ font-size: 15px; font-weight: 600; color: #FFFFFF; margin: 6px 0 4px 0; }}
</style>
"""


def hero(eyebrow, title, accent, subtitle):
    """En-tête de page : badge, titre blanc avec un mot en bleu-cyan, sous-titre gris, halo bleu."""
    st.markdown(f"""<div class="hero"><div class="ring"></div>
<span class="pill"><span class="dot"></span>{eyebrow}</span>
<h1>{title} <span class="accent">{accent}</span></h1><p>{subtitle}</p></div>""", unsafe_allow_html=True)


def dark(fig, ax):
    """Graphique matplotlib aux couleurs de l'interface (fond presque noir, texte beige, grille grise)."""
    fig.patch.set_facecolor("#080808")
    ax.set_facecolor("#080808")
    for spine in ax.spines.values():
        spine.set_color("#2A2A2A")
    ax.tick_params(colors=BEIGE)
    ax.xaxis.label.set_color(BEIGE)
    ax.yaxis.label.set_color(BEIGE)
    ax.grid(color="#1C1C1C")
    legend = ax.get_legend()
    if legend:
        for text in legend.get_texts():
            text.set_color(BEIGE)


@st.cache_resource(show_spinner="Chargement du modèle et des données…")
def resources():
    return core.load_resources()


@st.cache_resource
def explainer(_model, model_path):
    return core.Explainer(_model)


@st.cache_resource(show_spinner="Prédiction de tout le test…")
def test_proba(model_path):
    res = resources()
    return core.predict_proba(res.model, np.asarray(res.data.X_test), len(res.data.families))


@st.cache_data
def example_rows():
    rows, _ = core.read_feature_lines(core.EXAMPLE.read_bytes())
    return rows


def fr(value, digits=3):
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value):
    return f"{100 * value:.1f} %".replace(".", ",")


def probability_chart(proba_row, families, threshold):
    order = np.argsort(proba_row)
    best = order[-1]
    fig, ax = new_figure(height=8 / 2.54 * 1.2)
    ax.set_axisbelow(True)
    ax.barh([families[k] for k in order], proba_row[order],
            color=[VIOLET if k == best else CHART_GREY for k in order])  # la famille prédite en violet
    ax.axvline(threshold, color=GOLD, linestyle="--", linewidth=1.2, label=f"seuil {fr(threshold, 2)}")
    ax.set_xlim(0, 1)
    ax.set_xlabel("Probabilité")
    ax.legend(loc="lower right", frameon=False)
    dark(fig, ax)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def show_prediction(res, x, threshold, true_family=None):
    """Famille prédite, probabilités et explication d'un vecteur de features."""
    families = res.data.families
    proba = core.predict_proba(res.model, x, len(families))[0]
    d = core.decision(proba, families, threshold)
    left, middle, right = st.columns(3)
    left.metric("Famille prédite", "inconnue ?" if d["inconnue"] else d["famille"],
                help="« inconnue ? » : la probabilité la plus haute est sous le seuil.")
    middle.metric("Probabilité", fr(d["probabilité"], 2),
                  help=f"Famille la plus probable : {d['famille']}")
    if true_family is not None:
        verdict = "juste ✓" if (true_family == d["famille"] and not d["inconnue"]) else "faux ✗"
        right.metric("Vraie famille", true_family, verdict,
                     delta_color="normal" if verdict.startswith("juste") else "inverse")
    if d["inconnue"]:
        st.warning(f"Probabilité maximale {fr(d['probabilité'], 2)} sous le seuil {fr(threshold, 2)} : le "
                   f"modèle hésite. Famille la plus proche : {d['famille']}, à vérifier par un analyste.")

    chart, explanation = st.columns([1, 1.2])
    with chart:
        st.markdown('<p class="section-title">Probabilité de chaque famille</p>', unsafe_allow_html=True)
        probability_chart(proba, families, threshold)
    with explanation:
        st.markdown(f'<p class="section-title">Pourquoi « {d["famille"]} » ? Les 10 features '
                    'qui ont le plus pesé (SHAP)</p>', unsafe_allow_html=True)
        with st.spinner("Calcul de l'explication…"):
            exp = explainer(res.model, str(res.model_path))
            top = exp.top(x, d["indice"], res.data.feature_names, res.index)
        if top is None:
            st.caption(f"Explication indisponible : {exp.error}.")
        else:
            st.dataframe(top.style.format({"valeur": "{:.4g}", "contribution": "{:+.4f}"}),
                         hide_index=True, use_container_width=True)
            if res.index is None:
                st.caption("Colonnes hachées sans leur vrai nom : lancez « python -m scripts.hash_lookup "
                           f"index {res.dataset_path} » pour les nommer.")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def page_test_file(res, threshold):
    hero("Analyse statique · EMBER2024", "Reconnaître une famille,", "sans exécuter.",
         "Un fichier du test, jamais vu pendant l'entraînement, choisi au hasard ou par son empreinte "
         "(qui sert seulement d'identifiant). Le modèle donne sa famille et explique sa décision.")
    data = res.data
    left, right = st.columns(2)
    with left:
        family = st.selectbox("Famille", ["au hasard", *data.families])
        if st.button("Tirer un fichier", type="primary"):
            st.session_state.test_row = core.pick_test_row(data, None if family == "au hasard" else family)
    with right:
        prefix = st.text_input("… ou début de l'empreinte sha256 (8 caractères au moins)")
        if st.button("Chercher") and prefix:
            try:
                st.session_state.test_row = core.find_test_row(data, prefix)
            except ValueError as error:
                st.error(str(error))
    row = st.session_state.get("test_row")
    if row is None:
        st.info("Tirez un fichier pour commencer.")
        return
    meta = data.meta_test.iloc[row]
    st.markdown(f"**Fichier n° {row}** · empreinte `{meta.sha256}` · première soumission "
                f"{meta.first_seen} · confiance de l'étiquette "
                f"{fr(float(meta.family_confidence), 2) if 'family_confidence' in meta else '?'}")
    show_prediction(res, np.asarray(data.X_test[row]), threshold, data.families[int(data.y_test[row])])


def page_feature_lines(res, threshold):
    hero("Lignes de features", "Analyser des features,", "jamais un exécutable.",
         "Déposez un fichier .jsonl ou collez des lignes JSON de features au format d'EMBER2024. "
         "Un fichier binaire (exécutable, archive, PDF) est refusé.")
    uploaded = st.file_uploader("Fichier de features (.jsonl, .json, .txt ; 5 Mo au plus)",
                                type=["jsonl", "json", "txt"])
    pasted = st.text_area("… ou lignes JSON collées ici", height=100)
    if st.button("Utiliser l'exemple : 44 vraies lignes d'EMBER2024, de familles hors des 10"):
        st.session_state.use_example = True
    raw = uploaded.getvalue() if uploaded else pasted.encode("utf-8") if pasted.strip() else None
    if raw is None and st.session_state.get("use_example"):
        raw = core.EXAMPLE.read_bytes()
    if raw is None:
        st.info("Déposez un fichier, collez des lignes, ou utilisez l'exemple.")
        return
    try:
        rows, errors = core.read_feature_lines(raw)
    except ValueError as error:
        st.error(str(error))
        return
    if errors:
        st.warning(f"{len(errors)} ligne(s) ignorée(s) : " + " ; ".join(errors[:3]))
    table = pd.DataFrame([core.describe_row(row, i) for i, row in enumerate(rows, 1)])
    st.dataframe(table, hide_index=True, use_container_width=True, height=min(300, 40 + 35 * len(table)))
    number = st.number_input("Ligne à analyser", 1, len(rows), 1)
    row = rows[number - 1]
    if row.get("file_type") not in (None, "Win32"):
        st.warning(f"Fichier {row.get('file_type')} : le modèle n'a appris que des fichiers Win32, "
                   "sa réponse a peu de sens.")
    family = row.get("family")
    if family and family not in res.data.families:
        st.warning(f"La vraie famille ({family}) ne fait pas partie des {len(res.data.families)} familles "
                   "du modèle : il ne peut pas la reconnaître. Un bon seuil la signale comme inconnue.")
    show_prediction(res, core.vectorize_rows([row])[0], threshold,
                    family if family in res.data.families else None)


def page_results(res):
    hero("Modèle final", "Ce que vaut le modèle,", "sur le test.",
         "Scores du modèle retenu par scripts.train, et figures de l'évaluation (B), de l'importance "
         "des features (C) et des données (A).")
    m = res.metrics
    if m is None:
        st.warning(f"Pas de {res.results_dir / 'metrics.json'} : lancez « python -m scripts.train ».")
    else:
        st.markdown(f'<span class="pill"><span class="dot"></span>Modèle retenu : '
                    f'{m.get("selected_model", "?")}</span>', unsafe_allow_html=True)
        cols = st.columns(3)
        cols[0].metric("F1 macro (test)", fr(m["test_f1_macro"]))
        small = m.get("test_f1_macro_without_small_families")
        cols[1].metric("F1 macro sans les petites familles", fr(small) if small is not None else "—",
                       help="Sans les familles de moins de 30 fichiers dans le test (sinowal : 9).")
        cols[2].metric("Exactitude (test)", fr(m["test_accuracy"]))
        per_family = pd.DataFrame(m.get("test_per_family", {})).T
        per_family = per_family.loc[[f for f in res.data.families if f in per_family.index]]
        if len(per_family):
            st.markdown("**Par famille (test)**")
            st.dataframe(per_family.rename(columns={"precision": "précision", "recall": "rappel",
                                                    "f1-score": "F1", "support": "fichiers"})
                         .style.format({"précision": "{:.3f}", "rappel": "{:.3f}", "F1": "{:.3f}",
                                        "fichiers": "{:.0f}"}), use_container_width=True)
    figures = res.results_dir / "figures"
    tabs = st.tabs(["Évaluation (B)", "Importance des features (C)", "Données (A)"])
    for tab, prefix in zip(tabs, ("B_", "C_", "A_")):
        with tab:
            paths = sorted(figures.glob(f"{prefix}*.png"))
            if not paths:
                st.info("Pas encore de figures : lancez « python -m scripts.evaluate » et "
                        "« python -m scripts.importance ».")
            columns = st.columns(2)
            for i, path in enumerate(paths):
                with columns[i % 2]:
                    st.image(str(path), caption=path.stem, use_container_width=True)


def page_unknown(res, threshold):
    hero("Monde ouvert", "Et si la famille était", "inconnue ?",
         "Le modèle range toujours un fichier dans l'une de ses familles. Avec un seuil, il répond "
         "« inconnue » quand il hésite : il répond moins souvent, mais se trompe moins.")
    data = res.data
    proba = test_proba(str(res.model_path))
    pmax = proba.max(axis=1)
    correct = proba.argmax(axis=1) == data.y_test
    table = core.rejection_table(pmax, correct)
    here = core.rejection_table(pmax, correct, [threshold]).iloc[0]
    cols = st.columns(3)
    cols[0].metric("Seuil", fr(threshold, 2))
    cols[1].metric("Fichiers du test auxquels il répond", pct(here.couverture))
    cols[2].metric("Réponses justes", pct(here.justesse) if here.n_reponses else "—")
    chart, note = st.columns([3, 2])
    fig, ax = new_figure(height=8 / 2.54)
    ax.set_axisbelow(True)
    ax.plot(table.couverture, table.justesse, marker="o", markersize=3, color=VIOLET)
    ax.scatter([here.couverture], [here.justesse], s=90, color=GOLD, zorder=3,
               label=f"seuil {fr(threshold, 2)}")
    ax.invert_xaxis()
    ax.set_xlabel("Part des fichiers auxquels le modèle répond")
    ax.set_ylabel("Part de réponses justes")
    ax.legend(loc="lower left", frameon=False)
    dark(fig, ax)
    fig.tight_layout()
    with chart:
        st.pyplot(fig)
    plt.close(fig)
    with note:
        st.markdown('<p class="section-title">Comment lire la courbe</p>', unsafe_allow_html=True)
        st.write("De gauche à droite, le seuil monte : le modèle répond à moins de fichiers, mais ses "
                 "réponses sont plus souvent justes. Le point doré est le seuil choisi à gauche. "
                 "Un analyste reçoit les fichiers « inconnue » pour les examiner à la main.")

    st.subheader("Et sur des familles que le modèle n'a jamais vues ?")
    rows = [r for r in example_rows() if r.get("file_type") == "Win32"]
    p = core.predict_proba(res.model, core.vectorize_rows(rows), len(data.families))
    flagged = p.max(axis=1) < threshold
    st.write(f"Les {len(rows)} fichiers Win32 de l'exemple appartiennent à des familles hors des "
             f"{len(data.families)} (malicord, doenerium…). Avec ce seuil, **{int(flagged.sum())} sur "
             f"{len(rows)}** sont signalés « inconnue » ; les autres reçoivent à tort une "
             "famille connue.")
    st.dataframe(pd.DataFrame({
        "vraie famille": [r.get("family") or "aucune" for r in rows],
        "famille prédite": [data.families[k] for k in p.argmax(axis=1)],
        "probabilité": p.max(axis=1).round(3),
        "décision": np.where(flagged, "inconnue ✓", "famille connue ✗"),
    }), hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Familles de malwares — démo", page_icon="🛡️", layout="wide")
    st.markdown(STYLE, unsafe_allow_html=True)
    st.sidebar.markdown('<p style="font-size:22px;font-weight:600;margin:0">Familles de malwares</p>',
                        unsafe_allow_html=True)
    st.sidebar.caption("EMBER2024 · analyse statique · scikit-learn")
    page = st.sidebar.radio("Page", PAGES)
    threshold = st.sidebar.slider("Seuil « famille inconnue »", 0.0, 1.0, core.DEFAULT_THRESHOLD, 0.05,
                                  help="Sous ce seuil de probabilité, le modèle répond « inconnue ».")
    try:
        res = resources()
    except (FileNotFoundError, ValueError) as error:
        st.error(str(error))
        st.stop()
    st.sidebar.markdown(f"**Modèle** : {type(res.model).__name__}  \n**Jeu** : {res.dataset_path.name}  \n"
                        f"**Familles** : {len(res.data.families)}")
    st.sidebar.info(LIMITS)
    if page == PAGES[0]:
        page_test_file(res, threshold)
    elif page == PAGES[1]:
        page_feature_lines(res, threshold)
    elif page == PAGES[2]:
        page_results(res)
    else:
        page_unknown(res, threshold)


# Streamlit exécute ce fichier sous le nom « __main__ ». Un processus fils (multiprocessing) qui le
# réimporterait sous « __mp_main__ » ne doit pas relancer l'interface.
if __name__ == "__main__":
    main()
