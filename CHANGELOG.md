# Changelog

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
