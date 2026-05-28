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

export async function decodeTiffInWorker(
  buffer: ArrayBuffer,
): Promise<DecodedImage> {
  return api().decodeTiff(Comlink.transfer(buffer, [buffer]));
}
