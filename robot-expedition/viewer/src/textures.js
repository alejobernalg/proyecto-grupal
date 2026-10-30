import * as THREE from 'three';

function canvas(width, height) {
  const el = document.createElement('canvas');
  el.width = width;
  el.height = height;
  return [el, el.getContext('2d')];
}

function toTexture(el) {
  const texture = new THREE.CanvasTexture(el);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

// Generador pseudoaleatorio con semilla para que la textura sea siempre igual.
function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export function gradientBackground(top = '#46658a', bottom = '#16222f') {
  const [el, ctx] = canvas(4, 512);
  const g = ctx.createLinearGradient(0, 0, 0, 512);
  g.addColorStop(0, top);
  g.addColorStop(1, bottom);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 4, 512);
  return toTexture(el);
}

function speckle(ctx, size, rand, count, light, dark) {
  for (let i = 0; i < count; i++) {
    ctx.fillStyle = rand() > 0.5 ? `rgba(${light},${0.04 + rand() * 0.1})` : `rgba(${dark},${0.05 + rand() * 0.1})`;
    ctx.beginPath();
    ctx.arc(rand() * size, rand() * size, 0.5 + rand() * 1.8, 0, Math.PI * 2);
    ctx.fill();
  }
}

// Regolito marciano: base óxido con granos claros y oscuros y algunas piedrecitas.
export function regolithTexture(base = '#c46a3e', seed = 3) {
  const size = 512;
  const [el, ctx] = canvas(size, size);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, size, size);
  const rand = seeded(seed);
  for (let i = 0; i < 40; i++) {
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, 40 + rand() * 90);
    const tone = rand() > 0.5 ? '255,200,150' : '90,35,15';
    g.addColorStop(0, `rgba(${tone},0.07)`);
    g.addColorStop(1, `rgba(${tone},0)`);
    ctx.save();
    ctx.translate(rand() * size, rand() * size);
    ctx.fillStyle = g;
    ctx.fillRect(-130, -130, 260, 260);
    ctx.restore();
  }
  speckle(ctx, size, rand, 9000, '255,215,170', '70,25,10');
  for (let i = 0; i < 70; i++) {
    ctx.fillStyle = `rgba(80,32,16,${0.25 + rand() * 0.3})`;
    ctx.beginPath();
    ctx.ellipse(rand() * size, rand() * size, 1.5 + rand() * 3, 1 + rand() * 2, rand() * 3, 0, Math.PI * 2);
    ctx.fill();
  }
  const texture = toTexture(el);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  return texture;
}

// Arenisca estratificada: bandas horizontales de distintos tonos.
export function strataTexture(base = '#d2643f', seed = 11) {
  const [el, ctx] = canvas(256, 256);
  const rand = seeded(seed);
  const color = new THREE.Color(base);
  let y = 0;
  while (y < 256) {
    const h = 6 + rand() * 22;
    const c = color.clone().offsetHSL((rand() - 0.5) * 0.02, (rand() - 0.5) * 0.1, (rand() - 0.5) * 0.12);
    ctx.fillStyle = `#${c.getHexString()}`;
    ctx.fillRect(0, y, 256, h + 1);
    ctx.fillStyle = 'rgba(60,20,10,0.18)';
    ctx.fillRect(0, y + h - 1, 256, 1.5);
    y += h;
  }
  speckle(ctx, 256, rand, 1800, '255,220,180', '60,20,10');
  return toTexture(el);
}

// Contenedor de carga: costillas verticales, franja blanca y código.
export function containerTexture(base = '#e2782c', code = 'ARES-01') {
  const [el, ctx] = canvas(256, 256);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 256, 256);
  for (let x = 0; x < 256; x += 16) {
    ctx.fillStyle = 'rgba(0,0,0,0.12)';
    ctx.fillRect(x, 0, 4, 256);
    ctx.fillStyle = 'rgba(255,255,255,0.10)';
    ctx.fillRect(x + 5, 0, 2, 256);
  }
  ctx.fillStyle = 'rgba(245,240,230,0.9)';
  ctx.fillRect(0, 34, 256, 18);
  ctx.fillStyle = '#2a2f36';
  ctx.font = '700 15px ui-monospace, Menlo, monospace';
  ctx.fillText(code, 10, 48);
  const rand = seeded(code.length * 7);
  ctx.fillStyle = 'rgba(150,70,35,0.35)'; // polvo acumulado abajo
  for (let i = 0; i < 400; i++) ctx.fillRect(rand() * 256, 200 + rand() * 56, 2, 2);
  const g = ctx.createLinearGradient(0, 180, 0, 256);
  g.addColorStop(0, 'rgba(170,80,40,0)');
  g.addColorStop(1, 'rgba(170,80,40,0.45)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 180, 256, 76);
  return toTexture(el);
}

// Basalto: gris oscuro poroso.
export function basaltTexture(base = '#77706c', seed = 5) {
  const [el, ctx] = canvas(256, 256);
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 256, 256);
  const rand = seeded(seed);
  speckle(ctx, 256, rand, 3000, '210,200,195', '30,25,25');
  for (let i = 0; i < 120; i++) {
    ctx.fillStyle = 'rgba(25,20,20,0.35)';
    ctx.beginPath();
    ctx.arc(rand() * 256, rand() * 256, 1 + rand() * 2.5, 0, Math.PI * 2);
    ctx.fill();
  }
  const g = ctx.createLinearGradient(0, 170, 0, 256);
  g.addColorStop(0, 'rgba(170,80,40,0)');
  g.addColorStop(1, 'rgba(170,80,40,0.4)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 170, 256, 86);
  return toTexture(el);
}

export function solarPanelTexture() {
  const [el, ctx] = canvas(128, 128);
  ctx.fillStyle = '#16233f';
  ctx.fillRect(0, 0, 128, 128);
  ctx.strokeStyle = 'rgba(140,170,220,0.45)';
  ctx.lineWidth = 1.5;
  for (let i = 0; i <= 128; i += 16) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i, 128);
    ctx.moveTo(0, i);
    ctx.lineTo(128, i);
    ctx.stroke();
  }
  return toTexture(el);
}

// Punto suave para partículas de polvo.
export function softDotTexture() {
  const [el, ctx] = canvas(64, 64);
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.4, 'rgba(255,255,255,0.5)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  return toTexture(el);
}

export function textTexture(text, { width = 256, height = 128, color = '#ffffff', font, shadow = true } = {}) {
  const [el, ctx] = canvas(width, height);
  ctx.font = font ?? `800 ${Math.round(height * 0.62)}px ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  if (shadow) {
    ctx.shadowColor = 'rgba(0,0,0,0.35)';
    ctx.shadowBlur = height * 0.06;
  }
  ctx.fillStyle = color;
  ctx.fillText(text, width / 2, height / 2 + height * 0.04);
  return toTexture(el);
}

export function hazardTexture() {
  const [el, ctx] = canvas(128, 32);
  ctx.fillStyle = '#f4f1ea';
  ctx.fillRect(0, 0, 128, 32);
  ctx.fillStyle = '#e1453a';
  for (let x = -32; x < 160; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x, 32);
    ctx.lineTo(x + 16, 32);
    ctx.lineTo(x + 32, 0);
    ctx.lineTo(x + 16, 0);
    ctx.fill();
  }
  const texture = toTexture(el);
  texture.wrapS = THREE.RepeatWrapping;
  return texture;
}
