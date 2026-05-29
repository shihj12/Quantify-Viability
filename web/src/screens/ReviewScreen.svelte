<script lang="ts">
  // Review screen — a 4-column gallery of annotated thumbnails for a final
  // double-check. Untuned images get a red border; clicking a card jumps back to
  // re-tune it (returning to review on accept). Export writes the workbook,
  // annotated PNGs and QC PDF. Mirrors qviability/ui/review_screen.py.

  import { session } from "@/state/session.svelte";
  import { loadProcessed } from "@/state/imageCache";
  import { radiusFor, type ImageEntry } from "@/core/types";
  import { renderThumbnail } from "@/render/thumbnail";

  const project = $derived(session.project);

  interface Thumb {
    url: string | null;
    error: boolean;
  }
  let thumbs = $state<Record<number, Thumb>>({});
  let exporting = $state(false);
  let exportMsg = $state("");
  let progress = $state<{ done: number; total: number; label: string } | null>(null);

  const fmtInt = (n: number) => Math.round(n).toLocaleString("en-US");

  function signatureOf(e: ImageEntry): string {
    return JSON.stringify([
      e.threshold,
      Math.round(e.brightness * 1000) / 1000,
      Math.round(e.contrast * 1000) / 1000,
      e.exclusions,
      project?.subtract_background,
      radiusFor(project!, e.channel),
    ]);
  }
  let renderedSig: Record<number, string> = {};

  async function buildThumbs(): Promise<void> {
    if (!project) return;
    for (let i = 0; i < project.images.length; i++) {
      const e = project.images[i];
      const sig = signatureOf(e);
      if (renderedSig[i] === sig && thumbs[i]?.url) continue;
      const ref = session.refFor(e.path);
      if (!ref || e.missing) {
        thumbs[i] = { url: null, error: true };
        continue;
      }
      try {
        const img = await loadProcessed(
          e.path,
          ref,
          project.subtract_background,
          radiusFor(project, e.channel),
        );
        const threshold = e.threshold ?? 1_000_000_000;
        const url = renderThumbnail(
          img,
          threshold,
          e.channel,
          e.brightness,
          e.contrast,
          e.exclusions,
        );
        thumbs[i] = { url, error: false };
        renderedSig[i] = sig;
      } catch {
        thumbs[i] = { url: null, error: true };
      }
    }
  }

  function retune(index: number): void {
    session.openThreshold(index, true);
  }

  async function onExport(): Promise<void> {
    if (!project || exporting) return;
    const notTuned = project.images.filter((e) => e.threshold === null).length;
    if (notTuned > 0) {
      const ok = window.confirm(
        `${notTuned} image(s) have no threshold yet and will be exported with blank values. Export anyway?`,
      );
      if (!ok) return;
    }
    exporting = true;
    exportMsg = "";
    progress = { done: 0, total: 1, label: "Starting…" };
    try {
      // Lazily pull in the heavy export libs (exceljs, pdf-lib, fflate) only
      // when the user actually exports, keeping the initial bundle small.
      const { runExport } = await import("@/export/runExport");
      const outcome = await runExport(project, (done, total, label) => {
        progress = { done, total, label };
      });
      if (outcome.result.mode === "cancelled") {
        exportMsg = "Export cancelled.";
      } else if (outcome.result.mode === "folder") {
        exportMsg = `Wrote viability_results.xlsx, viability_QC.pdf, and ${outcome.pngCount} annotated image(s) to “${outcome.result.folderName}”.`;
      } else {
        exportMsg = `Downloaded ${outcome.result.filename} (workbook, QC PDF, and ${outcome.pngCount} annotated images).`;
      }
    } catch (e) {
      exportMsg = `Export failed: ${(e as Error).message}`;
    } finally {
      exporting = false;
      progress = null;
    }
  }

  $effect(() => {
    if (session.screen === "review" && project) void buildThumbs();
  });

  const notDone = $derived(project ? project.images.filter((e) => !e.done).length : 0);
</script>

<div class="review">
  <header>
    <h1>Review — double-check every image</h1>
    <p class="status">
      {#if project}
        {project.images.length} images · {project.images.length - notDone} accepted ·
        {#if notDone}{notDone} still need a threshold (red border){:else}all accepted ✓{/if}
      {/if}
    </p>
  </header>

  <div class="grid">
    {#if project}
      {#each project.images as entry, i (entry.path)}
        <button
          class="card"
          class:untuned={!entry.done}
          onclick={() => retune(i)}
          title="Click to re-tune"
        >
          <div class="thumb">
            {#if thumbs[i]?.url}
              <img src={thumbs[i].url} alt={entry.display_name} />
            {:else if thumbs[i]?.error}
              <span class="muted">(could not load)</span>
            {:else}
              <span class="muted">…</span>
            {/if}
          </div>
          <div class="name">{entry.display_name}</div>
          <div class="info">
            {#if entry.measurement}
              {entry.channel} · thr {entry.threshold}<br />
              area {entry.measurement.positive_area_pct.toFixed(2)}% · int.intensity
              {fmtInt(entry.measurement.integrated_intensity)}
            {:else}
              {entry.channel} · not tuned yet
            {/if}
          </div>
        </button>
      {/each}
    {/if}
  </div>

  <footer>
    <button onclick={() => session.go("threshold")}>◀ Back to tuning</button>
    <span class="spacer"></span>
    {#if progress}
      <span class="prog">{progress.label} ({progress.done}/{progress.total})</span>
    {/if}
    {#if exportMsg}<span class="msg">{exportMsg}</span>{/if}
    <button class="export" disabled={exporting} onclick={onExport}>
      {exporting ? "Exporting…" : "Export results ▶"}
    </button>
  </footer>
</div>

<style>
  .review {
    display: flex;
    flex-direction: column;
    height: 100vh;
    padding: 16px 20px;
    box-sizing: border-box;
  }
  header h1 {
    font-size: 1.3rem;
  }
  .status {
    color: #aaa;
    font-size: 0.85rem;
    margin-top: 4px;
  }
  .grid {
    flex: 1;
    overflow-y: auto;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    padding: 12px 2px;
    align-content: start;
  }
  .card {
    background: #16161c;
    border: 1px solid #555;
    border-radius: 8px;
    padding: 6px;
    cursor: pointer;
    text-align: left;
    color: #eee;
    font: inherit;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .card.untuned {
    border: 2px solid #d9534f;
  }
  .card:hover {
    background: #1d1d28;
  }
  .thumb {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 150px;
    background: #0e0e12;
    border-radius: 4px;
    overflow: hidden;
  }
  .thumb img {
    max-width: 100%;
    height: auto;
    display: block;
  }
  .muted {
    color: #666;
    font-size: 0.8rem;
  }
  .name {
    font-weight: 700;
    font-size: 0.78rem;
    word-break: break-all;
  }
  .info {
    font-size: 0.74rem;
    color: #ccc;
    line-height: 1.4;
  }
  footer {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 12px;
    border-top: 1px solid #2a2a2a;
  }
  .spacer {
    flex: 1;
  }
  .prog {
    color: #9ab;
    font-size: 0.82rem;
  }
  .msg {
    color: #6cae6c;
    font-size: 0.82rem;
    max-width: 50%;
  }
  button {
    background: #2c2c3a;
    color: #eee;
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    padding: 8px 16px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  button:hover {
    background: #353548;
  }
  button.export {
    font-weight: 700;
    background: #2f5d7d;
    border-color: #2f5d7d;
  }
  button.export:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
