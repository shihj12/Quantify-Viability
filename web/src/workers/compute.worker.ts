// Off-main-thread compute: TIFF decode now, rolling-ball background subtraction
// in Phase 3. Exposed via Comlink.

import * as Comlink from "comlink";
import { decodeTiff, type DecodedImage } from "@/core/decode";

const api = {
  decodeTiff(buffer: ArrayBuffer): DecodedImage {
    const img = decodeTiff(buffer);
    return Comlink.transfer(img, [img.data.buffer]);
  },
};

export type ComputeApi = typeof api;

Comlink.expose(api);
