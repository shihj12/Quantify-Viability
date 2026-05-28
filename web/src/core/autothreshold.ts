// Port of qviability/core/autothreshold.py.
//
// MaxEntropy (Kapur) is the default, ported exactly from the in-repo numpy.
// Otsu / Yen / Li / IsoData reproduce scikit-image's threshold_* on the
// per-integer-value histogram (min..max) it uses for integer images. The
// dispatcher applies the same round()+clamp the Python wrapper does.

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

// --- MaxEntropy / Kapur (exact) -------------------------------------------
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

export function thresholdMaxEntropy(
  data: Uint8Array | Uint16Array,
  maxval: number,
): number {
  const hist = histogram256(data, maxval);
  const tBin = kapurThreshold(hist);
  const raw = ((tBin + 1) / 256.0) * (maxval + 1);
  return Math.min(pyRound(raw), maxval);
}

// --- scikit-image per-integer-value histogram -----------------------------
interface IntHist {
  min: number; // bin_centers[0]
  counts: Float64Array; // counts[i] for value (min + i)
}

function integerHistogram(data: Uint8Array | Uint16Array): IntHist {
  let mn = Infinity;
  let mx = -Infinity;
  for (let i = 0; i < data.length; i++) {
    const v = data[i];
    if (v < mn) mn = v;
    if (v > mx) mx = v;
  }
  if (!isFinite(mn)) return { min: 0, counts: new Float64Array(1) };
  const counts = new Float64Array(mx - mn + 1);
  for (let i = 0; i < data.length; i++) counts[data[i] - mn]++;
  return { min: mn, counts };
}

/** scikit-image threshold_otsu on the integer histogram. */
export function otsu(data: Uint8Array | Uint16Array): number {
  const { min, counts } = integerHistogram(data);
  const n = counts.length;
  if (n === 1) return min;

  const w1 = new Float64Array(n);
  const cumIC = new Float64Array(n);
  let aw = 0;
  let ai = 0;
  for (let i = 0; i < n; i++) {
    aw += counts[i];
    w1[i] = aw;
    ai += counts[i] * (min + i);
    cumIC[i] = ai;
  }
  const totalW = w1[n - 1];
  const totalIC = cumIC[n - 1];

  let best = -1;
  let bestIdx = 0;
  for (let i = 0; i < n - 1; i++) {
    const wB = w1[i];
    const wF = totalW - wB;
    if (wF <= 0) break;
    const mB = cumIC[i] / wB;
    const mF = (totalIC - cumIC[i]) / wF;
    const d = mB - mF;
    const v = wB * wF * d * d;
    if (v > best) {
      best = v;
      bestIdx = i;
    }
  }
  return min + bestIdx;
}

/** scikit-image threshold_yen on the integer histogram. */
export function yen(data: Uint8Array | Uint16Array): number {
  const { min, counts } = integerHistogram(data);
  const n = counts.length;
  if (n === 1) return min;

  let total = 0;
  for (let i = 0; i < n; i++) total += counts[i];
  const pmf = new Float64Array(n);
  for (let i = 0; i < n; i++) pmf[i] = counts[i] / total;

  const P1 = new Float64Array(n);
  const P1sq = new Float64Array(n);
  const P2sq = new Float64Array(n);
  let a = 0;
  let b = 0;
  for (let i = 0; i < n; i++) {
    a += pmf[i];
    P1[i] = a;
    b += pmf[i] * pmf[i];
    P1sq[i] = b;
  }
  let c = 0;
  for (let i = n - 1; i >= 0; i--) {
    c += pmf[i] * pmf[i];
    P2sq[i] = c;
  }

  let best = -Infinity;
  let idx = 0;
  for (let i = 0; i < n - 1; i++) {
    const denom = P1sq[i] * P2sq[i + 1];
    if (denom <= 0) continue;
    const t = P1[i] * (1.0 - P1[i]);
    const crit = Math.log((t * t) / denom);
    if (crit > best) {
      best = crit;
      idx = i;
    }
  }
  return min + idx;
}

/** scikit-image threshold_isodata on the integer histogram (first threshold). */
export function isodata(data: Uint8Array | Uint16Array): number {
  const { min, counts } = integerHistogram(data);
  const n = counts.length;
  if (n === 1) return min;

  const csuml = new Float64Array(n);
  const csumI = new Float64Array(n);
  let a = 0;
  let b = 0;
  for (let i = 0; i < n; i++) {
    a += counts[i];
    csuml[i] = a;
    b += counts[i] * (min + i);
    csumI[i] = b;
  }
  const totalCount = csuml[n - 1];
  const totalI = csumI[n - 1];

  for (let i = 0; i < n - 1; i++) {
    const csl = csuml[i];
    const csh = totalCount - csl;
    const lower = csumI[i] / csl;
    const higher = (totalI - csumI[i]) / csh;
    const allMean = (lower + higher) / 2.0;
    const dist = allMean - (min + i);
    if (dist >= 0 && dist < 1) return min + i; // bin width = 1 for integers
  }
  return min;
}

/** scikit-image threshold_li (iterative min cross-entropy) on integer images. */
export function li(data: Uint8Array | Uint16Array): number {
  const { min, counts } = integerHistogram(data);
  const n = counts.length;
  if (n === 1) return min;

  let total = 0;
  let wsum = 0;
  for (let i = 0; i < n; i++) {
    total += counts[i];
    wsum += counts[i] * i; // shifted centers: value - min
  }
  const tol = 0.5;
  let tNext = wsum / total; // mean of shifted image
  let tCurr = -2 * tol;

  while (Math.abs(tNext - tCurr) > tol) {
    tCurr = tNext;
    let cntF = 0;
    let sumF = 0;
    let cntB = 0;
    let sumB = 0;
    for (let i = 0; i < n; i++) {
      if (i > tCurr) {
        cntF += counts[i];
        sumF += counts[i] * i;
      } else {
        cntB += counts[i];
        sumB += counts[i] * i;
      }
    }
    const meanFore = cntF > 0 ? sumF / cntF : 0;
    const meanBack = cntB > 0 ? sumB / cntB : 0;
    if (meanBack === 0) break;
    tNext =
      (meanBack - meanFore) / (Math.log(meanBack) - Math.log(meanFore));
  }
  return tNext + min;
}

/**
 * Compute an auto-threshold for `data` using `method`. Returns a sensible int
 * in [0, maxval]; falls back to the mean on failure (matches the Python wrapper).
 */
export function autoThreshold(
  data: Uint8Array | Uint16Array,
  maxval: number,
  method = "MaxEntropy",
): number {
  try {
    if (method === "MaxEntropy") return thresholdMaxEntropy(data, maxval);
    let value: number;
    if (method === "Otsu") value = otsu(data);
    else if (method === "Yen") value = yen(data);
    else if (method === "Li") value = li(data);
    else if (method === "IsoData") value = isodata(data);
    else return thresholdMaxEntropy(data, maxval);
    return Math.min(Math.max(pyRound(value), 0), maxval);
  } catch {
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i];
    const mean = data.length ? sum / data.length : 0;
    return Math.min(Math.max(pyRound(mean), 0), maxval);
  }
}
