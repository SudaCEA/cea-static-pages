/**
 * Loads three.bundle.js as bytes, reports real download progress, then imports
 * the bytes as a Blob module. The bundle must be a single self-contained ESM
 * build of three; mirror.js is deliberately kept out of it.
 */

const DEFAULT_URL = new URL('./three.bundle.js', import.meta.url).href;

let cachedModule = null;
let pending = null;
let lastLoaded = 0;
let lastTotal = null;
const listeners = new Set();

function emit(event, started = 0) {
  lastLoaded = Number.isFinite(event.loaded) ? event.loaded : lastLoaded;
  lastTotal = Number.isFinite(event.total) && event.total > 0
    ? event.total
    : event.total === null
      ? null
      : lastTotal;
  const payload = {
    phase: event.phase,
    source: 'bundle',
    url: event.url || DEFAULT_URL,
    loaded: lastLoaded,
    total: lastTotal,
    ratio: lastTotal ? Math.min(1, lastLoaded / lastTotal) : null,
    cached: !!event.cached,
    duration: started ? performance.now() - started : 0
  };
  if (event.error) payload.error = event.error;
  for (const listener of listeners) {
    try {
      const result = listener(payload);
      if (result && typeof result.catch === 'function') result.catch(() => {});
    } catch {
      // Progress UI must not break the loader.
    }
  }
}

async function fetchAndImport(url) {
  const started = performance.now();
  let loaded = 0;
  let total = null;

  emit({ phase: 'start', url, loaded, total: null, cached: false }, started);

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`three-bundle: HTTP ${response.status} for ${url}`);
    }

    // Content-Length describes the compressed body when content-encoding is
    // present; the stream bytes are decompressed, so don't fake a ratio.
    const encoding = response.headers.get('content-encoding');
    if (!encoding || encoding === 'identity') {
      const header = Number(response.headers.get('content-length'));
      if (Number.isFinite(header) && header > 0) {
        total = header;
        emit({ phase: 'progress', url, loaded: 0, total }, started);
      }
    }

    const chunks = [];
    if (response.body && typeof response.body.getReader === 'function') {
      const reader = response.body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        loaded += value.byteLength;
        emit({ phase: 'progress', url, loaded, total }, started);
      }
    } else {
      const buffer = await response.arrayBuffer();
      const bytes = new Uint8Array(buffer);
      chunks.push(bytes);
      loaded = bytes.byteLength;
      emit({ phase: 'progress', url, loaded, total }, started);
    }

    const blob = new Blob(chunks, { type: 'text/javascript' });
    const objectUrl = URL.createObjectURL(blob);
    try {
      const module = await import(objectUrl);
      emit({ phase: 'done', url, loaded, total, cached: false }, started);
      return module;
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  } catch (error) {
    emit({ phase: 'error', url, loaded, total, error, cached: false }, started);
    throw error;
  }
}

export async function loadThreeBundle({ url = DEFAULT_URL, onProgress } = {}) {
  const listener = typeof onProgress === 'function' ? onProgress : null;
  if (listener) listeners.add(listener);

  try {
    if (cachedModule) {
      emit({ phase: 'start', url, loaded: lastLoaded, total: lastTotal, cached: true });
      emit({ phase: 'done', url, loaded: lastLoaded, total: lastTotal, cached: true });
      return cachedModule;
    }

    if (!pending) {
      pending = fetchAndImport(url)
        .then((module) => {
          cachedModule = module;
          return module;
        })
        .finally(() => {
          pending = null;
        });
    }
    return await pending;
  } finally {
    if (listener) listeners.delete(listener);
  }
}

export { DEFAULT_URL };
