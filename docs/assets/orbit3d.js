// Orbite en 3D (WebGL, Three.js copié dans assets/vendor/, licence MIT) : un disque de particules en
// spirale autour d'un trou noir, et une planète éclairée avec son atmosphère. La caméra se déplace en 3D
// au défilement, avec un léger effet de profondeur qui suit la souris. Si WebGL ou Three.js manquent,
// la version 2D (assets/vortex.js) prend le relais.
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const small = matchMedia("(max-width: 960px)").matches;

function fallback(reason) {
  console.info("Orbite 3D indisponible, version 2D :", reason);
  if (window.startVortex2D) window.startVortex2D();
}

function webglAvailable() {
  try {
    const test = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (test.getContext("webgl2") || test.getContext("webgl")));
  } catch (error) {
    return false;
  }
}

// ---------------------------------------------------------------------- shaders du disque
// Le disque est fait de rubans lumineux : des bandes courbes qui tournent autour du trou, plus
// rapides près du centre, et qui se resserrent en spirale. Additionnés, ils forment des bandes lisses.
const RIBBON_VERTEX = /* glsl */ `
  uniform float uTime;
  attribute float aRadius;
  attribute float aAngle;
  attribute float aSpan;
  attribute float aWidth;
  attribute float aHeight;
  attribute float aTone;
  attribute vec2 aUV;
  varying vec3 vColor;
  varying vec2 vUV;
  varying float vFade;
  void main() {
    float omega = 0.38 / pow(aRadius, 1.5);                 // rotation képlérienne
    float theta = aAngle + aUV.x * aSpan + uTime * omega;
    float r = aRadius * (1.0 - 0.07 * aUV.x) + aUV.y * aWidth * 0.5;
    vec3 p = vec3(cos(theta) * r, sin(theta) * r, aHeight * (0.03 + 0.04 * aRadius));
    gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
    float t = clamp((aRadius - 1.0) / 2.3, 0.0, 1.0);
    vec3 inner = vec3(0.62, 0.93, 1.0), mid = vec3(0.10, 0.72, 1.0), outer = vec3(0.02, 0.22, 0.95);
    vColor = (t < 0.28 ? mix(inner, mid, t / 0.28) : mix(mid, outer, (t - 0.28) / 0.72)) * (0.75 + 0.4 * aTone);
    vFade = 0.26 - 0.17 * t;
    vUV = aUV;
  }
`;
const RIBBON_FRAGMENT = /* glsl */ `
  uniform float uOpacity;
  varying vec3 vColor;
  varying vec2 vUV;
  varying float vFade;
  void main() {
    float across = pow(max(0.0, 1.0 - vUV.y * vUV.y), 1.6);   // doux sur les bords du ruban
    float along = pow(sin(3.14159 * vUV.x), 0.7);             // fondu aux deux bouts
    gl_FragColor = vec4(vColor, across * along * vFade * uOpacity);
  }
`;
const DUST_VERTEX = /* glsl */ `
  uniform float uTime;
  uniform float uPixel;
  attribute float aRadius;
  attribute float aAngle;
  attribute float aSize;
  varying float vAlpha;
  void main() {
    float theta = aAngle + uTime * 0.38 / pow(aRadius, 1.5);
    vec4 mv = modelViewMatrix * vec4(cos(theta) * aRadius, sin(theta) * aRadius, 0.0, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aSize * uPixel / -mv.z;
    vAlpha = 0.35 - 0.09 * aRadius;
  }
`;
const DUST_FRAGMENT = /* glsl */ `
  uniform float uOpacity;
  varying float vAlpha;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    gl_FragColor = vec4(0.75, 0.95, 1.0, smoothstep(0.5, 0.0, d) * vAlpha * uOpacity);
  }
`;
const ATMOSPHERE_VERTEX = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;
const ATMOSPHERE_FRAGMENT = /* glsl */ `
  uniform float uOpacity;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    float rim = pow(1.0 - abs(dot(vNormal, vView)), 2.5);
    gl_FragColor = vec4(0.11, 0.76, 1.0, rim * 0.9 * uOpacity);
  }
`;

