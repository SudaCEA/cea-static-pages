/**
 * mirror.js — one API for two mirror backends.
 *
 *   import { createMirror } from './js/effects/mirror.js';
 *
 *   const mirror = await createMirror({
 *     container: document.querySelector('#stage'),
 *     content: document.querySelector('#art'),
 *     mode: 'svg',                       // 'svg' | 'webgl'
 *     contentSize: { width: '600px', height: '60%' },
 *     filter: { blur: 2, feather: 40 },
 *     resize: { interval: 120 },
 *     webgl: { dprCap: 2, renderScale: 0.5, contentScale: 1 }
 *   });
 *
 * The module fills `container` with a root layer, creates a content frame div,
 * moves `content` into it, and mirrors the frame's four sides / four corners.
 * `contentSize` accepts px or percentage strings (percentages are relative to
 * the container's clientWidth/clientHeight). A ResizeObserver keeps the DOM
 * layout, SVG displacement maps and WebGL uniforms in sync.
 *
 * `resize.interval` (ms, default 100) debounces ResizeObserver / window resize:
 * only the final size is laid out. `resizeStart`, `resizing` and `resizeEnd`
 * events expose the lifecycle; `resizing` is throttled to one event per
 * interval and never triggers a layout itself. Programmatic `setContentSize`
 * and `refresh` still update on the next animation frame.
 *
 * SVG mode uses a procedural R/G displacement map plus an optional
 * feGaussianBlur pass. WebGL mode uses three.js HTMLTexture + a fullscreen
 * shader and requires HTML-in-Canvas support in Chrome
 * (`--enable-features=CanvasDrawElement`). Use `checkHtmlInCanvasSupport()`
 * to probe support and known nested-canvas DPR issues before attempting WebGL.
 *
 * WebGL also accepts `webgl.renderScale` and `webgl.contentScale` in (0, 1].
 * The mirror bands and the centre body are rendered into separate offscreen
 * targets at their own scales, then composited with linear filtering onto the
 * DPR canvas. The canvas and DOM hit-testing geometry stay at full output
 * resolution, and `contentScale: 1` keeps the body at native resolution while
 * only the mirror content is reduced. A two-device-pixel, full-resolution
 * skirt repeats the body texture's edge over the low-resolution seam.
 *
 * `webgl.onProgress(event)` reports three-loader lifecycle. Native `import()`
 * exposes start/done only; `webgl.threeLoader({ url, onProgress })` can add
 * byte progress when it loads a single-file three build itself.
 */

const SVG_NS = 'http://www.w3.org/2000/svg';

const DEFAULT_FILTER = Object.freeze({
  blur: 0,
  feather: 40
});

const DEFAULT_SVG = Object.freeze({
  mapScale: 'device',
  maxMR: null,
  maskScale: 'device'
});

const DEFAULT_WEBGL = Object.freeze({
  dprCap: 2,
  renderScale: 1,
  contentScale: 1,
  fallbackToSvg: true,
  threeUrl: null
});

// A full-resolution ring outside the content rectangle. It repeats the
// content texture's edge pixels over the low-resolution composite seam.
const EDGE_SKIRT_DEVICE_PX = 2;

const DEFAULT_RESIZE = Object.freeze({
  interval: 100
});

export const HTML_IN_CANVAS_MIN_CHROME = '157.0.8080.0';

const CHROME_DPR_BUG_URL = 'https://issues.chromium.org/issues/540532973';
const CANVAS_DRAW_ELEMENT_FLAG = 'chrome://flags/#canvas-draw-element';

let nextId = 1;
const threeCache = new Map();

/* --------------------------------------------------------------------------
   Small helpers
   ----------------------------------------------------------------------- */

function clamp(value, min, max) {
  return value < min ? min : value > max ? max : value;
}

