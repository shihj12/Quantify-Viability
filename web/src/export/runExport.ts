// Export orchestration — assemble the annotated PNGs, the QC PDF, and the
// results workbook, then deliver them (FSA folder write or ZIP download).
// Mirrors ReviewScreen._run_export in the desktop app.

import type { Project, RawImage } from "@/core/types";
import { radiusFor } from "@/core/types";
import { loadProcessed } from "@/state/imageCache";
import { session } from "@/state/session.svelte";
import { renderAnnotatedPng } from "./annotate";
import { buildXlsx } from "./excel";
import { buildPdf, type QcItem } from "./pdf";
import {
  type ExportFile,
  type DeliveryResult,
  zipAndDownload,
} from "./bundle";

export type DeliveryResultEx = DeliveryResult;

const fmtInt = (n: number) => Math.round(n).toLocaleString("en-US");

function stemOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}

export interface ExportProgress {
  (done: number, total: number, label: string): void;
}

export interface ExportOutcome {
  result: DeliveryResultEx;
  pngCount: number;
  pdfPages: number;
}

/**
 * Run the full export. The assembled bundle (annotated PNGs, QC PDF, results
 * workbook) is always delivered as a single ZIP via the browser's native
 * download — no File System Access permission prompt.
 */
export async function runExport(
  project: Project,
  onProgress: ExportProgress = () => {},
): Promise<ExportOutcome> {
  const images = project.images;
  const tuned = images.filter((e) => e.threshold !== null);
  const total = images.length + tuned.length + 1;
  let step = 0;

  const files: ExportFile[] = [];
  const procCacheById = new Map<string, RawImage>();

  async function procFor(path: string, channel: string): Promise<RawImage | null> {
    if (procCacheById.has(path)) return procCacheById.get(path)!;
    const ref = session.refFor(path);
    if (!ref) return null;
    try {
      const img = await loadProcessed(
        path,
        ref,
        project.subtract_background,
        radiusFor(project, channel),
      );
      procCacheById.set(path, img);
      return img;
    } catch {
      return null;
    }
  }

  // 1. Annotated PNGs.
  for (const entry of images) {
    onProgress(step++, total, "Rendering annotated images…");
    if (entry.threshold === null) continue;
    const img = await procFor(entry.path, entry.channel);
    if (!img) continue;
    const m = entry.measurement;
    const caption = m
      ? `${entry.display_name}  |  ${entry.channel}  |  thr ${entry.threshold}  |  area ${m.positive_area_pct.toFixed(2)}%  |  int ${fmtInt(m.integrated_intensity)}`
      : `${entry.display_name}  |  ${entry.channel}`;
    const blob = await renderAnnotatedPng(
      img,
      entry.threshold,
      entry.channel,
      caption,
      entry.brightness,
      entry.contrast,
      entry.exclusions,
    );
    files.push({
      path: `annotated/${stemOf(entry.display_name)}_thr${entry.threshold}.png`,
      data: new Uint8Array(await blob.arrayBuffer()),
    });
  }

  // 2. QC PDF (one before/after page per tuned image).
  const qcItems: QcItem[] = [];
  for (const entry of tuned) {
    onProgress(step++, total, "Building QC PDF…");
    const img = await procFor(entry.path, entry.channel);
    if (img) qcItems.push({ entry, raw: img });
  }
  const pdfBytes = await buildPdf(project, qcItems);
  if (pdfBytes) files.push({ path: "viability_QC.pdf", data: pdfBytes });

  // 3. Results workbook.
  onProgress(step++, total, "Writing spreadsheet…");
  files.push({ path: "viability_results.xlsx", data: await buildXlsx(project) });

  onProgress(total, total, "Delivering…");

  zipAndDownload(files);
  const result: DeliveryResultEx = { mode: "zip", filename: "viability_export.zip" };

  return { result, pngCount: files.filter((f) => f.path.endsWith(".png")).length, pdfPages: qcItems.length };
}
