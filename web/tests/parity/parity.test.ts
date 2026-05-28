import { readFileSync } from "node:fs";
import { describe, it, expect } from "vitest";

import { measure, exclusionMask } from "@/core/measure";
import { autoThreshold } from "@/core/autothreshold";
import {
  histogram256,
  autoStretch,
  applyDisplay,
  maxValue,
  bitDepthOf,
} from "@/core/imageIo";
import type { Rect } from "@/core/types";

interface MeasureCase {
  threshold: number;
  exclusions: Rect[];
  result: {
    threshold: number;
    positive_pixels: number;
    total_pixels: number;
    positive_area_pct: number;
    mean_intensity_positive: number;
    integrated_intensity: number;
    method: string;
  };
}
interface DisplayCase {
  brightness: number;
  contrast: number;
  base_u8: number[];
}
interface Case {
  name: string;
  bit_depth: number;
  width: number;
  height: number;
  max_value: number;
  data: number[];
  histogram256: number[];
  auto: { MaxEntropy: number };
  measure: MeasureCase[];
  display: DisplayCase[];
}

const expected = JSON.parse(
  readFileSync(new URL("./expected.json", import.meta.url), "utf8"),
) as { cases: Case[] };

function raw(c: Case): Uint8Array | Uint16Array {
  return c.bit_depth === 8 ? Uint8Array.from(c.data) : Uint16Array.from(c.data);
}

function relClose(a: number, b: number, tol = 1e-9): boolean {
  if (a === b) return true;
  return Math.abs(a - b) <= tol * Math.max(1, Math.abs(a), Math.abs(b));
}

describe("core parity vs qviability.core", () => {
  for (const c of expected.cases) {
    describe(c.name, () => {
      const data = raw(c);

      it("max_value and bit_depth", () => {
        expect(bitDepthOf(data)).toBe(c.bit_depth);
        expect(maxValue(data)).toBe(c.max_value);
      });

      it("256-bin histogram is exact", () => {
        const h = histogram256(data, c.max_value);
        for (let i = 0; i < 256; i++) expect(h[i]).toBe(c.histogram256[i]);
      });

      it("MaxEntropy auto-threshold is exact", () => {
        expect(autoThreshold(data, c.max_value, "MaxEntropy")).toBe(
          c.auto.MaxEntropy,
        );
      });

      it("measure() matches at every threshold (incl. exclusions)", () => {
        for (const mc of c.measure) {
          const mask = exclusionMask(c.width, c.height, mc.exclusions);
          const r = measure(data, mc.threshold, "Manual", mask);
          expect(r.positive_pixels).toBe(mc.result.positive_pixels);
          expect(r.total_pixels).toBe(mc.result.total_pixels);
          expect(r.threshold).toBe(mc.result.threshold);
          expect(relClose(r.positive_area_pct, mc.result.positive_area_pct)).toBe(
            true,
          );
          expect(
            relClose(
              r.mean_intensity_positive,
              mc.result.mean_intensity_positive,
            ),
          ).toBe(true);
          expect(
            relClose(r.integrated_intensity, mc.result.integrated_intensity),
          ).toBe(true);
        }
      });

      it("auto_stretch + apply_display produce identical uint8 pixels", () => {
        const base = autoStretch(data);
        for (const dc of c.display) {
          const disp = applyDisplay(base, dc.brightness, dc.contrast);
          expect(disp.length).toBe(dc.base_u8.length);
          for (let i = 0; i < disp.length; i++) {
            expect(disp[i]).toBe(dc.base_u8[i]);
          }
        }
      });
    });
  }
});
