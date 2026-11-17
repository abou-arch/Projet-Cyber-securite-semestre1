// Démo statique : lit data/demo.json (écrit par « python -m scripts.export_demo ») et anime la page.
// Aucun calcul de modèle ici : les probabilités et les explications ont été calculées à l'avance.
"use strict";

const state = { data: null, threshold: 0.5, current: null };
const $ = (id) => document.getElementById(id);
const fr = (value, digits = 2) => Number(value).toLocaleString("fr-FR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const pct = (value) => `${fr(100 * value, 1)} %`;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // jamais innerHTML avec des données
  return node;
}

// ---------------------------------------------------------------------------- animations
function setupReveal() {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add("visible");
      observer.unobserve(entry.target);
      if (entry.target.dataset.onVisible) entry.target.dispatchEvent(new Event("visible"));
    }
  }, { threshold: 0.15 });
  document.querySelectorAll(".reveal, #curve").forEach((node) => observer.observe(node));
  return observer;
}

function countUp(node, target, digits) {
  if (target === null || target === undefined) { node.textContent = "—"; return; }
  if (reduceMotion) { node.textContent = fr(target, digits); return; }
  const start = performance.now(), duration = 1400;
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration), eased = 1 - Math.pow(1 - t, 3);
    node.textContent = fr(target * eased, digits);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function setupChrome() {
  const nav = $("nav"), progress = $("progress");
  const links = [...document.querySelectorAll(".nav nav a")];
  const onScroll = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    progress.style.width = `${(100 * scrollY) / Math.max(1, max)}%`;
    nav.classList.toggle("scrolled", scrollY > 30);
    let active = null;
    for (const link of links) {
      const section = document.querySelector(link.getAttribute("href"));
      if (section && section.getBoundingClientRect().top < innerHeight * 0.4) active = link;
    }
    links.forEach((link) => link.classList.toggle("active", link === active));
  };
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

// ---------------------------------------------------------------------------- barres
function barRow(label, value, max, className, text) {
  const row = el("div", "bar-row");
  const track = el("div", "bar-track"), fill = el("div", `bar-fill ${className || ""}`);
  track.append(fill);
  row.append(el("span", "bar-label", label), track, el("span", "bar-value", text));
  requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = `${Math.max(0, (100 * value) / max)}%`; }));
  row.title = `${label} : ${text}`;
  return row;
}

function renderFamilyScores(data) {
  const box = $("family-bars"); box.replaceChildren();
  const entries = data.familles.filter((f) => data.par_famille[f]);
  const best = Math.max(...entries.map((f) => data.par_famille[f].f1));
  for (const f of entries) {
    const s = data.par_famille[f];
    const row = barRow(`${f} (${s.fichiers.toLocaleString("fr-FR")})`, s.f1, 1, s.f1 === best ? "violet" : "", fr(s.f1, 3));
    box.append(row);
  }
}

function renderGroups(data) {
  const box = $("group-bars"); box.replaceChildren();
  if (!data.groupes.length) { box.append(el("p", "caption", "Importance non calculée : lancez « python -m scripts.importance » avant l'export.")); return; }
  const groups = [...data.groupes].sort((a, b) => b.perm_f1_drop_mean - a.perm_f1_drop_mean);
  const max = Math.max(...groups.map((g) => g.perm_f1_drop_mean), 1e-6);
  groups.forEach((g, i) => box.append(barRow(`${g.group} (${g.n_features})`, Math.max(0, g.perm_f1_drop_mean), max,
    i === 0 ? "violet" : i < 3 ? "gold" : "", fr(g.perm_f1_drop_mean, 3))));
}

// ---------------------------------------------------------------------------- démo
function decision(proba) {
  let best = 0;
  proba.forEach((p, k) => { if (p > proba[best]) best = k; });
  return { index: best, p: proba[best], unknown: proba[best] < state.threshold };
}

