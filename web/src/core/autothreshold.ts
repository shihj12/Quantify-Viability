// Port of qviability/core/autothreshold.py.
//
// MaxEntropy (Kapur) is the default and is ported here exactly. Otsu is a
// first-cut over the 0..maxval histogram. Yen / Li / IsoData (currently from
// scikit-image) and exact-skimage Otsu parity are Phase 3 — until then the
// dispatcher falls back to the mean for those, matching the Python except path.

import { histogram256 } from "./imageIo";

export const METHOD_NAMES = ["MaxEntropy", "Otsu", "Yen", "Li", "IsoData"];

/** Python's round() — round half to even. */
function pyRound(x: number): number {
  const fl = Math.floor(x);
  const diff = x - fl;
  if (diff < 0.5) return fl;
  if (diff > 0.5) return fl + 1;
  return fl % 2 === 0 ? fl : fl + 1;
}

/**
 * Kapur maximum-entropy threshold over a 256-bin histogram. Returns the bin
 * index maximizing the sum of background and foreground Shannon entropies.
 */
export function kapurThreshold(hist: Float64Array): number {
  let total = 0;
  for (let i = 0; i < 256; i++) total += hist[i];
  if (total <= 0) return 0;

  const p = new Float64Array(256);
  for (let i = 0; i < 256; i++) p[i] = hist[i] / total;

  const cumP = new Float64Array(256);
  const cumPlogp = new Float64Array(256);
  let accP = 0;
  let accPlogp = 0;
  for (let i = 0; i < 256; i++) {
    accP += p[i];
    cumP[i] = accP;
    accPlogp += p[i] > 0 ? p[i] * Math.log(p[i]) : 0;
    cumPlogp[i] = accPlogp;
  }
  const totalPlogp = cumPlogp[255];

  let bestT = 0;
  let bestVal = -Infinity;
  for (let t = 0; t < 256; t++) {
    const p1 = cumP[t];
    const p2 = 1.0 - p1;
    if (p1 < 1e-12 || p2 < 1e-12) continue;
    const hBack = Math.log(p1) - cumPlogp[t] / p1;
    const hFore = Math.log(p2) - (totalPlogp - cumPlogp[t]) / p2;
    const val = hBack + hFore;
    if (val > bestVal) {
      bestVal = val;
      bestT = t;
    }
  }
  return bestT;
}

/** MaxEntropy threshold for `data`, as a raw pixel value in [0, maxval]. */
export function thresholdMaxEntropy(
  data: Uint8Array | Uint16Array,
  maxval: number,
): number {
  const hist = histogram256(data, maxval);
  const tBin = kapurThreshold(hist);
  const raw = ((tBin + 1) / 256.0) * (maxval + 1);
  return Math.min(pyRound(raw), maxval);
}

/** First-cut Otsu over the 0..maxval 256-bin histogram (exact parity: Phase 3). */
export function otsu(data: Uint8Array | Uint16Array, maxval: number): number {
  const hist = histogram256(data, maxval);
  let total = 0;
  let sum = 0;
  for (let i = 0; i < 256; i++) {
    total += hist[i];
    sum += i * hist[i];
  }
  if (total === 0) return 0;

  let sumB = 0;
  let wB = 0;
  let bestVar = -1;
  let bestBin = 0;
  for (let t = 0; t < 256; t++) {
    wB += hist[t];
    if (wB === 0) continue;
    const wF = total - wB;
    if (wF === 0) break;
    sumB += t * hist[t];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    const between = wB * wF * (mB - mF) * (mB - mF);
    if (between > bestVar) {
      bestVar = between;
      bestBin = t;
    }
  }
  // Map bin back to a raw value in [0, maxval].
  const raw = (bestBin / 255.0) * maxval;
  return Math.min(pyRound(raw), maxval);
}

/**
 * Compute an auto-threshold for `data` using `method`. Always returns a
 * sensible int in [0, maxval]; falls back to the mean for not-yet-ported
 * methods or on failure.
 */
export function autoThreshold(
  data: Uint8Array | Uint16Array,
  maxval: number,
  method = "MaxEntropy",
): number {
  try {
    if (method === "MaxEntropy") return thresholdMaxEntropy(data, maxval);
    if (method === "Otsu") return otsu(data, maxval);
    // Yen / Li / IsoData: Phase 3.
    throw new Error(`method not yet ported: ${method}`);
  } catch {
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    const mean = data.length ? sum / data.length : 0;
    return Math.min(Math.max(pyRound(mean), 0), maxval);
  }
}
