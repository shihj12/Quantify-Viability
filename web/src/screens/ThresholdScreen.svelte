<script lang="ts">
  // Threshold screen — per-image tuning. Left: the image with a translucent
  // overlay on the pixels currently counted positive. Right: readouts, a
  // draggable-line histogram, display brightness/contrast, and exclusion-box
  // tools. Mirrors qviability/ui/threshold_screen.py, including the keymap.

  import { onMount, onDestroy } from "svelte";
  import { ImageCanvas } from "@/render/ImageCanvas";
  import { Histogram } from "@/render/Histogram";
  import { grayToRgba, fillOverlay } from "@/render/overlayRender";
  import { toImageData } from "@/render/imageData";
  import { session } from "@/state/session.svelte";
  import { loadRaw, loadProcessed } from "@/state/imageCache";
  import { measure, exclusionMask, type Mask } from "@/core/measure";
  import { autoThreshold } from "@/core/autothreshold";
  import {
    autoStretch,
    applyDisplay,
    rawDisplay,
    bitDepthOf,
    maxValue,
  } from "@/core/imageIo";
  import { radiusFor, type RawImage } from "@/core/types";

  let canvasEl: HTMLCanvasElement;
  let histEl: HTMLCanvasElement;
  let imageCanvas: ImageCanvas | null = null;
  let histogram: Histogram | null = null;

  let raw: RawImage | null = null;
  let proc: RawImage | null = null;
  let base: Float32Array | null = null;
  let rawDisplayU8: Uint8Array | null = null;
  let excludeMask: Mask | null = null;
  let overlayBuf: Uint8ClampedArray | null = null;
  let baseBuf: Uint8ClampedArray | null = null;
  let imgW = 0;
  let imgH = 0;

  let undoStack: number[] = [];
  let fine = 1;
  let coarse = 10;
  let spaceHeld = false;
  let outline = $state(false);
  let drawMode = $state(false);
  let loading = $state(false);
  let loadError = $state("");

  let brightnessVal = $state(0); // slider units (-100..100)
  let contrastVal = $state(100); // slider units (10..400)

  let loadSeq = 0;
  let loadedPath: string | null = null;
  let ready = $state(false);

  const entry = $derived(session.current);
  const meas = $derived(entry?.measurement ?? null);
  const project = $derived(session.project);

  const fmtInt = (n: number) => Math.round(n).toLocaleString("en-US");

  function renderBase(): void {
    if (!base || !imageCanvas || !baseBuf || !entry) return;
    const disp = applyDisplay(base, entry.brightness, entry.contrast);
    grayToRgba(disp, baseBuf);
    imageCanvas.setBaseImageData(toImageData(baseBuf, imgW, imgH));
    imageCanvas.render();
  }

  function paintOverlay(threshold: number): void {
    if (!proc || !imageCanvas || !overlayBuf || !entry) return;
    fillOverlay(
      overlayBuf,
      proc.data,
      threshold,
      imgW,
      imgH,
      entry.channel,
      excludeMask,
      outline,
    );
    imageCanvas.setOverlayImageData(toImageData(overlayBuf, imgW, imgH));
    imageCanvas.render();
  }

  function setThreshold(value: number, pushUndo = true, method = "Manual"): void {
    if (!proc || !entry) return;
    const v = Math.max(0, Math.min(Math.trunc(value), entry.max_value));
    if (pushUndo && entry.threshold !== null) {
      undoStack.push(entry.threshold);
      if (undoStack.length > 200) undoStack = undoStack.slice(-200);
    }
    entry.threshold = v;
    entry.measurement = measure(proc.data, v, method, excludeMask);
    paintOverlay(v);
    histogram?.setThreshold(v);
  }

  function refreshOverlay(): void {
    if (!entry || entry.threshold === null) return;
    paintOverlay(entry.threshold);
  }

  async function loadCurrent(): Promise<void> {
    const e = session.current;
    if (!e || !imageCanvas || !histogram || !project) return;
    loadedPath = e.path;
    const seq = ++loadSeq;
    loadError = "";
    undoStack = [];

    const ref = session.refFor(e.path);
    if (!ref || e.missing) {
      loadError = `Could not load ${e.display_name}`;
      return;
    }

    loading = true;
    try {
      const radius = radiusFor(project, e.channel);
      const p = await loadProcessed(e.path, ref, project.subtract_background, radius);
      const r = await loadRaw(e.path, ref);
      if (seq !== loadSeq) return; // superseded by a newer navigation

      proc = p;
      raw = r;
      imgW = r.width;
      imgH = r.height;
      e.bit_depth = bitDepthOf(p.data);
      e.max_value = maxValue(p.data);
      e.width = r.width;
      e.height = r.height;
      fine = Math.max(1, Math.round(e.max_value / 255));
      coarse = fine * 10;

      base = autoStretch(p.data);
      rawDisplayU8 = rawDisplay(r.data, maxValue(r.data));
      excludeMask = exclusionMask(r.width, r.height, e.exclusions);
      histogram.setData(p.data, e.max_value);

      imageCanvas.setImage(imgW, imgH);
      overlayBuf = new Uint8ClampedArray(imgW * imgH * 4);
      baseBuf = new Uint8ClampedArray(imgW * imgH * 4);

      brightnessVal = Math.round(e.brightness * 100);
      contrastVal = Math.round(e.contrast * 100);
      spaceHeld = false;
      imageCanvas.setOverlayVisible(true);
      imageCanvas.setDrawMode(drawMode);

      renderBase();
      imageCanvas.fit();

      if (e.threshold === null) {
        e.auto_method = "MaxEntropy";
        const thr = autoThreshold(p.data, e.max_value, "MaxEntropy");
        setThreshold(thr, false, "MaxEntropy");
      } else {
        const method = e.measurement?.method ?? "Manual";
        setThreshold(e.threshold, false, method);
      }
    } catch (err) {
      if (seq === loadSeq) loadError = `Could not load image: ${(err as Error).message}`;
    } finally {
      if (seq === loadSeq) loading = false;
    }
  }

  // --- navigation ---------------------------------------------------------
  function nextUnfinished(): number | null {
    if (!project) return null;
    const imgs = project.images;
    const cur = project.current_index;
    for (let i = cur + 1; i < imgs.length; i++) if (!imgs[i].done) return i;
    for (let i = 0; i < cur; i++) if (!imgs[i].done) return i;
    return null;
  }

  function accept(): void {
    const e = session.current;
    if (!e || !raw) {
      next();
      return;
    }
    e.done = true;
    void session.autosave();
    if (session.returnToReview) {
      session.go("review");
      return;
    }
    const nxt = nextUnfinished();
    if (nxt === null) session.go("review");
    else if (project) project.current_index = nxt;
  }

  function next(): void {
    if (project && project.current_index < project.images.length - 1)
      project.current_index += 1;
  }
  function prev(): void {
    if (project && project.current_index > 0) project.current_index -= 1;
  }

  async function saveSession(): Promise<void> {
    const r = await session.saveSession();
    session.status =
      r === "saved"
        ? "Session saved."
        : r === "downloaded"
          ? "Session downloaded (this browser can't write in place)."
          : "";
  }

  function resetAuto(): void {
    if (!proc || !entry) return;
    entry.auto_method = "MaxEntropy";
    const v = autoThreshold(proc.data, entry.max_value, "MaxEntropy");
    setThreshold(v, true, "MaxEntropy");
  }

  function undo(): void {
    if (undoStack.length) setThreshold(undoStack.pop()!, false);
  }

  function onBrightContrast(): void {
    if (!entry) return;
    entry.brightness = brightnessVal / 100;
    entry.contrast = contrastVal / 100;
    if (!spaceHeld) renderBase();
  }
  function resetDisplay(): void {
    brightnessVal = 0;
    contrastVal = 100;
    onBrightContrast();
  }
  function toggleOutline(): void {
    outline = !outline;
    if (!spaceHeld) refreshOverlay();
  }

  function showRaw(on: boolean): void {
    if (!raw || !imageCanvas || !baseBuf || !rawDisplayU8) return;
    spaceHeld = on;
    if (on) {
      grayToRgba(rawDisplayU8, baseBuf);
      imageCanvas.setBaseImageData(toImageData(baseBuf, imgW, imgH));
      imageCanvas.setOverlayVisible(false);
    } else {
      renderBase();
      refreshOverlay();
      imageCanvas.setOverlayVisible(true);
    }
  }

  // --- exclusions ---------------------------------------------------------
  function onRegionDrawn(x: number, y: number, w: number, h: number): void {
    if (!raw || !entry) return;
    const iw = raw.width;
    const ih = raw.height;
    const x0 = Math.max(0, Math.min(Math.round(x), iw));
    const y0 = Math.max(0, Math.min(Math.round(y), ih));
    const x1 = Math.max(0, Math.min(Math.round(x + w), iw));
    const y1 = Math.max(0, Math.min(Math.round(y + h), ih));
    const bw = x1 - x0;
    const bh = y1 - y0;
    if (bw < 3 || bh < 3) return;
    entry.exclusions.push([x0, y0, bw, bh]);
    refreshExclusions();
  }
  function refreshExclusions(): void {
    if (!raw || !entry) return;
    excludeMask = exclusionMask(raw.width, raw.height, entry.exclusions);
    const method = entry.measurement?.method ?? "Manual";
    setThreshold(entry.threshold ?? 0, false, method);
  }
  function toggleDraw(): void {
    drawMode = !drawMode;
    imageCanvas?.setDrawMode(drawMode);
  }
  function undoBox(): void {
    if (entry && entry.exclusions.length) {
      entry.exclusions.pop();
      refreshExclusions();
    }
  }
  function clearBoxes(): void {
    if (entry && entry.exclusions.length) {
      entry.exclusions = [];
      refreshExclusions();
    }
  }
  async function applyToAll(): Promise<void> {
    if (!project || !entry) return;
    const boxes = entry.exclusions.map((b) => [...b] as [number, number, number, number]);
    const others = project.images.filter((e) => e !== entry);
    if (others.length === 0) return;
    const msg = boxes.length
      ? `Apply the current ${boxes.length} box(es) to all ${project.images.length} images?\n\nThis replaces any exclusion boxes already on the other images.`
      : `The current image has no exclusion boxes.\n\nRemove exclusion boxes from all other ${others.length} images?`;
    if (!window.confirm(msg)) return;

    for (const o of others) o.exclusions = boxes.map((b) => [...b]);
    const toRecompute = others.filter((o) => o.threshold !== null);
    let done = 0;
    for (const o of toRecompute) {
      const ref = session.refFor(o.path);
      if (!ref) continue;
      try {
        const img = await loadProcessed(
          o.path,
          ref,
          project.subtract_background,
          radiusFor(project, o.channel),
        );
        const mask = exclusionMask(img.width, img.height, o.exclusions);
        const method = o.measurement?.method ?? "Manual";
        o.measurement = measure(img.data, o.threshold!, method, mask);
      } catch {
        // skip unreadable images
      }
      session.status = `Updating measurements… ${++done}/${toRecompute.length}`;
    }
    void session.autosave();
    session.status = boxes.length
      ? `Applied boxes to ${others.length} other image(s).`
      : `Cleared boxes from ${others.length} other image(s).`;
  }

  // --- keymap -------------------------------------------------------------
  function onKeyDown(ev: KeyboardEvent): void {
    if (session.screen !== "threshold") return;
    // Only text-entry fields swallow the keymap; range sliders / checkboxes /
    // buttons do not (the panel keeps focus off buttons, mirroring the desktop's
    // NoFocus policy, so arrows + Enter always tune the current image).
    const ae = document.activeElement as HTMLElement | null;
    if (
      ae &&
      (ae.tagName === "TEXTAREA" ||
        (ae.tagName === "INPUT" &&
          !["range", "checkbox"].includes((ae as HTMLInputElement).type)))
    )
      return;
    if (loading || !entry) return;
    const coarseMod = ev.shiftKey;
    const step = coarseMod ? coarse : fine;
    switch (ev.key) {
      case "ArrowUp":
        ev.preventDefault();
        setThreshold((entry.threshold ?? 0) + step);
        break;
      case "ArrowDown":
        ev.preventDefault();
        setThreshold((entry.threshold ?? 0) - step);
        break;
      case "PageUp":
        ev.preventDefault();
        setThreshold((entry.threshold ?? 0) + coarse);
        break;
      case "PageDown":
        ev.preventDefault();
        setThreshold((entry.threshold ?? 0) - coarse);
        break;
      case "Enter":
        ev.preventDefault();
        accept();
        break;
      case "ArrowLeft":
        ev.preventDefault();
        prev();
        break;
      case "ArrowRight":
        ev.preventDefault();
        next();
        break;
      case "z":
      case "Z":
        if (ev.ctrlKey || ev.metaKey) {
          ev.preventDefault();
          undo();
        }
        break;
      case "r":
      case "R":
        resetAuto();
        break;
      case "o":
      case "O":
        toggleOutline();
        break;
      case " ":
        if (!ev.repeat) {
          ev.preventDefault();
          showRaw(true);
        }
        break;
    }
  }
  function onKeyUp(ev: KeyboardEvent): void {
    if (ev.key === " " && spaceHeld) showRaw(false);
  }

  // Mirror the desktop's NoFocus panel: clicking a button must not steal
  // keyboard focus, so arrows/Enter/Space keep tuning the current image.
  // preventDefault on mousedown suppresses focusing while still firing onclick.
  function keepFocusOffButtons(ev: MouseEvent): void {
    if ((ev.target as HTMLElement | null)?.closest("button")) ev.preventDefault();
  }

  onMount(() => {
    imageCanvas = new ImageCanvas(canvasEl);
    imageCanvas.onRegionDrawn = onRegionDrawn;
    histogram = new Histogram(histEl);
    histogram.onThresholdChange = (v) => setThreshold(v);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    ready = true; // flips the load effect on, now that the canvases exist
  });

  onDestroy(() => {
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("keyup", onKeyUp);
    imageCanvas?.destroy();
    histogram?.destroy();
  });

  // Single load trigger: fires once the canvases are ready, then again whenever
  // the visible image changes (prev/next, or retune-from-review while mounted).
  $effect(() => {
    const path = session.current?.path;
    if (ready && session.screen === "threshold" && path && path !== loadedPath) {
      void loadCurrent();
    }
  });
