<script lang="ts">
  // Load screen — pick a green (live/GFP) folder and a red (dead/RFP) folder,
  // optionally filter by filename, choose which images to include, set
  // background subtraction, then Start. Mirrors qviability/ui/load_screen.py.

  import {
    supportsFSA,
    pickDirectoryFSA,
    directoryFromFileList,
    type DirectorySource,
    type ImageRef,
  } from "@/state/fileSystem";
  import { session } from "@/state/session.svelte";
  import {
    makeImageEntry,
    SCHEMA_VERSION,
    DEFAULT_GREEN_BG_RADIUS,
    DEFAULT_RED_BG_RADIUS,
    Channel,
    type Project,
    type ImageEntry,
  } from "@/core/types";

  type Ch = "Green" | "Red";
  interface Row {
    path: string;
    name: string;
    channel: Ch;
    include: boolean;
  }

  let greenDir = $state<DirectorySource | null>(null);
  let redDir = $state<DirectorySource | null>(null);
  let greenRefs: ImageRef[] = [];
  let redRefs: ImageRef[] = [];
  let greenFilter = $state("");
  let redFilter = $state("");
  let rows = $state<Row[]>([]);

  let bgSubtract = $state(false);
  let greenRadius = $state(DEFAULT_GREEN_BG_RADIUS);
  let redRadius = $state(DEFAULT_RED_BG_RADIUS);

  let resumeDir: DirectorySource | null = null;
  let resumeFile = $state<string | null>(null);
  let error = $state("");

  let pendingChannel: Ch = "Green";
  let fileInput: HTMLInputElement;

  const pathFor = (channel: Ch, name: string) => `${channel}/${name}`;
  const checkedCount = $derived(rows.filter((r) => r.include).length);

  function rescan(): void {
    const out: Row[] = [];
    const add = (refs: ImageRef[], channel: Ch, filter: string) => {
      const needle = filter.trim().toLowerCase();
      for (const r of refs) {
        if (needle && !r.name.toLowerCase().includes(needle)) continue;
        out.push({ path: pathFor(channel, r.name), name: r.name, channel, include: true });
      }
    };
    add(greenRefs, "Green", greenFilter);
    add(redRefs, "Red", redFilter);
    rows = out;
  }

  async function applyDir(channel: Ch, dir: DirectorySource): Promise<void> {
    error = "";
    const refs = await dir.list();
    if (channel === "Green") {
      greenDir = dir;
      greenRefs = refs;
    } else {
      redDir = dir;
      redRefs = refs;
    }
    const sess = await dir.findSession();
    if (sess) {
      resumeDir = dir;
      resumeFile = sess;
    }
    rescan();
  }

  async function chooseFolder(channel: Ch): Promise<void> {
    if (supportsFSA) {
      try {
        const dir = await pickDirectoryFSA();
        if (dir) await applyDir(channel, dir);
      } catch (e) {
        error = `Could not open folder: ${(e as Error).message}`;
      }
    } else {
      pendingChannel = channel;
      fileInput.value = "";
      fileInput.click();
    }
  }

  function onFilesPicked(e: Event): void {
    const input = e.target as HTMLInputElement;
    const files = input.files ? Array.from(input.files) : [];
    const dir = directoryFromFileList(files);
    if (dir) void applyDir(pendingChannel, dir);
  }

  function buildRegistryAll(): Map<string, ImageRef> {
    const reg = new Map<string, ImageRef>();
    for (const r of greenRefs) reg.set(pathFor("Green", r.name), r);
    for (const r of redRefs) reg.set(pathFor("Red", r.name), r);
    return reg;
  }

  function onStart(): void {
    const chosen = rows.filter((r) => r.include);
    if (chosen.length === 0) return;
    const refByPath = buildRegistryAll();
    const registry = new Map<string, ImageRef>();
    const images: ImageEntry[] = [];
    for (const r of chosen) {
      const entry = makeImageEntry(r.path, r.name, r.channel);
      images.push(entry);
      const ref = refByPath.get(r.path);
      if (ref) registry.set(r.path, ref);
    }
    const project: Project = {
      green_folder: greenDir?.name ?? null,
      red_folder: redDir?.name ?? null,
      images,
      current_index: 0,
      fine_step: 1,
      coarse_step: 10,
      output_folder: null,
      subtract_background: bgSubtract,
      green_bg_radius: greenRadius,
      red_bg_radius: redRadius,
      schema_version: SCHEMA_VERSION,
    };
    session.start(project, registry, greenDir, redDir);
  }

  async function onResume(): Promise<void> {
    if (!resumeDir || !resumeFile) return;
    try {
      const text = await resumeDir.readText(resumeFile);
      if (!text) throw new Error("session file is empty");
      const project = JSON.parse(text) as Project;
      const registry = buildRegistryAll();
      session.resume(project, registry, greenDir, redDir, resumeFile);
    } catch (e) {
      error = `Could not read session: ${(e as Error).message}`;
    }
  }

  void Channel; // keep the import meaningful for future channel logic
