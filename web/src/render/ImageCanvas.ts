// Canvas2D image view: a grayscale base layer with a translucent RGBA overlay,
// drawn under a {scale, offsetX, offsetY} transform. Mirrors the desktop's
// pyqtgraph ImageCanvas: fit-to-view, wheel zoom, drag-to-pan, and a draw mode
// that rubber-bands an exclusion box (reported back in image-pixel coords).
//
// The base and overlay live on full-resolution offscreen canvases; rendering
// just blits them with the current transform, so re-rendering on pan/zoom is
// cheap and the per-tick work is only repainting the overlay offscreen.

export interface Transform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export type RegionHandler = (x: number, y: number, w: number, h: number) => void;

const BG = "#1a1a1a";

export class ImageCanvas {
  private ctx: CanvasRenderingContext2D;
  private base: HTMLCanvasElement;
  private overlay: HTMLCanvasElement;
  private baseCtx: CanvasRenderingContext2D;
  private overlayCtx: CanvasRenderingContext2D;

  private imgW = 0;
  private imgH = 0;
  private tf: Transform = { scale: 1, offsetX: 0, offsetY: 0 };
  private overlayVisible = true;

  private drawMode = false;
  private dragging = false;
  private panning = false;
  private startSx = 0;
  private startSy = 0;
  private curSx = 0;
  private curSy = 0;
  private panStartX = 0;
  private panStartY = 0;

  onRegionDrawn: RegionHandler | null = null;

  private ro: ResizeObserver;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas unavailable");
    this.ctx = ctx;

    this.base = document.createElement("canvas");
    this.overlay = document.createElement("canvas");
    this.baseCtx = this.base.getContext("2d")!;
    this.overlayCtx = this.overlay.getContext("2d")!;

    canvas.addEventListener("wheel", this.onWheel, { passive: false });
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
    this.canvas.removeEventListener("wheel", this.onWheel);
    this.canvas.removeEventListener("pointerdown", this.onPointerDown);
    this.canvas.removeEventListener("pointermove", this.onPointerMove);
    this.canvas.removeEventListener("pointerup", this.onPointerUp);
    this.canvas.removeEventListener("pointerleave", this.onPointerUp);
  }

  /** (Re)allocate the offscreen layers for a new image size. */
  setImage(width: number, height: number): void {
    this.imgW = width;
    this.imgH = height;
    this.base.width = width;
    this.base.height = height;
    this.overlay.width = width;
    this.overlay.height = height;
  }

  setBaseImageData(data: ImageData): void {
    this.baseCtx.putImageData(data, 0, 0);
  }

  setOverlayImageData(data: ImageData): void {
    this.overlayCtx.putImageData(data, 0, 0);
  }

  setOverlayVisible(visible: boolean): void {
    this.overlayVisible = visible;
    this.render();
  }

  setDrawMode(on: boolean): void {
    this.drawMode = on;
    this.canvas.style.cursor = on ? "crosshair" : "grab";
    if (!on) this.dragging = false;
  }

  /** Fit the image into the viewport with a small padding margin. */
  fit(): void {
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    if (!this.imgW || !this.imgH || !cw || !ch) return;
    const scale = Math.min(cw / this.imgW, ch / this.imgH) * 0.98;
    this.tf = {
      scale,
      offsetX: (cw - this.imgW * scale) / 2,
      offsetY: (ch - this.imgH * scale) / 2,
    };
    this.render();
  }

  render(): void {
    const ctx = this.ctx;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, cw, ch);
    if (!this.imgW) return;

    ctx.imageSmoothingEnabled = false;
    const { scale, offsetX, offsetY } = this.tf;
    ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);
    ctx.drawImage(this.base, 0, 0);
    if (this.overlayVisible) ctx.drawImage(this.overlay, 0, 0);

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (this.dragging) {
      const x = Math.min(this.startSx, this.curSx);
      const y = Math.min(this.startSy, this.curSy);
      const w = Math.abs(this.curSx - this.startSx);
      const h = Math.abs(this.curSy - this.startSy);
      ctx.strokeStyle = "#ffd400";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      ctx.strokeRect(x + 0.5, y + 0.5, w, h);
      ctx.setLineDash([]);
    }
  }

  /** Map a screen (canvas-local CSS) point to image pixel coordinates. */
  screenToImage(sx: number, sy: number): [number, number] {
    return [
      (sx - this.tf.offsetX) / this.tf.scale,
      (sy - this.tf.offsetY) / this.tf.scale,
    ];
  }

  // --- internals ----------------------------------------------------------
  private syncSize(): void {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(rect.width * dpr));
    const h = Math.max(1, Math.round(rect.height * dpr));
    const first = this.canvas.width === 0 || this.canvas.height === 0;
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
      if (first) this.fit();
      else this.render();
    }
  }

  private localPoint(e: PointerEvent): [number, number] {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = this.canvas.width / rect.width;
    return [(e.clientX - rect.left) * dpr, (e.clientY - rect.top) * dpr];
  }

  private onWheel = (e: WheelEvent): void => {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    const dpr = this.canvas.width / rect.width;
    const sx = (e.clientX - rect.left) * dpr;
    const sy = (e.clientY - rect.top) * dpr;
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const [ix, iy] = this.screenToImage(sx, sy);
    this.tf.scale *= factor;
    this.tf.offsetX = sx - ix * this.tf.scale;
    this.tf.offsetY = sy - iy * this.tf.scale;
    this.render();
  };

  private onPointerDown = (e: PointerEvent): void => {
    const [sx, sy] = this.localPoint(e);
    this.canvas.setPointerCapture(e.pointerId);
    if (this.drawMode && e.button === 0) {
      this.dragging = true;
      this.startSx = sx;
      this.startSy = sy;
      this.curSx = sx;
      this.curSy = sy;
    } else {
      this.panning = true;
      this.panStartX = sx;
      this.panStartY = sy;
      this.canvas.style.cursor = "grabbing";
    }
  };

  private onPointerMove = (e: PointerEvent): void => {
    const [sx, sy] = this.localPoint(e);
    if (this.dragging) {
      this.curSx = sx;
      this.curSy = sy;
      this.render();
    } else if (this.panning) {
      this.tf.offsetX += sx - this.panStartX;
      this.tf.offsetY += sy - this.panStartY;
      this.panStartX = sx;
      this.panStartY = sy;
      this.render();
    }
  };

  private onPointerUp = (e: PointerEvent): void => {
    if (this.dragging) {
      this.dragging = false;
      const [ix0, iy0] = this.screenToImage(this.startSx, this.startSy);
      const [ix1, iy1] = this.screenToImage(this.curSx, this.curSy);
      const x = Math.min(ix0, ix1);
      const y = Math.min(iy0, iy1);
      const w = Math.abs(ix1 - ix0);
      const h = Math.abs(iy1 - iy0);
      this.render();
      if (this.onRegionDrawn) this.onRegionDrawn(x, y, w, h);
    }
    if (this.panning) {
      this.panning = false;
      this.canvas.style.cursor = this.drawMode ? "crosshair" : "grab";
    }
    if (this.canvas.hasPointerCapture(e.pointerId)) {
      this.canvas.releasePointerCapture(e.pointerId);
    }
  };
}
