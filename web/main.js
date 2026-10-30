// Three.js client for the Look Away heads. Implements SPECS/17 (Client).
// Heads are drawn left to right as zone 0, 1, 2 from the audience's view.
import * as THREE from "three";
import { indicator, personColor } from "./indicator.js";
import { applyPose } from "./pose.js";

const SLEEP_PITCH = -0.45;
const HEAD_X = [-2.4, 0, 2.4];
const SMOOTH_TIME = 0.03; // seconds; critically damped follow (D15: near-immediate)

const statusEl = document.getElementById("status");
const camPanel = document.getElementById("cam");
const camCanvas = document.getElementById("camview");
const camCtx = camCanvas.getContext("2d");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0b0e);
const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
camera.position.set(0, 0.2, 9);
scene.add(new THREE.HemisphereLight(0xdfe6ff, 0x1a1a22, 0.9));
const key = new THREE.DirectionalLight(0xffffff, 1.3);
key.position.set(2, 4, 6);
scene.add(key);

// Optional mannequin model: drop a GLB at web/assets/heads.glb (see web/assets/README.md).
async function loadHeadTemplate() {
  try {
    const probe = await fetch("./assets/heads.glb", { method: "HEAD" });
    if (!probe.ok) return null;
    const { GLTFLoader } = await import("./vendor/loaders/GLTFLoader.js");
    const gltf = await new GLTFLoader().loadAsync("./assets/heads.glb");
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const wrapper = new THREE.Group();
    gltf.scene.position.sub(center); // pivot at the model centre
    wrapper.add(gltf.scene);
    wrapper.scale.setScalar(2.0 / Math.max(size.y, 1e-6));
    return wrapper;
  } catch (err) {
    console.warn("heads.glb not used:", err);
    return null;
  }
}

function makeGlbHead(x, template) {
  const root = new THREE.Group();
  root.position.x = x;
  const group = new THREE.Group();
  group.add(template.clone(true));
  root.add(group);
  scene.add(root);
  return group;
}

function makeHead(x) {
  const group = new THREE.Group();
  group.position.x = x;
  const skin = new THREE.MeshStandardMaterial({ color: 0xe8e4dc, roughness: 0.55 });
  group.add(new THREE.Mesh(new THREE.SphereGeometry(0.85, 48, 32), skin));
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.5, 24), skin);
  nose.rotation.x = Math.PI / 2; // cone tip toward +z, the facing direction
  nose.position.set(0, -0.05, 0.95);
  group.add(nose);
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x1b1b22 });
  for (const sx of [-0.3, 0.3]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), eyeMat);
    eye.position.set(sx, 0.2, 0.78);
    group.add(eye);
  }
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.34, 0.9, 24), skin);
  neck.position.y = -1.15;
  const root = new THREE.Group();
  root.position.x = x;
  root.add(neck);
  group.position.x = 0;
  root.add(group);
  scene.add(root);
  return group;
}

const template = await loadHeadTemplate();
const heads = HEAD_X.map((x) => (template ? makeGlbHead(x, template) : makeHead(x)));
const target = HEAD_X.map(() => ({ yaw: 0, pitch: SLEEP_PITCH }));
const current = HEAD_X.map(() => ({ yaw: 0, pitch: SLEEP_PITCH, vy: 0, vp: 0 }));

// Indicator under each head: which face (#N, as in the camera view) it is looking at.
const TAG_ANCHOR_Y = -1.9; // just below the neck, in scene units
const tags = HEAD_X.map(() => {
  const el = document.createElement("div");
  el.className = "tag";
  el.innerHTML = '<i class="dot"></i><span></span>';
  document.body.appendChild(el);
  return el;
});

function setIndicators(list) {
  for (const h of list) {
    const el = tags[h.id];
    if (!el) continue;
    const ind = indicator(h);
    el.querySelector("span").textContent = ind.text;
    el.querySelector(".dot").style.background = personColor(ind.person);
    el.dataset.kind = ind.kind;
  }
}

