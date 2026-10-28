import * as THREE from 'three';

const SENSOR_HEIGHT = 0.8; // a la altura del visor

// Dirección en el plano para un rumbo en grados de brújula (0 = norte = −z, 90 = este = +x).
export function compassVector(deg) {
  const r = THREE.MathUtils.degToRad(deg);
  return new THREE.Vector3(Math.sin(r), 0, -Math.cos(r));
}

// Rayos de los sensores: líneas cian semitransparentes y un punto donde chocan.
export class Rays {
  constructor(count = 9) {
    this.count = count;
    this.positions = new Float32Array(count * 6);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(this.positions, 3));
    this.lines = new THREE.LineSegments(
      geometry,
      new THREE.LineBasicMaterial({ color: '#57e6f7', transparent: true, opacity: 0.55, depthWrite: false }),
    );
    this.hits = new THREE.InstancedMesh(
      new THREE.SphereGeometry(0.045, 10, 8),
      new THREE.MeshBasicMaterial({ color: '#9ff6ff' }),
      count,
    );
    this.object = new THREE.Group();
    this.object.add(this.lines, this.hits);
    this._m = new THREE.Matrix4();
  }

  // rays: [{angle_deg, distance, hit}] ya interpolados por el reproductor.
  update(origin, headingDeg, rays) {
    const p = this.positions;
    rays.forEach((ray, i) => {
      const dir = compassVector(headingDeg + ray.angle_deg);
      const sx = origin.x + dir.x * 0.25;
      const sz = origin.z + dir.z * 0.25;
      const ex = origin.x + dir.x * ray.distance;
      const ez = origin.z + dir.z * ray.distance;
      p.set([sx, SENSOR_HEIGHT, sz, ex, SENSOR_HEIGHT, ez], i * 6);
      const scale = ray.hit ? 1 : 0;
      this._m.makeScale(scale, scale, scale).setPosition(ex, SENSOR_HEIGHT, ez);
      this.hits.setMatrixAt(i, this._m);
    });
    this.lines.geometry.attributes.position.needsUpdate = true;
    this.lines.geometry.computeBoundingSphere();
    this.hits.instanceMatrix.needsUpdate = true;
  }
}

// Estela punteada blanca con la ruta recorrida.
export class Trail {
  constructor() {
    this.object = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineDashedMaterial({ color: '#ffffff', dashSize: 0.14, gapSize: 0.12, transparent: true, opacity: 0.9 }),
    );
    this.object.frustumCulled = false;
  }

  setPoints(points) {
    const old = this.object.geometry;
    this.object.geometry = new THREE.BufferGeometry().setFromPoints(points);
    this.object.computeLineDistances();
    old.dispose();
  }
}

// Línea guía del robot al objetivo actual.
export class GuideLine {
  constructor() {
    this.object = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineDashedMaterial({ color: '#57e6f7', dashSize: 0.08, gapSize: 0.16, transparent: true, opacity: 0.4 }),
    );
    this.object.frustumCulled = false;
  }

  update(from, to) {
    const pos = this.object.geometry.attributes.position;
    pos.setXYZ(0, from.x, 0.05, from.z);
    pos.setXYZ(1, to.x, 0.05, to.z);
    pos.needsUpdate = true;
    this.object.computeLineDistances();
  }
}

// Destellos de partículas (baliza visitada, misión completada).
export class Bursts {
  constructor() {
    this.object = new THREE.Group();
    this.active = [];
  }

  burst(position, color = '#3ee07a', count = 70) {
    const positions = new Float32Array(count * 3);
    const velocities = [];
    for (let i = 0; i < count; i++) {
      positions.set([position.x, position.y, position.z], i * 3);
      const a = Math.random() * Math.PI * 2;
      const up = 1.5 + Math.random() * 2.2;
      const out = 0.6 + Math.random() * 1.4;
      velocities.push(new THREE.Vector3(Math.cos(a) * out, up, Math.sin(a) * out));
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
      color,
      size: 0.11,
      transparent: true,
      opacity: 1,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, material);
    this.object.add(points);
    this.active.push({ points, velocities, life: 0, duration: 1.3 });
  }

  update(dt) {
    for (const b of this.active) {
      b.life += dt;
      const pos = b.points.geometry.attributes.position;
      b.velocities.forEach((v, i) => {
        v.y -= 4.5 * dt;
        pos.setXYZ(i, pos.getX(i) + v.x * dt, Math.max(0.03, pos.getY(i) + v.y * dt), pos.getZ(i) + v.z * dt);
      });
      pos.needsUpdate = true;
      b.points.material.opacity = Math.max(0, 1 - b.life / b.duration);
    }
    for (const b of this.active.filter((x) => x.life >= x.duration)) {
      this.object.remove(b.points);
      b.points.geometry.dispose();
      b.points.material.dispose();
    }
    this.active = this.active.filter((x) => x.life < x.duration);
  }
}