</script>

<div class="load">
  <nav class="topnav">
    <button class="link" onclick={() => session.go("howto")}>How to</button>
    <button class="link" onclick={() => session.go("about")}>About</button>
  </nav>
  <h1>ViabilityQuantifier</h1>
  {#if session.project}
    <button class="continue" onclick={() => session.go("threshold")}>
      Continue current session ▶
    </button>
  {/if}
  <p class="lead">
    Choose the folder of green (live / GFP) images and the folder of red (dead /
    RFP) images, then press Start.
  </p>
  {#if !supportsFSA}
    <p class="note">
      This browser can't write files in place; sessions and exports will download
      instead. For in-place saving use a Chromium browser.
    </p>
  {/if}

  <div class="boxes">
    <fieldset class="green">
      <legend>Green / Live (GFP) folder</legend>
      <div class="row">
        <button onclick={() => chooseFolder("Green")}>Choose folder…</button>
        <span class="path">{greenDir?.name ?? "(none)"}</span>
      </div>
      <label class="filter">
        Filename contains:
        <input
          type="text"
          placeholder="e.g. GFP — blank includes every image"
          bind:value={greenFilter}
          oninput={rescan}
        />
      </label>
    </fieldset>

    <fieldset class="red">
      <legend>Red / Dead (RFP) folder</legend>
      <div class="row">
        <button onclick={() => chooseFolder("Red")}>Choose folder…</button>
        <span class="path">{redDir?.name ?? "(none)"}</span>
      </div>
      <label class="filter">
        Filename contains:
        <input
          type="text"
          placeholder="e.g. RFP — blank includes every image"
          bind:value={redFilter}
          oninput={rescan}
        />
      </label>
    </fieldset>
  </div>

  <div class="tablewrap">
    <table>
      <thead>
        <tr><th>Include</th><th>Filename</th><th>Channel</th></tr>
      </thead>
      <tbody>
        {#each rows as row (row.path)}
          <tr>
            <td class="ck"><input type="checkbox" bind:checked={row.include} /></td>
            <td>{row.name}</td>
            <td class:green={row.channel === "Green"} class:red={row.channel === "Red"}
              >{row.channel}</td
            >
          </tr>
        {/each}
      </tbody>
    </table>
    {#if rows.length === 0}
      <p class="empty">No images match — choose a folder or adjust the filter.</p>
    {/if}
  </div>

  <p class="status">
    {rows.length} image(s) listed · {checkedCount} selected
  </p>

  <label class="bg">
    <input type="checkbox" bind:checked={bgSubtract} />
    Subtract background (rolling ball) — corrects uneven illumination before
    thresholding
  </label>
  {#if bgSubtract}
    <div class="radii">
      <label>Rolling-ball radius (px) — Green:
        <input type="number" min="1" max="500" bind:value={greenRadius} />
      </label>
      <label>Red:
        <input type="number" min="1" max="500" bind:value={redRadius} />
      </label>
    </div>
  {/if}

  {#if error}<p class="error">{error}</p>{/if}

  <div class="actions">
    {#if resumeFile}
      <button class="resume" onclick={onResume}>
        Resume previous session ({resumeFile})
      </button>
    {/if}
    <span class="spacer"></span>
    <button class="start" disabled={checkedCount === 0} onclick={onStart}>
      Start ▶
    </button>
  </div>

  <input
    bind:this={fileInput}
    type="file"
    multiple
    webkitdirectory
    style="display:none"
    onchange={onFilesPicked}
  />
</div>

<style>
  .load {
    max-width: 1000px;
    margin: 0 auto;
    padding: 28px 24px 48px;
  }
  .topnav {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-bottom: 8px;
  }
  .topnav .link {
    background: none;
    border: none;
    color: #9ab;
    cursor: pointer;
    font-size: 0.9rem;
    padding: 4px 8px;
  }
  .topnav .link:hover {
    color: #cde;
    text-decoration: underline;
  }
  .continue {
    background: #2f5d7d;
    color: #fff;
    border: 1px solid #2f5d7d;
    border-radius: 6px;
    padding: 8px 16px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: 12px;
  }
  .continue:hover {
    background: #366c91;
  }
  h1 {
    font-size: 1.7rem;
    margin-bottom: 6px;
  }
  .lead {
    color: #bbb;
    margin-bottom: 14px;
  }
  .note {
    color: #e0b15a;
    font-size: 0.85rem;
    margin-bottom: 12px;
  }
  .boxes {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }
  fieldset {
    border: 1px solid #333;
    border-radius: 8px;
    padding: 12px 14px;
  }
  legend {
    padding: 0 6px;
    font-weight: 600;
  }
  fieldset.green legend {
    color: #5fd16a;
  }
  fieldset.red legend {
    color: #ff6fae;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }
  .path {
    color: #ccc;
    font-size: 0.85rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .filter {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: #aaa;
  }
  .filter input {
    flex: 1;
  }
  .tablewrap {
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    max-height: 320px;
    overflow: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }
  thead th {
    position: sticky;
    top: 0;
    background: #1d1d28;
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid #333;
  }
  tbody td {
    padding: 5px 10px;
    border-bottom: 1px solid #232323;
  }
  td.ck {
    text-align: center;
  }
  td.green {
    color: #5fd16a;
  }
  td.red {
    color: #ff6fae;
  }
  .empty {
    padding: 16px;
    color: #888;
    text-align: center;
  }
  .status {
    color: #aaa;
    font-size: 0.85rem;
    margin: 10px 0;
  }
  .bg {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    color: #ddd;
    font-size: 0.9rem;
  }
  .radii {
    display: flex;
    gap: 22px;
    margin: 10px 0 0 26px;
    color: #bbb;
    font-size: 0.85rem;
  }
  .radii input {
    width: 70px;
    margin-left: 6px;
  }
  .error {
    color: #ff7777;
    margin-top: 12px;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 20px;
  }
  .spacer {
    flex: 1;
  }
  button {
    background: #2c2c3a;
    color: #eee;
    border: 1px solid #3a3a4a;
    border-radius: 6px;
    padding: 7px 14px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  button:hover {
    background: #353548;
  }
  button.start {
    font-weight: 700;
    padding: 8px 24px;
    background: #2f7d32;
    border-color: #2f7d32;
  }
  button.start:disabled {
    background: #2a2a2a;
    border-color: #2a2a2a;
    color: #666;
    cursor: not-allowed;
  }
  button.resume {
    background: #38406a;
    border-color: #444c7a;
  }
  input[type="text"],
  input[type="number"] {
    background: #1a1a22;
    border: 1px solid #333;
    border-radius: 4px;
    color: #eee;
    padding: 5px 7px;
  }
</style>