const anchor = new THREE.Vector3();
function placeIndicators() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  tags.forEach((el, i) => {
    anchor.set(HEAD_X[i], TAG_ANCHOR_Y, 0).project(camera);
    el.style.left = `${((anchor.x + 1) / 2) * w}px`;
    const y = ((1 - anchor.y) / 2) * h;
    el.style.top = `${Math.min(y, h - el.offsetHeight - 30)}px`; // never below the window edge
  });
}
let connected = false;

function smoothDamp(x, goal, v, dt) {
  // Critically damped spring (Game Programming Gems 4).
  const omega = 2 / SMOOTH_TIME;
  const xk = omega * dt;
  const exp = 1 / (1 + xk + 0.48 * xk * xk + 0.235 * xk * xk * xk);
  const change = x - goal;
  const temp = (v + omega * change) * dt;
  return [goal + (change + temp) * exp, (v - omega * temp) * exp];
}

function setTargets(list) {
  for (const h of list) {
    if (h.id >= 0 && h.id < target.length) {
      target[h.id].yaw = h.yaw;
      target[h.id].pitch = h.pitch;
    }
  }
}

function setStatus(text) {
  statusEl.textContent = text;
}

let decoding = false;
function drawCameraFrame(blob) {
  if (decoding) return; // drop frames while the previous one is still decoding
  decoding = true;
  createImageBitmap(blob)
    .then((bmp) => {
      if (camCanvas.width !== bmp.width || camCanvas.height !== bmp.height) {
        camCanvas.width = bmp.width;
        camCanvas.height = bmp.height;
      }
      camCtx.drawImage(bmp, 0, 0);
      bmp.close();
      if (camPanel.style.display !== "block") {
        camPanel.style.display = "block";
        resize(); // the heads move down to make room
      }
    })
    .catch(() => {})
    .finally(() => {
      decoding = false;
    });
}

let backoff = 0.5;
function connect() {
  const ws = new WebSocket(`ws://${location.host}/`);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "hello", client: "three" }));
  };
  ws.onmessage = (ev) => {
    if (typeof ev.data !== "string") {
      drawCameraFrame(ev.data); // binary message: one annotated JPEG of the camera view
      return;
    }
    const msg = JSON.parse(ev.data);
    if (msg.type === "snapshot") {
      connected = true;
      backoff = 0.5;
      setTargets(msg.heads);
      for (const h of msg.heads) {
        current[h.id].yaw = h.yaw;
        current[h.id].pitch = h.pitch;
      }
      setStatus("live");
    } else if (msg.type === "head_state") {
      setTargets(msg.heads);
      setIndicators(msg.heads);
      setStatus(msg.heads.map((h) => `${h.id}:${h.mode}`).join("  "));
    }
  };
  ws.onclose = () => {
    connected = false;
    for (const t of target) {
      t.yaw = 0;
      t.pitch = SLEEP_PITCH;
    }
    setIndicators(HEAD_X.map((_, id) => ({ id, mode: "idle", target_track: null, person: null })));
    setStatus("disconnected, retrying…");
    setTimeout(connect, backoff * 1000);
    backoff = Math.min(backoff * 2, 5);
  };
}

function resize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  // Shift the heads down just enough to clear the camera view (a touch lower without one).
  const panelBottom = camPanel.style.display === "block" ? camPanel.getBoundingClientRect().bottom : 0;
  const shift = panelBottom > 0 ? panelBottom * 0.3 : 0.03 * h;
  camera.setViewOffset(w, h, 0, -shift, w, h);
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

let last = performance.now();
function frame(now) {
  const dt = Math.min((now - last) / 1000, 0.1);
  last = now;
  heads.forEach((head, i) => {
    const c = current[i];
    [c.yaw, c.vy] = smoothDamp(c.yaw, target[i].yaw, c.vy, dt);
    [c.pitch, c.vp] = smoothDamp(c.pitch, target[i].pitch, c.vp, dt);
    applyPose(head.rotation, c.yaw, c.pitch);
  });
  renderer.render(scene, camera);
  placeIndicators();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
connect();
