// 1:1 port of qviability/core/measure.py.
//
// All math runs on the raw pixel array. `positive` pixels are those at or above
// the threshold (raw >= threshold) — matching ImageJ's "dark" auto-threshold.
// Exclusion boxes remove pixels from BOTH the positive count and the total, so
// they never affect any measurement.

import type { Measurement, Rect } from "./types";

// Overlay tint per channel (R, G, B), drawn translucently over positive pixels.
export const OVERLAY_COLORS: Record<string, [number, number, number]> = {
  Green: [40, 255, 70],
  Red: [255, 40, 220],
};
export const OVERLAY_ALPHA = 115; // ~45% opacity
export const EXCLUDE_RGBA: [number, number, number, number] = [140, 140, 140, 160];
export const OUTLINE_RGBA: [number, number, number, number] = [255, 230, 0, 255];

export type Mask = Uint8Array; // 1 = set, 0 = clear

/** Boolean (0/1) mask of positive (>= threshold) pixels. */
export function applyThreshold(
  raw: Uint8Array | Uint16Array,
  threshold: number,
): Mask {
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw[i] >= threshold ? 1 : 0;
  return out;
}

/**
 * Build a mask (1 = excluded) from a list of [x, y, w, h] rects.
 * Returns null when there are no exclusions so callers can keep a fast path.
 * Rectangles are clamped to the image bounds.
 */
export function exclusionMask(
  width: number,
  height: number,
  exclusions: Rect[],
): Mask | null {
  if (!exclusions || exclusions.length === 0) return null;
  const mask = new Uint8Array(width * height);
  for (const rect of exclusions) {
    const x = Math.round(rect[0]);
    const y = Math.round(rect[1]);
    const rw = Math.round(rect[2]);
    const rh = Math.round(rect[3]);
    const x0 = Math.max(0, x);
    const y0 = Math.max(0, y);
    const x1 = Math.min(width, x + rw);
    const y1 = Math.min(height, y + rh);
    for (let yy = y0; yy < y1; yy++) {
      const row = yy * width;
      for (let xx = x0; xx < x1; xx++) mask[row + xx] = 1;
    }
  }
  return mask;
}

/**
 * Measure the positive region of `raw` at `threshold`.
 * Pixels under `excludeMask` are dropped from both the positive count and the
 * total, so the percentage stays correct.
 */
export function measure(
  raw: Uint8Array | Uint16Array,
  threshold: number,
  method = "Manual",
  excludeMask: Mask | null = null,
): Measurement {
  let count = 0;
  let total: number;
  let sum = 0;

  if (excludeMask) {
    let valid = 0;
    for (let i = 0; i < raw.length; i++) {
      if (excludeMask[i]) continue;
      valid++;
      if (raw[i] >= threshold) {
        count++;
        sum += raw[i];
      }
    }
    total = valid;
  } else {
    total = raw.length;
    for (let i = 0; i < raw.length; i++) {
      if (raw[i] >= threshold) {
        count++;
        sum += raw[i];
      }
    }
  }

  const mean_intensity = count > 0 ? sum / count : 0.0;
  const integrated = count > 0 ? sum : 0.0;

  return {
    threshold: Math.trunc(threshold),
    positive_pixels: count,
    total_pixels: total,
    positive_area_pct: total ? (count / total) * 100.0 : 0.0,
    mean_intensity_positive: mean_intensity,
    integrated_intensity: integrated,
    method,
  };
}

/** Bool ring just outside `mask` — its dilation minus itself (display only). */
export function outlineMask(
  positive: Mask,
  width: number,
  height: number,
  thickness = 2,
): Mask {
  // cv2.getStructuringElement(MORPH_ELLIPSE, (3,3)) is the 4-connected cross;
  // dilating `thickness` times grows a diamond of that radius.
  let cur = positive;
  for (let it = 0; it < thickness; it++) {
    const next = new Uint8Array(width * height);
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const i = y * width + x;
        if (
          cur[i] ||
          (x > 0 && cur[i - 1]) ||
          (x < width - 1 && cur[i + 1]) ||
          (y > 0 && cur[i - width]) ||
          (y < height - 1 && cur[i + width])
        ) {
          next[i] = 1;
        }
      }
    }
    cur = next;
  }
  const ring = new Uint8Array(width * height);
  for (let i = 0; i < ring.length; i++) ring[i] = cur[i] && !positive[i] ? 1 : 0;
  return ring;
}

/**
 * Build an HxWx4 uint8 RGBA overlay (row-major, RGBA per pixel).
 * Positive pixels get the channel tint; excluded pixels get a gray fill.
 */
export function overlayRgba(
  positive: Mask,
  width: number,
  height: number,
  channel: string,
  excludeMask: Mask | null = null,
  outline = false,
): Uint8ClampedArray {
  const color = OVERLAY_COLORS[channel] ?? OVERLAY_COLORS.Green;
  const rgba = new Uint8ClampedArray(width * height * 4);

  const counted = new Uint8Array(width * height);
  for (let i = 0; i < counted.length; i++) {
    counted[i] = positive[i] && !(excludeMask && excludeMask[i]) ? 1 : 0;
  }

  for (let i = 0; i < counted.length; i++) {
    if (counted[i]) {
      const o = i * 4;
      rgba[o] = color[0];
      rgba[o + 1] = color[1];
      rgba[o + 2] = color[2];
      rgba[o + 3] = OVERLAY_ALPHA;
    }
  }

  if (outline) {
    const ring = outlineMask(counted, width, height);
    for (let i = 0; i < ring.length; i++) {
      if (ring[i]) {
        const o = i * 4;
        rgba[o] = OUTLINE_RGBA[0];
        rgba[o + 1] = OUTLINE_RGBA[1];
        rgba[o + 2] = OUTLINE_RGBA[2];
        rgba[o + 3] = OUTLINE_RGBA[3];
      }
    }
  }

  if (excludeMask) {
    for (let i = 0; i < excludeMask.length; i++) {
      if (excludeMask[i]) {
        const o = i * 4;
        rgba[o] = EXCLUDE_RGBA[0];
        rgba[o + 1] = EXCLUDE_RGBA[1];
        rgba[o + 2] = EXCLUDE_RGBA[2];
        rgba[o + 3] = EXCLUDE_RGBA[3];
      }
    }
  }

  return rgba;
}
