import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { buildObstacle, buildPebbles } from './obstacles.js';
import { hazardTexture, regolithTexture, textTexture } from './textures.js';

// Coordenadas del simulador: x hacia el este, y hacia el sur, celdas de 1 m.
// En three.js: x → x, y → z, y el mapa queda centrado en el origen.
export function cellCenter(map, x, y, height = 0) {
  return new THREE.Vector3(x + 0.5 - map.size / 2, height, y + 0.5 - map.size / 2);
}

export function rectCenter(map, rect, height = 0) {
  return new THREE.Vector3(rect.x + rect.w / 2 - map.size / 2, height, rect.y + rect.h / 2 - map.size / 2);
}

const BEACON_CYAN = new THREE.Color('#22d6ef');
const BEACON_GREEN = new THREE.Color('#1fcf5c');

function mesh(geometry, material, { cast = true, receive = true } = {}) {
  const m = new THREE.Mesh(geometry, material);
  m.castShadow = cast;
  m.receiveShadow = receive;
  return m;
}

function buildBeacon(map, beacon) {
  const group = new THREE.Group();
  group.position.copy(cellCenter(map, beacon.x, beacon.y));

  const plinth = mesh(
    new THREE.CylinderGeometry(0.26, 0.3, 0.14, 24),
    new THREE.MeshStandardMaterial({ color: '#2b3440', roughness: 0.7 }),
  );
  plinth.position.y = 0.07;

  const glow = new THREE.MeshStandardMaterial({
    color: BEACON_CYAN,
    emissive: BEACON_CYAN,
    emissiveIntensity: 0.9,
    roughness: 0.35,
  });
  const pole = mesh(new THREE.CylinderGeometry(0.07, 0.08, 0.8, 16), glow);
  pole.position.y = 0.54;
  const head = mesh(new RoundedBoxGeometry(0.38, 0.38, 0.38, 3, 0.06), glow);
  head.position.y = 1.08;

  const label = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: textTexture(String(beacon.id), { width: 128, height: 128 }), depthWrite: false }),
  );
  label.scale.set(0.62, 0.62, 1);
  label.position.y = 1.62;

  const halo = new THREE.Mesh(
    new THREE.RingGeometry(0.34, 0.46, 40),
    new THREE.MeshBasicMaterial({ color: BEACON_CYAN, transparent: true, opacity: 0.45, depthWrite: false }),
  );
  halo.rotation.x = -Math.PI / 2;
  halo.position.y = 0.02;

  group.add(plinth, pole, head, label, halo);

  const color = BEACON_CYAN.clone();
  let visited = false;
  return {
    id: beacon.id,
    group,
    position: group.position.clone(),
    setVisited(value) {
      visited = value;
    },
    update(time, dt) {
      // El color se acerca suavemente al estado que dicta el frame.
      color.lerp(visited ? BEACON_GREEN : BEACON_CYAN, 1 - Math.exp(-dt * 8));
      glow.color.copy(color);
      glow.emissive.copy(color);
      halo.material.color.copy(color);
      const pulse = 0.5 + 0.5 * Math.sin(time * 3 + beacon.id);
      glow.emissiveIntensity = 0.55 + pulse * 0.75;
      halo.scale.setScalar(1 + pulse * 0.25);
      halo.material.opacity = 0.25 + (1 - pulse) * 0.3;
      label.position.y = 1.62 + Math.sin(time * 2 + beacon.id) * 0.06;
    },
  };
}

function buildBase(map) {
  const { base } = map;
  const group = new THREE.Group();
  group.position.copy(rectCenter(map, base));

  const slab = mesh(
    new RoundedBoxGeometry(base.w - 0.12, 0.08, base.h - 0.12, 2, 0.03),
    new THREE.MeshStandardMaterial({ color: '#2f9e57', roughness: 0.6 }),
    { cast: false },
  );
  slab.position.y = 0.04;

  const text = new THREE.Mesh(
    new THREE.PlaneGeometry(Math.min(base.w, base.h * 2) * 0.8, Math.min(base.w, base.h * 2) * 0.4),
    new THREE.MeshBasicMaterial({
      map: textTexture('BASE', { width: 512, height: 256, color: '#eafff0' }),
      transparent: true,
      depthWrite: false,
    }),
  );
  text.rotation.x = -Math.PI / 2;
  text.position.y = 0.085;

  // Borde iluminado: cuatro listones emisivos.
  const edge = new THREE.MeshStandardMaterial({ color: '#7dffa8', emissive: '#56f08d', emissiveIntensity: 2.2 });
  const t = 0.06;
  const w = base.w - 0.08;
  const h = base.h - 0.08;
  for (const [sx, sz, px, pz] of [
    [w, t, 0, -h / 2],
    [w, t, 0, h / 2],
    [t, h, -w / 2, 0],
    [t, h, w / 2, 0],
  ]) {
    const strip = mesh(new THREE.BoxGeometry(sx, 0.05, sz), edge, { cast: false });
    strip.position.set(px, 0.09, pz);
    group.add(strip);
  }
  group.add(slab, text);
  return group;
}

