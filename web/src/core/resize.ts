// cv2.resize replacements for the rolling-ball downscale/upscale path.
//   - resizeAreaInt:   INTER_AREA on integer images (downscale), area-weighted
//                      average + round-half-to-even + saturate (matches cvRound).
//   - resizeLinearF32: INTER_LINEAR on float32 images (upscale), cv2's
//                      (x+0.5)*scale-0.5 sampling, no rounding.

const f32 = Math.fround;

/** cvRound: round to nearest, ties to even. */
function cvRound(x: number): number {
  const r = Math.round(x); // ties up
  if (Math.abs(x - Math.trunc(x)) === 0.5) {
    const fl = Math.floor(x);
    return fl % 2 === 0 ? fl : fl + 1;
  }
  return r;
}

type Weights = Array<Array<[number, number]>>; // per-dst: [srcIndex, weight] (sum=1)

function areaWeights(srcN: number, dstN: number): Weights {
  const scale = srcN / dstN;
  const res: Weights = [];
  for (let d = 0; d < dstN; d++) {
    const s1 = d * scale;
    const s2 = s1 + scale;
    const ent: Array<[number, number]> = [];
    let i = Math.floor(s1);
    while (i < s2 && i < srcN) {
      if (i >= 0) {
        const lo = Math.max(s1, i);
        const hi = Math.min(s2, i + 1);
        const w = hi - lo;
        if (w > 1e-12) ent.push([i, w / scale]);
      }
      i++;
    }
    res.push(ent);
  }
  return res;
}

export function resizeAreaInt(
  src: Uint8Array | Uint16Array,
  sw: number,
  sh: number,
  dw: number,
  dh: number,
  isU16: boolean,
): Uint8Array | Uint16Array {
  const wx = areaWeights(sw, dw);
  const wy = areaWeights(sh, dh);
  const maxv = isU16 ? 65535 : 255;
  const out = isU16 ? new Uint16Array(dw * dh) : new Uint8Array(dw * dh);
  for (let dy = 0; dy < dh; dy++) {
    const yent = wy[dy];
    for (let dx = 0; dx < dw; dx++) {
      const xent = wx[dx];
      let acc = 0;
      for (let yi = 0; yi < yent.length; yi++) {
        const sy = yent[yi][0];
        const wyy = yent[yi][1];
        const base = sy * sw;
        let rowAcc = 0;
        for (let xi = 0; xi < xent.length; xi++) {
          rowAcc += src[base + xent[xi][0]] * xent[xi][1];
        }
        acc += rowAcc * wyy;
      }
      let v = cvRound(acc);
      if (v < 0) v = 0;
      else if (v > maxv) v = maxv;
      out[dy * dw + dx] = v;
    }
  }
  return out;
}

export function resizeLinearF32(
  src: Float32Array,
  sw: number,
  sh: number,
  dw: number,
  dh: number,
): Float32Array {
  const out = new Float32Array(dw * dh);
  const sxScale = sw / dw;
  const syScale = sh / dh;

  const x0 = new Int32Array(dw);
  const x1 = new Int32Array(dw);
  const xw = new Float64Array(dw);
  for (let dx = 0; dx < dw; dx++) {
    let fx = (dx + 0.5) * sxScale - 0.5;
    let i = Math.floor(fx);
    let w = fx - i;
    if (i < 0) {
      i = 0;
      w = 0;
    }
    let i1 = i + 1;
    if (i1 > sw - 1) {
      i1 = sw - 1;
      if (i > sw - 1) i = sw - 1;
    }
    x0[dx] = i;
    x1[dx] = i1;
    xw[dx] = w;
  }

  for (let dy = 0; dy < dh; dy++) {
    let fy = (dy + 0.5) * syScale - 0.5;
    let y0 = Math.floor(fy);
    let wy = fy - y0;
    if (y0 < 0) {
      y0 = 0;
      wy = 0;
    }
    let y1 = y0 + 1;
    if (y1 > sh - 1) {
      y1 = sh - 1;
      if (y0 > sh - 1) y0 = sh - 1;
    }
    const r0 = y0 * sw;
    const r1 = y1 * sw;
    for (let dx = 0; dx < dw; dx++) {
      const ax = x0[dx];
      const bx = x1[dx];
      const wx = xw[dx];
      const v00 = src[r0 + ax];
      const v01 = src[r0 + bx];
      const v10 = src[r1 + ax];
      const v11 = src[r1 + bx];
      const top = v00 + (v01 - v00) * wx;
      const bot = v10 + (v11 - v10) * wx;
      out[dy * dw + dx] = f32(top + (bot - top) * wy);
    }
  }
  return out;
}
