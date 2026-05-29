// Export-overlay parity: renderOverlayRgb must reproduce annotate.py's EXPLICIT
// float blend  chan*(1-a) + colour*a  (float32, then astype(uint8) = truncate),
// not the canvas straight-alpha compositor. renderOverlayRgb is DOM-free (it
// returns RGBA bytes), so this runs in the node test env alongside the rest of
// the parity suite. autoStretch + applyDisplay are already byte-exact (parity
// test), so re-deriving the expected bytes from the same primitives here checks
// the blend + truncation specifically.

import { describe, it, expect } from "vitest";
import { renderDisplayRgb, renderOverlayRgb } from "@/export/annotate";
import { autoStretch, applyDisplay } from "@/core/imageIo";
import { OVERLAY_COLORS, OVERLAY_ALPHA, EXCLUDE_RGBA } from "@/core/measure";
import type { RawImage, Rect } from "@/core/types";

const f32 = Math.fround;

/** Reference float blend identical to qviability/export/annotate._tint + cast. */
function expectBlend(base: number, c: number, alpha: number): number {
  return Math.floor(f32(base * (1 - alpha) + c * alpha));
}

function makeImage(values: number[], width: number, height: number): RawImage {
  return { data: Uint8Array.from(values), width, height };
}

describe("export overlay float-blend parity (annotate.py)", () => {
  // A spread of 8-bit values so auto_stretch has a real dynamic range.
  const width = 4;
  const height = 2;
  const values = [0, 60, 120, 180, 30, 90, 200, 255];
  const img = makeImage(values, width, height);
  const threshold = 120; // positives: 120,180,200,255
  const tintA = OVERLAY_ALPHA / 255.0;

  it("tints positive pixels with the channel colour via the float blend", () => {
    const disp = applyDisplay(autoStretch(img.data), 0, 1); // grayscale base, byte-exact
    const color = OVERLAY_COLORS.Green;
    const out = renderOverlayRgb(img, threshold, "Green", 0, 1, []).data;

    for (let i = 0; i < values.length; i++) {
      const o = i * 4;
      const g = disp[i];
      if (values[i] >= threshold) {
        expect(out[o]).toBe(expectBlend(g, color[0], tintA));
        expect(out[o + 1]).toBe(expectBlend(g, color[1], tintA));
        expect(out[o + 2]).toBe(expectBlend(g, color[2], tintA));
        // Green tint must dominate.
        expect(out[o + 1]).toBeGreaterThan(out[o] + 10);
        expect(out[o + 1]).toBeGreaterThan(out[o + 2] + 10);
      } else {
        // Untouched pixels stay pure grayscale.
        expect(out[o]).toBe(g);
        expect(out[o + 1]).toBe(g);
        expect(out[o + 2]).toBe(g);
      }
      expect(out[o + 3]).toBe(255); // opaque
    }
  });

  it("uses the magenta tint for the Red channel (R and B dominate)", () => {
    const out = renderOverlayRgb(img, threshold, "Red", 0, 1, []).data;
    const o = 7 * 4; // value 255, positive
    expect(out[o]).toBeGreaterThan(out[o + 1] + 10); // R > G
    expect(out[o + 2]).toBeGreaterThan(out[o + 1] + 10); // B > G
  });

  it("fills exclusion boxes with the gray blend and never tints them", () => {
    // Exclude the whole bottom row (y=1): those positives must be gray-filled,
    // not channel-tinted, matching measure/overlay's exclusion semantics.
    const exclusions: Rect[] = [[0, 1, width, 1]];
    const disp = applyDisplay(autoStretch(img.data), 0, 1);
    const exclA = EXCLUDE_RGBA[3] / 255.0;
    const out = renderOverlayRgb(img, threshold, "Green", 0, 1, exclusions).data;

    for (let x = 0; x < width; x++) {
      const i = width + x; // bottom row
      const o = i * 4;
      expect(out[o]).toBe(expectBlend(disp[i], EXCLUDE_RGBA[0], exclA));
      expect(out[o + 1]).toBe(expectBlend(disp[i], EXCLUDE_RGBA[1], exclA));
      expect(out[o + 2]).toBe(expectBlend(disp[i], EXCLUDE_RGBA[2], exclA));
      // Gray fill: channels are near-equal (not green-dominant).
      expect(Math.abs(out[o] - out[o + 1])).toBeLessThanOrEqual(1);
    }
  });

  it("renderDisplayRgb is the plain grayscale 'before' image", () => {
    const disp = applyDisplay(autoStretch(img.data), 0, 1);
    const before = renderDisplayRgb(img, 0, 1).data;
    for (let i = 0; i < values.length; i++) {
      const o = i * 4;
      expect(before[o]).toBe(disp[i]);
      expect(before[o + 1]).toBe(disp[i]);
      expect(before[o + 2]).toBe(disp[i]);
      expect(before[o + 3]).toBe(255);
    }
  });

  it("a concrete hand-computed positive pixel matches byte-for-byte", () => {
    // Two pixels: 0 and 255. disp = [0, 255]. Threshold 100 -> only px1 positive.
    const two = makeImage([0, 255], 2, 1);
    const disp = applyDisplay(autoStretch(two.data), 0, 1);
    const out = renderOverlayRgb(two, 100, "Green", 0, 1, []).data;
    const color = OVERLAY_COLORS.Green;
    // px0 untouched grayscale
    expect([out[0], out[1], out[2], out[3]]).toEqual([disp[0], disp[0], disp[0], 255]);
    // px1 green-blended (exact)
    expect(out[4]).toBe(expectBlend(disp[1], color[0], tintA));
    expect(out[5]).toBe(expectBlend(disp[1], color[1], tintA));
    expect(out[6]).toBe(expectBlend(disp[1], color[2], tintA));
  });
});
