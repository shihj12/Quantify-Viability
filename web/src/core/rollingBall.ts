// Port of qviability/core/image_io.subtract_background (rolling-ball background
// subtraction). The rolling-ball core reproduces skimage.restoration.rolling_ball
// exactly: background[p] = min over ball offsets k of (img[p+k] + D[k]), where
// D[k] = radius - sqrt(radius^2 - |k|^2) inside the ball (+inf outside / out of
// bounds). skimage casts the background back to the integer dtype (truncation).

import { resizeAreaInt, resizeLinearF32 } from "./resize";

const f32 = Math.fround;

interface Offset {
  dy: number;
  dx: number;
  d: number;
}

function ballOffsets(radius: number): Offset[] {
  const R = Math.ceil(radius);
  const r2 = radius * radius;
  const offs: Offset[] = [];
  for (let dy = -R; dy <= R; dy++) {
    for (let dx = -R; dx <= R; dx++) {
      const ss = dx * dx + dy * dy;
      if (Math.sqrt(ss) > radius) continue;
      offs.push({ dy, dx, d: radius - Math.sqrt(r2 - ss) });
    }
  }
  return offs;
}

/** Rolling-ball background, returned as the integer dtype (truncated). */
export function rollingBallInt(
  img: Uint8Array | Uint16Array,
  w: number,
  h: number,
  radius: number,
  isU16: boolean,
): Uint8Array | Uint16Array {
  const offs = ballOffsets(radius);
  const out = isU16 ? new Uint16Array(w * h) : new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let m = Infinity;
      for (let k = 0; k < offs.length; k++) {
        const yy = y + offs[k].dy;
        const xx = x + offs[k].dx;
        if (yy < 0 || yy >= h || xx < 0 || xx >= w) continue;
        const v = img[yy * w + xx] + offs[k].d;
        if (v < m) m = v;
      }
      out[y * w + x] = Math.floor(m); // astype(uint) truncation
    }
  }
  return out;
}

/**
 * Rolling-ball background subtraction. Downscales for speed when the image is
 * large (shrink = clamp(radius//8, 1, 4) for min dim >= 256), keeping the
 * downscaled radius ~8+ px so small radii run full-resolution.
 */
export function subtractBackground(
  data: Uint8Array | Uint16Array,
  w: number,
  h: number,
  radius: number,
  isU16: boolean,
): Uint8Array | Uint16Array {
  let shrink = 1;
  if (Math.min(w, h) >= 256) {
    shrink = Math.max(1, Math.min(4, Math.floor(radius / 8)));
  }

  let background: Float32Array;
  if (shrink > 1) {
    const sw = Math.floor(w / shrink);
    const sh = Math.floor(h / shrink);
    const small = resizeAreaInt(data, w, h, sw, sh, isU16);
    const r2 = Math.max(1, Math.floor(radius / shrink));
    const bgSmall = rollingBallInt(small, sw, sh, r2, isU16);
    background = resizeLinearF32(Float32Array.from(bgSmall), sw, sh, w, h);
  } else {
    const bg = rollingBallInt(data, w, h, radius, isU16);
    background = Float32Array.from(bg);
  }

  const maxv = isU16 ? 65535 : 255;
  const out = isU16 ? new Uint16Array(w * h) : new Uint8Array(w * h);
  for (let i = 0; i < data.length; i++) {
    let v = f32(f32(data[i]) - background[i]);
    if (v < 0) v = 0;
    let t = Math.floor(v);
    if (t > maxv) t = maxv;
    out[i] = t;
  }
  return out;
}
