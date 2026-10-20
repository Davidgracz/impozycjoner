# Changelog

## Unreleased

- Scaling and cropping: new fit mode „Wypełnij ze spadem” (artwork covers net + bleed, e.g. A4 → A6 + 1.5 mm, overflow
  cropped, no white bleed) and „przytnij białe marginesy źródła” (detects a white frame around the artwork and uses
  the content area; `whitecrop.py`). Works in imposition, single-page export and preflight.
- „Programy dodatkowe”: „Dodaj spady” as in Imp4 (per edge: added bleed, strip width, strip distance from the
  MediaBox edge; stretched strips over or under the page) and „Skaluj strony” (mm or %, proportional, TrimBox or
  MediaBox, optional centring page).
- Built-in job template „Ulotka A6 + 1,5 mm z A4 (bez białych marginesów) — SRA3”; job templates accept the optional
  `white_trim` field (older templates still load).
- `docs/imp4-wersja-finalna.md` §5a: how the final Imp4 scales, crops and adds bleed (UI texts + REA call metadata).

- Marks from the final Imp4: centre cut gutter („Wycinka”, W) — vertical/horizontal width, applied only for an even
  number of columns/rows (otherwise a preflight and status-bar note), axis mark with length or across the print area;
  extra TrimBox hair crop („Docięcie TrimBox”, T) — left on even pages, right on odd; cut-mark offset, length and
  width (N); „Wyłącz wszystkie”. Click toggles, right click opens parameters. Rules in `marks.py`, tests in
  `tests/test_marks.py`. New `.psimp` settings are optional; defaults give the previous output.

- Mapped the final Impozycjoner 4.0.4.0 from its UI texts (REA static analysis, nothing executed) and compared it
  with Studio: `docs/imp4-wersja-finalna.md`.
- Added the „Programy dodatkowe” tab (`tools_ui.py`, `pdftools.py`, `pageops.py`): split into single pages
  (`--XX`), merge, extract (range / each page / remainder / even-odd / cover and body / N pages per file), rotate,
  duplicate, shuffle pages or leaves — vector, input never overwritten. Page ranges use the `-3, 6, 9-11, 15-` syntax.
- Added EAN-13 / EAN-8 generator from a text file (`barcodes.py`), vector bars with GS1 check digit.
- „WYKONAJ IMPOZYCJĘ” can run all sheets, only the active sheet, or all but the active sheet (`engine.select_sides`).
- New „Ustawienia…” dialog: `--IMPOZYCJONER` phrase and PDF metadata (empty = file name); output names with
  forbidden characters or equal to an input name are refused (`naming.py`).
