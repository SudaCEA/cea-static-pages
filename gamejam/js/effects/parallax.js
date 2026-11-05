/**
 * parallax.js — pointer-driven depth layers for a static content area.
 *
 * Mark child elements with `data-parallax="<depth>"`; depth 0 is fixed and
 * depth 1 moves by `maxShiftPx` at the pointer's edge. The root is the
 * coordinate space (usually the content rectangle). Layers are translated in
 * CSS pixels, so the effect does not affect layout or the content's size.
 *
 * The loop runs only while the smoothed pointer position is catching up. It
 * stops when the position settles, which keeps the mirror's capture quiet
 * between pointer moves.
 */

export const PARALLAX_DEFAULTS = Object.freeze({
  maxShiftPx: 20,
  smoothing: 8,
  selector: '[data-parallax]'
});

function clamp(value, min, max) {
  return value < min ? min : value > max ? max : value;
}

function normalizeDepth(value) {
  const depth = Number(value);
  if (!Number.isFinite(depth)) return 0;
  return clamp(depth, 0, 4);
}

export function createParallax(root, options = {}) {
  if (!root || root.nodeType !== 1) {
    throw new TypeError('parallax: a root element is required');
  }

  const settings = {
    maxShiftPx: Number.isFinite(Number(options.maxShiftPx))
      ? Math.max(0, Number(options.maxShiftPx))
      : PARALLAX_DEFAULTS.maxShiftPx,
    smoothing: Number.isFinite(Number(options.smoothing))
      ? Math.max(0.01, Number(options.smoothing))
      : PARALLAX_DEFAULTS.smoothing,
    selector: typeof options.selector === 'string' && options.selector
      ? options.selector
      : PARALLAX_DEFAULTS.selector
  };

  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)') || null;
  const controller = new AbortController();
  const signal = controller.signal;
  const state = {
    destroyed: false,
    animating: false,
    raf: 0,
    lastNow: 0,
    frames: 0,
    reducedMotion: media ? media.matches : false,
    target: { x: 0, y: 0 },
    current: { x: 0, y: 0 }
  };

  const layers = [...root.querySelectorAll(settings.selector)].map((element) => ({
    element,
    depth: normalizeDepth(element.dataset.parallax),
    shiftPx: 0
  }));
  for (const layer of layers) {
    layer.shiftPx = layer.depth * settings.maxShiftPx;
  }

  function render() {
    if (state.destroyed) return;
    for (const layer of layers) {
      const x = -state.current.x * layer.shiftPx;
      const y = -state.current.y * layer.shiftPx;
      layer.element.style.transform =
        `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0)`;
    }
    state.frames += 1;
  }

  function schedule() {
    if (
      state.destroyed ||
      state.reducedMotion ||
      document.hidden ||
      state.raf
    ) {
      return;
    }
    if (!state.animating) state.lastNow = 0;
    state.animating = true;
    state.raf = requestAnimationFrame(tick);
  }

  function tick(now) {
    state.raf = 0;
    if (state.destroyed) {
      state.animating = false;
      return;
    }
    if (state.reducedMotion || document.hidden) {
      state.animating = false;
      return;
    }

    const dt = state.lastNow > 0
      ? Math.min(0.05, Math.max(0, (now - state.lastNow) / 1000))
      : 0;
    state.lastNow = now;
    const amount = state.reducedMotion
      ? 1
      : 1 - Math.exp(-Math.max(0.0001, dt) * settings.smoothing);
    state.current.x += (state.target.x - state.current.x) * amount;
    state.current.y += (state.target.y - state.current.y) * amount;

    const settled =
      Math.abs(state.target.x - state.current.x) < 0.0005 &&
      Math.abs(state.target.y - state.current.y) < 0.0005;
    if (settled) {
      state.current.x = state.target.x;
      state.current.y = state.target.y;
    }

    render();

    if (settled) {
      state.animating = false;
      return;
    }
    schedule();
  }

  function setPointer(x, y) {
    if (state.destroyed) return;
    const nx = clamp(Number(x), -1, 1);
    const ny = clamp(Number(y), -1, 1);
    state.target.x = Number.isFinite(nx) ? nx : 0;
    state.target.y = Number.isFinite(ny) ? ny : 0;
    if (state.reducedMotion) {
      state.current.x = 0;
      state.current.y = 0;
      render();
      return;
    }
    schedule();
  }

  function reset() {
    setPointer(0, 0);
  }

  function pointerPosition(event, rect) {
    return {
      x: clamp(((event.clientX - rect.left) / rect.width) * 2 - 1, -1, 1),
      y: clamp(((event.clientY - rect.top) / rect.height) * 2 - 1, -1, 1)
    };
  }

  function onPointerMove(event) {
    if (state.destroyed || state.reducedMotion) return;
    const rect = root.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const point = pointerPosition(event, rect);
    setPointer(point.x, point.y);
  }

  function onPointerUp(event) {
    if (event.pointerType && event.pointerType !== 'mouse') reset();
  }

  function onVisibility() {
    if (document.hidden) {
      if (state.raf) cancelAnimationFrame(state.raf);
      state.raf = 0;
      state.animating = false;
      return;
    }
    if (state.reducedMotion) {
      render();
      return;
    }
    const settled =
      Math.abs(state.target.x - state.current.x) < 0.0005 &&
      Math.abs(state.target.y - state.current.y) < 0.0005;
    if (!settled) schedule();
  }

  function onReducedMotion(event) {
    state.reducedMotion = event.matches;
    if (state.reducedMotion) {
      if (state.raf) cancelAnimationFrame(state.raf);
      state.raf = 0;
      state.animating = false;
      state.target.x = 0;
      state.target.y = 0;
      state.current.x = 0;
      state.current.y = 0;
      render();
      return;
    }
    const settled =
      Math.abs(state.target.x - state.current.x) < 0.0005 &&
      Math.abs(state.target.y - state.current.y) < 0.0005;
    if (!settled) schedule();
  }

  window.addEventListener('pointermove', onPointerMove, {
    passive: true,
    signal
  });
  window.addEventListener('pointerup', onPointerUp, {
    passive: true,
    signal
  });
  window.addEventListener('pointercancel', onPointerUp, {
    passive: true,
    signal
  });
  document.documentElement.addEventListener('pointerleave', reset, {
    passive: true,
    signal
  });
  document.addEventListener('visibilitychange', onVisibility, { signal });
  media?.addEventListener('change', onReducedMotion, { signal });

  function refresh() {
    if (state.destroyed) return [];
    for (const layer of layers) {
      layer.depth = normalizeDepth(layer.element.dataset.parallax);
      layer.shiftPx = layer.depth * settings.maxShiftPx;
    }
    render();
    return getState();
  }

  function getState() {
    return {
      frames: state.frames,
      animating: state.animating,
      reducedMotion: state.reducedMotion,
      pointer: { ...state.target },
      current: { ...state.current },
      maxShiftPx: settings.maxShiftPx,
      smoothing: settings.smoothing,
      layers: layers.map((layer) => ({
        depth: layer.depth,
        shiftPx: layer.shiftPx,
        offset: {
          x: -state.current.x * layer.shiftPx,
          y: -state.current.y * layer.shiftPx
        }
      }))
    };
  }

  function destroy() {
    if (state.destroyed) return;
    state.destroyed = true;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = 0;
    state.animating = false;
    controller.abort();
    for (const layer of layers) {
      layer.element.style.transform = '';
    }
  }

  render();

  return {
    root,
    setPointer,
    reset,
    refresh,
    render,
    getState,
    destroy,
    get layers() { return [...layers]; }
  };
}