function renderSample(sample) {
  const data = state.data, d = decision(sample.proba);
  state.current = sample;
  const meta = $("file-meta"); meta.replaceChildren();
  meta.append(`Fichier n° ${sample.id} · empreinte `, el("code", "", `${sample.sha256}…`),
    ` · première soumission ${sample.date}` + (sample.confiance !== null ? ` · confiance de l'étiquette ${fr(sample.confiance, 2)}` : ""));

  const pred = $("pred"), prob = $("prob"), truth = $("truth"), tag = $("tag");
  for (const node of [pred, prob, truth]) { node.classList.remove("pop"); void node.offsetWidth; node.classList.add("pop"); }
  pred.textContent = d.unknown ? "inconnue ?" : data.familles[d.index];
  prob.textContent = fr(d.p, 2);
  truth.textContent = sample.famille;
  const right = !d.unknown && data.familles[d.index] === sample.famille;
  tag.className = `tag ${d.unknown ? "unknown" : right ? "ok" : "ko"}`;
  tag.textContent = d.unknown ? `hésite : ${data.familles[d.index]} ?` : right ? "juste ✓" : "faux ✗";

  const bars = $("proba-bars"); bars.replaceChildren();
  const order = sample.proba.map((p, k) => [p, k]).sort((a, b) => b[0] - a[0]);
  for (const [p, k] of order) bars.append(barRow(data.familles[k], p, 1, k === d.index ? "violet" : "", fr(p, 2)));
  const line = el("div", "threshold-line"); bars.append(line);
  placeThreshold();

  const shap = $("shap"); shap.replaceChildren();
  if (!sample.explication.length) { shap.append(el("p", "caption", "Explication indisponible pour ce modèle.")); return; }
  const max = Math.max(...sample.explication.map((e) => Math.abs(e.contribution)), 1e-9);
  for (const e of sample.explication) {
    const row = el("div", "shap-row"), track = el("div", "shap-track");
    const fill = el("div", `shap-fill ${e.contribution >= 0 ? "pos" : "neg"}`);
    track.append(fill);
    row.append(el("span", "shap-name", e.feature), track);
    row.title = `${e.feature} : ${e.contribution >= 0 ? "+" : ""}${fr(e.contribution, 4)}`;
    shap.append(row);
    requestAnimationFrame(() => requestAnimationFrame(() => { fill.style.width = `${(50 * Math.abs(e.contribution)) / max}%`; }));
  }
}

function placeThreshold() {
  // Ligne pointillée dorée au niveau du seuil, alignée sur les pistes des barres.
  const bars = $("proba-bars"), line = bars.querySelector(".threshold-line"), track = bars.querySelector(".bar-track");
  if (!line || !track) return;
  const left = track.offsetLeft + state.threshold * track.offsetWidth;
  line.style.left = `${left}px`;
}

function draw() {
  const family = $("family-select").value;
  const pool = state.data.echantillon.filter((s) => !family || s.famille === family);
  if (!pool.length) return;
  let pick = pool[Math.floor(Math.random() * pool.length)];
  if (pool.length > 1) while (pick === state.current) pick = pool[Math.floor(Math.random() * pool.length)];
  renderSample(pick);
}

// ---------------------------------------------------------------------------- seuil
function rejectionAt(threshold) {
  const rows = state.data.rejet;
  return rows.reduce((best, r) => (Math.abs(r.seuil - threshold) < Math.abs(best.seuil - threshold) ? r : best), rows[0]);
}

