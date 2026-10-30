import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const STRIDE = 0.5; // m por paso: un ciclo completo (dos pasos) por celda
const HIP_HEIGHT = 0.44;

// Explorador bípedo: cuerpo ovalado, visor con ojos, antena, mochila y dos piernas.
// Mira hacia −z cuando rotation.y = 0 (norte en el simulador). Solo es dibujo:
// la animación de caminar se deriva del desplazamiento que ya exportó el simulador.
export function createExplorer() {
  const root = new THREE.Group();
  const body = new THREE.Group(); // tambaleo al chocar sin mover la posición lógica
  const torso = new THREE.Group(); // balanceo y respiración
  root.add(body);
  body.add(torso);

  const shadow = (m) => {
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
  };
  const shell = new THREE.MeshStandardMaterial({ color: '#f4f1ea', roughness: 0.4 });
  const joint = new THREE.MeshStandardMaterial({ color: '#3a414b', roughness: 0.55 });
  const visorMat = new THREE.MeshStandardMaterial({ color: '#12202c', roughness: 0.15, metalness: 0.6 });
  const accent = new THREE.MeshStandardMaterial({ color: '#e2782c', roughness: 0.5 });
  const eyeMat = new THREE.MeshStandardMaterial({ color: '#8ff6ff', emissive: '#3fe6ff', emissiveIntensity: 3 });
  const tipMat = new THREE.MeshStandardMaterial({ color: '#ff7a4d', emissive: '#ff5a2a', emissiveIntensity: 2.5 });

  // Cuerpo: huevo blanco con cinturón naranja.
  const egg = shadow(new THREE.Mesh(new THREE.SphereGeometry(0.27, 28, 20), shell));
  egg.scale.set(1, 1.18, 0.95);
  egg.position.y = 0.76;
  const belt = shadow(new THREE.Mesh(new THREE.TorusGeometry(0.255, 0.025, 8, 32), accent));
  belt.rotation.x = Math.PI / 2;
  belt.position.y = 0.6;
  const pelvis = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.34, 0.1, 0.22, 2, 0.04), joint));
  pelvis.position.y = HIP_HEIGHT + 0.06;

  // Visor y ojos.
  const visor = shadow(new THREE.Mesh(new THREE.SphereGeometry(0.2, 24, 12, Math.PI * 0.2, Math.PI * 0.6, Math.PI * 0.28, Math.PI * 0.3), visorMat));
  visor.rotation.y = Math.PI / 2;
  visor.scale.set(1.08, 1.05, 1.15);
  visor.position.set(0, 0.8, -0.04);
  const eyes = [];
  for (const x of [-0.065, 0.065]) {
    const eye = new THREE.Mesh(new THREE.CapsuleGeometry(0.022, 0.03, 4, 8), eyeMat);
    eye.position.set(x, 0.84, -0.255);
    eyes.push(eye);
    torso.add(eye);
  }

  // Antena y mochila.
  const antenna = shadow(new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.22, 6), joint));
  antenna.position.set(0.08, 1.15, 0.05);
  antenna.rotation.z = -0.25;
  const antennaTip = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 8), tipMat);
  antennaTip.position.set(0.108, 1.26, 0.05);
  const pack = shadow(new THREE.Mesh(new RoundedBoxGeometry(0.3, 0.32, 0.14, 3, 0.05), shell));
  pack.position.set(0, 0.76, 0.26);
  const packStripe = new THREE.Mesh(new THREE.BoxGeometry(0.31, 0.04, 0.145), accent);
  packStripe.position.set(0, 0.84, 0.26);

  torso.add(egg, belt, visor, antenna, antennaTip, pack, packStripe);
  body.add(pelvis);

  // Piernas: cadera → muslo → rodilla → espinilla → pie.
  const legs = [];
  const thighGeo = new THREE.CapsuleGeometry(0.055, 0.12, 4, 10);
  const shinGeo = new THREE.CapsuleGeometry(0.048, 0.12, 4, 10);
  const footGeo = new RoundedBoxGeometry(0.13, 0.06, 0.21, 2, 0.025);
  for (const side of [-1, 1]) {
    const hip = new THREE.Group();
    hip.position.set(side * 0.11, HIP_HEIGHT, 0);
    const thigh = shadow(new THREE.Mesh(thighGeo, shell));
    thigh.position.y = -0.1;
    const knee = new THREE.Group();
    knee.position.y = -0.2;
    const kneeCap = shadow(new THREE.Mesh(new THREE.SphereGeometry(0.052, 12, 8), joint));
    const shin = shadow(new THREE.Mesh(shinGeo, joint));
    shin.position.y = -0.1;
    const ankle = new THREE.Group();
    ankle.position.y = -0.2;
    const foot = shadow(new THREE.Mesh(footGeo, accent));
    foot.position.set(0, -0.01, -0.04);
    ankle.add(foot);
    knee.add(kneeCap, shin, ankle);
    hip.add(thigh, knee);
    body.add(hip);
    legs.push({ hip, knee, ankle, side });
  }

  let phase = 0;
  let stepping = 0; // 0 quieto, 1 caminando
  let blinkTimer = 2;
  let clumsy = 0; // 0 camina con soltura, 1 recién empieza a aprender

  // Torpeza visual según cuánto entrenó el modelo (metadata del episodio). Solo dibujo.
  function setClumsiness(value) {
    clumsy = Math.max(0, Math.min(1, value));
  }

  // distance: metros recorridos con signo (negativo = retroceso); turn: grados girados este frame.
  function animate(dt, distance, turn, time) {
    const c = clumsy;
    const turning = Math.abs(turn) / 90; // un giro de 90° equivale a un paso corto
    const stride = STRIDE * (1 - 0.35 * c); // pasos más cortos y nerviosos al principio
    phase += (distance / stride) * Math.PI + Math.sign(turn || 1) * turning * Math.PI;
    const active = Math.abs(distance) > 1e-4 || turning > 1e-4;
    stepping += ((active ? 1 : 0) - stepping) * (1 - Math.exp(-dt * 10));

    const wobble = Math.sin(time * 7.3) * Math.sin(time * 3.1 + 1.7); // temblor irregular
    const swingAmp = 0.55 * stepping;
    for (const leg of legs) {
      const p = phase + (leg.side > 0 ? Math.PI : 0);
      // Con torpeza: zancadas desiguales, rodillas rígidas y piernas abiertas para no caerse.
      const uneven = 1 + 0.7 * c * Math.sin(p * 0.5 + leg.side);
      leg.hip.rotation.x = Math.sin(p) * swingAmp * uneven;
      leg.hip.rotation.z = leg.side * c * (0.1 + 0.08 * stepping);
      leg.knee.rotation.x = -Math.max(0, Math.cos(p)) * 0.95 * stepping * (1 - 0.6 * c);
      leg.ankle.rotation.x = -leg.hip.rotation.x - leg.knee.rotation.x;
    }
    const bob = Math.abs(Math.sin(phase)) * (0.045 + 0.04 * c) * stepping;
    const breathe = Math.sin(time * 2.2) * 0.008 * (1 - stepping);
    torso.position.y = bob + breathe;
    pelvis.position.y = HIP_HEIGHT + 0.06 + bob * 0.6;
    for (const leg of legs) leg.hip.position.y = HIP_HEIGHT + bob * 0.6;
    // Se inclina hacia donde camina; si es torpe además se bambolea y tiembla.
    torso.rotation.x = -0.08 * stepping * Math.sign(distance || 1) + c * 0.12 * wobble;
    torso.rotation.z =
      Math.sin(phase) * (0.05 + 0.12 * c) * stepping + c * (0.12 * Math.sin(time * 1.9) * (0.4 + stepping) + 0.07 * wobble);

    // Parpadeo.
    blinkTimer -= dt;
    const blink = blinkTimer < 0.12 ? 0.15 : 1;
    if (blinkTimer < 0) blinkTimer = 2 + Math.random() * 3;
    for (const eye of eyes) eye.scale.y = blink;
    antennaTip.material.emissiveIntensity = 1.8 + Math.sin(time * 5) * 0.8;
  }

  // Posiciones de los pies en coordenadas del mundo (para el polvo).
  const tmp = new THREE.Vector3();
  function feet() {
    return legs.map((leg) => leg.ankle.getWorldPosition(tmp.clone()));
  }

  return { root, body, animate, feet, setClumsiness };
}
