// Animations communes de la démo : viseur qui suit la souris, sections qui s'estompent, et
// version 2D du tourbillon (canvas 2D, sans dépendance). La version 3D (assets/orbit3d.js, WebGL)
// est utilisée en priorité ; celle-ci ne démarre que si la 3D est impossible (window.startVortex2D).
(() => {
  "use strict";
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const small = matchMedia("(max-width: 960px)").matches;

  // ------------------------------------------------------------------ tourbillon 2D (secours)
  window.startVortex2D = function startVortex2D() {
    const canvas = document.getElementById("vortex");
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext("2d");
    let W = 0, H = 0, DPR = 1;

    function resize() {
      DPR = Math.min(window.devicePixelRatio || 1, 1.5);
      W = innerWidth; H = innerHeight;
      canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
      canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      if (typeof layer !== "undefined") { layer.width = Math.ceil(W / 2); layer.height = Math.ceil(H / 2); }
    }

    // ------------------------------------------------------------------ traînées du tourbillon
    const N = small ? 380 : 760;
    const streaks = Array.from({ length: N }, () => {
      const u = Math.random();
      const r = 0.46 + 0.54 * Math.pow(u, 0.9);            // rayon relatif : plus dense près du trou
      return {
        r, a: Math.random() * Math.PI * 2,
        len: 0.35 + Math.random() * 1.2,                   // longueur de l'arc (radians)
        w: 2 + Math.random() * 9,                          // épaisseur : de larges bandes
        speed: (0.12 + Math.random() * 0.16) / r,          // plus rapide près du centre
        alpha: 0.05 + Math.random() * 0.2 * (1.3 - r),
        tone: Math.random(),
      };
    });
    // Couleur selon le rayon : bleu profond à l'extérieur, cyan vif puis presque blanc près du trou.
    function color(r, tone, alpha) {
      const t = Math.min(1, Math.max(0, (r - 0.46) / 0.54));
      const red = Math.round(10 + Math.pow(1 - t, 2) * 150 + tone * 15);
      const green = Math.round(60 + Math.pow(1 - t, 1.4) * 175 + tone * 15);
      return `rgba(${red},${Math.min(255, green)},255,${alpha})`;
    }
    // Les traînées sont dessinées dans un calque à demi-résolution, puis posées deux fois : floues
    // (le halo lumineux) et nettes.
    const layer = document.createElement("canvas"), lctx = layer.getContext("2d");
    const GLOW = typeof lctx.filter === "string" && !small;   // pas de flou sur téléphone : plus fluide

    // ------------------------------------------------------------------ texture de la planète
    const planetTexture = document.createElement("canvas");
    planetTexture.width = 512; planetTexture.height = 256;
    (function paintPlanet() {
      const p = planetTexture.getContext("2d");
      p.fillStyle = "#0b1016"; p.fillRect(0, 0, 512, 256);
      for (let i = 0; i < 260; i++) {                      // continents flous
        const x = Math.random() * 512, y = 30 + Math.random() * 196, s = 4 + Math.random() * 26;
        const g = p.createRadialGradient(x, y, 0, x, y, s);
        g.addColorStop(0, `rgba(120,140,160,${0.08 + Math.random() * 0.18})`); g.addColorStop(1, "rgba(0,0,0,0)");
        p.fillStyle = g; p.fillRect(x - s, y - s, 2 * s, 2 * s);
      }
      for (let i = 0; i < 380; i++) {                      // lumières des villes
        p.fillStyle = `rgba(190,220,255,${0.15 + Math.random() * 0.4})`;
        p.fillRect(Math.random() * 512, 40 + Math.random() * 176, 1, 1);
      }
    })();

    // ------------------------------------------------------------------ chorégraphie au défilement
    // x, y : centre (part de l'écran) ; R : rayon (part de la hauteur) ; tilt : écrasement vertical
    // (perspective) ; op : opacité ; px, py : position de la planète (en rayons) ; pr : sa taille.
    const STATES = {
      hero:       { x: 0.75, y: 0.52, R: 0.48, tilt: 1.0,  op: 1.0,  px: 0.30, py: 0.12, pr: 0.30 },
      chiffres:   { x: 0.50, y: 0.50, R: 0.28, tilt: 1.0,  op: 0.30, px: 0.00, py: 0.00, pr: 0.32 },
      demo:       { x: 0.92, y: 0.62, R: 0.30, tilt: 0.62, op: 0.28, px: 0.00, py: 0.00, pr: 0.30 },
      inconnu:    { x: 0.50, y: 0.50, R: 1.15, tilt: 1.0,  op: 0.45, px: 0.00, py: 0.00, pr: 0.00 },
      importance: { x: 0.10, y: 0.58, R: 0.36, tilt: 0.45, op: 0.30, px: 0.05, py: 0.0,  pr: 0.24 },
      methode:    { x: 0.55, y: 0.40, R: 0.48, tilt: 0.38, op: 0.45, px: 0.10, py: 0.0,  pr: 0.22 },
      fin:        { x: 0.50, y: 1.25, R: 0.60, tilt: 0.40, op: 0.30, px: 0.0,  py: 0.0,  pr: 0.20 },
    };
    const anchors = [
      ["hero", () => 0],
      ["chiffres", () => offset("#chiffres")],
      ["demo", () => offset("#demo")],
      ["inconnu", () => offset("#inconnu")],
      ["importance", () => offset("#importance")],
      ["methode", () => offset("#methode")],
      ["fin", () => Math.max(offset("#methode") + H, document.documentElement.scrollHeight - H)],
    ];
    function offset(selector) {
      const node = document.querySelector(selector);
      return node ? node.getBoundingClientRect().top + scrollY - H * 0.35 : 0;
    }
    const smooth = (t) => t * t * (3 - 2 * t);
    function target() {
      const positions = anchors.map(([name, at]) => [name, at()]);
      let i = 0;
      while (i < positions.length - 1 && scrollY >= positions[i + 1][1]) i++;
      if (i === positions.length - 1) return { ...STATES[positions[i][0]] };
      const [a, ya] = positions[i], [b, yb] = positions[i + 1];
      const t = smooth(Math.min(1, Math.max(0, (scrollY - ya) / Math.max(1, yb - ya))));
      const out = {};
      for (const key of Object.keys(STATES[a])) out[key] = STATES[a][key] + (STATES[b][key] - STATES[a][key]) * t;
      return out;
    }
    let view = target();

    // ------------------------------------------------------------------ dessin d'une image
    function frame(time) {
      const goal = target(), k = reduceMotion ? 1 : 0.075;  // inertie de la caméra
      for (const key of Object.keys(view)) view[key] += (goal[key] - view[key]) * k;
      const t = reduceMotion ? 0 : time / 1000;
      const cx = view.x * W, cy = view.y * H, R = view.R * H;
      canvas.style.opacity = view.op.toFixed(3);
      ctx.clearRect(0, 0, W, H);

      // traînées en spirale, dans le calque à demi-résolution, en mode additif : elles s'éclairent
      // en se superposant
      lctx.setTransform(1, 0, 0, 1, 0, 0);
      lctx.clearRect(0, 0, layer.width, layer.height);
      lctx.setTransform(0.5, 0, 0, 0.5, 0, 0);
      lctx.translate(cx, cy);
      lctx.scale(1, view.tilt);
      lctx.rotate(-0.35 * (1 - view.tilt));
      lctx.globalCompositeOperation = "lighter";
      lctx.lineCap = "round";
      const thickness = Math.max(0.5, R / 420);
      for (const s of streaks) {
        const start = s.a + t * s.speed, rad = s.r * R * (1 + 0.025 * Math.sin(t * 0.6 + s.a * 3));
        lctx.beginPath();
        for (let j = 0; j <= 6; j++) {
          const ang = start + (s.len * j) / 6, rr = rad * (1 - 0.07 * (j / 6));   // l'arc se resserre : spirale
          const x = Math.cos(ang) * rr, y = Math.sin(ang) * rr;
          j ? lctx.lineTo(x, y) : lctx.moveTo(x, y);
        }
        lctx.strokeStyle = color(s.r, s.tone, s.alpha);
        lctx.lineWidth = s.w * thickness;
        lctx.stroke();
      }
      // halo diffus derrière, puis le calque flou (lueur) et le calque net
      ctx.save();
      ctx.translate(cx, cy); ctx.scale(1, view.tilt);
      const halo = ctx.createRadialGradient(0, 0, R * 0.4, 0, 0, R * 1.3);
      halo.addColorStop(0, "rgba(0,0,0,0)");
      halo.addColorStop(0.4, "rgba(0,150,255,0.30)");
      halo.addColorStop(1, "rgba(0,60,255,0)");
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(0, 0, R * 1.3, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
      ctx.globalCompositeOperation = "lighter";
      if (GLOW) {
        ctx.filter = `blur(${Math.max(4, R / 40).toFixed(1)}px)`;
        ctx.drawImage(layer, 0, 0, W, H);
        ctx.filter = "none";
      }
      ctx.drawImage(layer, 0, 0, W, H);
      ctx.globalCompositeOperation = "source-over";

      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(1, view.tilt);
      // trou noir au centre
      const hole = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.56);
      hole.addColorStop(0, "rgba(0,0,0,1)"); hole.addColorStop(0.72, "rgba(0,0,0,0.96)"); hole.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = hole; ctx.beginPath(); ctx.arc(0, 0, R * 0.56, 0, Math.PI * 2); ctx.fill();
      ctx.restore();

      // planète (non écrasée par la perspective) et viseur qui tourne autour
      const pr = view.pr * R * 0.55;
      if (pr > 3) {
        const px = cx + view.px * R, py = cy + view.py * R * view.tilt + Math.sin(t * 0.8) * pr * 0.04;
        ctx.save();
        ctx.beginPath(); ctx.arc(px, py, pr, 0, Math.PI * 2); ctx.clip();
        const shift = ((t * 12) % 512 + 512) % 512;
        const scale = (2 * pr) / 256;
        ctx.drawImage(planetTexture, -shift * scale + px - pr, py - pr, 512 * scale, 2 * pr);
        ctx.drawImage(planetTexture, (512 - shift) * scale + px - pr, py - pr, 512 * scale, 2 * pr);
        const shade = ctx.createRadialGradient(px - pr * 0.4, py - pr * 0.45, pr * 0.1, px, py, pr * 1.05);
        shade.addColorStop(0, "rgba(255,255,255,0.18)"); shade.addColorStop(0.45, "rgba(0,0,0,0.1)"); shade.addColorStop(1, "rgba(0,0,0,0.85)");
        ctx.fillStyle = shade; ctx.fillRect(px - pr, py - pr, 2 * pr, 2 * pr);
        ctx.restore();
        ctx.strokeStyle = "rgba(28,194,255,0.25)"; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(px, py, pr, Math.PI * 0.9, Math.PI * 1.6); ctx.stroke();
        // viseur : 4 coins qui tournent lentement
        const b = pr * 0.28, c = b * 0.45;
        ctx.save(); ctx.translate(px, py); ctx.rotate(t * 0.5);
        ctx.strokeStyle = "rgba(255,255,255,0.85)"; ctx.lineWidth = 1.6;
        for (let q = 0; q < 4; q++) {
          ctx.rotate(Math.PI / 2);
          ctx.beginPath(); ctx.moveTo(b, b - c); ctx.lineTo(b, b); ctx.lineTo(b - c, b); ctx.stroke();
        }
        ctx.restore();
      }
      if (!reduceMotion) requestAnimationFrame(frame);
    }

    resize();
    addEventListener("resize", resize);
    if (reduceMotion) {
      addEventListener("scroll", () => requestAnimationFrame(frame), { passive: true });
      addEventListener("resize", () => requestAnimationFrame(frame));
    }
    requestAnimationFrame(frame);

  };
  // ------------------------------------------------------------------ viseur qui suit la souris
  const cursor = document.getElementById("cursor");
  if (cursor && matchMedia("(hover: hover) and (pointer: fine)").matches && !reduceMotion) {
    const SNAP = ".card, .stat, .verdict-box, .button, select, .pill-button, .slider, tbody tr";
    const box = { x: -100, y: -100, w: 24, h: 24 }, goal = { ...box };
    let mouse = null;
    addEventListener("mousemove", (event) => { mouse = event; }, { passive: true });
    document.addEventListener("mouseleave", () => { mouse = null; });
    (function follow() {
      if (mouse) {
        const hit = mouse.target instanceof Element ? mouse.target.closest(SNAP) : null;
        if (hit) {
          const r = hit.getBoundingClientRect(), pad = 6;
          Object.assign(goal, { x: r.left - pad, y: r.top - pad, w: r.width + 2 * pad, h: r.height + 2 * pad });
          cursor.classList.add("snapped");
        } else {
          Object.assign(goal, { x: mouse.clientX - 12, y: mouse.clientY - 12, w: 24, h: 24 });
          cursor.classList.remove("snapped");
        }
        cursor.classList.add("on");
      } else cursor.classList.remove("on");
      for (const key of ["x", "y", "w", "h"]) box[key] += (goal[key] - box[key]) * 0.22;
      cursor.style.transform = `translate(${box.x}px, ${box.y}px)`;
      cursor.style.width = `${box.w}px`; cursor.style.height = `${box.h}px`;
      requestAnimationFrame(follow);
    })();
  }

  // ------------------------------------------------------------------ texte qui s'estompe en quittant une section
  const sections = [...document.querySelectorAll(".section")];
  function dim() {
    const H = innerHeight;
    for (const section of sections) {
      const r = section.getBoundingClientRect();
      const edge = Math.max(0, -r.bottom + H * 0.55, r.top - H * 0.7);   // distance hors de la zone de lecture
      section.style.opacity = Math.max(0.15, 1 - edge / (H * 0.45)).toFixed(3);
    }
  }
  if (!reduceMotion) { addEventListener("scroll", dim, { passive: true }); dim(); }
})();
