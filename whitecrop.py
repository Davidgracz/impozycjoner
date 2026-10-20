"""Wykrywanie białych marginesów wokół grafiki strony PDF (rozszerzenie Studio).

Impozycjoner 4 nie wykrywa białych krawędzi automatycznie — obszar netto koryguje się ręcznie
(okno „Korekta położenia i rozmiaru obszaru netto”, kadrowanie do netto lub netto + 3 mm).
Studio robi to samo automatycznie: strona jest renderowana w niskiej rozdzielczości, a obszarem
treści jest najmniejszy prostokąt zawierający wszystkie piksele ciemniejsze niż próg bieli.

Decyzje (H-26): rozdzielczość 144 ppi (1 piksel ≈ 0,18 mm), wynik zmniejszony o 1 piksel z każdej
strony (piksel brzegowy bywa częściowo biały; lepiej uciąć 0,18 mm grafiki niż zostawić jasny pasek
na krawędzi spadu), pusta strona → bez zmian (cały TrimBox).
Wynik jest w nieobróconych współrzędnych MuPDF, tak jak TrimBox.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

ZOOM = 2.0  # 144 ppi (piksel ≈ 0,18 mm)
_cache: dict[tuple, tuple[float, float, float, float]] = {}


def content_rect(page: fitz.Page, area: fitz.Rect, level: int = 250) -> fitz.Rect:
    """Najmniejszy prostokąt w `area` zawierający piksele ciemniejsze niż `level` (0–255)."""
    if not 0 < level <= 255:
        raise ValueError('Próg bieli musi być w zakresie 1–255')
    doc = page.parent
    try:
        stamp = Path(doc.name).stat().st_mtime if doc.name else None
    except OSError:
        stamp = None
    key = (doc.name, stamp, page.number, tuple(round(v, 3) for v in area), level)
    if stamp is not None and key in _cache:
        return fitz.Rect(_cache[key])
    angle, old_crop = page.rotation, fitz.Rect(page.cropbox)
    media = fitz.Rect(page.mediabox)
    try:
        page.set_rotation(0)
        page.set_cropbox(fitz.Rect(media.x0, 0, media.x1, media.height))
        origin = page.cropbox.tl  # współrzędne renderu liczą się od lewego górnego rogu CropBox
        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), clip=area - (origin.x, origin.y, origin.x, origin.y),
                              alpha=False, colorspace=fitz.csGRAY)
    finally:
        page.set_cropbox(old_crop)
        page.set_rotation(angle)
    from PIL import Image
    image = Image.frombytes('L', (pix.width, pix.height), pix.samples)
    box = image.point(lambda v: 255 if v < level else 0).getbbox()
    if box is None:
        result = fitz.Rect(area)
    else:
        x0, y0, x1, y1 = box
        sx, sy = area.width / pix.width, area.height / pix.height
        # Jeden piksel do środka: piksel brzegowy bywa w połowie biały (wygładzanie) i dałby jasny pasek.
        if x1 - x0 > 2:
            x0, x1 = x0 + 1, x1 - 1
        if y1 - y0 > 2:
            y0, y1 = y0 + 1, y1 - 1
        result = fitz.Rect(area.x0 + x0 * sx, area.y0 + y0 * sy, area.x0 + x1 * sx, area.y0 + y1 * sy) & area
    if stamp is not None:
        _cache[key] = tuple(result)
    return result
