import { readFileSync } from "node:fs";
import { Buffer } from "node:buffer";
import { describe, it, expect } from "vitest";

import { subtractBackground } from "@/core/rollingBall";
import { autoThreshold } from "@/core/autothreshold";
import { measure } from "@/core/measure";
import { maxValue } from "@/core/imageIo";

interface RadiusCase {
  radius: number;
  shrink: number;
  sub_b64: string;
  threshold: number;
  positive_pixels: number;
}
interface Case {
  name: string;
  bit_depth: number;
  width: number;
  height: number;
  data_b64: string;
  radii: RadiusCase[];
}

const expected = JSON.parse(
  readFileSync(new URL("./expected_rolling.json", import.meta.url), "utf8"),
) as { cases: Case[] };

function decode(b64: string, bit: number): Uint8Array | Uint16Array {
  const buf = Uint8Array.from(Buffer.from(b64, "base64"));
  if (bit === 8) return buf;
  const n = buf.byteLength / 2;
  const out = new Uint16Array(n);
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  for (let i = 0; i < n; i++) out[i] = dv.getUint16(i * 2, true);
  return out;
}

describe("rolling-ball subtract_background parity", () => {
  for (const c of expected.cases) {
    const data = decode(c.data_b64, c.bit_depth);
    const isU16 = c.bit_depth === 16;
    for (const rc of c.radii) {
      it(`${c.name} r=${rc.radius} (shrink ${rc.shrink})`, () => {
        const exp = decode(rc.sub_b64, c.bit_depth);
        const got = subtractBackground(data, c.width, c.height, rc.radius, isU16);
        expect(got.length).toBe(exp.length);

        let maxDiff = 0;
        let nDiff = 0;
        for (let i = 0; i < exp.length; i++) {
          const d = Math.abs(got[i] - exp[i]);
          if (d > 0) {
            nDiff++;
            if (d > maxDiff) maxDiff = d;
          }
        }
        const mv = maxValue(got);
        const thr = autoThreshold(got, mv, "MaxEntropy");
        const pos = measure(got, thr).positive_pixels;

        if (rc.shrink === 1) {
          // No resize involved — must be bit-exact.
          expect(maxDiff).toBe(0);
          expect(thr).toBe(rc.threshold);
          expect(pos).toBe(rc.positive_pixels);
        } else {
          // Resize differs slightly from cv2; require close pixels + matching
          // tuned threshold and positive_pixels within a small tolerance.
          expect(maxDiff).toBeLessThanOrEqual(5);
          expect(nDiff / exp.length).toBeLessThanOrEqual(0.02);
          expect(Math.abs(thr - rc.threshold)).toBeLessThanOrEqual(2);
          const relPos =
            Math.abs(pos - rc.positive_pixels) / Math.max(1, rc.positive_pixels);
          expect(relPos).toBeLessThanOrEqual(0.02);
        }
      });
    }
  }
});