function buildBlocked(map, rect) {
  const group = new THREE.Group();
  group.position.copy(rectCenter(map, rect));
  const stripes = hazardTexture();
  stripes.repeat.set(Math.max(rect.w, rect.h), 1);
  const barrier = new THREE.MeshStandardMaterial({ map: stripes, roughness: 0.5 });
  const post = new THREE.MeshStandardMaterial({ color: '#3a3f47', roughness: 0.6 });
  const lamp = new THREE.MeshStandardMaterial({ color: '#ff5a3c', emissive: '#ff3b1f', emissiveIntensity: 2.5 });

  const horizontal = rect.w >= rect.h;
  const length = (horizontal ? rect.w : rect.h) - 0.1;
  for (const y of [0.3, 0.62]) {
    const bar = mesh(new RoundedBoxGeometry(horizontal ? length : 0.12, 0.16, horizontal ? 0.12 : length, 2, 0.03), barrier);
    bar.position.y = y;
    group.add(bar);
  }
  for (const s of [-1, 1]) {
    const p = mesh(new THREE.BoxGeometry(0.12, 0.8, 0.12), post);
    const offset = (s * length) / 2;
    p.position.set(horizontal ? offset : 0, 0.4, horizontal ? 0 : offset);
    const light = mesh(new THREE.SphereGeometry(0.07, 12, 8), lamp, { cast: false });
    light.position.set(p.position.x, 0.86, p.position.z);
    group.add(p, light);
  }
  return { group, lamp };
}

// Construye el diorama a partir de map (World.to_dict() del simulador).
export function buildWorld(map) {
  const n = map.size;
  const group = new THREE.Group();

  // Suelo compactado de la zona de pruebas (un poco más claro que el terreno de alrededor).
  const regolith = regolithTexture('#cf7748', 8);
  regolith.repeat.set(n / 6, n / 6);
  const floor = mesh(
    new THREE.PlaneGeometry(n, n),
    new THREE.MeshStandardMaterial({ map: regolith, roughness: 0.95 }),
    { cast: false },
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0.004;
  group.add(floor);

  // Paredes gris claro con bisel y grosor, con franja naranja y luces de posición.
  const wallMat = new THREE.MeshStandardMaterial({ color: '#d9dce1', roughness: 0.7 });
  const stripeMat = new THREE.MeshStandardMaterial({ color: '#e2782c', roughness: 0.6 });
  const lampMat = new THREE.MeshStandardMaterial({ color: '#ffe2b0', emissive: '#ffbf66', emissiveIntensity: 2 });
  const t = 0.35;
  const height = 0.75;
  for (const [sx, sz, px, pz] of [
    [n + 2 * t, t, 0, -n / 2 - t / 2],
    [n + 2 * t, t, 0, n / 2 + t / 2],
    [t, n, -n / 2 - t / 2, 0],
    [t, n, n / 2 + t / 2, 0],
  ]) {
    const wall = mesh(new RoundedBoxGeometry(sx, height, sz, 3, 0.07), wallMat);
    wall.position.set(px, height / 2, pz);
    const stripe = mesh(new THREE.BoxGeometry(sx + 0.01, 0.07, sz + 0.01), stripeMat, { cast: false });
    stripe.position.set(px, height * 0.62, pz);
    group.add(wall, stripe);
  }
  for (const [cx, cz] of [
    [-1, -1],
    [1, -1],
    [-1, 1],
    [1, 1],
  ]) {
    const post = mesh(new RoundedBoxGeometry(0.5, 1.1, 0.5, 2, 0.06), wallMat);
    post.position.set(cx * (n / 2 + t / 2), 0.55, cz * (n / 2 + t / 2));
    const lamp = mesh(new THREE.SphereGeometry(0.09, 12, 8), lampMat, { cast: false });
    lamp.position.set(post.position.x, 1.17, post.position.z);
    group.add(post, lamp);
  }

  map.obstacles.forEach((rect, i) => {
    const obstacle = buildObstacle(rect, i);
    obstacle.position.add(rectCenter(map, rect));
    group.add(obstacle);
  });
  group.add(buildPebbles(map, (x, y) => cellCenter(map, x, y)));

  const blocked = (map.blocked ?? []).map((rect) => buildBlocked(map, rect));
  for (const b of blocked) group.add(b.group);

  group.add(buildBase(map));

  const beacons = new Map();
  for (const beacon of map.beacons) {
    const b = buildBeacon(map, beacon);
    beacons.set(beacon.id, b);
    group.add(b.group);
  }

  const grid = new THREE.GridHelper(n, n, '#5a2a14', '#5a2a14');
  grid.material.transparent = true;
  grid.material.opacity = 0.16;
  grid.material.depthWrite = false;
  grid.position.y = 0.006;
  group.add(grid);

  return {
    group,
    beacons,
    guides: [grid],
    baseCenter: rectCenter(map, map.base),
    update(time, dt) {
      for (const b of beacons.values()) b.update(time, dt);
      for (const b of blocked) b.lamp.emissiveIntensity = 1.2 + (Math.sin(time * 6) > 0 ? 2.2 : 0);
    },
  };
}

export function disposeObject(root) {
  root.traverse((obj) => {
    obj.geometry?.dispose();
    const materials = Array.isArray(obj.material) ? obj.material : obj.material ? [obj.material] : [];
    for (const m of materials) {
      m.map?.dispose();
      m.dispose();
    }
  });
}
