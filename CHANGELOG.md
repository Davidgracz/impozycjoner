# Changelog

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
