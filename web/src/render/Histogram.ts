// Pixel-value histogram with a draggable threshold line (Canvas2D).
//
// Mirrors the desktop HistogramWidget: a 256-bin histogram of the working image,
// sqrt-compressed so the huge dark-background peak doesn't bury the signal, with
// a red vertical line the user can drag to set the threshold.

import { histogram256 } from "@/core/imageIo";

const BG = "#262626";
const FILL = "rgba(120, 130, 175, 0.63)";
const STROKE = "rgb(170, 180, 220)";
const LINE = "#ff5555";
const AXIS = "#888888";

export type ThresholdHandler = (value: number) => void;

export class Histogram {
  private ctx: CanvasRenderingContext2D;
  private bins = new Float64Array(256);
  private peak = 1;
  private maxval = 255;
  private threshold = 0;
  private dragging = false;
  private ro: ResizeObserver;

  onThresholdChange: ThresholdHandler | null = null;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas unavailable");
    this.ctx = ctx;
    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointermove", this.onPointerMove);
    canvas.addEventListener("pointerup", this.onPointerUp);
    canvas.addEventListener("pointerleave", this.onPointerUp);
    this.ro = new ResizeObserver(() => this.syncSize());
    this.ro.observe(canvas);
    this.syncSize();
  }

  destroy(): void {
    this.ro.disconnect();
    this.canvas.removeEventListener("pointerdown", this.onPointerDown);
    this.canvas.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("pointerup", this.onPointerUp);
    this.canvas.removeEventListener("pointerleave", this.onPointerUp);
  }

  setData(data: Uint8Array | Uint16Array, maxval: number): void {
    this.maxval = Math.max(1, maxval);
    const hist = histogram256(data, this.maxval);
    let peak = 1;
    for (let i = 0; i < 256; i++) {
      const v = Math.sqrt(hist[i]);
      this.bins[i] = v;
      if (v > peak) peak = v;
    }
    this.peak = peak;
    this.render();
  }

  setThreshold(value: number): void {
    this.threshold = value;
    this.render();
  }

  private syncSize(): void {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(rect.width * dpr));
    const h = Math.max(1, Math.round(rect.height * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.render();
  }

  render(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, w, h);

    const pad = Math.round(2 * (window.devicePixelRatio || 1));
    const plotH = h - pad * 2;

    // Histogram curve (filled).
    ctx.beginPath();
    ctx.moveTo(0, h - pad);
    for (let i = 0; i < 256; i++) {
      const x = (i / 255) * w;
      const y = h - pad - (this.bins[i] / this.peak) * plotH;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(w, h - pad);
    ctx.closePath();
    ctx.fillStyle = FILL;
    ctx.fill();
    ctx.strokeStyle = STROKE;
    ctx.lineWidth = 1;
    ctx.stroke();

    // Baseline axis.
    ctx.strokeStyle = AXIS;
    ctx.beginPath();
    ctx.moveTo(0, h - pad + 0.5);
    ctx.lineTo(w, h - pad + 0.5);
    ctx.stroke();

    // Threshold line.
    const lx = (this.threshold / this.maxval) * w;
    ctx.strokeStyle = LINE;
    ctx.lineWidth = Math.max(2, 2 * (window.devicePixelRatio || 1));
    ctx.beginPath();
    ctx.moveTo(lx, 0);
    ctx.lineTo(lx, h);
    ctx.stroke();
  }

  private valueAt(clientX: number): number {
    const rect = this.canvas.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.round(frac * this.maxval);
  }

  private emit(clientX: number): void {
    const v = this.valueAt(clientX);
    this.threshold = v;
    this.render();
    if (this.onThresholdChange) this.onThresholdChange(v);
  }

  private onPointerDown = (e: PointerEvent): void => {
    this.dragging = true;
    this.canvas.setPointerCapture(e.pointerId);
    this.emit(e.clientX);
  };

  private onPointerMove = (e: PointerEvent): void => {
    if (this.dragging) this.emit(e.clientX);
  };

  private onPointerUp = (e: PointerEvent): void => {
    this.dragging = false;
    if (this.canvas.hasPointerCapture(e.pointerId)) {
      this.canvas.releasePointerCapture(e.pointerId);
    }
  };
}
