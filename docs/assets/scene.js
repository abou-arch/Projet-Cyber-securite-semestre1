// Fond 3D de la démo (Three.js, sans étape de build).
// Accueil : un siphon lumineux ; au chargement, un bactériophage y est aspiré en spirale.
// En défilant, la caméra plonge dans le siphon et débouche sur un circuit imprimé : le phage
// y retombe, marche le long des pistes et infecte les puces une à une. Chaque section de la page
// a son point de vue. Si WebGL manque, le fond reste noir et la page reste lisible.
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const canvas = document.getElementById("scene");
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const small = matchMedia("(max-width: 960px)").matches;

try { start(); } catch (error) {
  console.warn("Fond 3D désactivé :", error);
  if (canvas) canvas.style.display = "none";
}

function start() {
  if (!canvas) return;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !small, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, small ? 1 : 1.5));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);
  scene.fog = new THREE.FogExp2(0x000000, 0.04);
  const camera = new THREE.PerspectiveCamera(35, innerWidth / innerHeight, 0.1, 300);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const D2R = Math.PI / 180;
  const ease = {
    inCubic: (t) => t * t * t,
    outCubic: (t) => 1 - Math.pow(1 - t, 3),
    inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    smooth: (t) => t * t * (3 - 2 * t),
  };
  const clamp01 = (x) => Math.min(1, Math.max(0, x));

  // ================================================================ le siphon (accueil)
  // Des traînées de points tournent sur un entonnoir y = 1 − 6 / (r + 0,6) puis descendent dans
  // la gorge : bleu profond au bord, cyan puis presque blanc près du trou.
  const FY = 30;                                            // hauteur de l'entonnoir au-dessus du circuit
  const funnelH = (r) => 1 - 6 / (r + 0.6);
  const funnel = new THREE.Group();
  funnel.position.y = FY;
  scene.add(funnel);
  const funnelUniforms = { uTime: { value: 0 }, uPR: { value: 1 }, uScale: { value: 400 } };
  function streaks(count, trail, throat) {
    const n = count * trail;
    const aU = new Float32Array(n), aA = new Float32Array(n), aS = new Float32Array(n);
    const aT = new Float32Array(n), aTone = new Float32Array(n), aSize = new Float32Array(n), aLen = new Float32Array(n);
    for (let s = 0; s < count; s++) {
      const u = Math.random(), a = Math.random() * Math.PI * 2, sp = 0.75 + Math.random() * 0.5;
      const tone = throat ? 0.5 + Math.random() * 0.5 : 0.25 + Math.random() * 0.75;
      const size = throat ? 0.09 + Math.random() * 0.12 : 0.16 + Math.random() * 0.42, len = 0.35 + Math.random() * 0.65;
      for (let k = 0; k < trail; k++) {
        const i = s * trail + k;
        aU[i] = u; aA[i] = a; aS[i] = sp; aT[i] = k / (trail - 1); aTone[i] = tone; aSize[i] = size; aLen[i] = len;
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    g.setAttribute("aU", new THREE.BufferAttribute(aU, 1));
    g.setAttribute("aA", new THREE.BufferAttribute(aA, 1));
    g.setAttribute("aSpeed", new THREE.BufferAttribute(aS, 1));
    g.setAttribute("aTrail", new THREE.BufferAttribute(aT, 1));
    g.setAttribute("aTone", new THREE.BufferAttribute(aTone, 1));
    g.setAttribute("aSize", new THREE.BufferAttribute(aSize, 1));
    g.setAttribute("aLen", new THREE.BufferAttribute(aLen, 1));
    const m = new THREE.ShaderMaterial({
      uniforms: funnelUniforms,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `
        uniform float uTime; uniform float uPR; uniform float uScale;
        attribute float aU; attribute float aA; attribute float aSpeed; attribute float aTrail;
        attribute float aTone; attribute float aSize; attribute float aLen;
        varying vec3 vColor; varying float vAlpha;
        const float RMIN = 0.55; const float RMAX = 9.0;
        float hgt(float r) { return 1.0 - 6.0 / (r + 0.6); }
        void main() {
          vec3 p; float t;
          ${throat ? `
          float depth = fract(aU + uTime * 0.05 * aSpeed);         // la gorge descend en boucle
          float r = 0.42 + 0.12 * aTone;
          float ang = aA + uTime * aSpeed * 4.2 - aTrail * 0.55 * aLen;
          p = vec3(cos(ang) * r, hgt(RMIN) - depth * 16.0, sin(ang) * r);
          t = 0.0;
          vAlpha = (1.0 - aTrail) * aTone * (1.0 - depth) * smoothstep(0.0, 0.08, depth);
          ` : `
          float r = mix(RMIN, RMAX, pow(aU, 1.5));
          float w = aSpeed * 1.6 / pow(r, 1.2);
          float ang = aA + uTime * w - aTrail * (0.2 + 0.7 / r) * aLen;
          float rr = r * (1.0 + 0.08 * aTrail * aLen);             // la traîne est plus à l'extérieur : spirale
          p = vec3(cos(ang) * rr, hgt(rr), sin(ang) * rr);
          t = clamp((r - RMIN) / (RMAX - RMIN), 0.0, 1.0);
          vAlpha = (1.0 - aTrail) * (0.22 + 0.78 * (1.0 - t)) * smoothstep(1.0, 0.82, t) * aTone;
          `}
          vec3 deep = vec3(0.04, 0.22, 1.0), cyan = vec3(0.11, 0.76, 1.0), white = vec3(0.85, 0.95, 1.0);
          vColor = mix(white, mix(cyan, deep, smoothstep(0.15, 0.8, t)), smoothstep(0.0, 0.12, t));
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = aSize * (1.0 - 0.55 * aTrail) * uPR * uScale / max(0.5, -mv.z);
        }`,
      fragmentShader: `
        varying vec3 vColor; varying float vAlpha;
        void main() {
          float d = length(gl_PointCoord - 0.5);
          gl_FragColor = vec4(vColor * smoothstep(0.5, 0.0, d) * vAlpha, 1.0);
        }`,
    });
    const pts = new THREE.Points(g, m);
    pts.frustumCulled = false;
    return pts;
  }
  funnel.add(streaks(small ? 1100 : 2400, small ? 10 : 16, false));
  funnel.add(streaks(small ? 260 : 520, 6, true));

  // ================================================================ le circuit imprimé
  function mulberry32(a) { return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const rand = mulberry32(11);
  const N = 72, HALF = N / 2;
  const DIRS = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  const K = (i, j) => i + "," + j;
  const EK = (a, b) => (a < b ? a + "|" + b : b + "|" + a);
  const nodes = new Map(), edges = new Set(), blocked = new Set();
  const traces = [], chips = [];
  const addNode = (i, j) => { const k = K(i, j); if (!nodes.has(k)) nodes.set(k, { i, j, k, n: [], chip: null }); return nodes.get(k); };
  const link = (a, b) => { a.n.push(b.k); b.n.push(a.k); edges.add(EK(a.k, b.k)); };
  const free = (i, j) => i > 2 && j > 2 && i < N - 3 && j < N - 3 && !nodes.has(K(i, j)) && !blocked.has(K(i, j));
  const crosses = (i, j, d) => { const [dx, dy] = DIRS[d]; return dx && dy && edges.has(EK(K(i + dx, j), K(i, j + dy))); };
  const wx = (i) => i - HALF;

  // 1. Les puces d'abord : emprise, marge et broche réservées.
  const root = addNode(HALF, HALF);                          // juste sous la gorge du siphon
  function placeChip() {
    const d = ((rand() * 4) | 0) * 2, [dx, dy] = DIRS[d], px = -dy, py = dx;
    const L = 3 + ((rand() * 2) | 0), hw = 1;
    const li = 6 + ((rand() * (N - 12)) | 0), lj = 6 + ((rand() * (N - 12)) | 0);
    const cells = [];
    for (let a = 0; a <= L + 1; a++) for (let b = -hw - 1; b <= hw + 1; b++) {
      const i = li + a * dx + b * px, j = lj + a * dy + b * py;
      if (i < 3 || j < 3 || i > N - 4 || j > N - 4 || blocked.has(K(i, j)) || nodes.has(K(i, j))) return;
      cells.push(K(i, j));
    }
    cells.forEach((k) => blocked.add(k));
    chips.push({ li, lj, leafKey: K(li, lj), d, L, hw, cx: wx(li) + (dx * (L + 1)) / 2, cz: wx(lj) + (dy * (L + 1)) / 2, infected: -1 });
  }
  for (let t = 0; t < 400 && chips.length < 28; t++) placeChip();
  // 2. Le réseau : un arbre qui part du centre, pistes droites ou à 45°.
  const pool = [root];
  for (let tries = 0; tries < 6000 && traces.length < 200; tries++) {
    const from = pool[(rand() * pool.length) | 0];
    if (from.n.length >= 3) continue;
    let d = rand() < 0.7 ? ((rand() * 4) | 0) * 2 : (rand() * 8) | 0;
    if (!free(from.i + DIRS[d][0], from.j + DIRS[d][1]) || crosses(from.i, from.j, d)) continue;
    const pts = [from];
    let i = from.i, j = from.j;
    const steps = 3 + ((rand() * 16) | 0);
    for (let s = 0; s < steps; s++) {
      if (s > 1 && rand() < 0.18) d = (d + (rand() < 0.5 ? 1 : 7)) % 8;
      const ni = i + DIRS[d][0], nj = j + DIRS[d][1];
      if (!free(ni, nj) || crosses(i, j, d)) break;
      const b = addNode(ni, nj); link(nodes.get(K(i, j)), b); i = ni; j = nj; pts.push(b); pool.push(b);
    }
    if (pts.length >= 2) traces.push(pts);
  }
  // 3. Chaque puce est raccordée au réseau par le plus court chemin libre (comme un autorouteur).
  for (const c of chips.slice()) {
    const startK = c.leafKey, prev = new Map([[startK, null]]), queue = [[c.li, c.lj]];
    let hit = null, from = null;
    while (queue.length && !hit && prev.size < 1500) {
      const [i, j] = queue.shift();
      for (let d = 0; d < 8 && !hit; d++) {
        const ni = i + DIRS[d][0], nj = j + DIRS[d][1], k = K(ni, nj);
        if (crosses(i, j, d)) continue;
        const n = nodes.get(k);
        if (n && n.n.length < 3 && !n.chip && K(i, j) !== startK) { hit = n; from = K(i, j); break; }
        if (prev.has(k) || !free(ni, nj)) continue;
        prev.set(k, K(i, j)); queue.push([ni, nj]);
      }
    }
    if (!hit) { chips.splice(chips.indexOf(c), 1); continue; }
    const pts = [hit];
    let last = hit;
    for (let k = from; k; k = prev.get(k)) { const [i, j] = k.split(",").map(Number); const n = addNode(i, j); link(last, n); pts.push(n); last = n; }
    c.leaf = last; last.chip = c;
    traces.push(pts);
  }

  const boardGroup = new THREE.Group();
  scene.add(boardGroup);
  // substrat : un point par cellule
  const dot = document.createElement("canvas"); dot.width = dot.height = 64;
  { const g = dot.getContext("2d"); g.fillStyle = "#03060a"; g.fillRect(0, 0, 64, 64); g.fillStyle = "#123342"; g.beginPath(); g.arc(32, 32, 2.2, 0, Math.PI * 2); g.fill(); }
  const dotTex = new THREE.CanvasTexture(dot);
  dotTex.wrapS = dotTex.wrapT = THREE.RepeatWrapping; dotTex.repeat.set(N, N); dotTex.colorSpace = THREE.SRGBColorSpace;
  dotTex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  const board = new THREE.Mesh(new THREE.PlaneGeometry(N, N), new THREE.MeshStandardMaterial({ map: dotTex, roughness: 0.9, metalness: 0.1, envMapIntensity: 0.05 }));
  board.rotation.x = -Math.PI / 2; board.position.set(-0.5, 0, -0.5);
  boardGroup.add(board);

  // pistes : une seule géométrie, un shader pour les impulsions cyan et l'infection rouge
  const pos = [], dist = [], seed = [], idx = [], W2 = 0.07;
  for (const tr of traces) {
    const pts = tr.map((n) => [wx(n.i), wx(n.j)]);
    const last = tr[tr.length - 1];
    if (last.chip) { const [dx, dy] = DIRS[last.chip.d]; pts.push([wx(last.i) + dx * 0.7, wx(last.j) + dy * 0.7]); }
    const s = rand();
    let acc = 0;
    for (let k = 1; k < pts.length; k++) {
      const [x0, z0] = pts[k - 1], [x1, z1] = pts[k];
      const len = Math.hypot(x1 - x0, z1 - z0), ux = (x1 - x0) / len, uz = (z1 - z0) / len, nx = -uz * W2, nz = ux * W2;
      const ax = x0 - ux * W2, az = z0 - uz * W2, bx = x1 + ux * W2, bz = z1 + uz * W2;
      const base = pos.length / 3;
      pos.push(ax + nx, 0.012, az + nz, ax - nx, 0.012, az - nz, bx + nx, 0.012, bz + nz, bx - nx, 0.012, bz - nz);
      dist.push(acc, acc, acc + len, acc + len);
      seed.push(s, s, s, s);
      idx.push(base, base + 1, base + 2, base + 1, base + 3, base + 2);
      acc += len;
    }
  }
  const tg = new THREE.BufferGeometry();
  tg.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  tg.setAttribute("aDist", new THREE.Float32BufferAttribute(dist, 1));
  tg.setAttribute("aSeed", new THREE.Float32BufferAttribute(seed, 1));
  tg.setIndex(idx);
  const MAXSRC = 8;
  const traceUniforms = {
    uTime: { value: 0 }, uPulse: { value: 1 }, uFog: { value: 0.04 },
    uSrc: { value: Array.from({ length: MAXSRC }, () => new THREE.Vector3(0, 0, -1)) },
  };
  boardGroup.add(new THREE.Mesh(tg, new THREE.ShaderMaterial({
    uniforms: traceUniforms, side: THREE.DoubleSide,
    vertexShader: `
      attribute float aDist; attribute float aSeed;
      varying float vDist; varying float vSeed; varying vec2 vXZ; varying float vDepth;
      void main() {
        vDist = aDist; vSeed = aSeed;
        vec4 wp = modelMatrix * vec4(position, 1.0); vXZ = wp.xz;
        vec4 mv = viewMatrix * wp; vDepth = -mv.z;
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: `
      uniform float uTime; uniform float uPulse; uniform float uFog; uniform vec3 uSrc[${MAXSRC}];
      varying float vDist; varying float vSeed; varying vec2 vXZ; varying float vDepth;
      void main() {
        vec3 col = vec3(0.020, 0.115, 0.170);
        if (vSeed < 0.5) {                                   // impulsions cyan : 6 cellules/s
          float x = fract((uTime * 6.0 - vDist + vSeed * 40.0) / 14.0);
          col += vec3(0.11, 0.76, 1.0) * smoothstep(0.86, 1.0, x) * 2.2 * uPulse;
        }
        float red = 0.0;
        for (int k = 0; k < ${MAXSRC}; k++) {                // onde d'infection : 4 cellules/s
          vec3 s = uSrc[k];
          if (s.z < 0.0) continue;
          float age = uTime - s.z;
          if (age < 0.0) continue;
          float d = length(vXZ - s.xy);
          red += exp(-pow((d - age * 4.0) / 0.7, 2.0)) * exp(-age * 0.33) * 2.4
               + exp(-d / 2.2) * 0.9 * smoothstep(0.0, 0.6, age);
        }
        col += vec3(1.0, 0.18, 0.27) * red;
        float f = 1.0 - exp(-uFog * uFog * vDepth * vDepth);
        gl_FragColor = vec4(mix(col, vec3(0.0), clamp(f, 0.0, 1.0)), 1.0);
      }`,
  })));

  // pastilles en bout de piste, vias aux embranchements
  const padMat = new THREE.MeshBasicMaterial({ color: 0x0c4560 });
  const leaves = [...nodes.values()].filter((n) => n.n.length === 1 && !n.chip);
  const vias = [...nodes.values()].filter((n) => n.n.length >= 3);
  const m4 = new THREE.Matrix4(), rotX = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
  const pads = new THREE.InstancedMesh(new THREE.RingGeometry(0.1, 0.18, 18), padMat, leaves.length);
  leaves.forEach((n, k) => pads.setMatrixAt(k, m4.makeTranslation(wx(n.i), 0.014, wx(n.j)).multiply(rotX)));
  const viaMesh = new THREE.InstancedMesh(new THREE.CircleGeometry(0.12, 14), padMat, vias.length);
  vias.forEach((n, k) => viaMesh.setMatrixAt(k, m4.makeTranslation(wx(n.i), 0.014, wx(n.j)).multiply(rotX)));
  boardGroup.add(pads, viaMesh);

  // puces
  const chipBodyMat = new THREE.MeshStandardMaterial({ color: 0x0b0e15, metalness: 0.5, roughness: 0.45, envMapIntensity: 0.4 });
  const pinMat = new THREE.MeshStandardMaterial({ color: 0x8aa4b8, metalness: 0.9, roughness: 0.3, envMapIntensity: 0.8 });
  const pinGeo = new THREE.BoxGeometry(0.12, 0.05, 0.3);
  const CYAN_DIM = new THREE.Color(0x1CC2FF).multiplyScalar(0.55), RED = new THREE.Color(0xFF4D6D), RED_HOT = RED.clone().multiplyScalar(1.4);
  for (const c of chips) {
    const [dx] = DIRS[c.d], along = c.L - 0.3, across = 2 * c.hw + 1 - 0.7;
    const sx = dx ? along : across, sz = dx ? across : along;
    const g = new THREE.Group(); g.position.set(c.cx, 0, c.cz);
    const bodyGeo = new THREE.BoxGeometry(sx, 0.26, sz);
    const body = new THREE.Mesh(bodyGeo, chipBodyMat); body.position.y = 0.13; g.add(body);
    c.edgeMat = new THREE.LineBasicMaterial({ color: CYAN_DIM });
    const e = new THREE.LineSegments(new THREE.EdgesGeometry(bodyGeo), c.edgeMat); e.position.y = 0.13; g.add(e);
    c.topMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
    const top = new THREE.Mesh(new THREE.PlaneGeometry(sx * 0.55, sz * 0.55), c.topMat); top.rotation.x = -Math.PI / 2; top.position.y = 0.262; g.add(top);
    for (let p = 0; p < Math.floor(along / 0.5); p++) for (const side of [-1, 1]) {
      const t = -along / 2 + 0.25 + p * 0.5, off = (across / 2 + 0.12) * side;
      const pin = new THREE.Mesh(pinGeo, pinMat);
      if (dx) pin.position.set(t, 0.05, off); else { pin.position.set(off, 0.05, t); pin.rotation.y = Math.PI / 2; }
      g.add(pin);
    }
    boardGroup.add(g);
  }

  // ================================================================ le bactériophage
  // Tête icosaédrique translucide (la charge rouge bat à l'intérieur), gaine annelée, plaque
  // hexagonale, six pattes à deux segments posées par cinématique inverse.
  const metal = new THREE.MeshStandardMaterial({ color: 0x3b3552, metalness: 0.92, roughness: 0.26, envMapIntensity: 0.9, fog: false });
  const ringMat = new THREE.MeshStandardMaterial({ color: 0x2c2640, metalness: 0.9, roughness: 0.3, emissive: 0x6b4fc4, emissiveIntensity: 0.55, fog: false });
  const phage = new THREE.Group(); scene.add(phage);
  const PLATE = 0.36;
  const plate = new THREE.Mesh(new THREE.CylinderGeometry(0.27, 0.3, 0.08, 6), metal); phage.add(plate);
  const sheath = new THREE.Group(); phage.add(sheath);
  const tube = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 1, 12), metal); sheath.add(tube);
  const rings = [];
  for (let r = 0; r < 6; r++) { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.115, 0.115, 0.045, 12), ringMat); sheath.add(m); rings.push(m); }
  const crown = new THREE.Group(); phage.add(crown);
  crown.add(new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.12, 0.07, 6), metal));
  const headGeo = new THREE.IcosahedronGeometry(0.42, 0);
  const head = new THREE.Mesh(headGeo, new THREE.MeshPhysicalMaterial({ color: 0x241a3d, metalness: 0.55, roughness: 0.18, clearcoat: 1, transparent: true, opacity: 0.62, flatShading: true, envMapIntensity: 1.2, fog: false }));
  head.scale.set(1, 1.28, 1); head.position.y = 0.6; crown.add(head);
  const headEdges = new THREE.LineSegments(new THREE.EdgesGeometry(headGeo), new THREE.LineBasicMaterial({ color: 0x9B7BEA, fog: false }));
  headEdges.scale.copy(head.scale); headEdges.position.copy(head.position); crown.add(headEdges);
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.19, 1), new THREE.MeshBasicMaterial({ color: RED.clone().multiplyScalar(0.7), fog: false }));
  core.position.y = 0.6; crown.add(core);
  const bolt = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff8095, fog: false }));
  bolt.visible = false; phage.add(bolt);
  const legGeo = new THREE.CylinderGeometry(0.024, 0.02, 1, 6);
  const footMat = new THREE.MeshBasicMaterial({ color: 0x1CC2FF, fog: false });
  const legs = [];
  for (let k = 0; k < 6; k++) {
    const a = (k * Math.PI) / 3 + Math.PI / 6;
    const leg = {
      sin: Math.sin(a), cos: Math.cos(a), group: k % 2,
      up: new THREE.Mesh(legGeo, metal), lo: new THREE.Mesh(legGeo, metal),
      knee: new THREE.Mesh(new THREE.SphereGeometry(0.04, 8, 6), ringMat),
      foot: new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), footMat),
    };
    phage.add(leg.up, leg.lo, leg.knee, leg.foot);
    legs.push(leg);
  }
  const Y = new THREE.Vector3(0, 1, 0);
  const _hip = new THREE.Vector3(), _foot = new THREE.Vector3(), _knee = new THREE.Vector3();
  const _u = new THREE.Vector3(), _n = new THREE.Vector3(), _d = new THREE.Vector3();
  const L1 = 0.55, L2 = 0.62, STRIDE = 0.38;
  function segment(mesh, a, b) {
    _d.subVectors(b, a);
    const len = _d.length();
    mesh.position.addVectors(a, b).multiplyScalar(0.5);
    mesh.scale.set(1, len, 1);
    mesh.quaternion.setFromUnitVectors(Y, _d.multiplyScalar(1 / len));
  }
  function solveKnee(hip, foot, out) {
    _u.subVectors(foot, hip);
    const d = Math.min(_u.length(), L1 + L2 - 1e-3);
    _u.normalize();
    const a = (L1 * L1 - L2 * L2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, L1 * L1 - a * a));
    _n.copy(Y).addScaledVector(_u, -Y.dot(_u)).normalize();
    return out.copy(hip).addScaledVector(_u, a).addScaledVector(_n, h);
  }
  function posePhage(gait, moving, contraction, bob, splay) {
    const sheathLen = 0.55 * (1 - 0.45 * contraction), plateY = PLATE + bob;
    plate.position.y = plateY;
    sheath.position.y = plateY + 0.04 + sheathLen / 2; tube.scale.y = sheathLen;
    for (let i = 0; i < rings.length; i++) rings[i].position.y = -sheathLen / 2 + 0.05 + (i * (sheathLen - 0.1)) / 5;
    crown.position.y = plateY + 0.04 + sheathLen + 0.035;
    for (const l of legs) {                                  // trépied alterné : 3 pattes au sol, 3 en l'air
      _hip.set(l.sin * 0.25, plateY - 0.02, l.cos * 0.25);
      const ph = (gait + l.group * 0.5) % 1;
      let off, lift = 0;
      if (ph < 0.5) off = STRIDE / 2 - STRIDE * (ph / 0.5);
      else { const s = (ph - 0.5) / 0.5; off = -STRIDE / 2 + STRIDE * ease.inOut(s); lift = 0.16 * Math.sin(Math.PI * s); }
      const reach = 0.85 + splay;
      _foot.set(l.sin * reach, lift * moving + 0.03 - splay * 0.4, l.cos * reach + off * moving);
      solveKnee(_hip, _foot, _knee);
      segment(l.up, _hip, _knee); segment(l.lo, _knee, _foot);
      l.knee.position.copy(_knee); l.foot.position.copy(_foot);
    }
  }

  // lumières
  scene.add(new THREE.AmbientLight(0x1b2733, 0.6));
  const key = new THREE.DirectionalLight(0xa9c9ff, 1.4); key.position.set(-6, 40, 4); scene.add(key);
  const glow = new THREE.PointLight(0x1CC2FF, 10, 7, 1.6); scene.add(glow);
  const redLight = new THREE.PointLight(0xFF4D6D, 0, 6, 1.6); scene.add(redLight);

  // ================================================================ navigation : il vise les puces une à une
  const nav = { cur: root, next: null, u: 0, path: [], yaw: 0, gait: 0, state: "walk", tState: 0, chip: null, src: 0 };
  function resetInfection() {
    for (const c of chips) { c.infected = -1; c.edgeMat.color.copy(CYAN_DIM); c.topMat.color.setRGB(0, 0, 0); }
    for (const v of traceUniforms.uSrc.value) v.set(0, 0, -1);
  }
  function plan(nearest) {
    const parent = new Map([[nav.cur.k, null]]), depth = new Map([[nav.cur.k, 0]]), queue = [nav.cur.k];
    while (queue.length) { const k = queue.shift(); for (const m of nodes.get(k).n) if (!parent.has(m)) { parent.set(m, k); depth.set(m, depth.get(k) + 1); queue.push(m); } }
    let cands = chips.filter((c) => c.infected < 0 && depth.has(c.leaf.k) && depth.get(c.leaf.k) >= 4);
    if (!cands.length) { resetInfection(); cands = chips.filter((c) => depth.has(c.leaf.k) && c.leaf !== nav.cur); }
    cands.sort((a, b) => depth.get(a.leaf.k) - depth.get(b.leaf.k));
    const target = cands[nearest ? 0 : (Math.random() * Math.min(4, cands.length)) | 0];
    const path = [];
    for (let k = target.leaf.k; k && k !== nav.cur.k; k = parent.get(k)) path.unshift(nodes.get(k));
    nav.path = path;
  }
  function turn(goal, dt) {
    const d = Math.atan2(Math.sin(goal - nav.yaw), Math.cos(goal - nav.yaw));
    nav.yaw += d * (1 - Math.exp(-dt / 0.12));              // ≈ 250 ms pour tourner de 45°
  }
  function stepNav(dt) {
    if (nav.state === "walk") {
      if (!nav.next) { if (!nav.path.length) plan(false); nav.next = nav.path.shift(); nav.u = 0; }
      const a = nav.cur, b = nav.next, len = Math.hypot(b.i - a.i, b.j - a.j);
      nav.u += (1.6 * dt) / len;                              // 1,6 cellule/s
      turn(Math.atan2(b.i - a.i, b.j - a.j), dt);
      nav.gait = (nav.gait + (1.6 * dt) / (2 * STRIDE)) % 1;
      if (nav.u >= 1) {
        nav.cur = b; nav.next = null; nav.u = 0;
        if (b.chip && b.chip.infected < 0 && !nav.path.length) { nav.state = "turn"; nav.tState = 0; nav.chip = b.chip; }
      }
      return;
    }
    nav.tState += dt;
    const c = nav.chip, [dx, dy] = DIRS[c.d];
    turn(Math.atan2(dx, dy), dt);
    if (nav.state === "turn" && nav.tState > 0.3) { nav.state = "inject"; nav.tState = 0; }
    else if (nav.state === "inject" && nav.tState > 0.55) {   // gaine 250 ms + éclair 300 ms
      nav.state = "infect"; nav.tState = 0; c.infected = time;
      traceUniforms.uSrc.value[nav.src].set(wx(c.leaf.i) + dx * 0.9, wx(c.leaf.j) + dy * 0.9, time);
      nav.src = (nav.src + 1) % MAXSRC;
    } else if (nav.state === "infect" && nav.tState > 0.6) { nav.state = "recover"; nav.tState = 0; }
    else if (nav.state === "recover" && nav.tState > 0.6) { nav.state = "walk"; nav.chip = null; }
  }
  function contraction() {
    if (nav.state === "inject") return ease.inCubic(Math.min(1, nav.tState / 0.25));
    if (nav.state === "infect") return 1;
    if (nav.state === "recover") return 1 - ease.outCubic(Math.min(1, nav.tState / 0.6));
    return 0;
  }

  // ================================================================ phases du phage
  // intro : aspiré dans le siphon ; gone : disparu dans la gorge ; landing : retombe sur le
  // circuit quand la caméra plonge ; board : marche et infecte.
  const INTRO_DELAY = 1.2, INTRO_LEN = 6.5;
  let mode = reduceMotion ? "board" : "intro", landT = 0, introAng = Math.random() * Math.PI * 2, time = 0;
  function land() {
    mode = "landing"; landT = time;
    nav.cur = root; nav.next = null; nav.path = []; nav.state = "walk";
    plan(true);
  }
  if (reduceMotion) {                                       // immobile, sur une puce déjà infectée
    const c = chips.reduce((best, x) => (Math.hypot(x.cx, x.cz) < Math.hypot(best.cx, best.cz) ? x : best), chips[0]);
    const [dx, dy] = DIRS[c.d];
    Object.assign(nav, { cur: c.leaf, yaw: Math.atan2(dx, dy) });
    c.infected = -10; time = 12;
    traceUniforms.uSrc.value[0].set(wx(c.leaf.i) + dx * 0.9, wx(c.leaf.j) + dy * 0.9, 0);
    c.edgeMat.color.copy(RED_HOT); c.topMat.color.copy(RED).multiplyScalar(0.55);
  }
  const here = new THREE.Vector3();
  function updatePhage(dt) {
    let moving = 0, bob = 0, splay = 0, c = 0;
    phage.rotation.set(0, 0, 0);
    phage.scale.setScalar(1);
    if (mode === "intro") {
      const s = (time - INTRO_DELAY) / INTRO_LEN;
      phage.visible = s >= 0 && s < 1;
      if (s >= 1) mode = "gone";
      if (phage.visible) {
        const r = 0.4 + 6.6 * Math.pow(1 - s, 1.3);           // il accélère vers le trou
        introAng += (dt * 1.6) / Math.pow(r, 1.2);            // et tourne avec le flux
        const plunge = r < 0.9 ? (0.9 - r) * 9 : 0;
        phage.position.set(Math.cos(introAng) * r, FY + funnelH(r) + 0.55 - plunge, Math.sin(introAng) * r);
        phage.rotation.set(0.35 * Math.sin(time * 2.1), -introAng, 0.5 * Math.sin(time * 2.9));
        phage.scale.setScalar(s < 0.75 ? 1.35 : 0.05 + 1.3 * (1 - (s - 0.75) / 0.25));
        nav.gait = (nav.gait + dt * 2.2) % 1;
        moving = 1;
      }
    } else if (mode === "gone") {
      phage.visible = false;
    } else {
      phage.visible = true;
      if (mode === "landing") {                             // retombe de la gorge en 700 ms
        const s = clamp01((time - landT) / 0.7);
        here.set(wx(root.i), 7 * (1 - ease.outCubic(s)), wx(root.j));
        splay = 0.12 * (1 - s);
        if (s >= 1) mode = "board";
      } else {
        if (!reduceMotion) stepNav(dt);
        const a = nav.cur, b = nav.next;
        if (b) here.set(wx(a.i) + (b.i - a.i) * nav.u, 0, wx(a.j) + (b.j - a.j) * nav.u);
        else here.set(wx(a.i), 0, wx(a.j));
        moving = nav.state === "walk" && !reduceMotion ? 1 : 0;
        bob = moving ? 0.03 * Math.sin(nav.gait * Math.PI * 4) : 0;
        c = contraction();
      }
      phage.position.copy(here);
      phage.rotation.y = nav.yaw;
    }
    posePhage(nav.gait, moving, c, bob, splay);
    core.scale.setScalar(reduceMotion ? 1 : 1 + 0.1 * Math.sin(time * 7.5));
    bolt.visible = mode === "board" && nav.state === "inject" && nav.tState > 0.25;
    if (bolt.visible) { const s = Math.min(1, (nav.tState - 0.25) / 0.3); const y0 = crown.position.y + 0.6; bolt.position.set(0, y0 - s * (y0 - 0.1), 0); }
    for (const ch of chips) if (ch.infected >= 0) {           // puce : cyan → rouge en 600 ms
      const t = ease.outCubic(Math.min(1, (time - ch.infected) / 0.6));
      ch.edgeMat.color.copy(CYAN_DIM).lerp(RED_HOT, t);
      ch.topMat.color.copy(RED).multiplyScalar(0.55 * t);
    }
    const infecting = mode === "board" && nav.chip && (nav.state === "infect" || nav.state === "recover");
    redLight.intensity = infecting ? 14 * (nav.state === "recover" ? 1 - nav.tState / 0.6 : 1) : 0;
    if (nav.chip) redLight.position.set(nav.chip.cx, 1, nav.chip.cz);
    glow.position.set(phage.position.x, phage.position.y + 1.8, phage.position.z);
  }

  // ================================================================ caméra pilotée par le défilement
  // dist, elev, azim : position autour du phage ; frame : décalage horizontal du sujet (part de la
  // demi-largeur) ; op : opacité du canvas ; fog : densité du brouillard.
  const PRESETS = {
    chiffres:   { dist: 17,  elev: 62, azim: 18,  frame: 0,     op: 0.6,  fog: 0.035 },
    demo:       { dist: 9,   elev: 26, azim: -38, frame: 0.5,   op: 0.45, fog: 0.05 },
    inconnu:    { dist: 5.5, elev: 18, azim: 62,  frame: 0.55,  op: 0.55, fog: 0.06 },
    importance: { dist: 12,  elev: 48, azim: 120, frame: -0.45, op: 0.5,  fog: 0.04 },
    methode:    { dist: 24,  elev: 84, azim: 0,   frame: 0,     op: 0.6,  fog: 0.028 },
    fin:        { dist: 34,  elev: 60, azim: 200, frame: 0,     op: 0.4,  fog: 0.022 },
  };
  const ORDER = ["hero", "chiffres", "demo", "inconnu", "importance", "methode", "fin"];
  let anchors = [];
  function measure() {
    const H = innerHeight;
    const at = (sel) => { const n = document.querySelector(sel); return n ? n.getBoundingClientRect().top + scrollY - H * 0.35 : 0; };
    const meth = at("#methode");
    anchors = [0, at("#chiffres"), at("#demo"), at("#inconnu"), at("#importance"), meth,
      Math.max(meth + H, document.documentElement.scrollHeight - H)];
  }
  const mix = {};
  function blendPresets(a, b, t) { for (const k of Object.keys(a)) mix[k] = a[k] + (b[k] - a[k]) * t; return mix; }
  const follow = new THREE.Vector3(), camPos = new THREE.Vector3(), camLook = new THREE.Vector3();
  const boardPos = new THREE.Vector3(), boardLook = new THREE.Vector3(), heroPos = new THREE.Vector3(), heroLook = new THREE.Vector3();
  const abovePos = new THREE.Vector3(0, FY + 13, 0.6), aboveLook = new THREE.Vector3(0, FY - 8, 0), throat = new THREE.Vector3(0, FY - 16, 0);
  function boardPose(p, outPos, outLook) {
    const e = p.elev * D2R, a = p.azim * D2R;
    outLook.set(follow.x, 0.6, follow.z);
    outPos.set(outLook.x + p.dist * Math.cos(e) * Math.sin(a), p.dist * Math.sin(e), outLook.z + p.dist * Math.cos(e) * Math.cos(a));
  }
  heroLook.set(0, FY - 1.2, 0);
  heroPos.set(25 * Math.cos(30 * D2R) * Math.sin(20 * D2R), FY - 1.2 + 25 * Math.sin(30 * D2R), 25 * Math.cos(30 * D2R) * Math.cos(20 * D2R));
  let scrollS = scrollY, frameShift = 0, opacity = 1, fogDensity = 0.03;
  function updateCamera(dt) {
    scrollS += (scrollY - scrollS) * (reduceMotion ? 1 : 1 - Math.exp(-dt / 0.3));
    let i = 0;
    while (i < anchors.length - 1 && scrollS >= anchors[i + 1]) i++;
    const t = i >= anchors.length - 1 ? 0 : ease.smooth(clamp01((scrollS - anchors[i]) / Math.max(1, anchors[i + 1] - anchors[i])));
    const kf = reduceMotion ? 1 : 1 - Math.exp(-dt / 0.35);  // suivi du phage : τ = 0,35 s
    if (mode === "board" || mode === "landing") follow.lerp(here, kf); else follow.set(0, 0, 0);
    if (i === 0) {
      // plongée : accueil → au-dessus du siphon → dans la gorge → le circuit
      const p = t;
      if (!reduceMotion && mode !== "landing" && mode !== "board" && p > 0.55) land();
      boardPose(PRESETS.chiffres, boardPos, boardLook);
      if (p < 0.45) {
        const s = ease.smooth(p / 0.45);
        camPos.lerpVectors(heroPos, abovePos, s); camLook.lerpVectors(heroLook, aboveLook, s);
        frameShift = 0.32 * (1 - s);
      } else {
        const s = ease.inOut((p - 0.45) / 0.55), q = 1 - s;
        camPos.set(0, 0, 0).addScaledVector(abovePos, q * q).addScaledVector(throat, 2 * q * s).addScaledVector(boardPos, s * s);
        camLook.lerpVectors(aboveLook.set(0, FY - 8, 0), boardLook, Math.pow(s, 1.5));
        frameShift = 0;
      }
      opacity = 1 + (PRESETS.chiffres.op - 1) * t;
      fogDensity = 0.012 + (PRESETS.chiffres.fog - 0.012) * clamp01((p - 0.45) / 0.55);
      boardGroup.visible = p > 0.3;
      funnel.visible = p < 0.97;
    } else {
      const a = PRESETS[ORDER[i]], b = PRESETS[ORDER[Math.min(i + 1, ORDER.length - 1)]];
      const m = blendPresets(a, b, t);
      boardPose(m, camPos, camLook);
      frameShift = m.frame; opacity = m.op; fogDensity = m.fog;
      boardGroup.visible = true; funnel.visible = false;
      if (!reduceMotion && mode !== "landing" && mode !== "board") land();
    }
    camera.position.copy(camPos);
    camera.lookAt(camLook);
    const halfW = Math.tan((camera.fov / 2) * D2R) * camPos.distanceTo(camLook) * camera.aspect;
    camera.translateX(-frameShift * halfW);
    scene.fog.density = fogDensity;
    traceUniforms.uFog.value = fogDensity;
    canvas.style.opacity = opacity.toFixed(3);
  }

  // ================================================================ rendu
  let composer = null;
  if (!small) {
    composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.7, 0.45, 0.6));
    composer.addPass(new OutputPass());
  }
  function resize() {
    renderer.setSize(innerWidth, innerHeight, false);
    if (composer) composer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
    funnelUniforms.uPR.value = renderer.getPixelRatio();
    funnelUniforms.uScale.value = innerHeight / 2;
    measure();
  }
  resize();
  addEventListener("resize", resize);
  addEventListener("load", measure);
  new ResizeObserver(measure).observe(document.body);         // la démo remplit la page après coup

  let last = performance.now();
  function frame(now) {
    const dt = reduceMotion ? 0 : Math.min(0.05, Math.max(0, (now - last) / 1000));
    last = now;
    time += dt;
    updatePhage(dt);
    updateCamera(dt);
    funnelUniforms.uTime.value = time;
    traceUniforms.uTime.value = time;
    traceUniforms.uPulse.value = reduceMotion ? 0 : 1;
    if (composer) composer.render(); else renderer.render(scene, camera);
    if (!reduceMotion) requestAnimationFrame(frame);
  }
  if (reduceMotion) {                                        // une image par défilement, sans transition
    const once = () => requestAnimationFrame(frame);
    addEventListener("scroll", once, { passive: true });
    addEventListener("resize", once);
  }
  requestAnimationFrame(frame);
}
