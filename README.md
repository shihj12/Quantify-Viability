# Quantify Viability

A desktop app for **intensity / area-based quantification of live/dead
fluorescence images** (green = live / GFP, red = dead / RFP).

It replaces the manual ImageJ loop — open image, auto-threshold, eyeball-adjust,
`Measure`, copy the number — with a guided, keyboard-driven workflow:

1. **Load** a folder of green images and a folder of red images.
2. **Tune** each image: it opens at a MaxEntropy auto-threshold; the pixels
   counted as positive are shown as a colored overlay. Nudge the threshold with
   the arrow keys, press **Enter** when happy.
3. **Review** every image in a gallery and re-tune any that look wrong.
4. **Export** a results spreadsheet, annotated images and a before/after QC PDF.

It does **not** count individual cells and does **not** compute the green/red
viability ratio — pair the channels yourself in the exported spreadsheet. This
is deliberate: clumped samples can't be segmented reliably, so the app measures
total thresholded signal instead.

## Download

**[Download Quantify Viability for Windows](https://shihj12.github.io/Quantify-Viability/)**

No Python or setup needed — run the installer (Start Menu entry, optional
desktop shortcut, no admin rights required), or grab the portable `.zip`. The
download page always points to the latest build; past versions and release
notes are on the [releases page](https://github.com/shihj12/Quantify-Viability/releases).

## What gets exported

`viability_results.xlsx` — one row per image with every candidate metric, so
you can decide which "intensity" number you want in Excel:

| column | meaning |
|---|---|
| `positive_pixels` | count of pixels at/above the threshold |
| `positive_area_pct` | that count as a % of the image (≈ ImageJ %Area) |
| `mean_intensity_positive` | mean raw value of the positive pixels |
| `integrated_intensity` | sum of raw values of positive pixels (ImageJ RawIntDen) |

plus `filename`, `channel`, `threshold`, `threshold_method`,
`background_subtracted`, `bit_depth`, `image_width`, `image_height`.

`annotated/` — one PNG per image: the view with the positive-pixel overlay and
a caption, as a visual record of what was counted.

`viability_QC.pdf` — a flip-through quality-control document: one page per
image, with the original on the left and the marked (counted) version on the
right, side by side, so you can sign off every threshold in one pass.

## Setup (for development / running from source)

The machine's default Python 3.14 is too new for the GUI libraries — use
**Python 3.13** (or 3.12 / 3.11):

```
py -V:3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```
.venv\Scripts\python run.py
```

## Build the standalone .exe

```
build_exe.bat
```

This produces `dist\QuantifyViability\QuantifyViability.exe` — double-click to
run, no Python needed. Zip the whole `dist\QuantifyViability` folder to share
it with labmates. (The one-folder build avoids most antivirus false positives;
a one-file `.exe` is more likely to be flagged.)

### Build the installer

With [Inno Setup 6](https://jrsoftware.org/isdl.php) installed, compile the
installer from the `dist\QuantifyViability` folder produced above:

```
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

This produces `installer\QuantifyViability-Setup.exe` — a per-user installer
with a Start Menu entry, an optional desktop shortcut, and an uninstaller; it
needs no administrator rights.

## Keyboard shortcuts (tuning screen)

| key | action |
|---|---|
| `↑` / `↓` | threshold up / down (fine step) |
| `Shift+↑/↓`, `PageUp` / `PageDown` | threshold up / down (coarse step) |
| `Enter` | accept this image, go to the next un-tuned one |
| `←` / `→` | previous / next image (without accepting) |
| `R` | reset to the auto-threshold |
| `O` | highlight marked regions — outline small blobs (display only) |
| `Ctrl+Z` | undo the last threshold change |
| hold `Space` | preview the raw image (overlay + brightness/contrast off) |

**Highlight marked regions** (`O`, or the checkbox in the Display panel) draws a
bright outline just outside the counted pixels, so small or faint blobs are easy
to spot while you tune. Like the brightness/contrast sliders it is a display aid
only — it never changes the measured numbers or the exported images.

Brightness and contrast sliders change only how the image *looks* — they never
affect the measured numbers. All quantification runs on the **raw, unprocessed
pixels**; there is no background subtraction, filtering or gamma. Hold `Space`
to preview the raw image (overlay and display brightness/contrast off) — that is
exactly the data the threshold and the four metrics are computed from.

## Excluding regions (scale bars, text, debris)

To leave part of an image out of the quantification:

1. Click **Draw exclusion box** in the "Exclude regions" panel.
2. Click-drag a rectangle over the area to ignore (e.g. a scale bar).
3. Draw as many boxes as needed; **Undo box** / **Clear boxes** remove them.
4. **Apply boxes to all images** copies the current image's boxes onto every
   other image — handy when a scale bar sits in the same spot on every photo.

Excluded pixels are dropped from *both* the positive count and the image total,
so every metric (including area %) stays correct. Boxes are saved per image in
the session and drawn in gray on the exported annotated PNGs. Click the toggle
again to turn drawing off and pan/zoom normally.

## Background subtraction (optional)

The load screen has a **Subtract background (rolling ball)** checkbox. Leave it
off for raw thresholding (the default, matching a plain ImageJ `Measure`). Tick
it to apply rolling-ball background subtraction — the same correction as
ImageJ's *Subtract Background* — to even out illumination before thresholding.
It applies to the whole session; the threshold screen shows a "✓ background
subtracted" note when it's on, and `Space` still previews the untouched raw
image so you can see exactly what it changed. The choice is recorded in the
`background_subtracted` column of the exported spreadsheet.

## Sessions

Progress is auto-saved to a `*.qviability.json` file inside the image folder, so
you can close the app part-way through a large batch and resume later — the load
screen offers "Resume previous session" when it finds one.

## Project layout

```
run.py                      entry point
qviability/
  app.py                    main window, screen switching
  core/                     pure logic, no Qt (unit-testable)
    image_io.py             image loading + display normalization
    autothreshold.py        MaxEntropy (Kapur) + Otsu/Yen/Li/IsoData
    measure.py              thresholding + measurements
    project.py              data model + JSON session persistence
  ui/                       Qt screens
    load_screen.py          two-folder loader
    threshold_screen.py     interactive tuning
    review_screen.py        review gallery
    widgets.py              image canvas + histogram
  export/
    excel.py                viability_results.xlsx
    annotate.py             annotated PNG rendering
    pdf.py                  before/after QC PDF
```
