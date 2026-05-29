// Lazily-created Comlink client for the compute worker.

import * as Comlink from "comlink";
import type { ComputeApi } from "./compute.worker";
import type { DecodedImage } from "@/core/decode";

let proxy: Comlink.Remote<ComputeApi> | null = null;

function api(): Comlink.Remote<ComputeApi> {
  if (!proxy) {
    const worker = new Worker(
      new URL("./compute.worker.ts", import.meta.url),
      { type: "module" },
    );
    proxy = Comlink.wrap<ComputeApi>(worker);
  }
  return proxy;
}

/** Decode a TIFF in the worker; the input buffer is transferred (consumed). */
export async function decodeTiffInWorker(
  buffer: ArrayBuffer,
): Promise<DecodedImage> {
  return api().decodeTiff(Comlink.transfer(buffer, [buffer]));
}

/**
 * Rolling-ball background subtraction in the worker. A copy of `data` is sent
 * (and transferred) so the caller's cached array stays intact; the worker
 * returns a freshly allocated array of the same dtype.
 */
export async function subtractBackgroundInWorker(
  data: Uint8Array | Uint16Array,
  width: number,
  height: number,
  radius: number,
): Promise<Uint8Array | Uint16Array> {
  const isU16 = data instanceof Uint16Array;
  const copy = data.slice();
  const res = await api().subtractBackground(
    Comlink.transfer(copy, [copy.buffer]),
    width,
    height,
    radius,
    isU16,
  );
  return res.data;
}