function finite(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function parseVersion(value) {
  const match = String(value == null ? '' : value).trim().match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (!match) return null;
  return {
    text: `${match[1]}.${match[2]}.${match[3]}.${match[4]}`,
    parts: match.slice(1).map(Number)
  };
}

function compareVersionParts(a, b) {
  for (let i = 0; i < 4; i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return 0;
}

function detectBrowser(userAgent) {
  const ua = String(userAgent || '');
  if (/\bEdg\//.test(ua)) return 'edge';
  if (/\bOPR\//.test(ua)) return 'opera';
  if (/\bChrome\//.test(ua)) return 'chrome';
  if (/\bChromium\//.test(ua)) return 'chromium';
  return 'unknown';
}

function parseChromeVersion(userAgent) {
  const match = String(userAgent || '').match(/\b(?:Chrome|Chromium)\/(\d+)\.(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return {
    text: `${match[1]}.${match[2]}.${match[3]}.${match[4]}`,
    parts: match.slice(1).map(Number)
  };
}

function preflightIssue(code, message, url) {
  const issue = { code, message };
  if (url) issue.url = url;
  return issue;
}

function applyStyles(el, styles) {
  for (const key of Object.keys(styles)) {
    const value = styles[key];
    if (value === undefined || value === null) continue;
    el.style[key] = value;
  }
}

function setVendorBackdrop(el, value) {
  el.style.backdropFilter = value;
  el.style.setProperty('-webkit-backdrop-filter', value);
}

function normalizeFilter(input, base = DEFAULT_FILTER) {
  const src = input && typeof input === 'object' ? input : {};
  if (Object.prototype.hasOwnProperty.call(src, 'ripple')) {
    throw new TypeError('mirror: filter.ripple has been removed');
  }
  if (Object.prototype.hasOwnProperty.call(src, 'region')) {
    throw new TypeError('mirror: filter.region has been removed; bands is fixed');
  }
  if (Object.prototype.hasOwnProperty.call(src, 'outer')) {
    throw new TypeError('mirror: filter.outer has been removed');
  }
  const pick = (key) => (src[key] === undefined ? base[key] : src[key]);
  return {
    blur: clamp(finite(pick('blur'), base.blur), 0, 32),
    feather: clamp(finite(pick('feather'), base.feather), 0, 512)
  };
}

function sameFilter(a, b) {
  return !!a && !!b &&
    a.blur === b.blur &&
    a.feather === b.feather;
}

function sameLayout(a, b, epsilon = 0.01) {
  if (!a || !b) return false;
  const sameCss =
    Math.abs(a.width - b.width) < epsilon &&
    Math.abs(a.height - b.height) < epsilon &&
    Math.abs(a.ax - b.ax) < epsilon &&
    Math.abs(a.ay - b.ay) < epsilon &&
    Math.abs(a.aw - b.aw) < epsilon &&
    Math.abs(a.ah - b.ah) < epsilon;
  if (!sameCss || !a.device || !b.device) return sameCss;
  return a.dpr === b.dpr &&
    a.device.width === b.device.width &&
    a.device.height === b.device.height &&
    a.device.ax === b.device.ax &&
    a.device.ay === b.device.ay &&
    a.device.aw === b.device.aw &&
    a.device.ah === b.device.ah;
}

/**
 * Quantize one CSS-pixel dimension to whole device pixels. The result is
 * floored (never wider than the requested box) and adjusted to share parity
 * with the surface so centering produces integer left/top coordinates.
 */
function snapDeviceDimension(cssValue, totalDevice, dpr) {
  const total = Math.max(1, Math.round(totalDevice));
  const target = Math.max(0, cssValue) * dpr;
  let device = Math.floor(target + 1e-6);
  if (cssValue > 0) device = Math.max(1, device);
  if (Math.abs(device - total) % 2 !== 0) {
    device = Math.max(0, device - 1);
  }
  return device;
}

function makeLayout(W, H, aw, ah, dpr) {
  const totalWidth = Math.max(1, Math.round(W * dpr));
  const totalHeight = Math.max(1, Math.round(H * dpr));
  const awDev = snapDeviceDimension(aw, totalWidth, dpr);
  const ahDev = snapDeviceDimension(ah, totalHeight, dpr);
  const axDev = Math.round((totalWidth - awDev) / 2);
  const ayDev = Math.round((totalHeight - ahDev) / 2);

  return {
    width: W,
    height: H,
    ax: axDev / dpr,
    ay: ayDev / dpr,
    aw: awDev / dpr,
    ah: ahDev / dpr,
    dpr,
    device: {
      width: totalWidth,
      height: totalHeight,
      ax: axDev,
      ay: ayDev,
      aw: awDev,
      ah: ahDev
    }
  };
}

function validateSizeSpec(value, name) {
  if (value === undefined || value === null || value === '') return;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new TypeError(`mirror: contentSize.${name} must be finite`);
    }
    return;
  }
  if (typeof value === 'string') {
    if (!/^\s*\d*\.?\d+\s*(px|%)\s*$/i.test(value)) {
      throw new TypeError(
        `mirror: invalid contentSize.${name} "${value}" (use a number, "600px" or "60%")`
      );
    }
    return;
  }
  throw new TypeError(`mirror: contentSize.${name} must be a number, px/% string, or null`);
}

/**
 * Resolve a content dimension.
 *   number        -> px
 *   "600px"       -> px
 *   "60%"         -> percentage of `base`
 *   null/undefined-> fallback
 */
function resolveSize(value, base, fallback) {
  if (value === undefined || value === null || value === '') return fallback;
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new TypeError('mirror: contentSize number must be finite');
    }
    return Math.max(0, value);
  }
  if (typeof value === 'string') {
    const match = /^\s*(\d*\.?\d+)\s*(px|%)\s*$/i.exec(value);
    if (!match) {
      throw new TypeError(
        `mirror: invalid contentSize "${value}" (use a number, "600px" or "60%")`
      );
    }
    const amount = parseFloat(match[1]);
    const px = match[2] === '%' ? base * amount / 100 : amount;
    return Math.max(0, px);
  }
  throw new TypeError('mirror: contentSize must be a number, px/% string, or null');
}

function normalizeSvgScale(value, name) {
  if (value === 'device') return 'device';
  if (typeof value === 'number') {
    if (Number.isFinite(value) && value > 0) return value;
    throw new TypeError(`mirror: svg.${name} must be "device" or a positive number`);
  }
  if (typeof value === 'string' && value.trim() !== '') {
    const number = Number(value);
    if (Number.isFinite(number) && number > 0) return number;
  }
  throw new TypeError(`mirror: svg.${name} must be "device" or a positive number`);
}

function normalizeMaxMR(value) {
  if (value === undefined || value === null || value === '') return null;
  let width;
  let height;
  if (typeof value === 'string') {
    const match = /^\s*(\d+)\s*[x×]\s*(\d+)\s*$/i.exec(value);
    if (!match) {
      throw new TypeError('mirror: svg.maxMR must look like "1920x1080"');
    }
    width = Number(match[1]);
    height = Number(match[2]);
  } else if (typeof value === 'object') {
    width = Number(value.width);
    height = Number(value.height);
  } else {
    throw new TypeError('mirror: svg.maxMR must look like "1920x1080"');
  }
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1) {
    throw new TypeError('mirror: svg.maxMR width/height must be positive integers');
  }
  return { width, height };
}

function normalizeSvgOptions(raw) {
  if (raw !== undefined && raw !== null && typeof raw !== 'object') {
    throw new TypeError('mirror: svg options must be an object');
  }
  const source = raw || {};
  if (Object.prototype.hasOwnProperty.call(source, 'maxMapPixels')) {
    throw new TypeError('mirror: svg.maxMapPixels has been removed; use maxMR');
  }
  if (Object.prototype.hasOwnProperty.call(source, 'rippleMapScale')) {
    throw new TypeError('mirror: svg.rippleMapScale has been removed');
  }
  const merged = { ...DEFAULT_SVG, ...source };

  return {
    mapScale: normalizeSvgScale(merged.mapScale, 'mapScale'),
    maxMR: normalizeMaxMR(merged.maxMR),
    maskScale: normalizeSvgScale(merged.maskScale, 'maskScale')
  };
}

function normalizeScale(value, name) {
  const scale = typeof value === 'number'
    ? value
    : (typeof value === 'string' && value.trim() !== '' ? Number(value) : NaN);
  if (!Number.isFinite(scale) || scale <= 0 || scale > 1) {
    throw new TypeError(`mirror: webgl.${name} must be a number in (0, 1]`);
  }
  return scale;
}

function normalizeRenderScale(value) {
  return normalizeScale(value, 'renderScale');
}

function normalizeContentScale(value) {
  return normalizeScale(value, 'contentScale');
}

function normalizeWebglOptions(raw) {
  if (raw !== undefined && raw !== null && typeof raw !== 'object') {
    throw new TypeError('mirror: webgl options must be an object');
  }
  const source = raw || {};
  const merged = { ...DEFAULT_WEBGL, ...source };
  const requested = source.renderScale === undefined
    ? DEFAULT_WEBGL.renderScale
    : source.renderScale;
  const contentRequested = source.contentScale === undefined
    ? DEFAULT_WEBGL.contentScale
    : source.contentScale;
  merged.renderScale = normalizeRenderScale(requested);
  merged.contentScale = normalizeContentScale(contentRequested);
  for (const key of ['onProgress', 'threeLoader']) {
    if (source[key] !== undefined && source[key] !== null && typeof source[key] !== 'function') {
      throw new TypeError(`mirror: webgl.${key} must be a function`);
    }
  }
  return merged;
}

function normalizeResizeOptions(raw) {
  if (raw === undefined || raw === null) return { ...DEFAULT_RESIZE };
  if (typeof raw !== 'object') {
    throw new TypeError('mirror: resize options must be an object { interval }');
  }
  const value = raw.interval === undefined ? DEFAULT_RESIZE.interval : raw.interval;
  const interval = typeof value === 'number'
    ? value
    : (typeof value === 'string' && value.trim() !== '' ? Number(value) : NaN);
  if (!Number.isFinite(interval) || interval < 0) {
    throw new TypeError('mirror: resize.interval must be a non-negative number of milliseconds');
  }
  return { interval };
}

function normalizeOptions(raw) {
  if (!raw || typeof raw !== 'object') {
    throw new TypeError('mirror: createMirror(options) requires an options object');
  }
  if (!raw.container || raw.container.nodeType !== 1) {
    throw new TypeError('mirror: options.container must be an element');
  }
  if (!raw.content || raw.content.nodeType !== 1) {
    throw new TypeError('mirror: options.content must be an element');
  }
  if (raw.container === raw.content) {
    throw new Error('mirror: container and content must be different elements');
  }
  if (raw.content.contains(raw.container)) {
    throw new Error('mirror: content cannot contain the container');
  }

  const mode = raw.mode === undefined ? 'svg' : raw.mode;
  if (mode !== 'svg' && mode !== 'webgl') {
    throw new TypeError('mirror: mode must be "svg" or "webgl"');
  }

  let contentSize = {};
  if (raw.contentSize !== undefined && raw.contentSize !== null) {
    if (typeof raw.contentSize !== 'object') {
      throw new TypeError('mirror: contentSize must be an object { width, height }');
    }
    contentSize = {
      width: raw.contentSize.width,
      height: raw.contentSize.height
    };
    validateSizeSpec(contentSize.width, 'width');
    validateSizeSpec(contentSize.height, 'height');
  }

  const contentFit = raw.contentFit === undefined ? 'fill' : raw.contentFit;
  if (contentFit !== 'fill' && contentFit !== 'none') {
    throw new TypeError('mirror: contentFit must be "fill" or "none"');
  }

  return {
    container: raw.container,
    content: raw.content,
    mode,
    contentSize,
    contentFit,
    background: raw.background === undefined ? null : raw.background,
    filter: normalizeFilter(raw.filter, DEFAULT_FILTER),
    svg: normalizeSvgOptions(raw.svg),
    webgl: normalizeWebglOptions(raw.webgl),
    resize: normalizeResizeOptions(raw.resize),
    autoObserve: raw.autoObserve !== false,
    debug: !!raw.debug
  };
}

/* --------------------------------------------------------------------------
   Procedural SVG maps
   ----------------------------------------------------------------------- */

function clampByte(value) {
  return value < 0 ? 0 : value > 255 ? 255 : value;
}

function makeCanvas(width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, width);
  canvas.height = Math.max(1, height);
  return canvas;
}

function mirrorCoord(p, a0, a1) {
  let s = p;
  if (p < a0) s = 2 * a0 - p;
  else if (p > a1) s = 2 * a1 - p;
  if (s < a0) s = a0;
  else if (s > a1) s = a1;
  return s;
}

/**
 * R/G map encoding the mirror displacement. Values are evaluated at the
 * continuous CSS coordinate of every texel, so increasing mapScale produces
 * a genuinely higher-resolution ramp instead of nearest-neighbour blocks.
 */
function makeMirrorMap(layout, mapScale) {
  const W = layout.width;
  const H = layout.height;
  const ax = layout.ax;
  const ay = layout.ay;
  const aw = Math.max(0, layout.aw);
  const ah = Math.max(0, layout.ah);
  const right = ax + aw;
  const bottom = ay + ah;
  const margin = Math.max(0, ax, W - right, ay, H - bottom);
  const scale = 4 * margin;
  const bias = (128 / 255 - 0.5) * scale;

  // Floor so the generated dimensions stay inside the maxMR cap.
  const width = Math.max(1, Math.floor(W * mapScale));
  const height = Math.max(1, Math.floor(H * mapScale));
  const canvas = makeCanvas(width, height);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const image = ctx.createImageData(width, height);
  const data = image.data;
  const inv = scale > 0 ? 1 / scale : 0;

  for (let y = 0; y < height; y++) {
    const cy = (y + 0.5) / mapScale;
    const sy = mirrorCoord(cy, ay, bottom);
    const dy = sy - cy;
    for (let x = 0; x < width; x++) {
      const cx = (x + 0.5) / mapScale;
      const sx = mirrorCoord(cx, ax, right);
      const dx = sx - cx;
      const i = (y * width + x) * 4;
      data[i] = scale > 0 ? clampByte(Math.round((0.5 + dx * inv) * 255)) : 128;
      data[i + 1] = scale > 0 ? clampByte(Math.round((0.5 + dy * inv) * 255)) : 128;
      data[i + 2] = 0;
      data[i + 3] = 255;
    }
  }

  ctx.putImageData(image, 0, 0);
  return {
    url: canvas.toDataURL('image/png'),
    width,
    height,
    scale,
    bias
  };
}

function makeMaskMap(layout, filter, mapScale) {
  const W = layout.width;
  const H = layout.height;
  const ax = layout.ax;
  const ay = layout.ay;
  const aw = Math.max(0, layout.aw);
  const ah = Math.max(0, layout.ah);
  const right = ax + aw;
  const bottom = ay + ah;
  const feather = filter.feather;
  const smooth = (t) => t * t * (3 - 2 * t);

  const width = Math.max(1, Math.floor(W * mapScale));
  const height = Math.max(1, Math.floor(H * mapScale));
  const canvas = makeCanvas(width, height);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const image = ctx.createImageData(width, height);
  const data = image.data;

  for (let y = 0; y < height; y++) {
    const py = (y + 0.5) / mapScale;
    for (let x = 0; x < width; x++) {
      const px = (x + 0.5) / mapScale;
      const distance = Math.max(ax - px, px - right, ay - py, py - bottom);
      let alpha = 0;
      if (distance > 0) {
        alpha = feather <= 0 ? 1 : smooth(Math.min(1, distance / feather));
      }

      const i = (y * width + x) * 4;
      data[i] = 255;
      data[i + 1] = 255;
      data[i + 2] = 255;
      data[i + 3] = clampByte(Math.round(alpha * 255));
    }
  }

  ctx.putImageData(image, 0, 0);
  return {
    url: canvas.toDataURL('image/png'),
    width,
    height
  };
}

/* --------------------------------------------------------------------------
   SVG backend
   ----------------------------------------------------------------------- */

class SvgBackend {
  constructor(mirror) {
    this.kind = 'svg';
    this.mirror = mirror;
    this.svg = null;
    this.glass = null;
    this.filter = null;
    this.feOffset = null;
    this.feMirror = null;
    this.feWarp = null;
    this.feBlur = null;
    this.feMask = null;
    this._layout = null;
    this._filter = mirror._filter;
    this._dpr = mirror._dpr;
    this._mirrorMap = null;
    this._mirrorScale = 0;
    this._mirrorSize = null;
    this._maskSize = null;
    this._mapInfo = null;
  }

  mount() {
    const m = this.mirror;
    const frame = m.contentFrame;

    frame.removeAttribute('drawable');
    frame.style.zoom = '';
    frame.style.transform = '';
    frame.style.transformOrigin = '';
    frame.style.left = '0px';
    frame.style.top = '0px';
    frame.style.zIndex = '1';
    if (frame.parentNode !== m.root) m.root.appendChild(frame);

    this.glass = document.createElement('div');
    this.glass.className = 'mirror-glass';
    this.glass.setAttribute('aria-hidden', 'true');
    applyStyles(this.glass, {
      position: 'absolute',
      top: '0',
      right: '0',
      bottom: '0',
      left: '0',
      zIndex: '2',
      pointerEvents: 'none',
      background: 'transparent'
    });
    m.root.appendChild(this.glass);

    this.svg = document.createElementNS(SVG_NS, 'svg');
    this.svg.setAttribute('aria-hidden', 'true');
    applyStyles(this.svg, {
      position: 'absolute',
      width: '0',
      height: '0',
      overflow: 'hidden',
      pointerEvents: 'none'
    });

    const defs = document.createElementNS(SVG_NS, 'defs');
    this.filter = this._createFilter();
    defs.appendChild(this.filter);
    this.svg.appendChild(defs);
    m.root.appendChild(this.svg);

    setVendorBackdrop(this.glass, `url(#${m._id})`);
  }

  _createFilter() {
    const filter = document.createElementNS(SVG_NS, 'filter');
    filter.setAttribute('id', this.mirror._id);
    filter.setAttribute('filterUnits', 'userSpaceOnUse');
    filter.setAttribute('primitiveUnits', 'userSpaceOnUse');
    filter.setAttribute('x', '0');
    filter.setAttribute('y', '0');
    filter.setAttribute('width', '1');
    filter.setAttribute('height', '1');
    filter.setAttribute('color-interpolation-filters', 'sRGB');

    const add = (name, attributes) => {
      const el = document.createElementNS(SVG_NS, name);
      for (const key of Object.keys(attributes)) {
        el.setAttribute(key, attributes[key]);
      }
      filter.appendChild(el);
      return el;
    };

    this.feOffset = add('feOffset', {
      in: 'SourceGraphic', dx: '0', dy: '0', result: 'src'
    });
    this.feMirror = add('feImage', {
      x: '0', y: '0', width: '1', height: '1',
      preserveAspectRatio: 'none', result: 'map'
    });
    this.feWarp = add('feDisplacementMap', {
      in: 'src', in2: 'map', scale: '0',
      xChannelSelector: 'R', yChannelSelector: 'G', result: 'warped'
    });
    this.feBlur = add('feGaussianBlur', {
      in: 'warped', stdDeviation: '0', result: 'blurred'
    });
    this.feMask = add('feImage', {
      x: '0', y: '0', width: '1', height: '1',
      preserveAspectRatio: 'none', result: 'blurMask'
    });
    add('feComposite', {
      in: 'blurred', in2: 'blurMask', operator: 'in', result: 'blurMasked'
    });
    add('feComposite', {
      in: 'blurMasked', in2: 'warped', operator: 'over'
    });

    return filter;
  }

  layout(layout, filter, { dpr }) {
    this._filter = filter;
    this._dpr = dpr;
    // The SVG filter is rasterized in CSS units; use the device surface in
    // CSS units so its texels line up with the integer device-pixel layout.
    const surface = layout.device
      ? {
        ...layout,
        width: layout.device.width / dpr,
        height: layout.device.height / dpr
      }
      : layout;
    this._layout = surface;

    const frame = this.mirror.contentFrame;
    frame.style.left = `${layout.ax}px`;
    frame.style.top = `${layout.ay}px`;
    frame.style.width = `${layout.aw}px`;
    frame.style.height = `${layout.ah}px`;
    frame.style.zoom = '';
    frame.style.transform = '';
    frame.style.transformOrigin = '';
    this._clipAroundContent(layout);

    this._updateFilterRegion(surface);
    this._mirrorScale = this._mapScale(surface, dpr);
    this._mirrorMap = makeMirrorMap(surface, this._mirrorScale);
    this._mirrorSize = {
      width: this._mirrorMap.width,
      height: this._mirrorMap.height
    };
    this._setImage(this.feMirror, this._mirrorMap.url);
    this._updateMask(surface, filter, dpr);
    this._updateAttrs(surface, filter);

    this._mapInfo = {
      mirror: `${this._mirrorMap.width}×${this._mirrorMap.height}`,
      mask: this._maskSize ? `${this._maskSize.width}×${this._maskSize.height}` : '—'
    };
  }

  updateFilter(next, prev) {
    this._filter = next;
    if (!this._layout || !this._mirrorMap) return;

    const maskChanged = !prev ||
      next.feather !== prev.feather;

    if (maskChanged) this._updateMask(this._layout, next, this._dpr);
    this._updateAttrs(this._layout, next);
  }

  _clipAroundContent(layout) {
    const W = Math.max(0, layout.width);
    const H = Math.max(0, layout.height);
    const x = Math.max(0, Math.min(W, layout.ax));
    const y = Math.max(0, Math.min(H, layout.ay));
    const right = Math.max(x, Math.min(W, layout.ax + layout.aw));
    const bottom = Math.max(y, Math.min(H, layout.ay + layout.ah));

    // The glass's filtered backdrop is painted over the content frame as well.
    // At the frame edge that warped copy can bleed a few pixels over the live
    // DOM (for example hiding a bottom rule). Clip the glass to the four side
    // bands and leave the content rectangle to the DOM underneath.
    if (right <= x || bottom <= y) {
      this.glass.style.clipPath = '';
      return;
    }

    this.glass.style.clipPath = `path("M0 0 H${W} V${H} H0 Z M${x} ${y} V${bottom} H${right} V${y} Z")`;
  }

  _updateFilterRegion(layout) {
    this.filter.setAttribute('x', '0');
    this.filter.setAttribute('y', '0');
    this.filter.setAttribute('width', String(layout.width));
    this.filter.setAttribute('height', String(layout.height));
  }

  _updateAttrs(layout, filter) {
    const W = layout.width;
    const H = layout.height;
    for (const image of [this.feMirror, this.feMask]) {
      image.setAttribute('x', '0');
      image.setAttribute('y', '0');
      image.setAttribute('width', String(W));
      image.setAttribute('height', String(H));
      image.setAttribute('preserveAspectRatio', 'none');
    }

    this.feOffset.setAttribute('dx', this._mirrorMap.bias.toFixed(4));
    this.feOffset.setAttribute('dy', this._mirrorMap.bias.toFixed(4));
    this.feWarp.setAttribute('scale', this._mirrorMap.scale.toFixed(4));
    this.feBlur.setAttribute('stdDeviation', filter.blur.toFixed(3));
  }

  _updateMask(layout, filter, dpr) {
    const maskScale = this._maskScale(layout, dpr);
    const mask = makeMaskMap(layout, filter, maskScale);
    this._setImage(this.feMask, mask.url);
    this._maskSize = { width: mask.width, height: mask.height };
  }

  _setImage(el, url) {
    el.setAttribute('href', url);
  }

  _requestedScale(option, dpr) {
    return option === 'device' ? dpr : Number(option);
  }

  _limitedScale(requested, layout) {
    const W = Math.max(1, layout.width);
    const H = Math.max(1, layout.height);
    let scale = requested;

    // maxMR is the only map-size limit. No maxMR means no cap.
    const maxMR = this.mirror._svg.maxMR;
    if (maxMR) {
      scale = Math.min(scale, maxMR.width / W, maxMR.height / H);
    }

    return Math.max(1e-4, scale);
  }

  _mapScale(layout, dpr) {
    return this._limitedScale(
      this._requestedScale(this.mirror._svg.mapScale, dpr),
      layout
    );
  }

  _maskScale(layout, dpr) {
    return this._limitedScale(
      this._requestedScale(this.mirror._svg.maskScale, dpr),
      layout
    );
  }

  getMapInfo() {
    return this._mapInfo ? { ...this._mapInfo } : null;
  }

  getMapDetail() {
    if (!this._mirrorSize) return null;
    return {
      requestedScale: this.mirror._svg.mapScale,
      effectiveScale: this._mirrorScale,
      width: this._mirrorSize.width,
      height: this._mirrorSize.height,
      pixels: this._mirrorSize.width * this._mirrorSize.height,
      maxMR: this.mirror._svg.maxMR ? { ...this.mirror._svg.maxMR } : null
    };
  }

  destroy() {
    // Drop the current data: URLs before detaching the filter, then release
    // every map/layout reference held by this backend.
    this.feMirror?.removeAttribute('href');
    this.feMask?.removeAttribute('href');
    if (this.glass) setVendorBackdrop(this.glass, 'none');
    this.glass?.remove();
    this.svg?.remove();
    this.glass = null;
    this.svg = null;
    this.filter = null;
    this.feOffset = null;
    this.feMirror = null;
    this.feWarp = null;
    this.feBlur = null;
    this.feMask = null;
    this._layout = null;
    this._filter = null;
    this._dpr = 0;
    this._mirrorMap = null;
    this._mirrorScale = 0;
    this._mirrorSize = null;
    this._maskSize = null;
    this._mapInfo = null;
    this.mirror = null;
  }
}

/* --------------------------------------------------------------------------
   WebGL backend (three.js HTML-in-Canvas)
   ----------------------------------------------------------------------- */

const VERTEX_SHADER = `
  varying vec2 vUv;
  void main(void) {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`;

const TRANSFORMED_VERTEX_SHADER = `
  varying vec2 vUv;
  void main(void) {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;

  uniform sampler2D uHtmlTexture;
  uniform vec2 uStageSize;
  uniform vec2 uArtOrigin;
  uniform vec2 uArtSize;
  uniform float uBlurPx;
  uniform float uFeatherPx;
  uniform float uCenterHole;    // 1 when the body is composited separately

  varying vec2 vUv;

  vec4 sampleArt(vec2 artUv) {
    return texture2D(uHtmlTexture, artUv);
  }

  void main(void) {
    vec2 stage = max(uStageSize, vec2(1.0));
    vec2 artSize = max(uArtSize, vec2(0.0001));
    vec2 p = vec2(vUv.x, 1.0 - vUv.y) * stage;
    vec2 a0 = uArtOrigin;
    vec2 a1 = uArtOrigin + artSize;

    float sx = p.x < a0.x ? 2.0 * a0.x - p.x : (p.x > a1.x ? 2.0 * a1.x - p.x : p.x);
    float sy = p.y < a0.y ? 2.0 * a0.y - p.y : (p.y > a1.y ? 2.0 * a1.y - p.y : p.y);
    vec2 source = vec2(
      clamp(sx, a0.x, a1.x),
      clamp(sy, a0.y, a1.y)
    );

    float outX = max(a0.x - p.x, p.x - a1.x);
    float outY = max(a0.y - p.y, p.y - a1.y);
    float outside = max(outX, outY);

    vec2 artUv = clamp((source - a0) / artSize, 0.0, 1.0);
    vec2 artUvSample = vec2(artUv.x, 1.0 - artUv.y);
    vec4 sharp = sampleArt(artUvSample);

    vec2 stepUv = vec2(uBlurPx) / artSize;
    vec4 blurred = vec4(0.0);
    float wsum = 0.0;
    for (int y = -1; y <= 1; y++) {
      for (int x = -1; x <= 1; x++) {
        float wx = x == 0 ? 2.0 : 1.0;
        float wy = y == 0 ? 2.0 : 1.0;
        float w = wx * wy;
        blurred += sampleArt(artUvSample + vec2(float(x), float(y)) * stepUv) * w;
        wsum += w;
      }
    }
    blurred /= wsum;

    float mask = uFeatherPx <= 0.0
      ? step(0.001, outside)
      : smoothstep(0.0, max(0.001, uFeatherPx), outside);

    vec4 col = mix(sharp, blurred, clamp(mask, 0.0, 1.0));
    float insideArt =
      step(a0.x, p.x) * step(p.x, a1.x) *
      step(a0.y, p.y) * step(p.y, a1.y);
    col.a *= 1.0 - insideArt * clamp(uCenterHole, 0.0, 1.0);
    gl_FragColor = vec4(col.rgb, clamp(col.a, 0.0, 1.0));
  }
`;

const BODY_FRAGMENT_SHADER = `
  precision highp float;

  uniform sampler2D uHtmlTexture;

  varying vec2 vUv;

  void main(void) {
    vec4 col = texture2D(uHtmlTexture, vUv);
    gl_FragColor = vec4(col.rgb, clamp(col.a, 0.0, 1.0));
  }
`;

const UPSCALE_FRAGMENT_SHADER = `
  precision highp float;

  uniform sampler2D uLowRes;

  varying vec2 vUv;

  void main(void) {
    gl_FragColor = texture2D(uLowRes, vUv);
  }
`;

const BODY_OVERLAY_FRAGMENT_SHADER = `
  precision highp float;

  uniform sampler2D uBody;

  varying vec2 vUv;

  void main(void) {
    gl_FragColor = texture2D(uBody, vUv);
  }
`;

// three r186's WebGLTextures still calls texElementImage2D. Chrome 157+
// removed that convenience entry point and only exposes the spec-shaped
// texElementSubImage2D. Install a tiny adapter so the existing HTMLTexture
// path keeps working without forking three.
function installHtmlTextureCompat(gl) {
  if (!gl) return;
  if (typeof gl.texElementImage2D === 'function') return;
  if (typeof gl.texElementSubImage2D !== 'function') return;

  const upload = gl.texElementSubImage2D.bind(gl);
  gl.texElementImage2D = function (target, internalFormat, image) {
    const rect = image.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) {
      throw new Error('HTML-in-Canvas: drawable frame has no measurable box');
    }
    const canvas = gl.canvas;
    const dpr = canvas.clientWidth > 0 ? canvas.width / canvas.clientWidth : 1;
    const zoom = parseFloat(getComputedStyle(image).zoom) || 1;
    let width = Math.max(1, Math.round(rect.width * dpr * zoom));
    let height = Math.max(1, Math.round(rect.height * dpr * zoom));

    if (typeof canvas.getElementImageDefaultSize === 'function') {
      try {
        const size = canvas.getElementImageDefaultSize(image);
        width = Math.max(1, Math.round(size.width));
        height = Math.max(1, Math.round(size.height));
      } catch {
        // Fall back to the CSS box calculation above.
      }
    }

    // texElementSubImage2D is texSubImage-like: allocate storage first.
    // Chrome captures the element at its canvas position, so crop it with a
    // CSS-pixel source rect and scale it into the full texture.
    const canvasRect = canvas.getBoundingClientRect();
    const sx = rect.left - canvasRect.left;
    const sy = rect.top - canvasRect.top;
    gl.texImage2D(
      target, 0, internalFormat || gl.RGBA8,
      width, height, 0,
      gl.RGBA, gl.UNSIGNED_BYTE, null
    );
    upload(target, 0, 0, 0, image, {
      sx,
      sy,
      swidth: rect.width,
      sheight: rect.height,
      width,
      height
    });
  };
}

class WebGLBackend {
  constructor(mirror, THREE) {
    this.kind = 'webgl';
    this.mirror = mirror;
    this.THREE = THREE;
    this.canvas = null;
    this.renderer = null;
    this.texture = null;
    this.scene = null;
    this.camera = null;
    this.mesh = null;
    this.material = null;
    this.uniforms = null;
    this.target = null;
    this.bodyTarget = null;
    this.upscaleScene = null;
    this.upscaleCamera = null;
    this.upscaleMesh = null;
    this.upscaleMaterial = null;
    this.bodyScene = null;
    this.bodyMesh = null;
    this.bodyMaterial = null;
    this.bodyOverlayMesh = null;
    this.bodyOverlayMaterial = null;
    this.skirtGeometry = null;
    this.skirtMesh = null;
    this.skirtMaterial = null;
    this._layout = null;
    this._filter = mirror._filter;
    this._dpr = mirror._dpr;
    this._renderScale = 1;
    this._contentScale = 1;
    this._composite = false;
    this._outputWidth = 1;
    this._outputHeight = 1;
    this._renderWidth = 1;
    this._renderHeight = 1;
    this._contentWidth = 1;
    this._contentHeight = 1;
    this._hitRaf = 0;
    this._hitTimer = 0;
    this._paintTimer = 0;
    this._paintReady = false;
    this._mapInfo = null;
  }

  mount() {
    const m = this.mirror;
    const THREE = this.THREE;
    const canvas = document.createElement('canvas');
    canvas.className = 'mirror-canvas';
    canvas.setAttribute('layoutsubtree', '');
    canvas.setAttribute('content', 'drawable');
    applyStyles(canvas, {
      position: 'absolute',
      top: '0',
      right: '0',
      bottom: '0',
      left: '0',
      width: '100%',
      height: '100%',
      display: 'block',
      zIndex: '1'
    });
    m.root.appendChild(canvas);
    this.canvas = canvas;

    const frame = m.contentFrame;
    frame.setAttribute('drawable', '');
    frame.style.zIndex = '1';
    canvas.appendChild(frame);

    try {
      const renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        premultipliedAlpha: true,
        antialias: false,
        powerPreference: 'high-performance'
      });
      this.renderer = renderer;

      const gl = renderer.getContext();
      if (!gl ||
          (typeof gl.texElementImage2D !== 'function' &&
           typeof gl.texElementSubImage2D !== 'function')) {
        throw new Error('HTML-in-Canvas is unavailable (texElementImage2D/texElementSubImage2D missing)');
      }
      installHtmlTextureCompat(gl);
      if (typeof canvas.updateElementGeometry !== 'function') {
        throw new Error('HTML-in-Canvas hit testing is unavailable (updateElementGeometry missing)');
      }

      renderer.setPixelRatio(this._dpr);
      renderer.setSize(1, 1, false);
      renderer.setClearColor(0x000000, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;

      const texture = new THREE.HTMLTexture(frame);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.minFilter = THREE.LinearFilter;
      texture.magFilter = THREE.LinearFilter;
      texture.generateMipmaps = false;
      texture.needsUpdate = true;
      this.texture = texture;

      // The first texElementImage2D must happen after Chrome has cached a paint
      // record for the drawable child. HTMLTexture already requests a paint;
      // wrap its handler so the render loop waits for the first paint event.
      const previousPaint = canvas.onpaint;
      canvas.onpaint = (event) => {
        if (typeof previousPaint === 'function') previousPaint.call(canvas, event);
        this._paintReady = true;
      };
      if (typeof canvas.requestPaint === 'function') canvas.requestPaint();
      this._paintTimer = setTimeout(() => {
        this._paintTimer = 0;
        this._paintReady = true;
      }, 250);

      this.uniforms = {
        uHtmlTexture: { value: texture },
        uStageSize: { value: new THREE.Vector2(1, 1) },
        uArtOrigin: { value: new THREE.Vector2(0, 0) },
        uArtSize: { value: new THREE.Vector2(1, 1) },
        uBlurPx: { value: 0 },
        uFeatherPx: { value: 40 },
        uCenterHole: { value: 0 }
      };

      this.material = new THREE.ShaderMaterial({
        uniforms: this.uniforms,
        vertexShader: VERTEX_SHADER,
        fragmentShader: FRAGMENT_SHADER,
        depthTest: false,
        depthWrite: false,
        side: THREE.DoubleSide
      });

      this.scene = new THREE.Scene();
      this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
      this.mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.material);
      this.mesh.frustumCulled = false;
      this.scene.add(this.mesh);

      const target = new THREE.WebGLRenderTarget(1, 1, {
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
        format: THREE.RGBAFormat,
        type: THREE.UnsignedByteType,
        depthBuffer: false,
        stencilBuffer: false,
        generateMipmaps: false,
        colorSpace: THREE.NoColorSpace
      });
      target.texture.name = 'mirror-lowres';
      target.texture.generateMipmaps = false;
      target.texture.colorSpace = THREE.NoColorSpace;
      this.target = target;

      const bodyTarget = new THREE.WebGLRenderTarget(1, 1, {
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
        format: THREE.RGBAFormat,
        type: THREE.UnsignedByteType,
        depthBuffer: false,
        stencilBuffer: false,
        generateMipmaps: false,
        colorSpace: THREE.NoColorSpace
      });
      bodyTarget.texture.name = 'mirror-body';
      bodyTarget.texture.generateMipmaps = false;
      bodyTarget.texture.colorSpace = THREE.NoColorSpace;
      this.bodyTarget = bodyTarget;

      this.upscaleMaterial = new THREE.ShaderMaterial({
        uniforms: { uLowRes: { value: target.texture } },
        vertexShader: VERTEX_SHADER,
        fragmentShader: UPSCALE_FRAGMENT_SHADER,
        depthTest: false,
        depthWrite: false,
        side: THREE.DoubleSide
      });
      this.upscaleScene = new THREE.Scene();
      this.upscaleCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
      this.upscaleMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        this.upscaleMaterial
      );
      this.upscaleMesh.frustumCulled = false;
      this.upscaleMesh.renderOrder = 0;
      this.upscaleScene.add(this.upscaleMesh);

      this.bodyMaterial = new THREE.ShaderMaterial({
        uniforms: {
          uHtmlTexture: { value: texture }
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: BODY_FRAGMENT_SHADER,
        depthTest: false,
        depthWrite: false,
        side: THREE.DoubleSide
      });
      this.bodyScene = new THREE.Scene();
      this.bodyMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        this.bodyMaterial
      );
      this.bodyMesh.frustumCulled = false;
      this.bodyScene.add(this.bodyMesh);

      this.bodyOverlayMaterial = new THREE.ShaderMaterial({
        uniforms: { uBody: { value: bodyTarget.texture } },
        vertexShader: TRANSFORMED_VERTEX_SHADER,
        fragmentShader: BODY_OVERLAY_FRAGMENT_SHADER,
        depthTest: false,
        depthWrite: false,
        side: THREE.DoubleSide
      });
      this.bodyOverlayMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        this.bodyOverlayMaterial
      );
      this.bodyOverlayMesh.frustumCulled = false;
      this.bodyOverlayMesh.renderOrder = 1;
      this.bodyOverlayMesh.visible = false;
      this.upscaleScene.add(this.bodyOverlayMesh);

      // Full-resolution skirt around the content. Each side repeats the
      // corresponding body-texture edge over the low-res upscale seam.
      this.skirtMaterial = new THREE.ShaderMaterial({
        uniforms: { uBody: { value: bodyTarget.texture } },
        vertexShader: VERTEX_SHADER,
        fragmentShader: BODY_OVERLAY_FRAGMENT_SHADER,
        depthTest: false,
        depthWrite: false,
        transparent: true,
        side: THREE.DoubleSide
      });
      this.skirtGeometry = new THREE.BufferGeometry();
      this.skirtGeometry.setAttribute(
        'position',
        new THREE.BufferAttribute(new Float32Array(4 * 6 * 3), 3)
      );
      this.skirtGeometry.setAttribute(
        'uv',
        new THREE.BufferAttribute(new Float32Array(4 * 6 * 2), 2)
      );
      this.skirtMesh = new THREE.Mesh(this.skirtGeometry, this.skirtMaterial);
      this.skirtMesh.frustumCulled = false;
      this.skirtMesh.renderOrder = 2;
      this.skirtMesh.visible = false;
      this.upscaleScene.add(this.skirtMesh);

      renderer.setAnimationLoop(() => {
        if (!this._paintReady) return;
        try {
          if (this._composite && this.target && this.bodyTarget) {
            renderer.setRenderTarget(this.target);
            renderer.render(this.scene, this.camera);
            renderer.setRenderTarget(this.bodyTarget);
            renderer.render(this.bodyScene, this.camera);
            renderer.setRenderTarget(null);
            renderer.render(this.upscaleScene, this.upscaleCamera);
          } else {
            renderer.setRenderTarget(null);
            renderer.render(this.scene, this.camera);
          }
        } catch (error) {
          // Chrome can report "No cached paint record" if the first frame
          // races the paint. The requestPaint callback will make the next
          // frame succeed; don't surface this transient error.
          if (!this._isPaintRecordError(error)) throw error;
        } finally {
          renderer.setRenderTarget(null);
        }
      });
    } catch (error) {
      this.destroy();
      throw error;
    }
  }

  layout(layout, filter, { dpr }) {
    this._layout = { ...layout };
    this._filter = filter;
    const capped = clamp(dpr, 1, Math.max(1, finite(this.mirror._webgl.dprCap, 2)));
    this._dpr = capped;

    const frame = this.mirror.contentFrame;
    frame.style.left = '0px';
    frame.style.top = '0px';
    // Do not oversample the layout. HTMLTexture already captures at
    // devicePixelContentBox (CSS x DPR); laying the frame out larger and
    // scaling it down only adds a redundant downsample and memory cost.
    frame.style.width = `${layout.aw}px`;
    frame.style.height = `${layout.ah}px`;
    frame.style.zoom = '';
    frame.style.transformOrigin = '0 0';
    frame.style.transform = `translate(${layout.ax}px, ${layout.ay}px)`;

    // Drive the canvas by integer device pixels instead of relying on
    // three.js to floor a fractional CSS-size * pixel-ratio product.
    this._outputWidth = Math.max(1, Math.round(layout.width * capped));
    this._outputHeight = Math.max(1, Math.round(layout.height * capped));
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(this._outputWidth, this._outputHeight, false);
    this._resizeTargets();

    const u = this.uniforms;
    u.uStageSize.value.set(layout.width, layout.height);
    u.uArtOrigin.value.set(layout.ax, layout.ay);
    u.uArtSize.value.set(layout.aw, layout.ah);
    u.uBlurPx.value = filter.blur;
    u.uFeatherPx.value = filter.feather;
    u.uCenterHole.value = this._composite ? 1 : 0;

    this._updateCompositeGeometry(layout);

    this._updateInfo();
    this._syncHitSoon();
  }

  setWebglOptions() {
    if (!this.renderer) return;
    this._resizeTargets();
    this._updateInfo();
  }

  _resizeTargets() {
    const renderRequested = this.mirror._webgl.renderScale;
    const contentRequested = this.mirror._webgl.contentScale;
    const renderScale = Number.isFinite(renderRequested) && renderRequested > 0
      ? renderRequested
      : 1;
    const contentScale = Number.isFinite(contentRequested) && contentRequested > 0
      ? contentRequested
      : 1;
    this._renderScale = renderScale;
    this._contentScale = contentScale;
    this._composite = renderScale < 1 || contentScale < 1;

    this._renderWidth = Math.max(1, Math.round(this._outputWidth * renderScale));
    this._renderHeight = Math.max(1, Math.round(this._outputHeight * renderScale));
    const layout = this._layout;
    this._contentWidth = Math.max(
      1,
      Math.round((layout ? layout.aw : 1) * this._dpr * contentScale)
    );
    this._contentHeight = Math.max(
      1,
      Math.round((layout ? layout.ah : 1) * this._dpr * contentScale)
    );

    if (this.uniforms) {
      this.uniforms.uCenterHole.value = this._composite ? 1 : 0;
    }

    if (this.target) {
      // Keep GPU memory small on the direct (1× / 1×) path.
      this.target.setSize(
        this._composite ? this._renderWidth : 1,
        this._composite ? this._renderHeight : 1
      );
    }
    if (this.bodyTarget) {
      this.bodyTarget.setSize(
        this._composite ? this._contentWidth : 1,
        this._composite ? this._contentHeight : 1
      );
    }
    if (this.bodyOverlayMesh) {
      this.bodyOverlayMesh.visible = this._composite;
    }
    if (this.skirtMesh) {
      this.skirtMesh.visible = this._composite;
    }
  }

  _updateCompositeGeometry(layout) {
    if (!this.bodyOverlayMesh) return;
    const W = Math.max(1, layout.width);
    const H = Math.max(1, layout.height);
    this.bodyOverlayMesh.scale.set(layout.aw / W, layout.ah / H, 1);
    this.bodyOverlayMesh.position.set(
      ((layout.ax + layout.aw / 2) / W) * 2 - 1,
      1 - ((layout.ay + layout.ah / 2) / H) * 2,
      0
    );
    this._updateSkirtGeometry(layout);
  }

  _updateSkirtGeometry(layout) {
    if (!this.skirtGeometry) return;
    const W = Math.max(1, layout.width);
    const H = Math.max(1, layout.height);
    const pad = EDGE_SKIRT_DEVICE_PX / Math.max(1, this._dpr);
    const x0 = clamp((layout.ax / W) * 2 - 1, -1, 1);
    const x1 = clamp(((layout.ax + layout.aw) / W) * 2 - 1, -1, 1);
    const y0 = clamp(1 - ((layout.ay + layout.ah) / H) * 2, -1, 1);
    const y1 = clamp(1 - (layout.ay / H) * 2, -1, 1);
    const dx = (pad / W) * 2;
    const dy = (pad / H) * 2;
    // Stay one texel inside the captured edge. The outermost body texel can
    // be partially transparent when the content box lands on a fractional
    // device pixel; the next texel carries the stable edge colour.
    const uInset = 1.5 / Math.max(1, this._contentWidth);
    const vInset = 1.5 / Math.max(1, this._contentHeight);
    const u0 = Math.min(0.5, uInset);
    const u1 = Math.max(0.5, 1 - uInset);
    const v0 = Math.min(0.5, vInset);
    const v1 = Math.max(0.5, 1 - vInset);

    const position = this.skirtGeometry.getAttribute('position');
    const uv = this.skirtGeometry.getAttribute('uv');
    let offset = 0;

    const put = (x, y, u, v) => {
      position.array[offset * 3] = x;
      position.array[offset * 3 + 1] = y;
      position.array[offset * 3 + 2] = 0;
      uv.array[offset * 2] = u;
      uv.array[offset * 2 + 1] = v;
      offset++;
    };

    const quad = (left, right, bottom, top, uvBottomLeft, uvBottomRight, uvTopRight, uvTopLeft) => {
      put(left, bottom, uvBottomLeft[0], uvBottomLeft[1]);
      put(right, bottom, uvBottomRight[0], uvBottomRight[1]);
      put(right, top, uvTopRight[0], uvTopRight[1]);
      put(left, bottom, uvBottomLeft[0], uvBottomLeft[1]);
      put(right, top, uvTopRight[0], uvTopRight[1]);
      put(left, top, uvTopLeft[0], uvTopLeft[1]);
    };

    // Top and bottom extend through the corners. Left and right cover the
    // remaining side strips; the horizontal strips already own the corners.
    const left = Math.max(-1, x0 - dx);
    const right = Math.min(1, x1 + dx);
    quad(left, right, Math.max(-1, y0 - dy), y0, [u0, v0], [u1, v0], [u1, v0], [u0, v0]);
    quad(left, right, y1, Math.min(1, y1 + dy), [u0, v1], [u1, v1], [u1, v1], [u0, v1]);
    quad(Math.max(-1, x0 - dx), x0, y0, y1, [u0, v0], [u0, v0], [u0, v1], [u0, v1]);
    quad(x1, Math.min(1, x1 + dx), y0, y1, [u1, v0], [u1, v0], [u1, v1], [u1, v1]);

    position.needsUpdate = true;
    uv.needsUpdate = true;
  }

  _updateInfo() {
    if (!this._layout) return;
    const dpr = this._dpr;
    const textureWidth = this._layout.device
      ? this._layout.device.aw
      : Math.round(this._layout.aw * dpr);
    const textureHeight = this._layout.device
      ? this._layout.device.ah
      : Math.round(this._layout.ah * dpr);
    this._mapInfo = {
      texture: `${textureWidth}×${textureHeight}`,
      dpr,
      render: `${this._renderWidth}×${this._renderHeight}`,
      content: `${this._contentWidth}×${this._contentHeight}`,
      scale: this._renderScale,
      contentScale: this._contentScale,
      mode: this._composite ? 'composite' : 'direct',
      canvas: `${this._outputWidth}×${this._outputHeight}`,
      upscale: 'linear',
      skirt: `${EDGE_SKIRT_DEVICE_PX}px`
    };
  }

  getRenderDetail() {
    if (!this._layout) return null;
    return {
      requestedScale: this.mirror._webgl.renderScale,
      renderScale: this._renderScale,
      contentScale: this._contentScale,
      effectiveScale: this._renderWidth / this._outputWidth,
      width: this._renderWidth,
      height: this._renderHeight,
      outputWidth: this._outputWidth,
      outputHeight: this._outputHeight,
      pixels: this._renderWidth * this._renderHeight,
      outputPixels: this._outputWidth * this._outputHeight,
      contentWidth: this._contentWidth,
      contentHeight: this._contentHeight,
      contentPixels: this._contentWidth * this._contentHeight,
      upscale: 'linear',
      skirtPx: EDGE_SKIRT_DEVICE_PX,
      active: this._composite
    };
  }

  updateFilter(next, prev) {
    this._filter = next;
    if (!this.uniforms) return;
    const u = this.uniforms;
    u.uBlurPx.value = next.blur;
    u.uFeatherPx.value = next.feather;
  }

  _isPaintRecordError(error) {
    return !!error &&
      error.name === 'InvalidStateError' &&
      /paint record/i.test(error.message || '');
  }

  _syncHitSoon() {
    if (!this.canvas) return;
    if (this._hitRaf) cancelAnimationFrame(this._hitRaf);
    this._hitRaf = requestAnimationFrame(() => {
      this._hitRaf = 0;
      this._syncHit();
    });
    clearTimeout(this._hitTimer);
    this._hitTimer = setTimeout(() => {
      this._hitTimer = 0;
      this._syncHit();
    }, 140);
  }

  _syncHit() {
    if (!this.canvas || !this._layout) return;
    if (typeof this.canvas.updateElementGeometry !== 'function') return;
    const frame = this.mirror.contentFrame;
    const rect = frame.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    const layout = this._layout;
    // Chrome 157+ exposes getElementImageDefaultSize and applies the frame's
    // CSS transform to the element geometry itself. Passing the layout
    // translation a second time shifts both painting and hit testing.
    const cssDrivenGeometry = typeof this.canvas.getElementImageDefaultSize === 'function';
    const matrix = cssDrivenGeometry
      ? new DOMMatrix()
      : new DOMMatrix([
        layout.aw / rect.width, 0,
        0, layout.ah / rect.height,
        layout.ax, layout.ay
      ]);
    this.canvas.updateElementGeometry(frame, { canvasTransform: matrix });
  }

  getMapInfo() {
    return this._mapInfo ? { ...this._mapInfo } : null;
  }

  destroy() {
    if (this._hitRaf) {
      cancelAnimationFrame(this._hitRaf);
      this._hitRaf = 0;
    }
    if (this._hitTimer) {
      clearTimeout(this._hitTimer);
      this._hitTimer = 0;
    }
    if (this._paintTimer) {
      clearTimeout(this._paintTimer);
      this._paintTimer = 0;
    }
    this._paintReady = false;

    const renderer = this.renderer;
    if (renderer) {
      renderer.setAnimationLoop(null);
      try { renderer.setRenderTarget(null); } catch { /* noop */ }
      try { this.target?.dispose(); } catch { /* noop */ }
      try { this.bodyTarget?.dispose(); } catch { /* noop */ }
      try { this.texture?.dispose(); } catch { /* noop */ }
      try { this.material?.dispose(); } catch { /* noop */ }
      try { this.upscaleMaterial?.dispose(); } catch { /* noop */ }
      try { this.bodyMaterial?.dispose(); } catch { /* noop */ }
      try { this.bodyOverlayMaterial?.dispose(); } catch { /* noop */ }
      try { this.skirtMaterial?.dispose(); } catch { /* noop */ }
      try { this.mesh?.geometry?.dispose(); } catch { /* noop */ }
      try { this.upscaleMesh?.geometry?.dispose(); } catch { /* noop */ }
      try { this.bodyMesh?.geometry?.dispose(); } catch { /* noop */ }
      try { this.bodyOverlayMesh?.geometry?.dispose(); } catch { /* noop */ }
      try { this.skirtGeometry?.dispose(); } catch { /* noop */ }
      try { renderer.dispose(); } catch { /* noop */ }
    }

    const frame = this.mirror.contentFrame;
    if (frame && this.canvas && frame.parentNode === this.canvas && this.mirror.root) {
      this.mirror.root.appendChild(frame);
    }
    if (this.canvas) this.canvas.remove();

    this.canvas = null;
    this.renderer = null;
    this.texture = null;
    this.scene = null;
    this.camera = null;
    this.mesh = null;
    this.material = null;
    this.uniforms = null;
    this.target = null;
    this.bodyTarget = null;
    this.upscaleScene = null;
    this.upscaleCamera = null;
    this.upscaleMesh = null;
    this.upscaleMaterial = null;
    this.bodyScene = null;
    this.bodyMesh = null;
    this.bodyMaterial = null;
    this.bodyOverlayMesh = null;
    this.bodyOverlayMaterial = null;
    this.skirtGeometry = null;
    this.skirtMesh = null;
    this.skirtMaterial = null;
  }
}

