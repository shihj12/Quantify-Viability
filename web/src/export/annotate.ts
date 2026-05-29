// Annotated-image rendering — 1:1 port of qviability/export/annotate.py.
//
// IMPORTANT: the positive-pixel tint and exclusion fill use the EXPLICIT float
// blend  chan*(1-a) + colour*a  (a = alpha/255), exactly as the desktop does.
// We do NOT lean on the canvas straight-alpha compositor here, so exported PNGs
// and the review thumbnails match the desktop byte-for-byte.

import { autoStretch, applyDisplay } from "@/core/imageIo";
import {
  OVERLAY_COLORS,
  OVERLAY_ALPHA,
  EXCLUDE_RGBA,
  exclusionMask,
} from "@/core/measure";
import { toImageData } from "@/render/imageData";
import type { RawImage, Rect } from "@/core/types";

const f32 = Math.fround;

export interface RgbImage {
  data: Uint8ClampedArray; // RGBA, row-major
  width: number;
  height: number;
}

/** The plain display view as RGBA (grayscale, opaque) — the QC "before" image. */
export function renderDisplayRgb(
  raw: RawImage,
  brightness = 0.0,
  contrast = 1.0,
): RgbImage {
  const base = autoStretch(raw.data);
  const disp = applyDisplay(base, brightness, contrast);
  const out = new Uint8ClampedArray(raw.width * raw.height * 4);
  for (let i = 0, o = 0; i < disp.length; i++, o += 4) {
    const v = disp[i];
    out[o] = v;
    out[o + 1] = v;
    out[o + 2] = v;
    out[o + 3] = 255;
  }
  return { data: out, width: raw.width, height: raw.height };
}

function blend(
  rgba: Uint8ClampedArray,
  o: number,
  color: readonly [number, number, number] | readonly number[],
  alpha: number,
): void {
  // Match annotate.py exactly: blend in float32, then astype(uint8) which
  // TRUNCATES toward zero (np, not canvas rounding). Pre-flooring an in-range
  // value means the Uint8ClampedArray store is a no-op, so the byte is exact.
  const ia = 1.0 - alpha;
  rgba[o] = Math.floor(f32(rgba[o] * ia + color[0] * alpha));
  rgba[o + 1] = Math.floor(f32(rgba[o + 1] * ia + color[1] * alpha));
  rgba[o + 2] = Math.floor(f32(rgba[o + 2] * ia + color[2] * alpha));
}

/**
 * The display view with positive pixels tinted and exclusion boxes filled gray,
 * via the float blend. Mirrors annotate.render_overlay_rgb.
 */
export function renderOverlayRgb(
  raw: RawImage,
  threshold: number,
  channel: string,
  brightness = 0.0,
  contrast = 1.0,
  exclusions: Rect[] = [],
): RgbImage {
  const img = renderDisplayRgb(raw, brightness, contrast);
  const rgba = img.data;
  const excl = exclusionMask(raw.width, raw.height, exclusions);
  const color = OVERLAY_COLORS[channel] ?? OVERLAY_COLORS.Green;
  const tintA = OVERLAY_ALPHA / 255.0;
  const exclA = EXCLUDE_RGBA[3] / 255.0;
  const data = raw.data;

  for (let i = 0, o = 0; i < data.length; i++, o += 4) {
    if (data[i] >= threshold && !(excl && excl[i])) blend(rgba, o, color, tintA);
  }
  if (excl) {
    for (let i = 0, o = 0; i < data.length; i++, o += 4) {
      if (excl[i]) blend(rgba, o, EXCLUDE_RGBA, exclA);
    }
  }
  return img;
}

/** Put an RgbImage onto a fresh canvas. */
export function rgbToCanvas(img: RgbImage): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = img.width;
  canvas.height = img.height;
  const ctx = canvas.getContext("2d")!;
  ctx.putImageData(toImageData(img.data, img.width, img.height), 0, 0);
  return canvas;
}

/**
 * Render the annotated image with a caption banner and encode it as a PNG Blob.
 * The banner (opaque black box + white text) is drawn with canvas text, like the
 * desktop's PIL banner; the image pixels themselves use the float blend above.
 */
export async function renderAnnotatedPng(
  raw: RawImage,
  threshold: number,
  channel: string,
  caption: string,
  brightness = 0.0,
  contrast = 1.0,
  exclusions: Rect[] = [],
): Promise<Blob> {
  const img = renderOverlayRgb(
    raw,
    threshold,
    channel,
    brightness,
    contrast,
    exclusions,
  );
  const canvas = rgbToCanvas(img);
  const ctx = canvas.getContext("2d")!;

  const fontPx = Math.max(14, Math.floor(img.width / 70));
  ctx.font = `${fontPx}px sans-serif`;
  ctx.textBaseline = "top";
  const pad = 6;
  const metrics = ctx.measureText(caption);
  const textH =
    (metrics.actualBoundingBoxAscent || fontPx) +
    (metrics.actualBoundingBoxDescent || Math.round(fontPx * 0.3));
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, Math.ceil(metrics.width) + 2 * pad, Math.ceil(textH) + 2 * pad);
  ctx.fillStyle = "#ffffff";
  ctx.fillText(caption, pad, pad);

  return await canvasToPngBlob(canvas);
}

export function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b);
      else reject(new Error("PNG encode failed"));
    }, "image/png");
  });
}
