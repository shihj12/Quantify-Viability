// Browser analogue of qviability/core/image_io's _ImageCache / _PROC_CACHE.
//
// Raw pixels are decoded once per file and kept in a small LRU; the optional
// background-subtracted ("processed") result is cached separately, keyed by
// (path, radius). Microscopy TIFFs are often 16-bit, so real Uint16Array values
// are carried end-to-end and never downsampled to 8-bit for measurement.

import type { ImageRef } from "./fileSystem";
import type { RawImage } from "@/core/types";
import { decodeRaster } from "@/core/decode";
import {
  decodeTiffInWorker,
  subtractBackgroundInWorker,
} from "@/workers/computeClient";

const TIFF_EXT = /\.(tif|tiff)$/i;

class Lru<V> {
  private store = new Map<string, V>();
  constructor(private capacity: number) {}

  get(key: string): V | undefined {
    const v = this.store.get(key);
    if (v !== undefined) {
      this.store.delete(key);
      this.store.set(key, v);
    }
    return v;
  }

  set(key: string, value: V): void {
    if (this.store.has(key)) this.store.delete(key);
    this.store.set(key, value);
    while (this.store.size > this.capacity) {
      const first = this.store.keys().next().value;
      if (first === undefined) break;
      this.store.delete(first);
    }
  }

  clear(): void {
    this.store.clear();
  }
}

const rawCache = new Lru<RawImage>(5);
const procCache = new Lru<RawImage>(8);
// Coalesce concurrent loads of the same key so a folder of N images doesn't
// decode the same file twice when review + threshold both request it.
const rawPending = new Map<string, Promise<RawImage>>();

async function decode(ref: ImageRef): Promise<RawImage> {
  const blob = await ref.getBlob();
  if (TIFF_EXT.test(ref.name)) {
    const buf = await blob.arrayBuffer();
    const img = await decodeTiffInWorker(buf);
    return { data: img.data, width: img.width, height: img.height };
  }
  const img = await decodeRaster(blob);
  return { data: img.data, width: img.width, height: img.height };
}

/** Load (and cache) the raw pixels for `path`, decoding via `ref` on a miss. */
export async function loadRaw(path: string, ref: ImageRef): Promise<RawImage> {
  const hit = rawCache.get(path);
  if (hit) return hit;
  const inflight = rawPending.get(path);
  if (inflight) return inflight;

  const p = decode(ref)
    .then((img) => {
      rawCache.set(path, img);
      return img;
    })
    .finally(() => rawPending.delete(path));
  rawPending.set(path, p);
  return p;
}

/**
 * The working image for `path`: the raw image, or the background-subtracted
 * image when `subtract` is true (cached by radius). Mirrors get_processed.
 */
export async function loadProcessed(
  path: string,
  ref: ImageRef,
  subtract: boolean,
  radius: number,
): Promise<RawImage> {
  const raw = await loadRaw(path, ref);
  if (!subtract) return raw;
  const key = `${path}|r${radius}`;
  const hit = procCache.get(key);
  if (hit) return hit;
  const data = await subtractBackgroundInWorker(
    raw.data,
    raw.width,
    raw.height,
    radius,
  );
  const proc: RawImage = { data, width: raw.width, height: raw.height };
  procCache.set(key, proc);
  return proc;
}

export function clearImageCache(): void {
  rawCache.clear();
  procCache.clear();
  rawPending.clear();
}
