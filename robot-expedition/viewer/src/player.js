// Reproductor: avanza un tiempo continuo t sobre la lista de frames.
// El frame i es el estado tras i acciones; entre i e i+1 solo se interpola el dibujo.
export const BASE_STEPS_PER_SECOND = 4;

export class Player {
  constructor() {
    this.frames = [];
    this.t = 0;
    this.speed = 1;
    this.playing = false;
    this.live = false; // en vivo sigue al último frame y nunca se detiene
  }

  load(episode) {
    this.frames = episode.frames;
    this.t = 0;
    this.playing = true;
  }

  get last() {
    return Math.max(0, this.frames.length - 1);
  }

  get finished() {
    return this.t >= this.last;
  }

  update(dt) {
    if (this.live && this.frames.length) {
      // Si se acumulan frames, acelera para alcanzar al CLI sin saltos.
      const lag = this.last - this.t;
      this.t = Math.min(this.last, this.t + dt * BASE_STEPS_PER_SECOND * Math.max(1.5, lag * 1.5));
      return;
    }
    if (!this.playing || !this.frames.length) return;
    this.t = Math.min(this.last, this.t + dt * BASE_STEPS_PER_SECOND * this.speed);
    if (this.finished) this.playing = false;
  }

  seek(t) {
    this.t = Math.max(0, Math.min(this.last, t));
  }

  toggle() {
    if (this.finished) this.t = 0;
    this.playing = !this.playing;
  }

  // Índice del frame base, fracción hacia el siguiente y frame "visible" (el más cercano).
  sample() {
    const i = Math.min(Math.floor(this.t), this.last);
    const alpha = i >= this.last ? 0 : this.t - i;
    const next = Math.min(i + 1, this.last);
    return {
      i,
      alpha,
      from: this.frames[i],
      to: this.frames[next],
      display: alpha >= 0.5 ? next : i,
    };
  }
}

export function easeInOut(x) {
  return x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2;
}

export function lerpAngleDeg(a, b, t) {
  const delta = ((((b - a) % 360) + 540) % 360) - 180;
  return a + delta * t;
}
