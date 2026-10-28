// Visor de episodios ROBOT EXPEDITION.
// Física ≠ decoración: aquí no hay reglas de juego. Todo lo que se ve (posición, rayos,
// balizas visitadas, batería, recompensa) viene de los frames que exporta el simulador;
// entre dos frames solo se interpola el dibujo para que el movimiento sea suave.
import './style.css';
import * as THREE from 'three';
import { CameraRig } from './cameras.js';
import { Bursts, GuideLine, Rays, Trail, compassVector } from './effects.js';
import { Hud } from './hud.js';
import { connectLive } from './live.js';
import { WheelDust, buildMars } from './mars.js';
import { Player, easeInOut, lerpAngleDeg } from './player.js';
import { WHEEL_RADIUS, createRobot } from './robot.js';
import { createStage } from './scene.js';
import { buildWorld, cellCenter, disposeObject } from './world.js';

const EPISODE_FORMAT = 'robot-expedition/episode@1';

const stage = createStage(document.getElementById('scene'));
const player = new Player();
const rig = new CameraRig(stage.camera, stage.controls);
const robot = createRobot();
const rays = new Rays();
const trail = new Trail();
const guide = new GuideLine();
const bursts = new Bursts();
const wheelDust = new WheelDust();
stage.scene.add(robot.root, rays.object, trail.object, guide.object, bursts.object, wheelDust.object);
robot.root.visible = false; // hasta que llegue un episodio
rig.setView(0, true);

let episode = null;
let world = null;
let mars = null;
let centers = [];
let lastDisplay = 0;
let guidesOn = true;
let lastRobotPos = new THREE.Vector3();

const hud = new Hud({
  togglePlay: () => player.toggle(),
  setSpeed: (s) => (player.speed = s),
  seek: (t) => seek(t),
  stepBy: (d) => {
    player.playing = false;
    seek(Math.round(player.t) + d);
  },
  nextView: () => {
    rig.next();
    syncToggles();
  },
  toggleGuides: () => {
    guidesOn = !guidesOn;
    applyGuides();
    syncToggles();
  },
  toggleLight: () => {
    stage.setLightMode(!stage.state.light);
    syncToggles();
  },
  selectEpisode: (id) => {
    if (!id.startsWith('local:')) loadFromServer(id);
  },
  openFile: (file) => openFile(file),
});

function syncToggles() {
  hud.setToggles({ view: rig.view.label, guides: guidesOn, light: stage.state.light });
}

function applyGuides() {
  for (const obj of [rays.object, trail.object, guide.object, ...(world?.guides ?? [])]) obj.visible = guidesOn;
}

function seek(t) {
  player.seek(t);
  lastDisplay = player.sample().display; // saltar en la línea de tiempo no dispara efectos
}

function loadEpisode(data, label) {
  if (data?.format !== EPISODE_FORMAT || !Array.isArray(data.frames) || !data.frames.length || !data.map) {
    throw new Error(`No es un episodio ${EPISODE_FORMAT}`);
  }
  for (const old of [world, mars]) {
    if (!old) continue;
    stage.scene.remove(old.group);
    disposeObject(old.group);
  }
  episode = data;
  world = buildWorld(data.map);
  mars = buildMars(data.map);
  stage.scene.add(world.group, mars.group);
  stage.fitShadows(data.map.size);
  centers = data.frames.map((f) => cellCenter(data.map, f.robot.x, f.robot.y));
  player.load(data);
  robot.root.visible = true;
  lastDisplay = 0;
  lastRobotPos.copy(centers[0]);
  rig.setSize(data.map.size);
  rig.setView(rig.index, true);
  hud.setEpisode(label, data);
  applyGuides();
  syncToggles();
}

