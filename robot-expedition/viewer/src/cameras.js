import * as THREE from 'three';
import { compassVector } from './effects.js';

export const VIEWS = [
  { id: 'iso', label: 'isométrica' },
  { id: 'top', label: 'cenital' },
  { id: 'follow', label: 'seguimiento' },
];

// Cámara orbital con tres vistas predefinidas y transiciones suaves.
export class CameraRig {
  constructor(camera, controls) {
    this.camera = camera;
    this.controls = controls;
    this.size = 12;
    this.index = 0;
    this.transitioning = false;
    this.goalPosition = new THREE.Vector3();
    this.goalTarget = new THREE.Vector3();
  }

  get view() {
    return VIEWS[this.index];
  }

  setSize(size) {
    this.size = size;
  }

  next() {
    this.setView((this.index + 1) % VIEWS.length);
  }

  setView(index, immediate = false) {
    this.index = index;
    const n = this.size;
    if (this.view.id === 'iso') {
      this.goalPosition.set(n * 0.9, n * 0.5, n * 1.25);
      this.goalTarget.set(-0.5, 0.4, -1.4);
    } else if (this.view.id === 'top') {
      this.goalPosition.set(0, n * 1.85, n * 0.03);
      this.goalTarget.set(0, 0, 0);
    }
    this.controls.enabled = this.view.id !== 'follow';
    this.transitioning = this.view.id !== 'follow';
    if (immediate && this.transitioning) {
      this.camera.position.copy(this.goalPosition);
      this.controls.target.copy(this.goalTarget);
      this.transitioning = false;
    }
  }

  update(dt, robotPosition, headingDeg) {
    const k = 1 - Math.exp(-dt * 4);
    if (this.view.id === 'follow') {
      const forward = compassVector(headingDeg);
      const goal = robotPosition.clone().addScaledVector(forward, -3.4).add(new THREE.Vector3(0, 2.6, 0));
      const look = robotPosition.clone().addScaledVector(forward, 1.2);
      this.camera.position.lerp(goal, k);
      this.controls.target.lerp(look, k);
    } else if (this.transitioning) {
      this.camera.position.lerp(this.goalPosition, k);
      this.controls.target.lerp(this.goalTarget, k);
      if (this.camera.position.distanceTo(this.goalPosition) < 0.02) this.transitioning = false;
    }
    this.controls.update();
  }
}
