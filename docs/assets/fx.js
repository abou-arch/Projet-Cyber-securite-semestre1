// Effets de page indépendants du fond 3D : viseur (4 coins) qui suit la souris et vient encadrer
// la carte survolée, texte qui s'estompe en quittant une section. Marche même sans WebGL.
(() => {
  "use strict";
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let H = innerHeight;
  addEventListener("resize", () => { H = innerHeight; });

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
    for (const section of sections) {
      const r = section.getBoundingClientRect();
      const edge = Math.max(0, -r.bottom + H * 0.55, r.top - H * 0.7);   // distance hors de la zone de lecture
      section.style.opacity = Math.max(0.15, 1 - edge / (H * 0.45)).toFixed(3);
    }
  }
  if (!reduceMotion) { addEventListener("scroll", dim, { passive: true }); dim(); }
})();
