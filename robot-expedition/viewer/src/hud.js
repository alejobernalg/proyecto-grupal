// HUD y controles. Solo muestra datos del frame exportado por el simulador.
const TARGET_LABELS = { beacon_1: 'Baliza 1', beacon_2: 'Baliza 2', base: 'Base' };
const REWARD_LABELS = {
  progress: 'progreso',
  beacon: 'baliza',
  return: 'retorno',
  time: 'tiempo',
  battery: 'batería',
  collision: 'colisión',
  depletion: 'batería agotada',
};
const EVENT_LABELS = {
  collision: '¡choque!',
  battery_depleted: 'batería agotada',
  mission_complete: 'misión completada',
  beacon_1: 'baliza 1 visitada',
  beacon_2: 'baliza 2 visitada',
  beacon_1_revisit: 'baliza 1 ya visitada (0 pts)',
  beacon_2_revisit: 'baliza 2 ya visitada (0 pts)',
  beacon_1_out_of_order: 'baliza 1 fuera de orden (0 pts)',
  beacon_2_out_of_order: 'baliza 2 fuera de orden (0 pts)',
};

export function outcome(frame) {
  if (frame.success) {
    return frame.collisions === 0
      ? { text: 'Misión completada sin colisiones', tone: 'good' }
      : { text: `Misión completada con ${frame.collisions} colisiones`, tone: 'good' };
  }
  if (frame.terminated) return { text: 'Batería agotada', tone: 'bad' };
  if (frame.truncated) return { text: 'Tiempo agotado (max_steps)', tone: 'warn' };
  return { text: 'Episodio sin terminar', tone: 'warn' };
}

const $ = (id) => document.getElementById(id);
const signed = (v, digits = 3) => `${v >= 0 ? '+' : ''}${v.toFixed(digits)}`;

export class Hud {
  constructor(handlers) {
    this.handlers = handlers;
    this.cache = new Map();
    this.scrubbing = false;
    this.el = {
      episode: $('hud-episode'),
      model: $('hud-model'),
      step: $('hud-step'),
      total: $('hud-total'),
      reward: $('hud-reward'),
      batteryFill: $('hud-battery-fill'),
      battery: $('hud-battery'),
      target: $('hud-target'),
      beacons: $('hud-beacons'),
      collisions: $('hud-collisions'),
      fps: $('hud-fps'),
      breakdown: $('hud-breakdown'),
      events: $('hud-events'),
      outcome: $('outcome'),
      play: $('btn-play'),
      speed: $('sel-speed'),
      timeline: $('timeline'),
      frame: $('lbl-frame'),
      view: $('btn-view'),
      guides: $('btn-guides'),
      light: $('btn-light'),
      select: $('sel-episode'),
      file: $('file-input'),
      drop: $('drop-hint'),
    };
    this.bind();
  }

