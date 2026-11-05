/**
 * fade.js — per-element enter/exit fades.
 *
 * Mark elements with `data-fade`. Optional `data-fade-in-delay` and
 * `data-fade-out-delay` values are milliseconds. Web Animations handles the
 * sequencing so every element can have its own delay while the caller waits
 * for the whole group to finish.
 */

export const FADE_DEFAULTS = Object.freeze({
  duration: 220,
  selector: '[data-fade]',
  easing: 'ease'
});

const FADE_ID = 'mirror-fade';

function toMilliseconds(value, fallback = 0) {
  const number = Number.parseFloat(value);
  return Number.isFinite(number) && number >= 0 ? number : fallback;
}

function getItems(root, selector) {
  if (!root || typeof root.querySelectorAll !== 'function') return [];
  return [...root.querySelectorAll(selector)];
}

function cancelAnimations(element) {
  for (const animation of element.getAnimations()) {
    if (animation.id === FADE_ID) animation.cancel();
  }
}

function delayFor(element, kind) {
  return toMilliseconds(
    kind === 'in'
      ? element.dataset.fadeInDelay
      : element.dataset.fadeOutDelay,
    0
  );
}

function animateGroup(root, direction, options) {
  const duration = Number.isFinite(Number(options.duration))
    ? Math.max(0, Number(options.duration))
    : FADE_DEFAULTS.duration;
  const easing = options.easing || FADE_DEFAULTS.easing;
  const selector = options.selector || FADE_DEFAULTS.selector;
  const reducedMotion = options.reducedMotion === true;

  if (reducedMotion) {
    for (const element of getItems(root, selector)) {
      cancelAnimations(element);
      element.style.opacity = direction === 'out' ? '0' : '';
    }
    return Promise.resolve({ count: 0, duration: 0, maxDelay: 0, total: 0 });
  }

  const items = getItems(root, selector);
  const waits = [];
  let maxDelay = 0;

  for (const element of items) {
    cancelAnimations(element);
    if (direction === 'in') element.style.opacity = '';

    const delay = delayFor(element, direction === 'in' ? 'in' : 'out');
    maxDelay = Math.max(maxDelay, delay);
    const from = direction === 'out'
      ? Number.parseFloat(getComputedStyle(element).opacity) || 0
      : 0;
    const to = direction === 'out' ? 0 : 1;
    const animation = element.animate(
      [{ opacity: from }, { opacity: to }],
      {
        duration,
        delay,
        easing,
        fill: direction === 'out' ? 'forwards' : 'backwards'
      }
    );
    animation.id = FADE_ID;
    waits.push(animation.finished.catch(() => {}));
  }

  return Promise.all(waits).then(() => {
    if (direction === 'in') {
      for (const element of items) cancelAnimations(element);
    }
    return {
      count: items.length,
      duration,
      maxDelay,
      total: items.length ? duration + maxDelay : 0
    };
  });
}

export function fadeIn(root, options = {}) {
  return animateGroup(root, 'in', options);
}

export function fadeOut(root, options = {}) {
  return animateGroup(root, 'out', options);
}

export function resetFade(root, options = {}) {
  const selector = options.selector || FADE_DEFAULTS.selector;
  for (const element of getItems(root, selector)) {
    cancelAnimations(element);
    element.style.opacity = '';
  }
}
