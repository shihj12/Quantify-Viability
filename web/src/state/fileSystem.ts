// Folder access abstraction. Prefers the File System Access API (Chromium:
// read+write, enables in-place session resume); falls back to a read-only
// <input webkitdirectory> File[] source (Firefox/Safari), where session resume
// is load-a-file and export is a ZIP download.
//
// Mirrors image_io.scan_folder: supported extensions only, natural-sorted,
// non-recursive.

import { compareNatural } from "@/core/imageIo";
import { SESSION_SUFFIX } from "@/core/types";

export const SUPPORTED_EXTS = [".tif", ".tiff", ".jpg", ".jpeg", ".png"];

export const supportsFSA =
  typeof (globalThis as any).showDirectoryPicker === "function";

function hasSupportedExt(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTS.some((e) => lower.endsWith(e));
}

/** A single image file, resolved lazily so pixels load on demand. */
export interface ImageRef {
  name: string;
  getBlob(): Promise<Blob>;
}

/** A chosen folder; the unit a green/red channel maps onto. */
export interface DirectorySource {
  readonly name: string;
  readonly canWrite: boolean;
  /** Supported images directly in the folder, natural-sorted. */
  list(): Promise<ImageRef[]>;
  /** Existing `*.qviability.json` filename in the folder, or null. */
  findSession(): Promise<string | null>;
  readText(filename: string): Promise<string | null>;
  /** Returns false when the source can't write (caller falls back to download). */
  writeText(filename: string, text: string): Promise<boolean>;
}

// --- File System Access API source ----------------------------------------
class FsaDirectory implements DirectorySource {
  readonly canWrite = true;
  constructor(private handle: FileSystemDirectoryHandle) {}

  get name(): string {
    return this.handle.name;
  }

  async list(): Promise<ImageRef[]> {
    const refs: ImageRef[] = [];
    // @ts-expect-error: entries() is async-iterable but missing in older libdom.
    for await (const [name, h] of this.handle.entries()) {
      if (h.kind !== "file" || !hasSupportedExt(name)) continue;
      const fh = h as FileSystemFileHandle;
      refs.push({ name, getBlob: () => fh.getFile() });
    }
    refs.sort((a, b) => compareNatural(a.name, b.name));
    return refs;
  }

  async findSession(): Promise<string | null> {
    // @ts-expect-error: entries() async iterable
    for await (const [name, h] of this.handle.entries()) {
      if (h.kind === "file" && name.endsWith(SESSION_SUFFIX)) return name;
    }
    return null;
  }

  async readText(filename: string): Promise<string | null> {
    try {
      const fh = await this.handle.getFileHandle(filename);
      return await (await fh.getFile()).text();
    } catch {
      return null;
    }
  }

  async writeText(filename: string, text: string): Promise<boolean> {
    try {
      const fh = await this.handle.getFileHandle(filename, { create: true });
      const w = await fh.createWritable();
      await w.write(text);
      await w.close();
      return true;
    } catch {
      return false;
    }
  }
}

// --- webkitdirectory File[] source (read-only) ----------------------------
class FileListDirectory implements DirectorySource {
  readonly canWrite = false;
  readonly name: string;
  private files: File[];

  constructor(name: string, files: File[]) {
    this.name = name;
    this.files = files;
  }

  async list(): Promise<ImageRef[]> {
    return this.files
      .filter((f) => hasSupportedExt(f.name))
      .sort((a, b) => compareNatural(a.name, b.name))
      .map((f) => ({ name: f.name, getBlob: async () => f }));
  }

  async findSession(): Promise<string | null> {
    const f = this.files.find((f) => f.name.endsWith(SESSION_SUFFIX));
    return f ? f.name : null;
  }

  async readText(filename: string): Promise<string | null> {
    const f = this.files.find((f) => f.name === filename);
    return f ? f.text() : null;
  }

  async writeText(): Promise<boolean> {
    return false; // no write capability — caller downloads instead
  }
}

/** Open a folder picker (FSA). Returns null if the user cancels. */
export async function pickDirectoryFSA(): Promise<DirectorySource | null> {
  try {
    const handle = await (globalThis as any).showDirectoryPicker({
      mode: "readwrite",
    });
    return new FsaDirectory(handle);
  } catch (e) {
    if ((e as Error).name === "AbortError") return null;
    throw e;
  }
}

/**
 * Build a directory source from a webkitdirectory <input> File[]. Keeps only
 * files directly inside the chosen folder (non-recursive, like scan_folder).
 */
export function directoryFromFileList(files: File[]): DirectorySource | null {
  if (!files.length) return null;
  const first = (files[0] as any).webkitRelativePath as string | undefined;
  const root = first ? first.split("/")[0] : "folder";
  const direct = files.filter((f) => {
    const rel = (f as any).webkitRelativePath as string | undefined;
    if (!rel) return true;
    return rel.split("/").length === 2; // root/file only
  });
  return new FileListDirectory(root, direct);
}