  bind() {
    const { el, handlers } = this;
    el.play.addEventListener('click', () => handlers.togglePlay());
    el.speed.addEventListener('change', () => handlers.setSpeed(Number(el.speed.value)));
    el.timeline.addEventListener('pointerdown', () => (this.scrubbing = true));
    window.addEventListener('pointerup', () => (this.scrubbing = false));
    el.timeline.addEventListener('input', () => handlers.seek(Number(el.timeline.value)));
    el.view.addEventListener('click', () => handlers.nextView());
    el.guides.addEventListener('click', () => handlers.toggleGuides());
    el.light.addEventListener('click', () => handlers.toggleLight());
    el.select.addEventListener('change', () => handlers.selectEpisode(el.select.value));
    el.file.addEventListener('change', () => {
      if (el.file.files[0]) handlers.openFile(el.file.files[0]);
      el.file.value = '';
    });

    window.addEventListener('dragover', (e) => {
      e.preventDefault();
      el.drop.hidden = false;
    });
    window.addEventListener('dragleave', (e) => {
      if (e.relatedTarget === null) el.drop.hidden = true;
    });
    window.addEventListener('drop', (e) => {
      e.preventDefault();
      el.drop.hidden = true;
      const file = e.dataTransfer?.files?.[0];
      if (file) handlers.openFile(file);
    });

    window.addEventListener('keydown', (e) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      const key = e.key.toLowerCase();
      if (key === ' ') {
        e.preventDefault();
        handlers.togglePlay();
      } else if (key === 'arrowright') handlers.stepBy(1);
      else if (key === 'arrowleft') handlers.stepBy(-1);
      else if (key === 'v') handlers.nextView();
      else if (key === 'g') handlers.toggleGuides();
      else if (key === 'l') handlers.toggleLight();
    });
  }

  set(key, node, value, prop = 'textContent') {
    if (this.cache.get(key) === value) return;
    this.cache.set(key, value);
    node[prop] = value;
  }

  setEpisodes(list, selectedId) {
    const { select } = this.el;
    select.innerHTML = '';
    for (const item of list) {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = item.id;
      select.append(option);
    }
    if (selectedId) select.value = selectedId;
  }

  addLocalEpisode(name) {
    const option = document.createElement('option');
    option.value = `local:${name}`;
    option.textContent = `local/${name}`;
    this.el.select.append(option);
    this.el.select.value = option.value;
  }

  setEpisode(label, episode) {
    this.cache.clear();
    this.el.episode.textContent = `${episode.experiment} · ${label}`;
    const meta = episode.metadata ?? {};
    this.el.model.textContent =
      meta.agent === 'q_learning'
        ? `Q-learning ${meta.trained_episodes}/${meta.total_episodes}`
        : { human: 'manual (CLI)', oracle: 'oracle (BFS)' }[meta.agent] ?? '—';
    this.el.timeline.max = String(Math.max(0, episode.frames.length - 1));
  }

  setTimelineMax(last) {
    this.el.timeline.max = String(last);
  }

  setToggles({ view, guides, light }) {
    this.el.view.textContent = `Vista: ${view}`;
    this.el.guides.classList.toggle('on', guides);
    this.el.light.classList.toggle('on', light);
  }

  update({ frame, t, last, fps, playing, finished }) {
    const { el } = this;
    this.set('play', el.play, playing ? '❚❚' : '▶');
    this.set('step', el.step, String(frame.step));
    this.set('total', el.total, signed(frame.reward.total));
    this.set('reward', el.reward, signed(frame.reward.step));
    el.reward.className = frame.reward.step > 0 ? 'pos' : frame.reward.step < 0 ? 'neg' : '';

    const fraction = frame.battery.fraction;
    const hue = Math.round(120 * Math.max(0, Math.min(1, fraction)));
    this.set('bfill-w', el.batteryFill.style, `${(fraction * 100).toFixed(1)}%`, 'width');
    this.set('bfill-c', el.batteryFill.style, `hsl(${hue} 75% 50%)`, 'background');
    this.set('battery', el.battery, `${frame.battery.value.toFixed(1)} / ${frame.battery.capacity} u`);

    this.set('target', el.target, frame.success ? '—' : TARGET_LABELS[frame.target] ?? frame.target);
    this.set('beacons', el.beacons, frame.visited.length ? frame.visited.join(' → ') : 'ninguna');
    this.set('collisions', el.collisions, String(frame.collisions));
    this.set('fps', el.fps, String(fps));

    const breakdown = Object.entries(frame.reward.breakdown)
      .filter(([, v]) => Math.abs(v) > 1e-9)
      .map(([k, v]) => `<span>${REWARD_LABELS[k] ?? k}</span><span class="${v > 0 ? 'pos' : 'neg'}">${signed(v)}</span>`)
      .join('');
    this.set('breakdown', el.breakdown, breakdown, 'innerHTML');
    this.set('events', el.events, frame.events.map((e) => EVENT_LABELS[e] ?? e).join(' · '));

    if (!this.scrubbing) this.set('timeline', el.timeline, String(t), 'value');
    this.set('frame', el.frame, `${Math.round(t)} / ${last}`);

    const result = finished ? outcome(frame) : null;
    this.set('outcome', el.outcome, result ? result.text : '');
    this.set('outcome-tone', el.outcome, result ? result.tone : '', 'className');
    this.set('outcome-hidden', el.outcome, !result, 'hidden');
  }
}
