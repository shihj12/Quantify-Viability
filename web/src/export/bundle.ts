// Export delivery: write result files into a user-chosen output directory via
// the File System Access API, or fall back to a single ZIP download (fflate).
//
// The directory picker must be requested *inside* the user gesture, before the
// (async) rendering work, or the browser invalidates the activation — so the
// API is split: pickOutputDir() up front, then writeFiles() once rendering is
// done. Browsers without writable dir access use zipAndDownload().

import { zipSync, type Zippable } from "fflate";

export interface ExportFile {
  /** Relative path inside the output folder, e.g. "annotated/foo.png". */
  path: string;
  data: Uint8Array;
}

export type DeliveryResult =
  | { mode: "folder"; folderName: string }
  | { mode: "zip"; filename: string }
  | { mode: "cancelled" };

export const supportsDirWrite =
  typeof (globalThis as { showDirectoryPicker?: unknown }).showDirectoryPicker ===
  "function";

/** Prompt for a writable output directory. Returns null if the user cancels. */
export async function pickOutputDir(): Promise<FileSystemDirectoryHandle | null> {
  try {
    return await (
      globalThis as unknown as {
        showDirectoryPicker: (o?: {
          mode?: string;
        }) => Promise<FileSystemDirectoryHandle>;
      }
    ).showDirectoryPicker({ mode: "readwrite" });
  } catch (e) {
    if ((e as Error).name === "AbortError") return null;
    throw e;
  }
}

async function writeInto(
  dir: FileSystemDirectoryHandle,
  path: string,
  data: Uint8Array,
): Promise<void> {
  const parts = path.split("/");
  const filename = parts.pop()!;
  let cur = dir;
  for (const seg of parts) {
    cur = await cur.getDirectoryHandle(seg, { create: true });
  }
  const fh = await cur.getFileHandle(filename, { create: true });
  const w = await fh.createWritable();
  await w.write(new Blob([data.slice().buffer]));
  await w.close();
}

export async function writeFiles(
  dir: FileSystemDirectoryHandle,
  files: ExportFile[],
): Promise<void> {
  for (const f of files) await writeInto(dir, f.path, f.data);
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function zipAndDownload(
  files: ExportFile[],
  zipName = "viability_export.zip",
): void {
  const tree: Zippable = {};
  for (const f of files) tree[f.path] = f.data;
  const zipped = zipSync(tree, { level: 6 });
  triggerDownload(new Blob([zipped.buffer], { type: "application/zip" }), zipName);
}

/** Download arbitrary text as a file (session JSON when not writable in place). */
export function downloadText(text: string, filename: string): void {
  triggerDownload(new Blob([text], { type: "application/json" }), filename);
}