- Page table: multi-select and a right-click menu (select all/even/odd/invert, find first sheet with the page,
  use the page size as the use size, skip/restore pages, remove the file's rows, open in PDF reader)
  — logic in `table_actions.py`.
- Shortcuts as in Imp4: Ctrl+N new imposition, Ctrl+W load project, Shift+Ctrl+S save project as.
- A non-PDF or damaged input now gives a clear error instead of a PyMuPDF exception.
- Without the new options, export output, project format and the TAXI module are unchanged.
  New tests: `test_imp4_functions.py`, `test_pageops.py`, `test_pdftools.py`, `test_barcodes.py`.

- Reworked the main window to follow the Impozycjoner 4 layout: light theme, ribbon tabs (Montaż akcydensów / Kadrowanie PDF / Druk cyfrowy — recto/verso; simple sheet imposition only, no book tab — the Broszura mode is hidden from the UI but old projects still load and export) with captioned groups (Użytek, Tabela K×W, Spady, Odstępy i marginesy, Arkusz, Rodzaj arkuszy).
- "Rodzaj arkuszy" icon buttons replace the mode/flip combo boxes (single-sided, duplex long/short edge, economic, booklet).
- Page table with one row per PDF page (S, SPDF, Nazwa pliku, Szer., Wys., Nakład, Rola), coloured per file; clicking a use on the sheet selects its page.
- New symbolic preview ("Symbole"): coloured uses with page number:rotation and a bar on the page-head edge, drawn without rendering PDF content.
- Summary box (pages, sheets, uses per side, unused slots, gross/net), large WYKONAJ IMPOZYCJĘ button, sheet tabs (1, 2… / 1R, 1V) under the preview, vertical marks strip, printable-area readout.
- Engine, PDF output, project format and the TAXI module are unchanged. Added `ui_icons.py` and `tests/test_symbolic_preview.py`.

- Added job templates (`job_templates.py`): one-click presets for sheet, net size, bleed, gaps, mode, rotation, scaling and marks.
- Seven built-in starting points (business cards, A6/DL/A5 flyers on SRA3) plus user templates stored in `%APPDATA%\Impozycjoner Studio\job_templates.json`.
- Templates never carry per-file data (original size, crop offsets) or machine calibration; a template may only reference a machine profile by name.
- New "SZABLONY PRAC" section in the settings panel (load / save as / delete); built-in templates are read-only.
- Added `tests/test_job_templates.py`. The engine and PDF output are unchanged.

## 0.4.1 — 2026-10-14

- Reworked crop UI to source PDF → net dimensions → per-edge bleed → automatically derived gross size.
- Added practical net size presets for business cards, DL, A7 and ISO A-sizes.
- Auto-detected original PDF dimensions per selected source while preserving manual source validation for old projects.
- Added a real-PDF visual crop editor with draggable gross/net guides, 0.1-mm X/Y offsets and one-click reset.
- Stored independent crop offsets per source PDF in .psimp and validated source margins before printing.
- Unified manual crop offsets across sheet preview, vector export, single-page export and preflight.
- Added backwards-compatible auto_source/auto_gross settings and new regression/GUI checks.
- Kept regular-sheet geometry and the complete TAXI module unchanged.


## 0.4.0 — 2026-10-13

- Added single-sided economic gang-run mode for multiple PDFs with differing requested quantities.
- Combined each non-skipped page as its own artwork; exact quantity accounting and proportional per-sheet mixing.
- Minimum physical sheet count for one common gross/net size, no forced overproduction; deterministic placement.
- Added the production planning UI with sheet totals, unused slots, overproduction/shortages and UTF-8 Excel CSV reports.
- Export produces all physical sheet pages directly and saves a matching per-artwork/per-pattern CSV report.
- Added preflight and export blocking when manual changes alter ordered artwork quantities.
- Added a vector SRA3 sample, .psimp project, preview, CSV and integration/property-style tests.
- Preserved all existing imposition and TAXI generator functionality.


## 0.3.7 — 2026-10-13

- Added a printable two-page, vector-only duplex alignment sheet at the current physical sheet size.
- Added five cross/ruler targets on recto and corresponding ring targets on verso; follow flip direction and active machine offsets.
- Added a measurement calculator for front-face displacement with correct axis signs for landscape/portrait and long/short edge flipping.
- Applied measurement corrections incrementally to the current verso offset; operator can save the result as a printer profile.
- Added geometry, sign, vector PDF and profile regression tests; preserved all current imposition and TAXI functions.


## 0.3.6 — 2026-10-13

- Added 0.1-mm whole-side verso X/Y calibration after all per-slot manual edits and physical flip.
- Added per-machine calibration profiles (offsets and flip method), saved locally in a versioned JSON file outside the project.
- Persisted current duplex offsets in backward-compatible `.psimp` project settings.
- Unified calibrated placements for sheet editor, registration preview, preflight and vector PDF output, including crop marks.
- Added preflight checks for out-of-sheet calibrated back uses; reject invalid or non-0.1-mm offsets.
- Added two-sided demo PDFs, project, registration screenshot, GUI smoke check and regression tests.
- Kept source code and template files of the TAXI generator unchanged.


## 0.3.5 — 2026-10-13

- Added a real visual drag/drop sheet editor for source PDF pages, including empty grid positions.
- Added move-by-drag, arrow-key 0.1-mm nudging, exact X/Y inputs and independent 90-degree per-use rotation.
- Added drag-to-swap, reset-to-auto and clear operations, preserving independent recto and verso edits.
- Persisted artwork assignments, displacement and rotation in backward-compatible `.psimp` files.
- Unified edited geometry for preview and vector PDF output; visual page overlays remain preview-only.
- Added physical sheet-boundary checks and overlap warnings in editor and preflight.
- Kept the TAXI generator and all its template assets unchanged.
- Added regression tests for vector output, backward compatibility, save/load, duplex and 110x70 crop.


## 0.3.4 — 2026-10-13

- Added three explicit operator dimensions: original PDF, gross/with-bleed use, and final net trim.
- Made 1:1 cropping derive symmetric bleed from the gross-minus-net difference (default 1.5 mm/edge).
- Added source dimension verification and gross-fit preflight/export checks.
- Maintained project compatibility, existing scaling modes, manual recto/verso editing and page overlays.
- Kept TAXI generator source and assets unchanged.
- Added vector sample PDFs and production-focused integration tests.


## 0.3.3 — 2026-10-13

- Added centered 1:1 physical crop mode using distinct source PDF dimensions, finished trim size, and bleed.
- Preserved no-scaling exact-size mode and existing fit/fill modes.
- Added crop-mode size checks and preflight reporting.


## 0.3.2 — preview-only page overlays

- Added large semi-transparent per-slot page numbers in the raster preview only.
- Added Off / Page number / Filename + page number modes.
- Applies on recto and verso, including manually assigned cells and registration view.
- Final exported PDF is unchanged by these preview-only overlays.


## 0.3.1 — 2026-10-13

- Added manual sheet slot assignment, swapping, clearing and resetting on selected recto/verso sheet.
- Stored manual cell overrides in .psimp and applied them consistently during PDF preview and export.
- Added duplex registration overlay with appropriate flip-edge mirroring.
- Retained the TAXI generator unchanged.
- Added regression tests for overridden duplex export and project persistence.


## 0.2.8 — 2026-10-12

- Preserved proportional side-number scaling: the TAXI number is no longer stretched independently in X/Y.
- Centered the raster side number inside its target area after proportional fitting.

- Changed the TAXI generator output to one shared ZIP with all files stored flat, without per-number subfolders.
- Simplified the rear cut artwork to SVG-only output.
- Removed mirrored rear duplicates; each rear decal now contains one number above one SZCZECIN word.
- Locked rear decal geometry to operator rules: number height 55 mm, SZCZECIN width 120 mm.
- Kept side artwork as original 200 DPI TIFF templates while still changing only the taxi number.
- Updated the Windows UI texts, ZIP naming and production notes for the new TAXI workflow.
- Refreshed tests to validate flat ZIP output and the fixed SVG geometry.


## 0.2.5 — 2026-10-12

- Added a dedicated email-to-print labels tab with direct IMAP-over-SSL mail listing and read-only fetch.
- Added MIME plain-text/HTML extraction, category detection and PLN price parsing without inventing missing prices.
- Restored bakery 110x50 mm labels with prices (A4 landscape) and ice-cream 90x50 mm labels without prices (A4 portrait).
- Added editable label entries, per-item copies, category templates, and Unicode vector PDF export.
- Added optional local persistence of IMAP host, port, login and filter; never store password or email body.
- Added anonymized sample email, a production-style vector PDF example, and regression tests.


## 0.2.4 — 2026-10-12

- Added editable recto/verso roles for each input PDF and individual PDF pages (Normal, Front, Paired Back, Shared Back, Exclude).
- Added multi-select and number/range assignment (e.g. `1,3-8,22`) in a dedicated Windows dialog.
- Added common-back duplication for personalized fronts, even when a single PDF mixes fronts with one special shared-back page.
- Added explicit front-to-back pairing across separate input files, preserving front order and the chosen duplex flipping edge.
- Kept legacy sequential pairing for unchanged projects and stored assignments in backward-compatible `.psimp` project files.
- Added role validation in preflight so missing or extra backs, multiple different common backs, and non-duplex exports cannot silently misprint.
- Added a vector PDF demo and tests covering pairing, shared backs, skipping, project persistence and placement.


## 0.2.3 — 2026-10-12

- Detected mixed source page sizes in one PDF and warned about implicit enlargement or reduction to the selected target trim size.
- Consolidated low-resolution image findings by page to avoid repeating dozens of similar warnings.
- Reported effective DPI after scaling, retaining exact image instances, coordinates, pixel dimensions, and native DPI in the JSON report.
- Added regression tests for a 22-page document mixing A4/A6, grouped DPI warnings, and improved effective DPI after downscaling.

## 0.2.2 — 2026-10-12

- Added explicit vector-safe PDF resizing: Fit and Fill, with centered placement and controlled clipping.
- Added A6/A5/A4 target presets and scaling controls in the Windows GUI.
- Added standalone multipage output at the target trim size; source page order is preserved.
- Made preflight aware of scaling, crop warnings, output bleed and effective image DPI.
- Added tests for 22-page A4→A6 workflows, booklet/imposition scaling, cropped fill, shifted MediaBox and rotated pages.

## 0.2.1 — 2026-10-12

- Fixed false TRIMBOX preflight errors when a PDF has a non-zero MediaBox origin.
- Used consistent MuPDF geometry for MediaBox, TrimBox and BleedBox in PDF export.
- Fixed full-media CropBox setup for shifted MediaBox documents.
- Added regression tests covering offset media boxes, 22-page files and real invalid TrimBox rejection.

## 0.2.0 — 2026-10-12

- Added the Preflight PDF window and export gate, with TXT/JSON reports.
- Checks source dimensions against requested trim without silent rescaling.
- Detects insufficient physical bleed, potentially low-resolution images and some unembedded fonts.
- Improved vector PDF placement with asymmetric bleeds, intrinsic PDF rotation and rotated sheet slots (0/90/180/270 degrees).
- Uses the source MediaBox for placing available bleed even when the source CropBox is smaller.
- Added regression tests for rotated bleeds, dimensional mismatches and preflight reports.

**Caution:** Not a full PDF/X, CMYK/spot or ICC profile inspection. Verify a production proof and duplex orientation before running a print job.

## 0.1.0 — 2026-10-12

- First desktop preview of Impozycjoner Studio (Tkinter + PyMuPDF).
- Added PDF input jobs, imposition grid, basic duplex and booklet modes.
- Added vector PDF export, crop marks, `.psimp` projects and sample PDFs.
- Added Windows venv/pip bootstrap fix.
- Added engine tests, CI and GitHub project setup scripts.
