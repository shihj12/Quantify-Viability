// Port of the pure (non-cv2) parts of qviability/core/image_io.py: display
// normalization, bit-depth/max-value helpers, the 256-bin histogram, and
// natural-sort. Arithmetic uses Math.fround at each step to reproduce numpy's
// float32 results bit-for-bit, so display and exported-PNG pixels match.

const f32 = Math.fround;

/** 8 for uint8 images, 16 otherwise. */
export function bitDepthOf(data: Uint8Array | Uint16Array): number {
  return data instanceof Uint8Array ? 8 : 16;
}

/** Upper bound for the threshold range (255 for uint8, actual max for uint16). */
export function maxValue(data: Uint8Array | Uint16Array): number {
  if (data instanceof Uint8Array) return 255;
  let m = 0;
  for (let i = 0; i < data.length; i++) if (data[i] > m) m = data[i];
  return Math.max(m, 1);
}

/** 256-bin histogram over [0, maxval+1), matching np.histogram. */
export function histogram256(
  data: Uint8Array | Uint16Array,
  maxval: number,
): Float64Array {
  const hist = new Float64Array(256);
  const span = maxval + 1;
  for (let i = 0; i < data.length; i++) {
    let idx = Math.floor((data[i] * 256) / span);
    if (idx > 255) idx = 255;
    else if (idx < 0) idx = 0;
    hist[idx]++;
  }
  return hist;
}

/** numpy.percentile with the default linear interpolation. */
export function percentile(data: Uint8Array | Uint16Array, q: number): number {
  const n = data.length;
  if (n === 0) return 0;
  const sorted = Array.from(data).sort((a, b) => a - b);
  if (n === 1) return sorted[0];
  const pos = (q / 100) * (n - 1);
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  if (lo === hi) return sorted[lo];
  const frac = pos - lo;
  return sorted[lo] + (sorted[hi] - sorted[lo]) * frac;
}

/**
 * Percentile-stretch to a float32 image in [0, 1] for viewing, using the
 * 0.5 / 99.5 percentiles (mirrors image_io.auto_stretch).
 */
export function autoStretch(data: Uint8Array | Uint16Array): Float32Array {
  let lo = percentile(data, 0.5);
  let hi = percentile(data, 99.5);
  if (hi <= lo) {
    const mm = minMax(data);
    lo = mm[0];
    hi = mm[1];
  }
  if (hi <= lo) hi = lo + 1.0;

  const loF = f32(lo);
  const denomF = f32(hi - lo);
  const out = new Float32Array(data.length);
  for (let i = 0; i < data.length; i++) {
    let v = f32(f32(f32(data[i]) - loF) / denomF);
    if (v < 0) v = 0;
    else if (v > 1) v = 1;
    out[i] = v;
  }
  return out;
}

function minMax(data: Uint8Array | Uint16Array): [number, number] {
  let mn = Infinity;
  let mx = -Infinity;
  for (let i = 0; i < data.length; i++) {
    if (data[i] < mn) mn = data[i];
    if (data[i] > mx) mx = data[i];
  }
  if (!isFinite(mn)) {
    mn = 0;
    mx = 0;
  }
  return [mn, mx];
}

/**
 * Apply brightness/contrast to an auto-stretched base, returning a uint8
 * grayscale array (one value per pixel). Mirrors image_io.apply_display.
 */
export function applyDisplay(
  base: Float32Array,
  brightness = 0.0,
  contrast = 1.0,
): Uint8Array {
  const b = f32(brightness);
  const c = f32(contrast);
  const out = new Uint8Array(base.length);
  for (let i = 0; i < base.length; i++) {
    let v = f32(f32(base[i]) - 0.5);
    v = f32(v * c);
    v = f32(v + 0.5);
    v = f32(v + b);
    if (v < 0) v = 0;
    else if (v > 1) v = 1;
    out[i] = Math.floor(f32(v * 255.0));
  }
  return out;
}

/**
 * Linear map of raw pixel values to a uint8 grayscale array — the unprocessed
 * preview (mirrors image_io.raw_display). No stretch, no gamma.
 */
export function rawDisplay(
  data: Uint8Array | Uint16Array,
  maxval: number,
): Uint8Array {
  if (data instanceof Uint8Array) return data.slice();
  const out = new Uint8Array(data.length);
  const denom = Math.max(1, maxval);
  for (let i = 0; i < data.length; i++) {
    let v = (data[i] / denom) * 255.0;
    if (v < 0) v = 0;
    else if (v > 255) v = 255;
    out[i] = v | 0;
  }
  return out;
}

// --- natural sort (port of image_io._natural_key) -------------------------
type Token = number | string;

export function naturalKey(name: string): Token[] {
  const parts = name.split(/(\d+)/);
  const tokens: Token[] = [];
  for (const t of parts) {
    if (t === "") continue;
    if (/^\d+$/.test(t)) tokens.push(parseInt(t, 10));
    else tokens.push(t.toLowerCase());
  }
  return tokens;
}

export function compareNatural(a: string, b: string): number {
  const ka = naturalKey(a);
  const kb = naturalKey(b);
  const n = Math.min(ka.length, kb.length);
  for (let i = 0; i < n; i++) {
    const x = ka[i];
    const y = kb[i];
    if (typeof x === "number" && typeof y === "number") {
      if (x !== y) return x - y;
    } else {
      const xs = String(x);
      const ys = String(y);
      if (xs !== ys) return xs < ys ? -1 : 1;
    }
  }
  return ka.length - kb.length;
}