function renderCurve() {
  const rows = state.data.rejet.filter((r) => r.justesse !== null);
  const W = 560, H = 300, m = { l: 48, r: 16, t: 14, b: 40 };
  const ys = rows.map((r) => r.justesse), yMin = Math.max(0, Math.min(...ys) - 0.02), yMax = Math.min(1, Math.max(...ys) + 0.02);
  const x = (c) => m.l + (1 - c) * (W - m.l - m.r);             // de gauche à droite : on répond de moins en moins
  const y = (v) => H - m.b - ((v - yMin) / Math.max(1e-6, yMax - yMin)) * (H - m.t - m.b);
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Justesse des réponses selon la part des fichiers auxquels le modèle répond");
  const add = (tag, attrs, text) => { const n = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text) n.textContent = text; svg.append(n); return n; };
  for (let i = 0; i <= 4; i++) {
    const v = yMin + ((yMax - yMin) * i) / 4;
    add("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "grid" });
    add("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, fr(v, 2));
  }
  for (const c of [1, 0.75, 0.5, 0.25, 0]) add("text", { x: x(c), y: H - m.b + 18, "text-anchor": "middle" }, pct(c).replace(",0", ""));
  add("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, class: "axis" });
  add("text", { x: (W + m.l) / 2, y: H - 4, "text-anchor": "middle" }, "part des fichiers auxquels le modèle répond");
  add("path", { d: rows.map((r, i) => `${i ? "L" : "M"}${x(r.couverture).toFixed(1)},${y(r.justesse).toFixed(1)}`).join(" "), class: "curve" });
  const marker = add("circle", { r: 7, class: "marker" });
  $("curve").replaceChildren(svg);
  state.curve = { x, y, marker };
}

function renderUnknown() {
  const body = $("unknown").querySelector("tbody"), data = state.data;
  body.replaceChildren();
  let flagged = 0;
  for (const u of data.inconnues) {
    const d = decision(u.proba);
    if (d.unknown) flagged++;
    const tr = el("tr"), tag = el("span", `tag ${d.unknown ? "ok" : "ko"}`, d.unknown ? "inconnue ✓" : "famille connue ✗");
    const decisionCell = el("td"); decisionCell.append(tag);
    tr.append(el("td", "", u.famille), el("td", "", data.familles[d.index]), el("td", "", fr(d.p, 2)), decisionCell);
    body.append(tr);
  }
  $("flagged").textContent = `${flagged} / ${data.inconnues.length}`;
}

function setThreshold(value) {
  state.threshold = value;
  const slider = $("threshold");
  slider.style.setProperty("--fill", `${100 * value}%`);
  $("threshold-value").textContent = fr(value, 2);
  const r = rejectionAt(value);
  $("coverage").textContent = pct(r.couverture);
  $("accuracy").textContent = r.justesse === null ? "—" : pct(r.justesse);
  if (state.curve && r.justesse !== null) {
    state.curve.marker.setAttribute("cx", state.curve.x(r.couverture));
    state.curve.marker.setAttribute("cy", state.curve.y(r.justesse));
  }
  renderUnknown();
  if (state.current) {
    // Met à jour le verdict du fichier affiché sans relancer les animations des barres.
    const d = decision(state.current.proba), data = state.data;
    $("pred").textContent = d.unknown ? "inconnue ?" : data.familles[d.index];
    const right = !d.unknown && data.familles[d.index] === state.current.famille;
    $("tag").className = `tag ${d.unknown ? "unknown" : right ? "ok" : "ko"}`;
    $("tag").textContent = d.unknown ? `hésite : ${data.familles[d.index]} ?` : right ? "juste ✓" : "faux ✗";
    placeThreshold();
  }
}

// ---------------------------------------------------------------------------- démarrage
async function main() {
  setupChrome();
  setupReveal();
  let data;
  try {
    const response = await fetch("data/demo.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(response.status);
    data = await response.json();
  } catch (error) {
    const notice = $("notice");
    notice.textContent = "Données de la démo absentes : lancez « python -m scripts.export_demo » sur le modèle final, " +
      "puis publiez docs/data/demo.json (README, § 6.7).";
    notice.classList.remove("hidden");
    return;
  }
  state.data = data;
  $("model-line").textContent = `Modèle ${data.modele.nom || data.modele.type} · jeu ${data.jeu} · ` +
    `${data.n_train.toLocaleString("fr-FR")} fichiers d'entraînement, ${data.n_test.toLocaleString("fr-FR")} de test, ` +
    `${data.familles.length} familles.`;
  $("generated").textContent = `données exportées le ${data.genere_le}`;
  $("m-data").textContent = `EMBER2024 : ${data.n_train.toLocaleString("fr-FR")} fichiers Windows en entraînement et ` +
    `${data.n_test.toLocaleString("fr-FR")} en test, réduits à 2 568 caractéristiques ; ${data.familles.length} familles, ` +
    "un découpage dans le temps.";

  // F1 macro sans les familles de moins de 30 fichiers du test : recalculé à partir des scores par
  // famille si metrics.json vient d'une version de scripts.train qui ne le donnait pas encore.
  let f1small = data.scores.test_f1_macro_without_small_families;
  if (f1small === null || f1small === undefined) {
    const kept = Object.values(data.par_famille).filter((s) => s.fichiers >= 30);
    if (kept.length) f1small = kept.reduce((sum, s) => sum + s.f1, 0) / kept.length;
  }
  const targets = { f1: data.scores.test_f1_macro, f1small,
                    acc: data.scores.test_accuracy, ntest: data.n_test };
  const statObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const node = entry.target;
      countUp(node, targets[node.dataset.count], Number(node.dataset.digits));
      statObserver.unobserve(node);
    }
  }, { threshold: 0.4 });
  document.querySelectorAll("[data-count]").forEach((node) => statObserver.observe(node));

  const select = $("family-select");
  for (const f of data.familles) select.append(new Option(f, f));
  $("draw").addEventListener("click", draw);
  select.addEventListener("change", draw);
  renderFamilyScores(data);
  renderGroups(data);
  renderCurve();
  $("threshold").addEventListener("input", (event) => setThreshold(Number(event.target.value)));
  setThreshold(0.5);
  draw();
  addEventListener("resize", placeThreshold);
}

main();
