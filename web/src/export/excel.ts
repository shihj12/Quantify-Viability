// Results workbook — port of qviability/export/excel.py.
//
// One row per image: the four desktop columns, sorted by channel then natural
// filename. Built with exceljs and returned as bytes for FSA write or ZIP.

import ExcelJS from "exceljs";
import type { Project } from "@/core/types";
import { compareNatural } from "@/core/imageIo";

export const COLUMNS = [
  "Filename",
  "Channel",
  "Positive pixels",
  "% above threshold",
] as const;

interface Row {
  filename: string;
  channel: string;
  positivePixels: number | null;
  pctAbove: number | null;
}

function rowsFor(project: Project): Row[] {
  const rows: Row[] = project.images.map((e) => {
    const m = e.measurement;
    return {
      filename: e.display_name,
      channel: e.channel,
      positivePixels: m ? m.positive_pixels : null,
      // round(x, 4) — matches pandas round on positive_area_pct.
      pctAbove: m ? Math.round(m.positive_area_pct * 1e4) / 1e4 : null,
    };
  });
  rows.sort((a, b) => {
    if (a.channel !== b.channel) return a.channel < b.channel ? -1 : 1;
    return compareNatural(a.filename, b.filename);
  });
  return rows;
}

export async function buildXlsx(project: Project): Promise<Uint8Array> {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("Sheet1");
  ws.addRow([...COLUMNS]);
  for (const r of rowsFor(project)) {
    ws.addRow([r.filename, r.channel, r.positivePixels, r.pctAbove]);
  }
  const buf = await wb.xlsx.writeBuffer();
  return new Uint8Array(buf as ArrayBuffer);
}
