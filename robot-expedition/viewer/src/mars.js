// Ambientación de Marte alrededor de la sala: terreno con dunas, montañas, cráteres,
// rocas, hábitat junto a la base, lunas y polvo en suspensión. Todo es decoración:
// nada de esto existe en el simulador y queda fuera de la grilla jugable.
import * as THREE from 'three';
import { regolithTexture, softDotTexture, solarPanelTexture } from './textures.js';

function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function smoothstep(a, b, x) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

function duneHeight(x, z) {
  return (
    Math.sin(x * 0.11 + Math.cos(z * 0.07) * 2) * 1.1 +
    Math.sin(z * 0.09 + x * 0.03) * 0.9 +
    Math.sin((x + z) * 0.23) * 0.25
  );
}

function buildTerrain(clear) {
  const size = 260;
  const geometry = new THREE.PlaneGeometry(size, size, 160, 160);
  geometry.rotateX(-Math.PI / 2);
  const pos = geometry.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i);
    const z = pos.getZ(i);
    // Plano alrededor de la sala; las dunas crecen con la distancia.
    const d = Math.max(Math.abs(x), Math.abs(z));
    const k = smoothstep(clear, clear + 14, d);
    pos.setY(i, -0.02 + duneHeight(x, z) * k * (1 + d / 60));
  }
  geometry.computeVertexNormals();
  const map = regolithTexture('#b9603a', 21);
  map.repeat.set(size / 6, size / 6);
  const terrain = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({ map, roughness: 1, flatShading: true }),
  );
  terrain.receiveShadow = true;
  return terrain;
}

function buildMountains(rand) {
  const group = new THREE.Group();
  const rock = new THREE.MeshStandardMaterial({ color: '#8c472b', roughness: 1, flatShading: true });
  const mesaMat = new THREE.MeshStandardMaterial({ color: '#9b5233', roughness: 1, flatShading: true });
  for (let i = 0; i < 34; i++) {
    const angle = (i / 34) * Math.PI * 2 + rand() * 0.15;
    const radius = 75 + rand() * 40;
    const mesa = rand() < 0.3;
    const h = mesa ? 5 + rand() * 6 : 8 + rand() * 16;
    const r = 10 + rand() * 16;
    const geometry = mesa
      ? new THREE.CylinderGeometry(r * 0.75, r, h, 7 + Math.floor(rand() * 3), 1)
      : new THREE.ConeGeometry(r, h, 5 + Math.floor(rand() * 3), 2);
    const m = new THREE.Mesh(geometry, mesa ? mesaMat : rock);
    m.position.set(Math.cos(angle) * radius, h / 2 - 1.5, Math.sin(angle) * radius);
    m.rotation.y = rand() * Math.PI;
    m.scale.z = 0.6 + rand() * 0.6;
    group.add(m);
  }
  return group;
}

function buildCraters(rand, clear) {
  const group = new THREE.Group();
  const rim = new THREE.MeshStandardMaterial({ color: '#a8583a', roughness: 1, flatShading: true });
  const floor = new THREE.MeshStandardMaterial({ color: '#8a4429', roughness: 1 });
  for (let i = 0; i < 9; i++) {
    const angle = rand() * Math.PI * 2;
    const dist = clear + 8 + rand() * 40;
    const r = 1.5 + rand() * 4.5;
    const crater = new THREE.Group();
    const ring = new THREE.Mesh(new THREE.TorusGeometry(r, r * 0.22, 6, 18), rim);
    ring.rotation.x = -Math.PI / 2;
    ring.scale.z = 0.45;
    const dish = new THREE.Mesh(new THREE.CircleGeometry(r * 0.95, 18), floor);
    dish.rotation.x = -Math.PI / 2;
    dish.position.y = 0.03;
    crater.add(ring, dish);
    const x = Math.cos(angle) * dist;
    const z = Math.sin(angle) * dist;
    const k = smoothstep(clear, clear + 14, Math.max(Math.abs(x), Math.abs(z)));
    crater.position.set(x, duneHeight(x, z) * k * (1 + dist / 60), z);
    ring.receiveShadow = dish.receiveShadow = true;
    group.add(crater);
  }
  return group;
}