/* --------------------------------------------------------------------------
   three loader
   ----------------------------------------------------------------------- */

async function loadThree(webglOptions) {
  const callback = typeof webglOptions.onProgress === 'function'
    ? webglOptions.onProgress
    : null;
  const started = performance.now();
  let lastLoaded = 0;
  let lastTotal = null;
  const emit = (event = {}) => {
    if (!callback) return;
    if (Number.isFinite(event.total) && event.total > 0) {
      lastTotal = event.total;
    }
    if (Number.isFinite(event.loaded) && event.loaded >= 0) {
      lastLoaded = event.loaded;
    }
    const total = lastTotal;
    const loaded = lastLoaded;
    const payload = {
      phase: event.phase || 'progress',
      source: event.source || 'import',
      url: event.url || null,
      loaded,
      total,
      ratio: total ? Math.min(1, loaded / total) : null,
      cached: !!event.cached,
      duration: performance.now() - started
    };
    if (event.error) payload.error = event.error;
    try {
      const result = callback(payload);
      if (result && typeof result.catch === 'function') result.catch(() => {});
    } catch {
      // A progress UI must never break module loading.
    }
  };

  if (webglOptions.three) {
    emit({ phase: 'start', source: 'injected' });
    emit({ phase: 'done', source: 'injected' });
    return webglOptions.three;
  }

  const url = webglOptions.threeUrl ||
    new URL('../../libs/three/vendor/three.module.js', import.meta.url).href;

  if (typeof webglOptions.threeLoader === 'function') {
    emit({ phase: 'start', source: 'custom', url });
    try {
      const three = await webglOptions.threeLoader({
        url,
        onProgress: (event) => emit({ ...event, source: 'custom', url })
      });
      emit({ phase: 'done', source: 'custom', url });
      return three;
    } catch (error) {
      emit({ phase: 'error', source: 'custom', url, error });
      throw error;
    }
  }

  const cached = threeCache.has(url);
  emit({ phase: 'start', source: 'import', url, cached });
  if (!cached) {
    const loading = import(url).catch((error) => {
      threeCache.delete(url);
      emit({ phase: 'error', source: 'import', url, error });
      throw error;
    });
    threeCache.set(url, loading);
  }

  try {
    const three = await threeCache.get(url);
    emit({ phase: 'done', source: 'import', url, cached });
    return three;
  } catch (error) {
    // The import catch above already emitted the error for the first load.
    if (cached) emit({ phase: 'error', source: 'import', url, error });
    throw error;
  }
}

