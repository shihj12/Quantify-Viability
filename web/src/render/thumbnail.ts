// Review-gallery thumbnails: render the annotated overlay (float blend, same as
// export) then downscale to a fixed width. Returns a data URL for an <img>.

import type { RawImage, Rect } from "@/core/types";
import { renderOverlayRgb, rgbToCanvas } from "@/export/annotate";

export const THUMB_W = 230;

export function renderThumbnail(
  raw: RawImage,
  threshold: number,
  channel: string,
  brightness: number,
  contrast: number,
  exclusions: Rect[],
): string {
  const img = renderOverlayRgb(raw, threshold, channel, brightness, contrast, exclusions);
  const src = rgbToCanvas(img);
  const w = THUMB_W;
  const h = Math.max(1, Math.round((img.height * w) / img.width));
  const dst = document.createElement("canvas");
  dst.width = w;
  dst.height = h;
  const ctx = dst.getContext("2d")!;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, 0, 0, w, h);
  return dst.toDataURL("image/png");
}
