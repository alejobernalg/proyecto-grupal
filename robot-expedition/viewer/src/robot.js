import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { solarPanelTexture } from './textures.js';

export const WHEEL_RADIUS = 0.15;

// Robot low-poly: chasis blanco, ruedas oscuras, cabeza de sensores y antena.
// Mira hacia −z cuando rotation.y = 0 (norte en el simulador).
export function createRobot() {
  const root = new THREE.Group();
  const body = new THREE.Group(); // recibe el rebote al chocar sin mover la posición lógica
  root.add(body);

  const shadow = (m) => {
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
  };
  const white = new THREE.MeshStandardMaterial({ color: '#f2efe8', roughness: 0.45 });
  const trim = new THREE.MeshStandardMaterial({ color: '#cfcac0', roughness: 0.6 });
  const dark = new THREE.MeshStandardMaterial({ color: '#262b33', roughness: 0.55 });
  const tire = new THREE.MeshStandardMaterial({ color: '#1d2026', roughness: 0.85 });
  const hub = new THREE.MeshStandardMaterial({ color: '#9aa1ab', roughness: 0.4, metalness: 0.3 });
  const eye = new THREE.MeshStandardMaterial({ color: '#7ff4ff', emissive: '#3fe6ff', emissiveIntensity: 3 });
  const tip = new THREE.MeshStandardMaterial({ color: '#ff7a4d', emissive: '#ff5a2a', emissiveIntensity: 2.5 });

  const chassis = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.6, 0.24, 0.72, 3, 0.07), white));
  chassis.position.y = 0.27;
  const deck = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.46, 0.08, 0.44, 2, 0.03), trim));
  deck.position.set(0, 0.42, 0.07);
  const bumper = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.5, 0.08, 0.06, 2, 0.02), dark));
  bumper.position.set(0, 0.2, -0.38);

  const neck = shadow(new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.14, 10), dark));
  neck.position.set(0, 0.48, -0.14);
  const head = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.3, 0.17, 0.16, 2, 0.04), dark));
  head.position.set(0, 0.6, -0.16);
  for (const x of [-0.07, 0.07]) {
    const e = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.05, 0.02), eye);
    e.position.set(x, 0.61, -0.245);
    body.add(e);
  }

  const antenna = shadow(new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.36, 6), dark));
  antenna.position.set(0.17, 0.62, 0.2);
  const antennaTip = new THREE.Mesh(new THREE.SphereGeometry(0.04, 12, 8), tip);
  antennaTip.position.set(0.17, 0.81, 0.2);

  // Panel solar sobre la cubierta y mástil de cámara, estilo rover.
  const panel = shadow(new THREE.Mesh(
    new THREE.BoxGeometry(0.52, 0.025, 0.36),
    new THREE.MeshStandardMaterial({ map: solarPanelTexture(), roughness: 0.3, metalness: 0.5 }),
  ));
  panel.position.set(0, 0.475, 0.12);
  const mastCam = shadow(new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.22, 8), dark));
  mastCam.position.set(-0.17, 0.57, 0.24);
  const camBox = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.1, 0.07, 0.08, 2, 0.015), white));
  camBox.position.set(-0.17, 0.7, 0.22);

  body.add(chassis, deck, bumper, neck, head, antenna, antennaTip, panel, mastCam, camBox);

  const wheels = [];
  const tireGeo = new THREE.CylinderGeometry(WHEEL_RADIUS, WHEEL_RADIUS, 0.1, 22);
  tireGeo.rotateZ(Math.PI / 2);
  const hubGeo = new THREE.CylinderGeometry(0.06, 0.06, 0.11, 12);
  hubGeo.rotateZ(Math.PI / 2);
  for (const x of [-0.34, 0.34]) {
    for (const z of [-0.23, 0.23]) {
      const wheel = new THREE.Group();
      wheel.add(shadow(new THREE.Mesh(tireGeo, tire)), new THREE.Mesh(hubGeo, hub));
      wheel.position.set(x, WHEEL_RADIUS, z);
      body.add(wheel);
      wheels.push(wheel);
    }
  }

  return { root, body, wheels, antennaTip };
}