/* --------------------------------------------------------------------------
   Public mirror instance
   ----------------------------------------------------------------------- */

class Mirror extends EventTarget {
  constructor(options) {
    super();
    this._options = options;
    this.container = options.container;
    this.content = options.content;
    this._requestedMode = options.mode;
    this._mode = null;
    this._fallbackReason = null;
    this._filter = options.filter;
    this._size = options.contentSize;
    this._contentFit = options.contentFit;
    this._background = options.background;
    this._svg = options.svg;
    this._webgl = options.webgl;
    this._resize = options.resize;
    this._dpr = Math.max(1, window.devicePixelRatio || 1);
    this._layout = null;
    this._suspended = false;
    this._destroyed = false;
    this._raf = 0;
    this._force = false;
    this._resizeTimer = 0;
    this._resizeActive = false;
    this._resizeStartedAt = 0;
    this._resizeLastEmitAt = 0;
    this._resizePendingForce = false;
    this._root = null;
    this._contentFrame = null;
    this._backend = null;
    this._ro = null;
    this._dprMedia = null;
    this._dprChange = null;
    this._onWindowResize = null;
    this._natural = { width: 0, height: 0 };
    this._contentStyles = null;
    this._originalParent = null;
    this._originalNext = null;
    this._containerPosition = '';
    this._containerPositionChanged = false;
    this._id = `mirror-${nextId++}`;
  }

