// Relieve marciano para los obstáculos. Para la física cada obstáculo es un rectángulo
// infranqueable; aquí solo se decide cómo se ve dentro de ese rectángulo según `kind`.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { basaltTexture, containerTexture, strataTexture } from './textures.js';

function seeded(seed) {
  let s = (seed * 2654435761) >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function shade(m) {
  m.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  return m;
}

function box(rect, height, material, inset = 0.08) {
  return new THREE.Mesh(new RoundedBoxGeometry(rect.w - inset, height, rect.h - inset, 4, 0.09), material);
}

// Contenedor de carga.
function container(rect, index) {
  const h = 1.3 + (index % 3) * 0.08;
  const m = box(rect, h, new THREE.MeshStandardMaterial({
    map: containerTexture('#e2782c', `ARES-${String(index + 1).padStart(2, '0')}`),
    roughness: 0.55,
    metalness: 0.15,
  }));
  m.position.y = h / 2;
  return m;
}

// Bloque de arenisca o de basalto (los tipos del experimento 1).
function block(rect, index, kind) {
  const h = kind === 'coral' ? 1.0 + (index % 3) * 0.06 : 1.15 + (index % 3) * 0.06;
  const map = kind === 'coral' ? strataTexture('#d9614a', 11 + index) : basaltTexture('#8d8884', 5 + index);
  const m = box(rect, h, new THREE.MeshStandardMaterial({ map, roughness: 0.92 }));
  m.position.y = h / 2;
  return m;
}

// Meseta: capas de arenisca apiladas, cada una algo más pequeña y desplazada.
function mesa(rect, index) {
  const rand = seeded(index + 101);
  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({ map: strataTexture('#b9573a', 31 + index), roughness: 0.95 });
  const layers = 3 + Math.floor(rand() * 2);
  let y = 0;
  for (let k = 0; k < layers; k++) {
    const shrink = k * 0.22;
    const w = Math.max(0.5, rect.w - 0.08 - shrink * (0.6 + rand() * 0.6));
    const d = Math.max(0.5, rect.h - 0.08 - shrink * (0.6 + rand() * 0.6));
    const h = 0.45 + rand() * 0.3;
    const layer = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, 0.07), material);
    layer.position.set((rand() - 0.5) * shrink * 0.4, y + h / 2, (rand() - 0.5) * shrink * 0.4);
    group.add(layer);
    y += h * 0.96;
  }
  return group;
}

// Cráter: borde levantado y fondo oscuro, ajustado al rectángulo.
function crater(rect, index) {
  const rand = seeded(index + 7);
  const group = new THREE.Group();
  const rimHeight = 0.35 + Math.min(rect.w, rect.h) * 0.1;
  // Perfil (radio, altura) de un cráter de radio 0.5; luego se escala al rectángulo.
  const profile = [
    [0.0, 0.03], [0.22, 0.04], [0.33, 0.12], [0.4, 0.55], [0.44, 0.92], [0.46, 1.0], [0.49, 0.45], [0.5, 0.0],
  ].map(([r, h]) => new THREE.Vector2(r, h));
  const geometry = new THREE.LatheGeometry(profile, 28);
  const rim = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: '#b2603c', roughness: 1, flatShading: true }));
  rim.scale.set(rect.w - 0.06, rimHeight, rect.h - 0.06);
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(0.34, 28),
    new THREE.MeshStandardMaterial({ color: '#6a2f1b', roughness: 1 }),
  );
  floor.rotation.x = -Math.PI / 2;
  floor.scale.set(rect.w - 0.06, rect.h - 0.06, 1);
  floor.position.y = 0.045;
  group.add(rim, floor);
  // Unas piedras dentro del cráter.
  const rockMat = new THREE.MeshStandardMaterial({ color: '#7a3a22', roughness: 1, flatShading: true });
  for (let k = 0; k < 4; k++) {
    const s = 0.08 + rand() * 0.12;
    const r = new THREE.Mesh(new THREE.DodecahedronGeometry(s, 0), rockMat);
    r.position.set((rand() - 0.5) * rect.w * 0.4, 0.06 + s * 0.4, (rand() - 0.5) * rect.h * 0.4);
    r.rotation.set(rand() * 3, rand() * 3, 0);
    group.add(r);
  }
  return group;
}

