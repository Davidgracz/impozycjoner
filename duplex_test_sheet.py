"""Duplex registration test sheet, vector-only and independent of source PDF jobs.

Measurements are made while looking at the FRONT of the printed sheet against
light. e_x/e_y describe how far the BACK marks appear from the corresponding
FRONT targets, with X right and Y down in this front-facing view.
"""
from __future__ import annotations

from math import isfinite
from pathlib import Path

import pymupdf as fitz

from duplex_calibration import FLIPS, _offset

PT_PER_MM = 72.0 / 25.4


def _pt(v: float) -> float:
    return v * PT_PER_MM


def horizontal_flip(flip: str, sheet_w: float, sheet_h: float) -> bool:
    """Same physical sheet flip convention as engine._flip_slot()."""
    if flip not in FLIPS:
        raise ValueError('Nieznana krawędź odwracania arkusza.')
    return (flip == 'Długa krawędź') != (sheet_w > sheet_h)


def on_back(x: float, y: float, sheet_w: float, sheet_h: float,
            flip: str) -> tuple[float, float]:
    """Position in the backside PDF corresponding to a front-face coordinate."""
    if horizontal_flip(flip, sheet_w, sheet_h):
        return sheet_w - x, y
    return x, sheet_h - y


def correction_from_front_error(error_x: float, error_y: float, *,
                                flip: str, sheet_w: float, sheet_h: float,
                                current_x: float = 0, current_y: float = 0) -> tuple[float, float]:
    """Return *absolute* offsets in verso PDF coordinates, to 0.1 mm.

    If backside artwork lies +1 mm to the RIGHT in front-face transparency,
    we must move it -1 mm in front coordinates. A horizontal flip reverses the
    sign of X when converted to the actual backside page. The existing offsets
    are kept as the starting point so multiple test prints can refine a profile.
    """
    for name, value in [('Błąd X', error_x), ('Błąd Y', error_y),
                        ('Szerokość', sheet_w), ('Wysokość', sheet_h)]:
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError(f'{name}: wpisz poprawną liczbę.')
    if sheet_w <= 0 or sheet_h <= 0:
        raise ValueError('Wymiary arkusza muszą być dodatnie.')
    if abs(error_x) > 20 or abs(error_y) > 20:
        raise ValueError('Pomiar poza zakresem ±20 mm — sprawdź obrót arkusza i skalowanie wydruku.')
    if abs(error_x * 10 - round(error_x * 10)) > 1e-6 or abs(error_y * 10 - round(error_y * 10)) > 1e-6:
        raise ValueError('Wpisz pomiar z dokładnością do 0,1 mm.')
    x, y = _offset(current_x), _offset(current_y)
    if horizontal_flip(flip, sheet_w, sheet_h):
        new_x, new_y = x + error_x, y - error_y
    else:
        new_x, new_y = x - error_x, y + error_y
    return _offset(round(new_x, 1)), _offset(round(new_y, 1))


def measurement_points(sheet_w: float, sheet_h: float) -> tuple[tuple[str, float, float], ...]:
    """4 corners + centre, symmetrically placed away from printer edges."""
    margin_x = min(32.0, sheet_w * 0.28)
    margin_y = min(32.0, sheet_h * 0.28)
    return (
        ('A', margin_x, margin_y),
        ('B', sheet_w - margin_x, margin_y),
        ('C', margin_x, sheet_h - margin_y),
        ('D', sheet_w - margin_x, sheet_h - margin_y),
        ('E', sheet_w / 2, sheet_h / 2),
    )


def _line(page: fitz.Page, xa: float, ya: float, xb: float, yb: float,
          *, width: float = 0.16, gray: float = 0.0):
    page.draw_line(fitz.Point(_pt(xa), _pt(ya)), fitz.Point(_pt(xb), _pt(yb)),
                   color=(gray, gray, gray), width=_pt(width))


def _text(page: fitz.Page, value: str, x: float, y: float, *, size: float = 8, gray: float = 0):
    page.insert_text((_pt(x), _pt(y)), value, fontsize=size, fontname='helv', color=(gray,gray,gray))


