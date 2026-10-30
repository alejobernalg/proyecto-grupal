import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { gradientBackground } from './textures.js';

// Renderer, cámara, luces y postproceso. El "modo ligero" apaga sombras y bloom.
export function createStage(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  // Cielo marciano: caramelo pálido en el horizonte, más rosado arriba, con bruma de polvo.
  const scene = new THREE.Scene();
  scene.background = gradientBackground('#a8674a', '#e3b58f');
  scene.fog = new THREE.Fog('#dcaa84', 30, 130);

  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 400);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.minDistance = 4;
  controls.maxDistance = 110;

  const hemi = new THREE.HemisphereLight('#f6c9a4', '#6a2f1a', 1.3);
  scene.add(hemi);

  const sun = new THREE.DirectionalLight('#ffe1bd', 2.6);
  sun.position.set(-8, 16, 6);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.02;
  sun.shadow.radius = 4;
  scene.add(sun, sun.target);

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.45, 0.35, 0.9);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  const state = { light: false };

  function resize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const ratio = state.light ? 1 : Math.min(window.devicePixelRatio, 2);
    renderer.setPixelRatio(ratio);
    renderer.setSize(width, height, false);
    composer.setPixelRatio(ratio);
    composer.setSize(width, height);
    // El bloom trabaja a media resolución para mantener 60 FPS.
    bloom.resolution.set(width / 2, height / 2);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  function fitShadows(size) {
    // La bruma empieza detrás de la sala para que los mapas grandes se vean nítidos.
    scene.fog.near = size * 1.6 + 10;
    scene.fog.far = size * 1.6 + 150;
    const half = size / 2 + 8; // incluye el hábitat junto a la sala
    const cam = sun.shadow.camera;
    cam.left = -half;
    cam.right = half;
    cam.top = half;
    cam.bottom = -half;
    cam.near = 1;
    cam.far = 80;
    cam.updateProjectionMatrix();
  }

  function setLightMode(on) {
    state.light = on;
    renderer.shadowMap.enabled = !on;
    sun.castShadow = !on;
    scene.traverse((obj) => {
      if (!obj.material) return;
      for (const m of Array.isArray(obj.material) ? obj.material : [obj.material]) m.needsUpdate = true;
    });
    resize();
  }

  function render() {
    if (state.light) renderer.render(scene, camera);
    else composer.render();
  }

  return { renderer, scene, camera, controls, sun, fitShadows, setLightMode, render, state };
}