async function loadFromServer(id) {
  try {
    const res = await fetch(`/api/episodes/${id}`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    loadEpisode(await res.json(), id);
    const url = new URL(window.location.href);
    url.searchParams.set('episode', id);
    window.history.replaceState(null, '', url);
  } catch (err) {
    alert(`No se pudo cargar ${id}: ${err.message}`);
  }
}

async function openFile(file) {
  try {
    loadEpisode(JSON.parse(await file.text()), file.name);
    hud.addLocalEpisode(file.name);
  } catch (err) {
    alert(`No se pudo abrir ${file.name}: ${err.message}`);
  }
}

async function init() {
  let list = [];
  try {
    list = await (await fetch('/api/episodes')).json();
  } catch {
    // Sin servidor de episodios (por ejemplo, build estático): queda "Abrir…" y arrastrar.
  }
  const params = new URL(window.location.href).searchParams;
  if (params.has('live')) {
    startLive(params.get('live') || 'ws://localhost:8765');
    return;
  }
  const wanted = params.get('episode');
  const first = list.find((e) => e.id === wanted) ?? list[0];
  hud.setEpisodes(list, first?.id);
  syncToggles();
  if (first) await loadFromServer(first.id);
  // ?t=<paso> abre el episodio en ese paso y en pausa; ?view=0|1|2 elige la vista.
  if (params.has('view')) {
    rig.setView(Number(params.get('view')) % 3, true);
    syncToggles();
  }
  if (episode && params.has('t')) {
    player.playing = false;
    seek(Number(params.get('t')));
  }
}

// Modo en vivo: el CLI manda el episodio y luego un frame por cada tecla.
function startLive(url) {
  const badge = document.getElementById('live-badge');
  badge.hidden = false;
  document.getElementById('sel-episode').hidden = true;
  const labels = { connecting: 'CONECTANDO', connected: 'EN VIVO', waiting: 'ESPERANDO CLI' };
  connectLive(url, {
    onStatus: (status) => {
      badge.textContent = labels[status];
      badge.className = status === 'connected' ? 'connected' : '';
    },
    onEpisode: (data) => {
      loadEpisode(data, 'en vivo');
      player.live = true;
      player.seek(player.last);
    },
    onFrame: (frame) => {
      if (!episode) return;
      episode.frames.push(frame);
      centers.push(cellCenter(episode.map, frame.robot.x, frame.robot.y));
      hud.setTimelineMax(player.last);
    },
  });
}

// ------------------------------------------------------------------ bucle de dibujo
const clock = new THREE.Clock();
let fps = 0;
let fpsFrames = 0;
let fpsTime = 0;

function interpolatedRays(from, to, alpha) {
  return from.rays.map((ray, i) => {
    const next = to.rays[i];
    return {
      angle_deg: ray.angle_deg,
      distance: ray.distance + (next.distance - ray.distance) * alpha,
      hit: alpha < 0.5 ? ray.hit : next.hit,
    };
  });
}

function targetPosition(frame) {
  if (frame.target === 'base') return world.baseCenter;
  const id = Number(frame.target.split('_')[1]);
  return world.beacons.get(id).position;
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.1);
  const time = clock.elapsedTime;

  fpsFrames += 1;
  fpsTime += dt;
  if (fpsTime >= 0.5) {
    fps = Math.round(fpsFrames / fpsTime);
    fpsFrames = 0;
    fpsTime = 0;
  }

  if (!episode) {
    stage.controls.update();
    stage.render();
    return;
  }

  player.update(dt);
  const { i, alpha, from, to, display } = player.sample();
  const e = easeInOut(alpha);

  // Pose interpolada entre dos estados exportados.
  const pos = centers[i].clone().lerp(centers[Math.min(i + 1, player.last)], e);
  const heading = lerpAngleDeg(from.robot.heading_deg, to.robot.heading_deg, e);
  robot.root.position.copy(pos);
  robot.root.rotation.y = -THREE.MathUtils.degToRad(heading);

  // Rebote leve cuando el simulador reporta colisión en el paso siguiente.
  const bump = to.events.includes('collision') && i < player.last ? Math.sin(Math.PI * alpha) : 0;
  robot.body.position.set(0, Math.abs(Math.sin(Math.PI * 2 * alpha)) * 0.05 * bump, -0.16 * bump);
  robot.body.rotation.x = 0.12 * bump;

  // Ruedas: giran según el avance real del dibujo.
  const moved = pos.distanceTo(lastRobotPos);
  const forward = compassVector(heading);
  const sign = Math.sign(forward.dot(pos.clone().sub(lastRobotPos))) || 1;
  for (const wheel of robot.wheels) wheel.rotation.x -= (sign * moved) / WHEEL_RADIUS;
  if (moved > 0.002) {
    const side = new THREE.Vector3(-forward.z, 0, forward.x).multiplyScalar(0.34);
    const rear = pos.clone().addScaledVector(forward, -0.25 * sign);
    wheelDust.emit(rear.clone().add(side), 1);
    wheelDust.emit(rear.clone().sub(side), 1);
  }
  lastRobotPos.copy(pos);
  robot.antennaTip.material.emissiveIntensity = 1.8 + Math.sin(time * 5) * 0.8;

  // Rayos, estela y guía.
  rays.update(pos, heading, interpolatedRays(from, to, e));
  const trailPoints = [];
  for (let k = 0; k <= i; k++) {
    if (!k || !centers[k].equals(centers[k - 1])) trailPoints.push(centers[k].clone().setY(0.03));
  }
  trailPoints.push(pos.clone().setY(0.03));
  trail.setPoints(trailPoints);

  const shown = episode.frames[display];
  if (!shown.success) guide.update(pos, targetPosition(shown));
  guide.object.visible = guidesOn && !shown.success;

  // Balizas y efectos: el estado "visitada" viene del frame.
  for (const b of shown.beacons) world.beacons.get(b.id).setVisited(b.visited);
  if (display === lastDisplay + 1) {
    for (const ev of shown.events) {
      const match = /^beacon_(\d)$/.exec(ev);
      if (match) bursts.burst(world.beacons.get(Number(match[1])).position.clone().setY(1.1), '#5dff9a');
      if (ev === 'mission_complete') bursts.burst(pos.clone().setY(0.6), '#ffd36b', 120);
    }
  }
  lastDisplay = display;

  world.update(time, dt);
  mars.update(time, dt);
  bursts.update(dt);
  wheelDust.update(dt);
  rig.update(dt, pos, heading);

  hud.update({
    frame: shown,
    t: player.t,
    last: player.last,
    fps,
    playing: player.playing || player.live,
    finished: player.finished && (!player.live || shown.terminated || shown.truncated),
  });
  stage.render();
}

init();
animate();