function buildRocks(rand, clear) {
  const count = 160;
  const geometry = new THREE.DodecahedronGeometry(1, 0);
  const material = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.95, flatShading: true });
  const rocks = new THREE.InstancedMesh(geometry, material, count);
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  const color = new THREE.Color();
  for (let i = 0; i < count; i++) {
    const near = i < 70;
    const angle = rand() * Math.PI * 2;
    const dist = near ? clear + 0.8 + rand() * 7 : clear + 8 + rand() * 50;
    const x = Math.cos(angle) * dist;
    const z = Math.sin(angle) * dist;
    const s = near ? 0.08 + rand() * 0.35 : 0.2 + rand() * 1.1;
    e.set(rand() * 3, rand() * 3, rand() * 3);
    q.setFromEuler(e);
    const k = smoothstep(clear, clear + 14, Math.max(Math.abs(x), Math.abs(z)));
    const y = duneHeight(x, z) * k * (1 + dist / 60) + s * 0.35;
    m.compose(new THREE.Vector3(x, y, z), q, new THREE.Vector3(s * (0.8 + rand() * 0.6), s * 0.7, s));
    rocks.setMatrixAt(i, m);
    rocks.setColorAt(i, color.set('#a5563a').offsetHSL(0, 0, (rand() - 0.5) * 0.14));
  }
  rocks.castShadow = true;
  rocks.receiveShadow = true;
  return rocks;
}

// Hábitat con domo, paneles solares y antena, por fuera de la pared más cercana a la base.
function buildHabitat(map) {
  const group = new THREE.Group();
  const n = map.size;
  const bx = map.base.x + map.base.w / 2 - n / 2;
  const bz = map.base.y + map.base.h / 2 - n / 2;
  const outward = new THREE.Vector3(Math.sign(bx) || 1, 0, Math.sign(bz) || 1);
  const center = new THREE.Vector3(bx, 0, bz);
  // Se ubica al lado de la base, pasando la pared en la dirección x de la base.
  center.x = outward.x * (n / 2 + 4.2);

  const white = new THREE.MeshStandardMaterial({ color: '#eeebe4', roughness: 0.5 });
  const metal = new THREE.MeshStandardMaterial({ color: '#9ea4ad', roughness: 0.4, metalness: 0.4 });
  const windowMat = new THREE.MeshStandardMaterial({ color: '#ffd9a0', emissive: '#ffb75e', emissiveIntensity: 1.6 });
  const stripe = new THREE.MeshStandardMaterial({ color: '#e2782c', roughness: 0.6 });

  const dome = new THREE.Mesh(new THREE.SphereGeometry(2.1, 18, 10, 0, Math.PI * 2, 0, Math.PI / 2), white);
  dome.position.copy(center);
  const ring = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 2.25, 0.35, 24), stripe);
  ring.position.copy(center).setY(0.17);
  group.add(dome, ring);
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2 + 0.4;
    const w = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.18, 0.05), windowMat);
    w.position.set(center.x + Math.cos(a) * 1.75, 1.1, center.z + Math.sin(a) * 1.75);
    w.lookAt(center.x, 1.1, center.z);
    group.add(w);
  }
  // Túnel hacia la sala.
  const tunnel = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.55, 2.2, 14), white);
  tunnel.rotation.z = Math.PI / 2;
  tunnel.position.set(center.x - outward.x * 2.6, 0.55, center.z);
  group.add(tunnel);

  // Paneles solares.
  const panelMat = new THREE.MeshStandardMaterial({ map: solarPanelTexture(), roughness: 0.3, metalness: 0.5 });
  for (let i = 0; i < 4; i++) {
    const panel = new THREE.Group();
    const p = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.05, 1.0), panelMat);
    p.rotation.x = -0.5;
    p.position.y = 0.8;
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.8, 6), metal);
    leg.position.y = 0.4;
    panel.add(p, leg);
    panel.position.set(center.x + outward.x * 1.2 + (i % 2) * 1.9 * outward.x, 0, center.z - outward.z * (3.2 + Math.floor(i / 2) * 1.5));
    group.add(panel);
  }

  // Antena parabólica.
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.08, 2.4, 8), metal);
  mast.position.set(center.x + outward.x * 2.6, 1.2, center.z + outward.z * 2.2);
  const dish = new THREE.Mesh(new THREE.SphereGeometry(0.7, 16, 6, 0, Math.PI * 2, 0, Math.PI / 3.2), white);
  dish.material = white.clone();
  dish.material.side = THREE.DoubleSide;
  dish.position.set(mast.position.x, 2.5, mast.position.z);
  dish.rotation.set(-0.9, 0.6, 0);
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 8), new THREE.MeshStandardMaterial({
    color: '#ff5a3c', emissive: '#ff3b1f', emissiveIntensity: 2.5,
  }));
  beacon.position.set(mast.position.x, 2.45, mast.position.z);
  group.add(mast, dish, beacon);

  group.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
    }
  });
  return { group, beacon };
}