  get mode() { return this._mode; }
  get requestedMode() { return this._requestedMode; }
  get fallbackReason() { return this._fallbackReason; }
  get root() { return this._root; }
  get contentFrame() { return this._contentFrame; }

  on(type, listener, options) {
    this.addEventListener(type, listener, options);
    return this;
  }

  off(type, listener, options) {
    this.removeEventListener(type, listener, options);
    return this;
  }

  async _init() {
    if (!this.container.isConnected) {
      // A detached container has no measurable size; it can still mount and
      // will lay out when the ResizeObserver sees it after insertion.
    }
    const content = this.content;

    const rect = content.getBoundingClientRect();
    this._natural.width = rect.width || content.offsetWidth || 0;
    this._natural.height = rect.height || content.offsetHeight || 0;
    this._contentStyles = {
      width: content.style.width,
      height: content.style.height,
      boxSizing: content.style.boxSizing
    };
    this._originalParent = content.parentNode;
    this._originalNext = content.nextSibling;

    const view = getComputedStyle(this.container);
    if (view.display === 'contents') {
      throw new Error('mirror: container must generate a box (display:contents is not supported)');
    }
    this._containerPosition = this.container.style.position;
    if (view.position === 'static') {
      this.container.style.position = 'relative';
      this._containerPositionChanged = true;
    }

    const root = document.createElement('div');
    root.className = 'mirror-root';
    root.dataset.mirrorId = this._id;
    applyStyles(root, {
      position: 'absolute',
      top: '0',
      right: '0',
      bottom: '0',
      left: '0',
      overflow: 'hidden',
      isolation: 'isolate'
    });
    if (this._background) root.style.background = this._background;

    const frame = document.createElement('div');
    frame.className = 'mirror-content';
    applyStyles(frame, {
      position: 'absolute',
      boxSizing: 'border-box',
      overflow: 'hidden',
      zIndex: '1'
    });
    frame.appendChild(content);
    root.appendChild(frame);
    this._root = root;
    this._contentFrame = frame;
    this.container.appendChild(root);

    if (this._contentFit === 'fill') {
      content.style.width = '100%';
      content.style.height = '100%';
      content.style.boxSizing = 'border-box';
    }

    try {
      this._backend = await this._createBackend(this._requestedMode);
    } catch (error) {
      if (this._requestedMode === 'webgl' && this._webgl.fallbackToSvg) {
        this._fallbackReason = error instanceof Error ? error.message : String(error);
        try {
          this._backend = await this._createBackend('svg');
          this._mode = 'svg';
        } catch (fallbackError) {
          this._restore();
          throw fallbackError;
        }
      } else {
        this._restore();
        throw error;
      }
    }

    this._mode = this._backend.kind;
    this._root.setAttribute('data-mirror-mode', this._mode);
    this._backend.updateFilter(this._filter, null);
    this._observe();
    this._watchDpr();
    this._relayout(true);
    requestAnimationFrame(() => this._relayout(true));
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => this._schedule(true)).catch(() => {});
    }
  }

  async _createBackend(mode) {
    if (mode === 'svg') {
      const backend = new SvgBackend(this);
      backend.mount();
      return backend;
    }
    const support = checkHtmlInCanvasSupport();
    if (!support.ok) {
      const details = support.errors
        .map((issue) => `${issue.code}: ${issue.message}`)
        .join(' ');
      throw new Error(`HTML-in-Canvas preflight failed: ${details}`);
    }
    const THREE = await loadThree(this._webgl);
    if (!THREE || typeof THREE.HTMLTexture !== 'function') {
      throw new Error('three.js build does not expose HTMLTexture');
    }
    const backend = new WebGLBackend(this, THREE);
    backend.mount();
    return backend;
  }

  _observe() {
    if (this._options.autoObserve && typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(() => this._requestResize());
      this._ro.observe(this.container);
    }
    this._onWindowResize = () => {
      const next = Math.max(1, window.devicePixelRatio || 1);
      if (next !== this._dpr) {
        this._dpr = next;
        if (this._dprChange) this._armDpr(this._dprChange);
        this._requestResize(true);
        return;
      }
      this._requestResize();
    };
    window.addEventListener('resize', this._onWindowResize, { passive: true });
  }

  _watchDpr() {
    this._dpr = Math.max(1, window.devicePixelRatio || 1);
    const onChange = () => {
      const next = Math.max(1, window.devicePixelRatio || 1);
      this._armDpr(onChange);
      if (next === this._dpr) return;
      this._dpr = next;
      this._requestResize(true);
    };
    this._dprChange = onChange;
    this._armDpr(onChange);
  }

  _armDpr(onChange) {
    if (this._dprMedia) {
      this._dprMedia.removeEventListener('change', onChange);
      this._dprMedia = null;
    }
    try {
      const media = matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
      media.addEventListener('change', onChange, { once: true });
      this._dprMedia = media;
    } catch {
      this._dprMedia = null;
    }
  }

  _schedule(force = false) {
    if (this._destroyed) return;
    if (force) this._force = true;
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = 0;
      const nextForce = this._force;
      this._force = false;
      this._relayout(nextForce);
    });
  }

  _resizeInfo(elapsed = 0) {
    return {
      ...this.getState(),
      width: this.container.clientWidth,
      height: this.container.clientHeight,
      dpr: this._dpr,
      interval: this._resize.interval,
      elapsed
    };
  }

  _requestResize(force = false) {
    if (this._destroyed) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    if (!force && !this._resizeActive && !this._suspended && this._layout &&
        width === this._layout.width && height === this._layout.height) {
      return;
    }

    if (force) this._resizePendingForce = true;
    const now = performance.now();
    if (!this._resizeActive) {
      this._resizeActive = true;
      this._resizeStartedAt = now;
      this._resizeLastEmitAt = now;
      this._emit('resizeStart', this._resizeInfo(0));
    } else if (now - this._resizeLastEmitAt >= this._resize.interval) {
      this._resizeLastEmitAt = now;
      this._emit('resizing', this._resizeInfo(now - this._resizeStartedAt));
    }

    if (this._destroyed) return;
    if (this._resizeTimer) clearTimeout(this._resizeTimer);
    this._resizeTimer = setTimeout(() => {
      this._resizeTimer = 0;
      this._finishResize();
    }, this._resize.interval);
  }

  _finishResize() {
    if (this._destroyed || !this._resizeActive) return;
    const force = this._resizePendingForce;
    const startedAt = this._resizeStartedAt;
    this._resizeActive = false;
    this._resizePendingForce = false;
    this._relayout(force);
    if (this._destroyed) return;
    this._emit('resizeEnd', this._resizeInfo(performance.now() - startedAt));
  }

  _relayout(force = false) {
    if (this._destroyed) return;
    const W = this.container.clientWidth;
    const H = this.container.clientHeight;
    if (!W || !H) {
      this._suspended = true;
      this._emit('resize', this.getState());
      return;
    }

    const naturalW = this._natural.width > 0 ? this._natural.width : W;
    const naturalH = this._natural.height > 0 ? this._natural.height : H;
    let aw;
    let ah;
    try {
      aw = Math.min(resolveSize(this._size.width, W, naturalW), 100_000);
      ah = Math.min(resolveSize(this._size.height, H, naturalH), 100_000);
    } catch (error) {
      this._emit('error', { error });
      return;
    }

    const next = makeLayout(W, H, aw, ah, this._dpr);
    if (!force && sameLayout(this._layout, next)) {
      this._suspended = false;
      return;
    }

    this._layout = next;
    this._suspended = false;
    try {
      this._backend.layout(next, this._filter, { dpr: this._dpr, force });
    } catch (error) {
      this._emit('error', { error });
      return;
    }
    this._emit('resize', this.getState());
  }

  setFilter(patch = {}) {
    if (this._destroyed) return this;
    const next = normalizeFilter(patch, this._filter);
    const prev = this._filter;
    if (sameFilter(prev, next)) return this;
    this._filter = next;
    this._backend?.updateFilter(next, prev);
    this._emit('filter', { filter: { ...next } });
    return this;
  }

  setSvgOptions(patch = {}) {
    if (this._destroyed) return this;
    if (!patch || typeof patch !== 'object') {
      throw new TypeError('mirror: setSvgOptions expects an object');
    }
    if (patch.maxMapPixels !== undefined) {
      throw new TypeError('mirror: svg.maxMapPixels has been removed; use maxMR');
    }
    if (patch.rippleMapScale !== undefined) {
      throw new TypeError('mirror: svg.rippleMapScale has been removed');
    }
    const next = { ...this._svg };
    if (patch.mapScale !== undefined) {
      next.mapScale = normalizeSvgScale(patch.mapScale, 'mapScale');
    }
    if (patch.maskScale !== undefined) {
      next.maskScale = normalizeSvgScale(patch.maskScale, 'maskScale');
    }
    if (patch.maxMR !== undefined) {
      next.maxMR = normalizeMaxMR(patch.maxMR);
    }
    this._svg = next;
    this._schedule(true);
    return this;
  }

  getSvgOptions() {
    return {
      ...this._svg,
      maxMR: this._svg.maxMR ? { ...this._svg.maxMR } : null
    };
  }

  setWebglOptions(patch = {}) {
    if (this._destroyed) return this;
    if (!patch || typeof patch !== 'object') {
      throw new TypeError('mirror: setWebglOptions expects an object');
    }
    const next = { ...this._webgl };
    if (patch.renderScale !== undefined) {
      next.renderScale = normalizeRenderScale(patch.renderScale);
    }
    if (patch.contentScale !== undefined) {
      next.contentScale = normalizeContentScale(patch.contentScale);
    }
    this._webgl = next;
    this._backend?.setWebglOptions?.(next);
    this._emit('render', {
      renderScale: next.renderScale,
      contentScale: next.contentScale,
      detail: this._backend?.getRenderDetail?.() || null
    });
    return this;
  }

  getWebglOptions() {
    return {
      dprCap: this._webgl.dprCap,
      renderScale: this._webgl.renderScale,
      contentScale: this._webgl.contentScale,
      fallbackToSvg: this._webgl.fallbackToSvg,
      threeUrl: this._webgl.threeUrl
    };
  }

  setContentSize(patch = {}) {
    if (this._destroyed) return this;
    if (!patch || typeof patch !== 'object') {
      throw new TypeError('mirror: setContentSize expects an object { width, height }');
    }
    if (patch.width !== undefined) validateSizeSpec(patch.width, 'width');
    if (patch.height !== undefined) validateSizeSpec(patch.height, 'height');
    if (patch.width !== undefined) this._size.width = patch.width;
    if (patch.height !== undefined) this._size.height = patch.height;
    this._schedule(true);
    return this;
  }

  refresh() {
    this._schedule(true);
    return this;
  }

  getFilter() {
    return { ...this._filter };
  }

  getState() {
    const map = this._backend?.getMapInfo?.() || null;
    const mapDetail = this._backend?.getMapDetail?.() || null;
    const renderDetail = this._backend?.getRenderDetail?.() || null;
    const layout = this._layout
      ? {
        ...this._layout,
        device: this._layout.device ? { ...this._layout.device } : null
      }
      : null;
    return {
      mode: this._mode,
      requestedMode: this._requestedMode,
      fallbackReason: this._fallbackReason,
      dpr: this._dpr,
      layout,
      filter: { ...this._filter },
      contentSize: { ...this._size },
      suspended: this._suspended,
      map,
      mapDetail,
      renderDetail
    };
  }

  destroy() {
    if (this._destroyed) return;
    this._destroyed = true;
    if (this._raf) {
      cancelAnimationFrame(this._raf);
      this._raf = 0;
    }
    if (this._resizeTimer) {
      clearTimeout(this._resizeTimer);
      this._resizeTimer = 0;
    }
    this._resizeActive = false;
    this._resizePendingForce = false;
    if (this._ro) {
      this._ro.disconnect();
      this._ro = null;
    }
    if (this._dprMedia) {
      this._dprMedia.removeEventListener('change', this._dprChange);
      this._dprMedia = null;
    }
    if (this._onWindowResize) {
      window.removeEventListener('resize', this._onWindowResize);
      this._onWindowResize = null;
    }
    this._backend?.destroy();
    this._backend = null;
    this._restore();
  }

  _restore() {
    const content = this.content;
    const frame = this._contentFrame;
    if (content && frame && frame.contains(content)) {
      const parent = this._originalParent;
      if (parent) {
        if (this._originalNext && this._originalNext.parentNode === parent) {
          parent.insertBefore(content, this._originalNext);
        } else {
          parent.appendChild(content);
        }
      }
    }

    if (content && this._contentStyles) {
      content.style.width = this._contentStyles.width;
      content.style.height = this._contentStyles.height;
      content.style.boxSizing = this._contentStyles.boxSizing;
    }
    if (this._containerPositionChanged) {
      this.container.style.position = this._containerPosition;
    }
    this._root?.remove();
    this._root = null;
    this._contentFrame = null;
  }

  _emit(type, detail) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }
}

