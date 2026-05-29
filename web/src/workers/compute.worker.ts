// Off-main-thread compute: TIFF decode and rolling-ball background subtraction.
// The two genuinely heavy, one-shot-per-image operations live here so the UI
// thread stays responsive while loading 16-bit microscopy images. Per-threshold
// measurement and overlay are cheap O(N) loops and run on the main thread.
//
// Exposed via Comlink. Typed-array buffers are transferred (not cloned) in and
// out; callers hand in a throwaway copy so the cached original is never detached.

import * as Comlink from "comlink";
import { decodeTiff, type DecodedImage } from "@/core/decode";
import { subtractBackground } from "@/core/rollingBall";

export interface ProcessedImage {
  data: Uint8Array | Uint16Array;
  width: number;
  height: number;
}

const api = {
  decodeTiff(buffer: ArrayBuffer): DecodedImage {
    const img = decodeTiff(buffer);
    return Comlink.transfer(img, [img.data.buffer]);
  },

  subtractBackground(
    data: Uint8Array | Uint16Array,
    width: number,
    height: number,
    radius: number,
    isU16: boolean,
  ): ProcessedImage {
    const out = subtractBackground(data, width, height, radius, isU16);
    return Comlink.transfer({ data: out, width, height }, [out.buffer]);
  },
};

export type ComputeApi = typeof api;

Comlink.expose(api);
