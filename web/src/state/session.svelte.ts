// Central app state (Svelte 5 runes): the current Project, which screen is
// showing, and session persistence. Mirrors the desktop MainWindow's ownership
// of the project plus app.py's autosave / resume behaviour.
//
// The Project model is snake_case and JSON-serializable, so the session file
// interops structurally with the desktop's *.qviability.json. Pixel access goes
// through `registry` (entry.path -> ImageRef), rebuilt whenever folders are
// (re)picked, since the browser has no persistent filesystem paths.

import type { Project } from "@/core/types";
import { SESSION_SUFFIX } from "@/core/types";
import type { DirectorySource, ImageRef } from "./fileSystem";
import { clearImageCache } from "./imageCache";

export type Screen = "load" | "threshold" | "review" | "howto" | "about";

class SessionStore {
  screen = $state<Screen>("load");
  project = $state<Project | null>(null);
  /** When true, accepting on the threshold screen returns to review. */
  returnToReview = $state(false);
  status = $state("");
  /** Bumped after every autosave so screens can show a "saved" hint. */
  savedTick = $state(0);

  // Non-reactive plumbing.
  registry = new Map<string, ImageRef>();
  greenDir: DirectorySource | null = null;
  redDir: DirectorySource | null = null;
  sessionDir: DirectorySource | null = null;
  sessionFilename: string | null = null;

  refFor(path: string): ImageRef | undefined {
    return this.registry.get(path);
  }

  get current() {
    const p = this.project;
    if (!p || p.images.length === 0) return null;
    return p.images[p.current_index] ?? null;
  }

  doneCount(): number {
    return this.project?.images.filter((e) => e.done).length ?? 0;
  }

  firstUnfinished(): number {
    const imgs = this.project?.images ?? [];
    for (let i = 0; i < imgs.length; i++) if (!imgs[i].done) return i;
    return 0;
  }

  private computeSessionTarget(): void {
    const dir =
      this.greenDir?.canWrite
        ? this.greenDir
        : this.redDir?.canWrite
          ? this.redDir
          : null;
    this.sessionDir = dir;
    const named = this.greenDir ?? this.redDir;
    this.sessionFilename = named ? `${named.name}${SESSION_SUFFIX}` : null;
  }

  start(
    project: Project,
    registry: Map<string, ImageRef>,
    greenDir: DirectorySource | null,
    redDir: DirectorySource | null,
  ): void {
    clearImageCache();
    this.project = project;
    this.registry = registry;
    this.greenDir = greenDir;
    this.redDir = redDir;
    this.computeSessionTarget();
    project.current_index = 0;
    this.returnToReview = false;
    this.screen = "threshold";
    void this.autosave();
  }

  resume(
    project: Project,
    registry: Map<string, ImageRef>,
    greenDir: DirectorySource | null,
    redDir: DirectorySource | null,
    sessionFilename: string,
  ): void {
    clearImageCache();
    // Flag entries whose file is no longer present after re-picking folders.
    for (const e of project.images) e.missing = !registry.has(e.path);
    this.project = project;
    this.registry = registry;
    this.greenDir = greenDir;
    this.redDir = redDir;
    this.computeSessionTarget();
    if (this.sessionFilename === null) this.sessionFilename = sessionFilename;
    project.current_index = this.firstUnfinished();
    this.returnToReview = false;
    this.screen = "threshold";
    this.status = `Resumed — ${this.doneCount()} of ${project.images.length} done.`;
  }

  openThreshold(index: number, returnToReview: boolean): void {
    if (!this.project) return;
    const n = this.project.images.length;
    this.project.current_index = Math.max(0, Math.min(index, n - 1));
    this.returnToReview = returnToReview;
    this.screen = "threshold";
  }

  go(screen: Screen): void {
    this.screen = screen;
  }

  serialize(): string {
    return JSON.stringify(this.project, null, 2);
  }

  /** True if the session was written in place; false means caller should offer a download. */
  async autosave(): Promise<boolean> {
    if (!this.project || !this.sessionDir || !this.sessionFilename) return false;
    const ok = await this.sessionDir.writeText(
      this.sessionFilename,
      this.serialize(),
    );
    if (ok) this.savedTick++;
    return ok;
  }

  /**
   * Explicit save (the panel's "Save" button). Writes the session in place when
   * the source folder is writable (FSA); otherwise falls back to a one-off JSON
   * download so read-only browsers can still persist progress.
   */
  async saveSession(): Promise<"saved" | "downloaded" | "none"> {
    if (!this.project) return "none";
    if (await this.autosave()) return "saved";
    const { downloadText } = await import("@/export/bundle");
    downloadText(this.serialize(), this.sessionFilename ?? `session${SESSION_SUFFIX}`);
    return "downloaded";
  }

  get canWriteSession(): boolean {
    return this.sessionDir !== null && this.sessionDir.canWrite;
  }
}

export const session = new SessionStore();