/* --------------------------------------------------------------------------
   Public factory
   ----------------------------------------------------------------------- */

/**
 * Probe the WebGL HTML-in-Canvas path without creating a mirror.
 *
 * Feature checks are authoritative; the Chrome version check is a
 * compatibility warning by default because an older Chrome can still
 * create a mirror, but may render nested canvases incorrectly. Pass
 * `strictVersion: true` to promote a known-buggy Chrome version to a
 * fatal error.
 *
 * @param {object} [options]
 * @param {string} [options.minChromeVersion='157.0.8080.0']
 * @param {boolean} [options.requireTexImage2D=false]
 * @param {boolean} [options.requireSubImage=false]
 * @param {boolean} [options.strictVersion=false]
 * @returns {{
 *   ok: boolean,
 *   supported: boolean,
 *   compatible: boolean|null,
 *   browser: object,
 *   version: object,
 *   features: object,
 *   errors: Array<{code: string, message: string, url?: string}>,
 *   warnings: Array<{code: string, message: string, url?: string}>,
 *   summary: string
 * }}
 */
export function checkHtmlInCanvasSupport(options = {}) {
  const opts = options && typeof options === 'object' ? options : {};
  const minimum = parseVersion(
    opts.minChromeVersion === undefined ? HTML_IN_CANVAS_MIN_CHROME : opts.minChromeVersion
  );
  if (!minimum) {
    throw new TypeError('mirror: minChromeVersion must look like "157.0.8080.0"');
  }
  const requireTexImage2D = opts.requireTexImage2D === true;
  const requireSubImage = opts.requireSubImage === true;
  const strictVersion = opts.strictVersion === true;

  const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : '';
  const browserName = detectBrowser(userAgent);
  const chrome = parseChromeVersion(userAgent);
  const versionOk = chrome
    ? compareVersionParts(chrome.parts, minimum.parts) >= 0
    : null;

  const features = {
    htmlInCanvas: false,
    contentDrawable: false,
    paintEvent: false,
    requestPaint: false,
    captureElementImage: false,
    updateElementGeometry: false,
    elementImage: false,
    webgl2: false,
    texElementImage2D: false,
    texElementSubImage2D: false
  };
  const errors = [];
  const warnings = [];
  const hasDom = typeof document !== 'undefined' &&
    typeof HTMLCanvasElement !== 'undefined';

  if (!hasDom) {
    errors.push(preflightIssue(
      'environment-unavailable',
      'HTML-in-Canvas preflight requires a DOM with HTMLCanvasElement support.',
      CANVAS_DRAW_ELEMENT_FLAG
    ));
  } else {
    const probe = document.createElement('canvas');
    probe.setAttribute('content', 'drawable');
    features.contentDrawable = probe.content === 'drawable';
    features.paintEvent = 'onpaint' in probe;
    features.requestPaint = typeof probe.requestPaint === 'function';
    features.captureElementImage = typeof probe.captureElementImage === 'function';
    features.updateElementGeometry = typeof probe.updateElementGeometry === 'function';
    features.elementImage = typeof ElementImage === 'function';

    let gl = null;
    try {
      gl = probe.getContext('webgl2');
    } catch {
      gl = null;
    }
    if (gl) {
      features.webgl2 = true;
      features.texElementImage2D = typeof gl.texElementImage2D === 'function';
      features.texElementSubImage2D = typeof gl.texElementSubImage2D === 'function';
      try {
        gl.getExtension('WEBGL_lose_context')?.loseContext();
      } catch {
        // A probe context is disposable; failing to lose it is harmless.
      }
    }

    features.htmlInCanvas = features.contentDrawable &&
      features.requestPaint &&
      features.captureElementImage &&
      features.updateElementGeometry &&
      features.webgl2 &&
      (features.texElementImage2D || features.texElementSubImage2D);

    if (!features.contentDrawable) {
      errors.push(preflightIssue(
        'content-drawable-missing',
        'The canvas content="drawable" attribute is not supported. HTML-in-Canvas cannot capture the content frame without it.',
        CANVAS_DRAW_ELEMENT_FLAG
      ));
    }
    if (!features.requestPaint) {
      errors.push(preflightIssue(
        'request-paint-missing',
        'HTMLCanvasElement.requestPaint() is missing. mirror.js cannot synchronize nested-canvas updates.',
        CANVAS_DRAW_ELEMENT_FLAG
      ));
    }
    if (!features.captureElementImage) {
      errors.push(preflightIssue(
        'capture-element-image-missing',
        'HTMLCanvasElement.captureElementImage() is missing. The HTML-in-Canvas snapshot API is incomplete.',
        CANVAS_DRAW_ELEMENT_FLAG
      ));
    }
    if (!features.updateElementGeometry) {
      errors.push(preflightIssue(
        'update-element-geometry-missing',
        'HTMLCanvasElement.updateElementGeometry() is missing. HTML-in-Canvas hit testing would not work.',
        CANVAS_DRAW_ELEMENT_FLAG
      ));
    }
    if (!features.webgl2) {
      errors.push(preflightIssue(
        'webgl2-unavailable',
        'WebGL2 is unavailable. mirror.js WebGL mode requires a WebGL2 context.'
      ));
    } else {
      if (requireTexImage2D && !features.texElementImage2D) {
        errors.push(preflightIssue(
          'tex-element-image2d-missing',
          'WebGL2RenderingContext.texElementImage2D() is missing, but requireTexImage2D was set. Use texElementSubImage2D or disable requireTexImage2D.',
          CANVAS_DRAW_ELEMENT_FLAG
        ));
      }
      if (requireSubImage && !features.texElementSubImage2D) {
        errors.push(preflightIssue(
          'tex-element-subimage2d-missing',
          'WebGL2RenderingContext.texElementSubImage2D() is missing. Explicit-size capture is unavailable.',
          CANVAS_DRAW_ELEMENT_FLAG
        ));
      }
      if (!features.texElementImage2D && !features.texElementSubImage2D) {
        errors.push(preflightIssue(
          'tex-element-upload-missing',
          'Neither texElementImage2D nor texElementSubImage2D is available; HTML cannot be uploaded to a WebGL texture.',
          CANVAS_DRAW_ELEMENT_FLAG
        ));
      }
    }

    if (!features.paintEvent) {
      warnings.push(preflightIssue(
        'paint-event-missing',
        'The canvas paint event is not exposed. requestPaint() may still work, but update timing may be unreliable.',
        CANVAS_DRAW_ELEMENT_FLAG
      ));
    }
  }

  if (!chrome) {
    warnings.push(preflightIssue(
      'chrome-version-unknown',
      'Unable to detect a Chrome/Chromium version. HTML-in-Canvas nested-canvas compatibility cannot be verified.'
    ));
  } else if (versionOk === false) {
    const issue = preflightIssue(
      'chrome-nested-canvas-dpr-bug',
      `Chrome ${chrome.text} predates the nested-canvas device-pixel fix in Chrome ${minimum.text}. ` +
      'Using an incompatible Chrome version can cause unexpected visual effects: nested canvases may be ' +
      'captured at CSS resolution instead of device resolution and appear offset or scaled ' +
      '(crbug.com/540532973). Upgrade to Chrome ' + `${minimum.text} or newer to avoid this issue.`,
      CHROME_DPR_BUG_URL
    );
    if (strictVersion) errors.push(issue);
    else warnings.push(issue);
  }

  const ok = errors.length === 0;
  const summary = errors[0]?.message ||
    warnings[0]?.message ||
    'HTML-in-Canvas support is available and the Chrome version is compatible.';

  return {
    ok,
    supported: features.htmlInCanvas,
    compatible: versionOk,
    browser: {
      name: browserName,
      version: chrome ? chrome.text : null,
      major: chrome ? chrome.parts[0] : null,
      userAgent
    },
    version: {
      detected: chrome ? chrome.text : null,
      minimum: minimum.text,
      ok: versionOk,
      issue: versionOk === false ? CHROME_DPR_BUG_URL : null
    },
    features,
    errors,
    warnings,
    summary
  };
}

export async function createMirror(rawOptions) {
  const options = normalizeOptions(rawOptions);
  const mirror = new Mirror(options);
  try {
    await mirror._init();
    return mirror;
  } catch (error) {
    try { mirror.destroy(); } catch { /* noop */ }
    throw error;
  }
}

export default createMirror;
