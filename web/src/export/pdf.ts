// QC PDF export — port of qviability/export/pdf.py.
//
// One landscape page per tuned image: the plain image ("Before") beside the
// marked version ("After"), with a header and panel labels. Built with pdf-lib
// using a bundled DejaVuSans font (so glyphs render without relying on viewer
// fonts). Before/after panels reuse the float-blend renderer in annotate.ts.

import { PDFDocument, rgb, type PDFFont, type PDFImage } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import type { ImageEntry, Project, RawImage } from "@/core/types";
import {
  renderDisplayRgb,
  renderOverlayRgb,
  rgbToCanvas,
  canvasToPngBlob,
  type RgbImage,
} from "./annotate";

const PAGE_W = 1500;
const PAGE_H = 1060;
const MARGIN = 40;
const GUTTER = 28;
const HEADER_H = 84;
const LABEL_H = 32;

const INK = rgb(20 / 255, 20 / 255, 20 / 255);
const SUBINK = rgb(95 / 255, 95 / 255, 95 / 255);
const PANEL_BG = rgb(24 / 255, 24 / 255, 24 / 255);
const PANEL_BORDER = rgb(170 / 255, 170 / 255, 170 / 255);

export interface QcItem {
  entry: ImageEntry;
  raw: RawImage;
}

function fmtInt(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

/** Downscale (never upscale) an RgbImage to fit box, return PNG bytes + draw size. */
async function panelPng(
  img: RgbImage,
  boxW: number,
  boxH: number,
): Promise<{ bytes: Uint8Array; w: number; h: number }> {
  const scale = Math.min(1, boxW / img.width, boxH / img.height);
  const w = Math.max(1, Math.round(img.width * scale));
  const h = Math.max(1, Math.round(img.height * scale));
  const src = rgbToCanvas(img);
  const dst = document.createElement("canvas");
  dst.width = w;
  dst.height = h;
  const ctx = dst.getContext("2d")!;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, 0, 0, w, h);
  const blob = await canvasToPngBlob(dst);
  return { bytes: new Uint8Array(await blob.arrayBuffer()), w, h };
}

async function loadFontBytes(): Promise<ArrayBuffer> {
  const url = `${import.meta.env.BASE_URL}fonts/DejaVuSans.ttf`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load PDF font (${res.status})`);
  return res.arrayBuffer();
}

async function renderPage(
  doc: PDFDocument,
  font: PDFFont,
  project: Project,
  item: QcItem,
): Promise<void> {
  const { entry, raw } = item;
  const before = renderDisplayRgb(raw, entry.brightness, entry.contrast);
  const after = renderOverlayRgb(
    raw,
    entry.threshold ?? 0,
    entry.channel,
    entry.brightness,
    entry.contrast,
    entry.exclusions,
  );

  const page = doc.addPage([PAGE_W, PAGE_H]);
  // White background.
  page.drawRectangle({ x: 0, y: 0, width: PAGE_W, height: PAGE_H, color: rgb(1, 1, 1) });

  const top = (yFromTop: number) => PAGE_H - yFromTop;

  // Header.
  page.drawText(entry.display_name, {
    x: MARGIN,
    y: top(MARGIN + 30),
    size: 30,
    font,
    color: INK,
  });
  const m = entry.measurement;
  const parts = [entry.channel, `threshold ${entry.threshold}`];
  if (m) {
    parts.push(`positive area ${m.positive_area_pct.toFixed(2)}%`);
    parts.push(`integrated intensity ${fmtInt(m.integrated_intensity)}`);
  }
  if (project.subtract_background) parts.push("background subtracted");
  page.drawText(parts.join("     "), {
    x: MARGIN,
    y: top(MARGIN + 40 + 20),
    size: 20,
    font,
    color: SUBINK,
  });

  const panelTop = MARGIN + HEADER_H + LABEL_H;
  const panelH = PAGE_H - panelTop - MARGIN;
  const panelW = Math.floor((PAGE_W - 2 * MARGIN - GUTTER) / 2);

  const labels = ["Before  (original)", "After  (marked = counted)"];
  const imgs = [before, after];
  for (let i = 0; i < 2; i++) {
    const x0 = MARGIN + i * (panelW + GUTTER);
    page.drawText(labels[i], {
      x: x0,
      y: top(MARGIN + HEADER_H + 22),
      size: 22,
      font,
      color: INK,
    });
    // Panel background.
    page.drawRectangle({
      x: x0,
      y: top(panelTop + panelH),
      width: panelW,
      height: panelH,
      color: PANEL_BG,
    });
    // Scaled image, centered.
    const { bytes, w, h } = await panelPng(imgs[i], panelW, panelH);
    const png: PDFImage = await doc.embedPng(bytes);
    const ox = (panelW - w) / 2;
    const oy = (panelH - h) / 2;
    page.drawImage(png, {
      x: x0 + ox,
      y: top(panelTop + oy + h),
      width: w,
      height: h,
    });
    // Border.
    page.drawRectangle({
      x: x0,
      y: top(panelTop + panelH),
      width: panelW,
      height: panelH,
      borderColor: PANEL_BORDER,
      borderWidth: 1,
    });
  }
}

/** Build the multi-page QC PDF. Returns null when there are no tuned items. */
export async function buildPdf(
  project: Project,
  items: QcItem[],
): Promise<Uint8Array | null> {
  if (items.length === 0) return null;
  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  const font = await doc.embedFont(await loadFontBytes());
  for (const item of items) {
    if (item.entry.threshold === null) continue;
    await renderPage(doc, font, project, item);
  }
  return doc.save();
}