function buildSky() {
  const group = new THREE.Group();
  const dot = softDotTexture();
  const sun = new THREE.Sprite(new THREE.SpriteMaterial({ map: dot, color: '#fff3dc', fog: false, depthWrite: false }));
  sun.scale.setScalar(16);
  sun.position.set(-70, 95, 40);
  const moonMat = (c) => new THREE.MeshBasicMaterial({ color: c, fog: false });
  const phobos = new THREE.Mesh(new THREE.DodecahedronGeometry(2.2, 1), moonMat('#d8c3b0'));
  phobos.position.set(60, 55, -110);
  phobos.scale.set(1.3, 1, 1);
  const deimos = new THREE.Mesh(new THREE.DodecahedronGeometry(1.1, 1), moonMat('#e6d6c5'));
  deimos.position.set(-35, 70, -120);
  group.add(sun, phobos, deimos);
  return group;
}

// Polvo en suspensión que deriva con el viento.
function buildDust(count = 600, spread = 34) {
  const rand = seeded(99);
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    positions.set([(rand() - 0.5) * spread * 2, rand() * 5, (rand() - 0.5) * spread * 2], i * 3);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const points = new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      map: softDotTexture(),
      color: '#f0b083',
      size: 0.09,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    }),
  );
  return {
    points,
    update(dt, time) {
      const pos = geometry.attributes.position;
      for (let i = 0; i < count; i++) {
        let x = pos.getX(i) + dt * (0.9 + Math.sin(i) * 0.3);
        let y = pos.getY(i) + Math.sin(time * 0.8 + i) * dt * 0.15;
        if (x > spread) x = -spread;
        if (y < 0.05) y = 4.5;
        pos.setXY(i, x, y);
      }
      pos.needsUpdate = true;
    },
  };
}

export function buildMars(map) {
  const rand = seeded(2026);
  const clear = map.size / 2 + 0.6;
  const group = new THREE.Group();
  const habitat = buildHabitat(map);
  const dust = buildDust();
  group.add(
    buildTerrain(clear),
    buildMountains(rand),
    buildCraters(rand, clear + 6),
    buildRocks(rand, clear),
    habitat.group,
    buildSky(),
    dust.points,
  );
  return {
    group,
    update(time, dt) {
      dust.update(dt, time);
      habitat.beacon.material.emissiveIntensity = Math.sin(time * 2.5) > 0.6 ? 3 : 0.3;
    },
  };
}

// Nubecitas de polvo que levantan las ruedas al moverse.
export class WheelDust {
  constructor() {
    this.count = 160;
    this.positions = new Float32Array(this.count * 3).fill(-999);
    this.velocities = Array.from({ length: this.count }, () => new THREE.Vector3());
    this.life = new Float32Array(this.count);
    this.next = 0;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(this.positions, 3));
    this.object = new THREE.Points(
      geometry,
      new THREE.PointsMaterial({
        map: softDotTexture(),
        color: '#d9915f',
        size: 0.22,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
      }),
    );
    this.object.frustumCulled = false;
  }

  emit(position, amount) {
    for (let k = 0; k < amount; k++) {
      const i = this.next;
      this.next = (this.next + 1) % this.count;
      this.positions.set(
        [position.x + (Math.random() - 0.5) * 0.4, 0.08, position.z + (Math.random() - 0.5) * 0.4],
        i * 3,
      );
      this.velocities[i].set((Math.random() - 0.5) * 0.4, 0.25 + Math.random() * 0.35, (Math.random() - 0.5) * 0.4);
      this.life[i] = 1;
    }
  }

  update(dt) {
    for (let i = 0; i < this.count; i++) {
      if (this.life[i] <= 0) continue;
      this.life[i] -= dt * 1.1;
      const v = this.velocities[i];
      this.positions[i * 3] += v.x * dt;
      this.positions[i * 3 + 1] += v.y * dt;
      this.positions[i * 3 + 2] += v.z * dt;
      if (this.life[i] <= 0) this.positions[i * 3 + 1] = -999;
    }
    this.object.geometry.attributes.position.needsUpdate = true;
  }
}