// ---------------------------------------------------------------------- texture de la planète
function planetTexture(THREE) {
  const c = document.createElement("canvas");
  c.width = 1024; c.height = 512;
  const p = c.getContext("2d");
  p.fillStyle = "#0a0f15"; p.fillRect(0, 0, 1024, 512);
  for (let i = 0; i < 520; i++) {                 // continents flous
    const x = Math.random() * 1024, y = 60 + Math.random() * 392, s = 8 + Math.random() * 46;
    const g = p.createRadialGradient(x, y, 0, x, y, s);
    g.addColorStop(0, `rgba(110,130,150,${0.08 + Math.random() * 0.2})`); g.addColorStop(1, "rgba(0,0,0,0)");
    p.fillStyle = g; p.fillRect(x - s, y - s, 2 * s, 2 * s);
  }
  for (let i = 0; i < 1600; i++) {                // lumières des villes
    p.fillStyle = `rgba(200,225,255,${0.15 + Math.random() * 0.5})`;
    p.fillRect(Math.random() * 1024, 80 + Math.random() * 352, 1.2, 1.2);
  }
  const texture = new THREE.CanvasTexture(c);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// ---------------------------------------------------------------------- chorégraphie
// Disque : position (x, y, z), échelle, inclinaison (rx, en radians : 0 = face à la caméra) et
// rotation dans son plan (rz) ; planète : position relative au disque (px, py, pz) et taille (ps) ;
// op : opacité de la scène.
const STATES = {
  hero:       { x: 2.75, y: -0.05, z: 0,    s: 1.00, rx: 0.32, rz: 0.0, px: 0.55, py: -0.50, pz: 1.2, ps: 1.0, op: 1.0 },
  chiffres:   { x: 0.00, y: 0.25,  z: -2.0, s: 0.62, rx: 0.20, rz: 0.4, px: 0.0,  py: 0.0,   pz: 0.3, ps: 0.9, op: 0.40 },
  demo:       { x: 4.20, y: -1.30, z: -1.5, s: 0.72, rx: 1.05, rz: 0.8, px: 0.0,  py: 0.0,   pz: 0.3, ps: 0.8, op: 0.32 },
  inconnu:    { x: 0.00, y: 0.00,  z: 2.4,  s: 1.90, rx: 0.05, rz: 1.2, px: 0.0,  py: 0.0,   pz: 0.0, ps: 0.0, op: 0.26 },
  importance: { x: -4.1, y: -0.70, z: -1.5, s: 0.80, rx: 1.10, rz: 1.6, px: 0.2,  py: 0.0,   pz: 0.3, ps: 0.7, op: 0.36 },
  methode:    { x: 0.30, y: 2.25,  z: -1.5, s: 0.95, rx: 1.22, rz: 2.0, px: 0.3,  py: 0.0,   pz: 0.3, ps: 0.0, op: 0.38 },
  fin:        { x: 0.00, y: -4.6,  z: -1.0, s: 1.10, rx: 1.30, rz: 2.4, px: 0.0,  py: 0.0,   pz: 0.3, ps: 0.6, op: 0.35 },
};
const ANCHORS = ["hero", "chiffres", "demo", "inconnu", "importance", "methode", "fin"];

function anchorPositions(H) {
  const at = (selector) => {
    const node = document.querySelector(selector);
    return node ? node.getBoundingClientRect().top + scrollY - H * 0.35 : 0;
  };
  const methode = at("#methode");
  return [0, at("#chiffres"), at("#demo"), at("#inconnu"), at("#importance"), methode,
          Math.max(methode + H, document.documentElement.scrollHeight - H)];
}
const smooth = (t) => t * t * (3 - 2 * t);
function targetState(H) {
  const positions = anchorPositions(H);
  let i = 0;
  while (i < positions.length - 1 && scrollY >= positions[i + 1]) i++;
  if (i === positions.length - 1) return { ...STATES[ANCHORS[i]] };
  const a = STATES[ANCHORS[i]], b = STATES[ANCHORS[i + 1]];
  const t = smooth(Math.min(1, Math.max(0, (scrollY - positions[i]) / Math.max(1, positions[i + 1] - positions[i]))));
  const out = {};
  for (const key of Object.keys(a)) out[key] = a[key] + (b[key] - a[key]) * t;
  return out;
}

// ---------------------------------------------------------------------- scène
async function start() {
  if (!webglAvailable()) return fallback("WebGL absent");
  let THREE;
  try {
    THREE = await import("./vendor/three.module.min.js");
  } catch (error) {
    return fallback(error);
  }

  const renderer = new THREE.WebGLRenderer({ antialias: !small, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, small ? 1 : 1.5));
  renderer.setClearColor(0x000000, 0);
  const canvas = renderer.domElement;
  canvas.id = "orbit3d";
  canvas.setAttribute("aria-hidden", "true");
  document.getElementById("vortex")?.replaceWith(canvas);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  camera.position.set(0, 0, 8);

  // Disque : rubans lumineux en spirale (bras spiraux plus quelques rubans libres).
  const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5;
  const RIBBONS = small ? 550 : 1300, SEG = 18;
  const perRibbon = (SEG + 1) * 2;
  const ribbonAttrs = { aRadius: 1, aAngle: 1, aSpan: 1, aWidth: 1, aHeight: 1, aTone: 1, aUV: 2 };
  const buffers = Object.fromEntries(Object.entries(ribbonAttrs).map(([k, n]) => [k, new Float32Array(RIBBONS * perRibbon * n)]));
  const indices = new Uint32Array(RIBBONS * SEG * 6);
  for (let i = 0, v = 0, ix = 0; i < RIBBONS; i++) {
    const r = 1.04 + 2.3 * Math.pow(Math.random(), 1.5);
    const arm = Math.floor(Math.random() * 3);
    const a = Math.random() < 0.6 ? arm * (2 * Math.PI / 3) + Math.log(r) * 2.4 + gauss() * 0.5 : Math.random() * Math.PI * 2;
    const span = 0.5 + Math.random() * 1.6, width = 0.03 + Math.random() * 0.13 * (0.6 + r / 3);
    const h = gauss(), tone = Math.random();
    for (let j = 0; j <= SEG; j++) {
      for (const side of [-1, 1]) {
        buffers.aRadius[v] = r; buffers.aAngle[v] = a; buffers.aSpan[v] = span; buffers.aWidth[v] = width;
        buffers.aHeight[v] = h; buffers.aTone[v] = tone;
        buffers.aUV[2 * v] = j / SEG; buffers.aUV[2 * v + 1] = side;
        v++;
      }
      if (j < SEG) {
        const b = i * perRibbon + j * 2;
        indices.set([b, b + 1, b + 2, b + 1, b + 3, b + 2], ix); ix += 6;
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(RIBBONS * perRibbon * 3), 3));
  for (const [name, n] of Object.entries(ribbonAttrs)) geometry.setAttribute(name, new THREE.BufferAttribute(buffers[name], n));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);
  const diskMaterial = new THREE.ShaderMaterial({
    vertexShader: RIBBON_VERTEX, fragmentShader: RIBBON_FRAGMENT,
    uniforms: { uTime: { value: 0 }, uOpacity: { value: 1 } },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  const disk = new THREE.Mesh(geometry, diskMaterial);

  // Poussière scintillante, peu nombreuse, par-dessus les rubans.
  const DUST = small ? 1500 : 4000;
  const dustGeometry = new THREE.BufferGeometry();
  dustGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(DUST * 3), 3));
  const dr = new Float32Array(DUST), da = new Float32Array(DUST), ds = new Float32Array(DUST);
  for (let i = 0; i < DUST; i++) { dr[i] = 1.05 + 2.3 * Math.pow(Math.random(), 1.3); da[i] = Math.random() * 6.283; ds[i] = 4 + Math.random() * 10; }
  dustGeometry.setAttribute("aRadius", new THREE.BufferAttribute(dr, 1));
  dustGeometry.setAttribute("aAngle", new THREE.BufferAttribute(da, 1));
  dustGeometry.setAttribute("aSize", new THREE.BufferAttribute(ds, 1));
  dustGeometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 4);
  const dustMaterial = new THREE.ShaderMaterial({
    vertexShader: DUST_VERTEX, fragmentShader: DUST_FRAGMENT,
    uniforms: { uTime: { value: 0 }, uPixel: { value: 1 }, uOpacity: { value: 1 } },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const dust = new THREE.Points(dustGeometry, dustMaterial);

  // Trou noir : une sphère noire qui cache les particules situées derrière elle.
  const hole = new THREE.Mesh(new THREE.SphereGeometry(0.98, 48, 32), new THREE.MeshBasicMaterial({ color: 0x000000 }));
  hole.renderOrder = -1;

  const orbit = new THREE.Group();
  orbit.add(hole, disk, dust);
  scene.add(orbit);

  // Planète éclairée, qui tourne sur elle-même, avec une atmosphère cyan sur le bord.
  const planet = new THREE.Group();
  const globe = new THREE.Mesh(new THREE.SphereGeometry(0.42, 64, 48),
    new THREE.MeshStandardMaterial({ map: planetTexture(THREE), roughness: 1, metalness: 0,
                                     emissive: 0x0a1a2a, emissiveIntensity: 0.4 }));
  const atmosphereMaterial = new THREE.ShaderMaterial({
    vertexShader: ATMOSPHERE_VERTEX, fragmentShader: ATMOSPHERE_FRAGMENT, uniforms: { uOpacity: { value: 1 } },
    transparent: true, blending: THREE.AdditiveBlending, side: THREE.BackSide, depthWrite: false,
  });
  const atmosphere = new THREE.Mesh(new THREE.SphereGeometry(0.5, 48, 32), atmosphereMaterial);
  planet.add(globe, atmosphere);
  scene.add(planet);
  scene.add(new THREE.AmbientLight(0x334455, 0.6));
  const sun = new THREE.DirectionalLight(0xbfe6ff, 2.2);
  sun.position.set(-4, 3, 5);
  scene.add(sun);

  // Viseur HTML qui suit la planète à l'écran.
  const target = document.createElement("div");
  target.className = "orbit-target";
  target.setAttribute("aria-hidden", "true");
  target.innerHTML = '<span class="spin"><i></i><i></i><i></i><i></i></span>';
  document.body.append(target);

  let W = 0, H = 0;
  function resize() {
    W = innerWidth; H = innerHeight;
    renderer.setSize(W, H, false);
    canvas.style.width = `${W}px`; canvas.style.height = `${H}px`;
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
    dustMaterial.uniforms.uPixel.value = renderer.getPixelRatio() * H / 900 * 1.6;
  }
  resize();
  addEventListener("resize", resize);

  const mouse = { x: 0, y: 0 }, parallax = { x: 0, y: 0 };
  addEventListener("mousemove", (event) => {
    mouse.x = event.clientX / W * 2 - 1; mouse.y = event.clientY / H * 2 - 1;
  }, { passive: true });

  let view = targetState(H);
  const world = new THREE.Vector3(), screen = new THREE.Vector3();
  const clock = new THREE.Clock();

  function frame() {
    const goal = targetState(H), k = reduceMotion ? 1 : 0.06;     // inertie de la caméra
    for (const key of Object.keys(view)) view[key] += (goal[key] - view[key]) * k;
    const t = reduceMotion ? 0 : clock.getElapsedTime();

    orbit.position.set(view.x, view.y, view.z);
    orbit.scale.setScalar(view.s);
    orbit.rotation.set(view.rx, 0, view.rz);
    diskMaterial.uniforms.uTime.value = t;
    diskMaterial.uniforms.uOpacity.value = view.op;
    dustMaterial.uniforms.uTime.value = t;
    dustMaterial.uniforms.uOpacity.value = view.op;
    atmosphereMaterial.uniforms.uOpacity.value = Math.min(1, view.op * 1.6);

    world.set(view.px, view.py, view.pz).multiplyScalar(view.s).add(orbit.position);
    planet.position.copy(world);
    planet.position.y += Math.sin(t * 0.8) * 0.04;
    planet.scale.setScalar(Math.max(0.0001, view.ps * view.s));
    planet.visible = view.ps > 0.05;
    globe.rotation.y = t * 0.12;

    if (!reduceMotion) {
      parallax.x += (mouse.x * 0.35 - parallax.x) * 0.04;
      parallax.y += (-mouse.y * 0.22 - parallax.y) * 0.04;
    }
    camera.position.set(parallax.x, parallax.y, 8);
    camera.lookAt(parallax.x * 0.3, parallax.y * 0.3, 0);
    renderer.render(scene, camera);

    // Viseur : centré sur la planète, de la taille de son disque à l'écran.
    if (planet.visible && view.op > 0.2) {
      screen.copy(planet.position).project(camera);
      const edge = planet.position.clone().add(new THREE.Vector3(0.42 * planet.scale.x, 0, 0)).project(camera);
      const px = (screen.x + 1) / 2 * W, py = (1 - screen.y) / 2 * H;
      const pr = Math.abs(edge.x - screen.x) / 2 * W * 0.62;
      target.style.transform = `translate(${px - pr}px, ${py - pr}px)`;
      target.style.width = target.style.height = `${2 * pr}px`;
      target.style.opacity = Math.min(1, view.op * 1.2).toFixed(2);
    } else {
      target.style.opacity = "0";
    }
    if (!reduceMotion) requestAnimationFrame(frame);
  }
  if (reduceMotion) {
    addEventListener("scroll", () => requestAnimationFrame(frame), { passive: true });
    addEventListener("resize", () => requestAnimationFrame(frame));
  }
  requestAnimationFrame(frame);
  document.documentElement.dataset.orbit = "3d";
}

start().catch(fallback);
