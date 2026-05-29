// Pixel-buffer builders for the threshold screen's Canvas2D layers.
//
// The base layer is the grayscale display image expanded to opaque RGBA. The
// overlay layer is the translucent positive-pixel tint (channel colour),
// exclusion fill, and optional highlight ring — built straight-alpha so the
// browser composites it over the base. Exports use the explicit float blend in
// export/annotate.ts instead and must not rely on this straight-alpha overlay.

import {
  OVERLAY_COLORS,
  OVERLAY_ALPHA,
  EXCLUDE_RGBA,
  OUTLINE_RGBA,
  outlineMask,
  type Mask,
} from "@/core/measure";

/** Expand a grayscale uint8 array (one value per pixel) into opaque RGBA. */
export function grayToRgba(
  gray: Uint8Array,
  out: Uint8ClampedArray,
): Uint8ClampedArray {
  for (let i = 0, o = 0; i < gray.length; i++, o += 4) {
    const v = gray[i];
    out[o] = v;
    out[o + 1] = v;
    out[o + 2] = v;
    out[o + 3] = 255;
  }
  return out;
}

/**
 * Fill `out` (length w*h*4, reused across ticks) with the overlay for `proc`
 * thresholded at `threshold`. One O(N) pass for the common no-outline case:
 * positive & not-excluded pixels get the channel tint, excluded pixels get the
 * gray fill. The optional highlight ring needs an extra dilation pass.
 */
export function fillOverlay(
  out: Uint8ClampedArray,
  proc: Uint8Array | Uint16Array,
  threshold: number,
  width: number,
  height: number,
  channel: string,
  excludeMask: Mask | null,
  outline: boolean,
): void {
  out.fill(0);
  const color = OVERLAY_COLORS[channel] ?? OVERLAY_COLORS.Green;
  const c0 = color[0];
  const c1 = color[1];
  const c2 = color[2];
  const n = proc.length;

  for (let i = 0, o = 0; i < n; i++, o += 4) {
    if (proc[i] >= threshold && !(excludeMask && excludeMask[i])) {
      out[o] = c0;
      out[o + 1] = c1;
      out[o + 2] = c2;
      out[o + 3] = OVERLAY_ALPHA;
    }
  }

  if (outline) {
    const counted: Mask = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      counted[i] =
        proc[i] >= threshold && !(excludeMask && excludeMask[i]) ? 1 : 0;
    }
    const ring = outlineMask(counted, width, height);
    for (let i = 0, o = 0; i < n; i++, o += 4) {
      if (ring[i]) {
        out[o] = OUTLINE_RGBA[0];
        out[o + 1] = OUTLINE_RGBA[1];
        out[o + 2] = OUTLINE_RGBA[2];
        out[o + 3] = OUTLINE_RGBA[3];
      }
    }
  }

  if (excludeMask) {
    for (let i = 0, o = 0; i < n; i++, o += 4) {
      if (excludeMask[i]) {
        out[o] = EXCLUDE_RGBA[0];
        out[o + 1] = EXCLUDE_RGBA[1];
        out[o + 2] = EXCLUDE_RGBA[2];
        out[o + 3] = EXCLUDE_RGBA[3];
      }
    }
  }
}
