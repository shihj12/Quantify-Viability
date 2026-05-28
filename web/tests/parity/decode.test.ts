import { readFileSync } from "node:fs";
import { describe, it, expect } from "vitest";

import { decodeTiff } from "@/core/decode";

interface DecodeCase {
  name: string;
  file: string;
  bit_depth: number;
  width: number;
  height: number;
  data: number[];
}

const dir = new URL(".", import.meta.url);
const expected = JSON.parse(
  readFileSync(new URL("./expected_decode.json", import.meta.url), "utf8"),
) as { cases: DecodeCase[] };

describe("TIFF decode parity vs image_io.load_image", () => {
  for (const c of expected.cases) {
    it(`${c.name} decodes to identical pixels`, () => {
      const buf = readFileSync(new URL(c.file, dir));
      const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
      const img = decodeTiff(ab);
      expect(img.width).toBe(c.width);
      expect(img.height).toBe(c.height);
      expect(img.bitDepth).toBe(c.bit_depth);
      expect(img.data.length).toBe(c.data.length);
      for (let i = 0; i < img.data.length; i++) {
        expect(img.data[i]).toBe(c.data[i]);
      }
    });
  }
});
