// Image decoding for the browser. TIFF (incl. 16-bit grayscale) is decoded with
// utif2 — a pure-JS path that also runs under Node, so it can be parity-tested
// against qviability.image_io.load_image. PNG/JPEG use the browser's native
// decoder (createImageBitmap), reduced to a single channel.
//
// Mirrors load_image (image_io.py:46-70): single-channel uint8/uint16 are kept
// as-is; RGB(A) is reduced to grayscale with the same luminosity weights cv2
// uses for COLOR_*2GRAY (0.299 R + 0.587 G + 0.114 B, rounded).

import * as UTIF from "utif2";

const U: any = (UTIF as any).default ?? UTIF;

export interface DecodedImage {
  data: Uint8Array | Uint16Array;
  width: number;
  height: number;
  bitDepth: number; // 8 or 16
}

function cvGray(r: number, g: number, b: number): number {
  // cv2 COLOR_BGR2GRAY rounds the weighted sum to nearest integer.
  return Math.round(0.299 * r + 0.587 * g + 0.114 * b);
}

/** Decode a TIFF (pure JS). Handles 8/16-bit grayscale and RGB(A). */
export function decodeTiff(buffer: ArrayBuffer): DecodedImage {
  const ifds = U.decode(buffer);
  if (!ifds || ifds.length === 0) throw new Error("TIFF: no image found");
  const ifd = ifds[0];
  U.decodeImage(buffer, ifd);

  const width: number = ifd.width;
  const height: number = ifd.height;
  const n = width * height;
  const spp: number = (ifd.t277 && ifd.t277[0]) || 1;
  const bps: number = (ifd.t258 && ifd.t258[0]) || 8;
  const raw: Uint8Array = ifd.data;

  if (spp === 1) {
    if (bps <= 8) {
      return { data: raw.slice(0, n), width, height, bitDepth: 8 };
    }
    // 16-bit unsigned, little-endian (utif2 normalizes to LE in data).
    const dv = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
    const out = new Uint16Array(n);
    for (let i = 0; i < n; i++) out[i] = dv.getUint16(i * 2, true);
    return { data: out, width, height, bitDepth: 16 };
  }

  // Multi-channel → grayscale (rare for microscopy).
  if (bps <= 8) {
    const out = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      const o = i * spp;
      out[i] = cvGray(raw[o], raw[o + 1], raw[o + 2]);
    }
    return { data: out, width, height, bitDepth: 8 };
  }
  const dv = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
  const out = new Uint16Array(n);
  for (let i = 0; i < n; i++) {
    const o = i * spp * 2;
    const r = dv.getUint16(o, true);
    const g = dv.getUint16(o + 2, true);
    const b = dv.getUint16(o + 4, true);
    out[i] = cvGray(r, g, b);
  }
  return { data: out, width, height, bitDepth: 16 };
}

/** Decode PNG/JPEG via the browser, reduced to an 8-bit single channel. */
export async function decodeRaster(blob: Blob): Promise<DecodedImage> {
  const bmp = await createImageBitmap(blob);
  const { width, height } = bmp;
  const canvas = new OffscreenCanvas(width, height);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("2D canvas unavailable");
  ctx.drawImage(bmp, 0, 0);
  bmp.close();
  const rgba = ctx.getImageData(0, 0, width, height).data;
  const n = width * height;
  const out = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const o = i * 4;
    const r = rgba[o];
    const g = rgba[o + 1];
    const b = rgba[o + 2];
    // Grayscale source has R=G=B; only weight when it's genuinely colored.
    out[i] = r === g && g === b ? r : cvGray(r, g, b);
  }
  return { data: out, width, height, bitDepth: 8 };
}

const TIFF_EXT = /\.(tif|tiff)$/i;

/** Decode any supported image File/Blob by filename. */
export async function decodeImageFile(
  name: string,
  blob: Blob,
): Promise<DecodedImage> {
  if (TIFF_EXT.test(name)) {
    return decodeTiff(await blob.arrayBuffer());
  }
  return decodeRaster(blob);
}