// Campo de rocas: varios bloques que llenan el rectángulo.
function rocks(rect, index) {
  const rand = seeded(index + 53);
  const group = new THREE.Group();
  const material = new THREE.MeshStandardMaterial({ color: '#8a4a30', roughness: 0.95, flatShading: true });
  const count = Math.max(3, Math.round(rect.w * rect.h * 2.5));
  for (let k = 0; k < count; k++) {
    const s = 0.22 + rand() * 0.28;
    const r = new THREE.Mesh(new THREE.DodecahedronGeometry(s, 0), material.clone());
    r.material.color.offsetHSL(0, 0, (rand() - 0.5) * 0.12);
    const px = (rand() - 0.5) * (rect.w - 2 * s * 0.8);
    const pz = (rand() - 0.5) * (rect.h - 2 * s * 0.8);
    r.position.set(px, s * (0.55 + rand() * 0.6), pz);
    r.scale.set(1, 0.7 + rand() * 0.8, 1);
    r.rotation.set(rand() * 3, rand() * 3, rand() * 3);
    group.add(r);
  }
  return group;
}

// Duna: joroba alargada de arena con ondulaciones.
function dune(rect) {
  const long = Math.max(rect.w, rect.h);
  const short = Math.min(rect.w, rect.h);
  const geometry = new THREE.PlaneGeometry(long - 0.06, short - 0.06, 48, 16);
  geometry.rotateX(-Math.PI / 2);
  const pos = geometry.attributes.position;
  const height = 0.55 + short * 0.15;
  for (let i = 0; i < pos.count; i++) {
    const u = pos.getX(i) / (long - 0.06) + 0.5; // 0..1 a lo largo
    const v = pos.getZ(i) / (short - 0.06) + 0.5; // 0..1 a lo ancho
    const across = Math.sin(Math.PI * v) ** 1.4;
    const along = Math.min(1, Math.sin(Math.PI * u) * 1.6);
    const ripple = 1 + Math.sin(u * long * 6) * 0.04;
    // Cresta desplazada hacia un lado, como las dunas reales.
    const crest = Math.max(0, across * (1 - 0.25 * (v - 0.5)));
    pos.setY(i, height * crest * along * ripple);
  }
  geometry.computeVertexNormals();
  const m = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: '#d68a57', roughness: 1, flatShading: true }));
  if (rect.h > rect.w) m.rotation.y = Math.PI / 2;
  return m;
}

export function buildObstacle(rect, index) {
  const builders = { orange: container, mesa, crater, rocks, dune };
  const object = builders[rect.kind]?.(rect, index) ?? block(rect, index, rect.kind);
  return shade(object);
}

// Piedrecitas sobre las celdas libres: textura de suelo, demasiado bajas para estorbar.
export function buildPebbles(map, cellToWorld) {
  const occupied = new Set();
  const mark = (r) => {
    for (let y = r.y; y < r.y + r.h; y++) for (let x = r.x; x < r.x + r.w; x++) occupied.add(`${x},${y}`);
  };
  map.obstacles.forEach(mark);
  (map.blocked ?? []).forEach(mark);
  mark(map.base);
  for (const b of map.beacons) occupied.add(`${b.x},${b.y}`);

  const rand = seeded(map.size * 13 + 1);
  const spots = [];
  for (let y = 0; y < map.size; y++) {
    for (let x = 0; x < map.size; x++) {
      if (occupied.has(`${x},${y}`)) continue;
      const count = rand() < 0.35 ? 1 + Math.floor(rand() * 3) : 0;
      for (let k = 0; k < count; k++) spots.push([x + rand(), y + rand(), 0.025 + rand() * 0.05]);
    }
  }
  const mesh = new THREE.InstancedMesh(
    new THREE.DodecahedronGeometry(1, 0),
    new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 1, flatShading: true }),
    Math.max(1, spots.length),
  );
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const color = new THREE.Color();
  spots.forEach(([x, y, s], i) => {
    const p = cellToWorld(x - 0.5, y - 0.5);
    q.setFromEuler(new THREE.Euler(rand() * 3, rand() * 3, rand() * 3));
    m.compose(new THREE.Vector3(p.x, s * 0.4, p.z), q, new THREE.Vector3(s * 1.3, s * 0.6, s));
    mesh.setMatrixAt(i, m);
    mesh.setColorAt(i, color.set('#7d3b22').offsetHSL(0, 0, (rand() - 0.5) * 0.15));
  });
  mesh.count = spots.length;
  mesh.receiveShadow = true;
  return mesh;
}