def _front_target(page: fitz.Page, x: float, y: float, label: str):
    """Graduated cross: 1 mm ticks over +/-5 mm, with conspicuous centre."""
    _line(page, x - 12, y, x + 12, y, width=.18)
    _line(page, x, y - 12, x, y + 12, width=.18)
    page.draw_circle(fitz.Point(_pt(x), _pt(y)), _pt(1.0), color=(0,0,0), width=_pt(.18))
    # small ruler ticks, 1 mm steps, 5 mm major labels
    for k in range(-5, 6):
        if k == 0:
            continue
        delta=2.1 if abs(k)==5 else 1.0
        _line(page, x + k, y - delta / 2, x + k, y + delta / 2, width=.12, gray=.32)
        _line(page, x - delta / 2, y + k, x + delta / 2, y + k, width=.12, gray=.32)
    _text(page, label, x - 9, y - 9.5, size=9)
    _text(page, '-5', x - 7.7, y + 4.7, size=5, gray=.35)
    _text(page, '+5', x + 5.2, y + 4.7, size=5, gray=.35)


def _back_target(page: fitz.Page, x: float, y: float, label: str):
    """Back registration target. Circle and diagonal avoid overprinting ruler."""
    center = fitz.Point(_pt(x), _pt(y))
    for r in (1.8, 4.0):
        page.draw_circle(center, _pt(r), color=(0,0,0), width=_pt(.26))
    _line(page, x - 7, y - 7, x - 4.8, y - 4.8, width=.27)
    _line(page, x + 4.8, y + 4.8, x + 7, y + 7, width=.27)
    _line(page, x - 7, y + 7, x - 4.8, y + 4.8, width=.27)
    _line(page, x + 4.8, y - 4.8, x + 7, y - 7, width=.27)
    _text(page, label, x - 9, y - 9.5, size=9)


def create_duplex_test_pdf(destination: str | Path, *, sheet_w: float, sheet_h: float,
                           flip: str, verso_shift_x: float = 0, verso_shift_y: float = 0) -> Path:
    """Export two vector PDF pages sized exactly like the selected printing sheet.

    Current verso offsets ARE used when printing back targets, allowing iterative
    re-measurement and correction with the calculator in the same UI.
    """
    for value in (sheet_w, sheet_h):
        if type(value) not in (int, float) or not isfinite(value) or value < 110 or value > 1000:
            raise ValueError('Arkusz testowy wymaga wymiarów 110–1000 mm.')
    if flip not in FLIPS:
        raise ValueError('Nieznana krawędź odwracania arkusza.')
    verso_shift_x, verso_shift_y = _offset(verso_shift_x), _offset(verso_shift_y)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    try:
        front=doc.new_page(width=_pt(sheet_w),height=_pt(sheet_h))
        _text(front, 'IMPOZYCJONER 0.3.7  |  TEST RECTO/VERSO - FRONT', 9, 9, size=9)
        _text(front, f'Format {sheet_w:g} x {sheet_h:g} mm  |  Print at 100%, duplex, no fit-to-page', 9, 14, size=7)
        _text(front, f'Flip: {"LONG" if flip == FLIPS[0] else "SHORT"} edge', 9, 18, size=7)
        for label,x,y in measurement_points(sheet_w,sheet_h):
            _front_target(front,x,y,label)
        _text(front,'View from FRONT against light. Back ring displacement: X right(+), Y down(+).',9,sheet_h-8,size=7)

        back=doc.new_page(width=_pt(sheet_w),height=_pt(sheet_h))
        _text(back, 'IMPOZYCJONER 0.3.7  |  TEST RECTO/VERSO - BACK',9,9,size=9)
        _text(back, f'Applied back offset in PDF: X={verso_shift_x:+.1f} mm  Y={verso_shift_y:+.1f} mm',9,14,size=7)
        for label,x,y in measurement_points(sheet_w,sheet_h):
            bx,by=on_back(x,y,sheet_w,sheet_h,flip)
            bx+=verso_shift_x
            by+=verso_shift_y
            # Large current offset beyond the paper should not silently lose a target.
            if not (8 <= bx <= sheet_w-8 and 8 <= by <= sheet_h-8):
                raise ValueError('Korekta jest za duża dla arkusza testowego: znaczniki wychodzą poza papier.')
            _back_target(back,bx,by,label)
        _text(back,'Print at 100%. Turn paper according to duplex edge selection.',9,sheet_h-8,size=7)
        doc.set_metadata({'title':'Impozycjoner Studio - Duplex registration test 0.3.7',
                          'subject':'Front/back alignment test at actual size'})
        doc.save(str(target),garbage=4,deflate=True)
    finally:
        doc.close()
    return target
