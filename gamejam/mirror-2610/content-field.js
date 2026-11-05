/**
 * content-field.js — rising particle field for mirror-2610.
 *
 * One nested Canvas 2D canvas draws the solid content surface and a slow,
 * decorative particle column. The canvas is a normal child of the drawable
 * content frame: it is not a drawable root, it does not use CSS transforms or
 * filters, and its backing store follows CSS size × min(devicePixelRatio, 2).
 *
 * The animation loop runs continuously while the page is visible. There is no
 * pointer state and no idle pause: particles keep rising even when the pointer
 * is still or outside the content.
 */

export const PARTICLE_DEFAULTS = Object.freeze({
  minSizePx: 1.2,
  maxSizePx: 4.2,
  minSpeedPxPerSec: 16,
  maxSpeedPxPerSec: 38,
  densityAreaPx: 7000,
  minCount: 24,
  maxCount: 120,
  dprCap: 2
});

const TAU = Math.PI * 2;

function clamp(value, min, max) {
  return value < min ? min : value > max ? max : value;
}

function smoothstep(edge0, edge1, value) {
  const t = clamp((value - edge0) / Math.max(0.0001, edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function parseColor(value, fallback) {
  const match = /^#([0-9a-f]{6})$/i.exec(String(value || ''));
  if (!match) return fallback;
  const hex = match[1];
  return [
    parseInt(hex.slice(0, 2), 16) / 255,
    parseInt(hex.slice(2, 4), 16) / 255,
    parseInt(hex.slice(4, 6), 16) / 255
  ];
}

function colorCss(rgb) {
  return `rgb(${rgb.map((channel) => Math.round(channel * 255)).join(', ')})`;
}

function colorAlphaCss(rgb, alpha) {
  return `rgba(${rgb.map((channel) => Math.round(channel * 255)).join(', ')}, ${alpha})`;
}

function createRandom(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = Math.imul(state ^ (state >>> 15), 1 | state);
    value ^= value + Math.imul(value ^ (value >>> 7), 61 | value);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function buildParticleSprite(rgb) {
  const size = 64;
  const sprite = document.createElement('canvas');
  sprite.width = size;
  sprite.height = size;
  const context = sprite.getContext('2d');
  if (!context) return null;

  const centre = size / 2;
  const gradient = context.createRadialGradient(
    centre, centre, 0,
    centre, centre, centre - 0.5
  );
  gradient.addColorStop(0, colorAlphaCss(rgb, 1));
  gradient.addColorStop(0.28, colorAlphaCss(rgb, 0.92));
  gradient.addColorStop(0.58, colorAlphaCss(rgb, 0.44));
  gradient.addColorStop(0.82, colorAlphaCss(rgb, 0.12));
  gradient.addColorStop(1, colorAlphaCss(rgb, 0));
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  return sprite;
}

export function createContentField(canvas, options = {}) {
  if (!canvas || typeof canvas.getContext !== 'function') {
    throw new TypeError('content-field: a canvas element is required');
  }

  const host = canvas.parentElement;
  if (!host) throw new Error('content-field: the canvas must have a parent');

  let context = null;
  try {
    context = canvas.getContext('2d', { alpha: false });
  } catch {
    context = null;
  }

  if (!context) {
    canvas.hidden = true;
    host.classList.add('is-field-fallback');
    return null;
  }

  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null;
  const controller = new AbortController();
  const signal = controller.signal;
  const random = createRandom(0x2610);
  const state = {
    destroyed: false,
    failed: false,
    rendered: false,
    frames: 0,
    animating: false,
    raf: 0,
    lastNow: 0,
    elapsed: 0,
    reducedMotion: media ? media.matches : false,
    cssWidth: 1,
    cssHeight: 1,
    canvasWidth: 1,
    canvasHeight: 1,
    dpr: 1,
    needsMeasure: true,
    particles: [],
    sprite: null,
    palette: {
      center: [1, 1, 1],
      particle: parseColor('#242622', [0.14, 0.15, 0.13])
    }
  };

  function particleCount(width, height) {
    const target = Math.round(
      (width * height) / PARTICLE_DEFAULTS.densityAreaPx
    );
    return clamp(
      target,
      PARTICLE_DEFAULTS.minCount,
      PARTICLE_DEFAULTS.maxCount
    );
  }

  function resetParticle(particle, prewarm) {
    particle.size = PARTICLE_DEFAULTS.minSizePx +
      random() * (PARTICLE_DEFAULTS.maxSizePx - PARTICLE_DEFAULTS.minSizePx);
    particle.speed = PARTICLE_DEFAULTS.minSpeedPxPerSec +
      random() * (
        PARTICLE_DEFAULTS.maxSpeedPxPerSec -
        PARTICLE_DEFAULTS.minSpeedPxPerSec
      );
    particle.alpha = 0.35 + random() * 0.55;
    particle.baseX = random() * state.cssWidth;
    particle.phase = random() * TAU;
    particle.swaySpeed = 0.16 + random() * 0.34;
    particle.swayAmp = 2 + random() * 12;
    particle.rise = (state.cssHeight + 120) * (0.78 + random() * 0.25);
    particle.life = particle.rise / particle.speed;
    particle.age = prewarm
      ? (0.02 + random() * 0.96) * particle.life
      : 0;
    updateParticle(particle);
  }

  function updateParticle(particle) {
    const progress = clamp(particle.age / particle.life, 0, 1);
    particle.progress = progress;
    particle.y = state.cssHeight + 24 - progress * particle.rise;
    particle.x = particle.baseX +
      Math.sin(particle.age * particle.swaySpeed + particle.phase) *
      particle.swayAmp;
  }

  function resetParticles() {
    const count = particleCount(state.cssWidth, state.cssHeight);
    state.particles = Array.from({ length: count }, (_, id) => {
      const particle = { id };
      resetParticle(particle, true);
      return particle;
    });
  }

  function buildSprite() {
    state.sprite = buildParticleSprite(state.palette.particle);
  }

  function measure() {
    const rect = host.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return false;

    const dpr = Math.min(
      window.devicePixelRatio || 1,
      PARTICLE_DEFAULTS.dprCap
    );
    const width = Math.max(1, Math.round(rect.width * dpr));
    const height = Math.max(1, Math.round(rect.height * dpr));
    const sizeChanged =
      Math.abs(rect.width - state.cssWidth) > 0.01 ||
      Math.abs(rect.height - state.cssHeight) > 0.01;

    state.cssWidth = rect.width;
    state.cssHeight = rect.height;
    state.dpr = dpr;

    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    state.canvasWidth = width;
    state.canvasHeight = height;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    context.imageSmoothingEnabled = true;

    if (sizeChanged || state.particles.length === 0) {
      resetParticles();
    }
    state.needsMeasure = false;
    return true;
  }

  function render() {
    if (state.destroyed || state.failed) return false;
    if (state.needsMeasure) {
      if (!measure()) return false;
    }

    context.globalAlpha = 1;
    context.globalCompositeOperation = 'source-over';
    context.fillStyle = colorCss(state.palette.center);
    context.fillRect(0, 0, state.cssWidth, state.cssHeight);

    const sprite = state.sprite;
    if (sprite) {
      for (const particle of state.particles) {
        const progress = particle.progress;
        const alpha = particle.alpha *
          smoothstep(0, 0.06, progress) *
          (1 - smoothstep(0.58, 1.0, progress));
        if (alpha < 0.002) continue;

        const radius = particle.size * (1 - 0.55 * progress);
        if (radius < 0.08) continue;
        const spread = radius * 1.7;

        // Soft halo first, then a small solid core so the field reads as
        // particles rather than blurred smudges.
        context.globalAlpha = alpha * 0.55;
        context.drawImage(
          sprite,
          particle.x - spread,
          particle.y - spread,
          spread * 2,
          spread * 2
        );
        context.globalAlpha = alpha;
        context.fillStyle = colorCss(state.palette.particle);
        context.beginPath();
        context.arc(
          particle.x,
          particle.y,
          Math.max(0.15, radius * 0.45),
          0,
          TAU
        );
        context.fill();
      }
    } else {
      context.fillStyle = colorCss(state.palette.particle);
      for (const particle of state.particles) {
        const progress = particle.progress;
        const alpha = particle.alpha *
          smoothstep(0, 0.06, progress) *
          (1 - smoothstep(0.58, 1.0, progress));
        if (alpha < 0.002) continue;
        const radius = particle.size * (1 - 0.55 * progress);
        context.globalAlpha = alpha;
        context.beginPath();
        context.arc(particle.x, particle.y, Math.max(0.12, radius), 0, TAU);
        context.fill();
      }
    }

    context.globalAlpha = 1;
    state.rendered = true;
    state.frames += 1;
    return true;
  }

  function schedule() {
    if (
      state.destroyed ||
      state.failed ||
      state.reducedMotion ||
      document.hidden ||
      state.raf
    ) {
      return;
    }
    state.animating = true;
    state.raf = requestAnimationFrame(tick);
  }

  function tick(now) {
    state.raf = 0;
    if (state.destroyed || state.failed) {
      state.animating = false;
      return;
    }
    if (document.hidden) {
      state.animating = false;
      return;
    }

    const dt = state.lastNow > 0
      ? Math.min(0.05, Math.max(0, (now - state.lastNow) / 1000))
      : 0;
    state.lastNow = now;
    state.elapsed += dt;

    for (const particle of state.particles) {
      particle.age += dt;
      if (particle.age >= particle.life) {
        resetParticle(particle, false);
      } else {
        updateParticle(particle);
      }
    }

    render();

    if (state.reducedMotion) {
      state.animating = false;
      return;
    }
    schedule();
  }

  function setPalette(next = {}) {
    if (state.destroyed) return;
    const palette = next && typeof next === 'object' ? next : {};
    state.palette = {
      center: parseColor(palette.center, state.palette.center),
      particle: parseColor(palette.particle, state.palette.particle)
    };
    buildSprite();
    render();
    if (!state.reducedMotion && !state.animating) {
      state.lastNow = 0;
      schedule();
    }
  }

  const onResize = () => {
    state.needsMeasure = true;
    render();
  };

  const observer = typeof ResizeObserver !== 'undefined'
    ? new ResizeObserver(onResize)
    : null;
  observer?.observe(host);
  window.addEventListener('resize', onResize, { passive: true, signal });

  const onVisibility = () => {
    if (document.hidden) {
      if (state.raf) cancelAnimationFrame(state.raf);
      state.raf = 0;
      state.animating = false;
      return;
    }
    state.lastNow = 0;
    if (state.reducedMotion) {
      render();
    } else {
      schedule();
    }
  };
  document.addEventListener('visibilitychange', onVisibility, { signal });

  const onReducedMotion = (event) => {
    state.reducedMotion = event.matches;
    if (state.reducedMotion) {
      if (state.raf) cancelAnimationFrame(state.raf);
      state.raf = 0;
      state.animating = false;
      render();
      return;
    }
    state.lastNow = 0;
    schedule();
  };
  media?.addEventListener('change', onReducedMotion, { signal });

  function ready() {
    render();
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve(state.rendered));
      });
    });
  }

  function getState() {
    const sample = state.particles.slice(0, 4).map((particle) => ({
      id: particle.id,
      x: Number(particle.x.toFixed(2)),
      y: Number(particle.y.toFixed(2)),
      progress: Number(particle.progress.toFixed(4)),
      size: Number(particle.size.toFixed(3)),
      alpha: Number(particle.alpha.toFixed(3))
    }));
    return {
      rendered: state.rendered,
      frames: state.frames,
      animating: state.animating,
      fallback: state.failed,
      reducedMotion: state.reducedMotion,
      time: state.reducedMotion ? 0 : state.elapsed,
      css: { width: state.cssWidth, height: state.cssHeight },
      canvas: { width: state.canvasWidth, height: state.canvasHeight },
      dpr: state.dpr,
      count: state.particles.length,
      samples: sample,
      particle: {
        sizePx: [PARTICLE_DEFAULTS.minSizePx, PARTICLE_DEFAULTS.maxSizePx],
        speedPxPerSec: [
          PARTICLE_DEFAULTS.minSpeedPxPerSec,
          PARTICLE_DEFAULTS.maxSpeedPxPerSec
        ],
        densityAreaPx: PARTICLE_DEFAULTS.densityAreaPx,
        dprCap: PARTICLE_DEFAULTS.dprCap
      },
      palette: {
        center: [...state.palette.center],
        particle: [...state.palette.particle]
      }
    };
  }

  function destroy() {
    if (state.destroyed) return;
    state.destroyed = true;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    state.animating = false;
    controller.abort();
    observer?.disconnect();
    state.particles = [];
    state.sprite = null;
    canvas.hidden = true;
  }

  buildSprite();
  render();
  if (!state.reducedMotion) schedule();

  return {
    canvas,
    setPalette,
    render,
    ready,
    getState,
    destroy,
    get context() { return context; }
  };
}