</script>

<div class="threshold">
  <div class="canvaswrap">
    <canvas bind:this={canvasEl}></canvas>
    {#if loadError}<div class="overlaymsg error">{loadError}</div>{/if}
    {#if loading}<div class="overlaymsg">Loading…</div>{/if}
  </div>

  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <!-- mousedown keeps focus off panel buttons so the global tuning keymap
       (arrows/Enter/Space) is never swallowed — mirrors the desktop NoFocus panel. -->
  <aside class="panel" onmousedown={keepFocusOffButtons}>
    <div class="file">{entry?.display_name ?? "—"}</div>
    <div class="chan">Channel: {entry?.channel ?? ""}</div>
    {#if project?.subtract_background}
      <div class="bg">✓ background subtracted (rolling ball)</div>
    {/if}

    <div class="thr">
      Threshold: {entry?.threshold ?? "—"} / {entry?.max_value ?? "—"}
    </div>
    <button onclick={resetAuto}>Reset to auto-threshold</button>

    <fieldset>
      <legend>Measurements</legend>
      <div class="grid">
        <span>Positive pixels:</span>
        <span class="num">{meas ? fmtInt(meas.positive_pixels) : "—"}</span>
        <span>Positive area %:</span>
        <span class="num">{meas ? meas.positive_area_pct.toFixed(2) + " %" : "—"}</span>
        <span>Mean intensity:</span>
        <span class="num">{meas ? meas.mean_intensity_positive.toFixed(1) : "—"}</span>
        <span>Integrated intensity:</span>
        <span class="num integ">{meas ? fmtInt(meas.integrated_intensity) : "—"}</span>
      </div>
    </fieldset>

    <fieldset>
      <legend>Histogram (drag the red line)</legend>
      <canvas class="hist" bind:this={histEl}></canvas>
    </fieldset>

    <fieldset>
      <legend>Display (does not affect measurement)</legend>
      <label class="slider">
        Brightness
        <input
          type="range"
          min="-100"
          max="100"
          bind:value={brightnessVal}
          oninput={onBrightContrast}
          onpointerup={(e) => (e.currentTarget as HTMLInputElement).blur()}
        />
      </label>
      <label class="slider">
        Contrast
        <input
          type="range"
          min="10"
          max="400"
          bind:value={contrastVal}
          oninput={onBrightContrast}
          onpointerup={(e) => (e.currentTarget as HTMLInputElement).blur()}
        />
      </label>
      <button onclick={resetDisplay}>Reset display</button>
      <label class="check">
        <input type="checkbox" checked={outline} onchange={toggleOutline} />
        Highlight marked regions (O)
      </label>
    </fieldset>

    <fieldset>
      <legend>Exclude regions (e.g. scale bars)</legend>
      <button class:active={drawMode} onclick={toggleDraw}>
        {drawMode ? "Drawing… (click-drag on image)" : "Draw exclusion box"}
      </button>
      <div class="excl-btns">
        <button onclick={undoBox}>Undo box</button>
        <button onclick={clearBoxes}>Clear boxes</button>
      </div>
      <button onclick={applyToAll}>Apply boxes to all images</button>
      <div class="excl-info">
        {#if entry && entry.exclusions.length}
          {entry.exclusions.length} exclusion box(es) — not counted
        {:else}
          No exclusion boxes
        {/if}
      </div>
    </fieldset>

    <div class="progress">
      Image {(project?.current_index ?? 0) + 1} / {project?.images.length ?? 0} ·
      {session.doneCount()} accepted
    </div>

    <div class="nav">
      <button onclick={prev}>◀ Prev</button>
      <button onclick={next}>Next ▶</button>
    </div>
    <button class="accept" onclick={accept}>
      {entry?.done ? "Accepted ✓ — Enter for next" : "Accept (Enter)"}
    </button>
    <div class="nav">
      <button onclick={saveSession}>Save</button>
      <button onclick={() => session.go("review")}>Go to Review</button>
    </div>

    <p class="help">
      ↑/↓ tune · Shift or PageUp/Dn = coarse · Enter = accept · ←/→ navigate · R =
      reset auto · O = highlight marks · Ctrl+Z = undo · hold Space = original
      image
    </p>
    {#if session.status}<p class="savemsg">{session.status}</p>{/if}
  </aside>
</div>

<style>
  .threshold {
    display: flex;
    height: 100vh;
    width: 100vw;
    overflow: hidden;
  }
  .canvaswrap {
    position: relative;
    flex: 1;
    min-width: 0;
    background: #1a1a1a;
  }
  canvas {
    width: 100%;
    height: 100%;
    display: block;
    touch-action: none;
  }
  .overlaymsg {
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(0, 0, 0, 0.7);
    padding: 6px 12px;
    border-radius: 6px;
    color: #ddd;
    font-size: 0.85rem;
  }
  .overlaymsg.error {
    color: #ff8a8a;
  }
  .panel {
    width: 360px;
    flex: none;
    overflow-y: auto;
    padding: 14px;
    background: #16161c;
    border-left: 1px solid #2a2a2a;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .file {
    font-weight: 700;
    font-size: 0.95rem;
    word-break: break-all;
  }
  .chan {
    color: #ccc;
    font-size: 0.85rem;
  }
  .bg {
    color: #6cae6c;
    font-size: 0.78rem;
  }
  .thr {
    font-size: 1.4rem;
    font-weight: 700;
    color: #ff7777;
  }
  fieldset {
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 8px 10px;
    margin: 0;
  }
  legend {
    padding: 0 5px;
    font-size: 0.8rem;
    color: #aaa;
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 4px 8px;
    font-size: 0.85rem;
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .integ {
    font-weight: 700;
    color: #ffd966;
  }
  canvas.hist {
    width: 100%;
    height: 120px;
    display: block;
    touch-action: none;
  }
  .slider {
    display: grid;
    grid-template-columns: 80px 1fr;
    align-items: center;
    font-size: 0.82rem;
    color: #bbb;
    margin-bottom: 4px;
  }
  .slider input {
    width: 100%;
  }
  .check {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 0.82rem;
    color: #bbb;
    margin-top: 6px;
  }
  .excl-btns {
    display: flex;
    gap: 8px;
    margin: 6px 0;
  }
  .excl-btns button {
    flex: 1;
  }
  .excl-info {
    color: #aaa;
    font-size: 0.78rem;
    margin-top: 4px;
  }
  .progress {
    text-align: center;
    color: #ccc;
    font-size: 0.85rem;
    margin-top: 4px;
  }
  .nav {
    display: flex;
    gap: 8px;
  }
  .nav button {
    flex: 1;
  }
  button {
    background: #2c2c3a;
    color: #eee;
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    padding: 7px 12px;
    cursor: pointer;
    font-size: 0.85rem;
    width: 100%;
  }
  button:hover {
    background: #353548;
  }
  button.active {
    background: #4a6a2f;
    border-color: #5f8a3a;
  }
  button.accept {
    font-weight: 700;
    background: #2f5d7d;
    border-color: #2f5d7d;
  }
  .help {
    color: #888;
    font-size: 0.72rem;
    line-height: 1.5;
  }
  .savemsg {
    color: #6cae6c;
    font-size: 0.78rem;
  }
</style>
