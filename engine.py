"""Impozycjoner Studio 0.4.1 - vector PDF imposition engine.

Uses PDF form XObjects via PyMuPDF. No source pages are rasterized during export.
Units exposed to the operator are millimetres; PyMuPDF operates in points.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import islice
from math import floor, isfinite
from pathlib import Path
from collections import Counter
from typing import Iterator
import json
import zipfile

import marks as marks_rules

import pymupdf as fitz

# Role labels are persisted in project files; keep them stable across releases.
ROLE_AUTO = 'Normalnie'
ROLE_FRONT = 'Przód'
ROLE_BACK = 'Tył sparowany'
ROLE_SHARED = 'Tył wspólny'
ROLE_SKIP = 'Pomiń'
PAGE_ROLES = (ROLE_AUTO, ROLE_FRONT, ROLE_BACK, ROLE_SHARED, ROLE_SKIP)

PT_PER_MM = 72.0 / 25.4


def pt(mm: float) -> float:
    return mm * PT_PER_MM


def mm(points: float) -> float:
    return points / PT_PER_MM


def media_rect(page: fitz.Page) -> fitz.Rect:
    """MediaBox in the same (unrotated MuPDF) coordinates as Trim/BleedBox.

    PyMuPDF exposes `Page.mediabox` in *PDF* coordinates, with the original
    vertical origin. CropBox, TrimBox and BleedBox use MuPDF coordinates where
    y=0 corresponds to the MediaBox's upper edge. Comparing them without
    normalising causes false TRIMBOX errors for non-zero MediaBox origins.

    The horizontal coordinates are already in the same space; only y shifts.
    This normalised rect can also be passed to Page.set_cropbox().
    """
    media = fitz.Rect(page.mediabox)
    return fitz.Rect(media.x0, 0, media.x1, media.height)


@dataclass
class Job:
    path: str
    copies: int = 1
    role: str = ROLE_AUTO
    page_roles: dict[str, str] = field(default_factory=dict)  # 1-based page numbers
    crop_x: float = 0.0  # mm: desired crop-centre displacement in source visual X
    crop_y: float = 0.0  # mm: desired crop-centre displacement in source visual Y

    def role_for(self, zero_based_page: int) -> str:
        return self.page_roles.get(str(zero_based_page + 1), self.role)


@dataclass
class Settings:
    sheet_w: float = 450
    sheet_h: float = 320
    trim_w: float = 90
    trim_h: float = 50
    bleed: float = 2  # legacy/non-crop projects; crop derives it from gross and net
    source_w: float = 0  # 0 = automatically use PDF source TrimBox dimensions
    source_h: float = 0
    gross_w: float = 0   # 0 = legacy trim + 2 * bleed
    gross_h: float = 0
    auto_gross: bool = False  # legacy projects keep manually entered gross
    auto_source: bool = False  # legacy projects keep manually entered source dimensions
    margin_x: float = 6
    margin_y: float = 6
    gap_x: float = 5
    gap_y: float = 5
    rotation: str = "Auto"  # Auto, 0, 90
    columns: int = 0          # 0 = automatic
    rows: int = 0
    mode: str = "Jednostronnie"  # Jednostronnie | Dwustronnie | Broszura | Ekonomiczny
    flip: str = "Długa krawędź"
    verso_shift_x: float = 0.0  # mm in physical (unflipped) back PDF coordinates
    verso_shift_y: float = 0.0
    crop_marks: bool = True
    show_page_labels: bool = False
    scale_mode: str = "Bez skalowania"  # Bez skalowania | Kadruj 1:1 | Dopasuj | Wypełnij
    # Znaczniki wzorowane na Impozycjonerze 4 (marks.py). Wartości domyślne = zachowanie sprzed zmiany.
    mark_offset: float = 0.8      # mm: odstęp znaczników cięcia od krawędzi spadu
    mark_length: float = 3.0      # mm: długość kreski znacznika cięcia
    mark_width_pt: float = 0.25   # pt: grubość kreski znacznika cięcia
    gutter_on: bool = False       # wycinka środkowa
    gutter_v: float = 0.0         # mm: szerokość wycinki pionowej (parzysta liczba kolumn)
    gutter_h: float = 0.0         # mm: szerokość wycinki poziomej (parzysta liczba wierszy)
    gutter_marks: bool = True     # rysuj znacznik w osi wycinki
    gutter_mark_length: float = 5.0  # mm; 0 = przez całe pole zadruku
    gutter_mark_pt: float = 0.25
    trim_crop: bool = False       # dodatkowe docięcie TrimBox („crop”)
    trim_crop_pt: float = 0.5     # pt: z lewej na stronach parzystych, z prawej na nieparzystych


@dataclass
class Project:
    settings: Settings = field(default_factory=Settings)
    jobs: list[Job] = field(default_factory=list)
    overrides: dict[str, dict] = field(default_factory=dict)  # "sheet:side:slot" -> source or blank


@dataclass(frozen=True)
class SourcePage:
    path: str
    index: int


@dataclass(frozen=True)
class Slot:
    x: float
    y: float
    w: float
    h: float
    rotation: int
    col: int
    row: int


@dataclass(frozen=True)
class Placement:
    source: SourcePage | None
    slot: Slot
    side: int


@dataclass(frozen=True)
class SheetSide:
    sheet_number: int
    side: int  # 0 recto / 1 verso
    placements: tuple[Placement, ...]


@dataclass(frozen=True)
class Geometry:
    cols: int
    rows: int
    rotation: int
    slots: tuple[Slot, ...]
    capacity: int
    gutter_x: float | None = None  # mm: oś wycinki pionowej, gdy została uwzględniona
    gutter_y: float | None = None  # mm: oś wycinki poziomej


def gross_dimensions(s: Settings) -> tuple[float, float]:
    """Physical size of a single imposed use, including symmetric bleed."""
    if s.scale_mode == 'Kadruj 1:1' and s.auto_gross:
        return s.trim_w + 2*s.bleed, s.trim_h + 2*s.bleed
    if s.scale_mode == 'Kadruj 1:1' and s.gross_w > 0 and s.gross_h > 0:
        return s.gross_w, s.gross_h
    return s.trim_w + 2*s.bleed, s.trim_h + 2*s.bleed


def bleed_for(s: Settings) -> float:
    """For three-size crop workflow, derive bleed from gross minus net."""
    if s.scale_mode == 'Kadruj 1:1' and s.auto_gross:
        return s.bleed
    if s.scale_mode == 'Kadruj 1:1' and s.gross_w > 0 and s.gross_h > 0:
        return (s.gross_w-s.trim_w)/2
    return s.bleed


def validate(settings: Settings):
    for key in ('sheet_w', 'sheet_h', 'trim_w', 'trim_h'):
        if not isfinite(getattr(settings, key)) or getattr(settings, key) <= 0:
            raise ValueError(f'{key}: wymiar musi być większy od zera')
    for key in ('source_w', 'source_h', 'gross_w', 'gross_h'):
        value = getattr(settings, key)
        if not isfinite(value) or value < 0:
            raise ValueError(f'{key}: wymiar musi być nieujemny')
    if (settings.source_w == 0) != (settings.source_h == 0):
        raise ValueError('Wprowadź oba wymiary oryginału PDF albo pozostaw oba jako automatyczne.')
    if (settings.gross_w == 0) != (settings.gross_h == 0):
        raise ValueError('Wprowadź szerokość i wysokość użytku ze spadami.')
    if settings.scale_mode == 'Kadruj 1:1' and not settings.auto_gross and settings.gross_w > 0:
        bx = (settings.gross_w - settings.trim_w)/2
        by = (settings.gross_h - settings.trim_h)/2
        if bx < -.001 or by < -.001:
            raise ValueError('Użytek ze spadami nie może być mniejszy niż format netto.')
        if abs(bx-by) > .02:
            raise ValueError('Spad ma być jednakowy z każdej strony: różnica użytek–netto musi być taka sama w obu wymiarach.')
    for key in ('bleed', 'margin_x', 'margin_y', 'gap_x', 'gap_y'):
        if not isfinite(getattr(settings, key)) or getattr(settings, key) < 0:
            raise ValueError(f'{key}: wartość nie może być ujemna')
    if settings.columns < 0 or settings.rows < 0:
        raise ValueError('Liczba kolumn/wierszy musi być dodatnia')
    if settings.rotation not in ('Auto', '0', '90', '180', '270'):
        raise ValueError('Nieznana orientacja')
    if settings.mode not in ('Jednostronnie', 'Dwustronnie', 'Broszura', 'Ekonomiczny'):
        raise ValueError('Nieznany tryb montażu')
    if settings.flip not in ('Długa krawędź', 'Krótka krawędź'):
        raise ValueError('Nieznana metoda odwracania')
    for key in ('verso_shift_x', 'verso_shift_y'):
        value = getattr(settings, key)
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError(f'{key}: nieprawidłowe przesunięcie rewersu')
        if abs(value * 10 - round(value * 10)) > 1e-6:
            raise ValueError('Kalibracja rewersu musi być ustawiona co 0,1 mm.')
        if abs(value) > 20.0:
            raise ValueError('Kalibracja rewersu może wynosić maksymalnie ±20 mm.')
    if settings.scale_mode not in ('Bez skalowania', 'Kadruj 1:1', 'Dopasuj', 'Wypełnij'):
        raise ValueError('Nieznany sposób skalowania PDF')
    for key, low, high, label in (('mark_offset', 0, 50, 'Odstęp znaczników od użytków [mm]'),
                                  ('mark_length', 0.1, 50, 'Długość znacznika cięcia [mm]'),
                                  ('mark_width_pt', 0.05, 5, 'Grubość znacznika cięcia [pt]'),
                                  ('gutter_v', 0, 500, 'Szerokość wycinki pionowej [mm]'),
                                  ('gutter_h', 0, 500, 'Szerokość wycinki poziomej [mm]'),
                                  ('gutter_mark_length', 0, 500, 'Długość znacznika wycinki [mm]'),
                                  ('gutter_mark_pt', 0.05, 5, 'Grubość znacznika wycinki [pt]'),
                                  ('trim_crop_pt', 0, 20, 'Szerokość docięcia TrimBox [pt]')):
        value = getattr(settings, key)
        if type(value) not in (int, float) or not isfinite(value) or not low <= value <= high:
            raise ValueError(f'{label}: dozwolone {low:g}–{high:g}')


def geometry(s: Settings) -> Geometry:
    """Find the most productive regular grid. Cell size includes bleed.

    Crop marks are an annotation outside trim and may be suppressed by clip at
    the edges of the sheet; gap and margins should allow for their length.
    """
    validate(s)
    available_w = s.sheet_w - 2 * s.margin_x
    available_h = s.sheet_h - 2 * s.margin_y
    if available_w <= 0 or available_h <= 0:
        raise ValueError('Marginesy są większe niż arkusz')
    candidates = []
    for angle in ([0, 90] if s.rotation == 'Auto' else [int(s.rotation)]):
        w, h = (s.trim_w, s.trim_h) if angle in (0, 180) else (s.trim_h, s.trim_w)
        cell_w, cell_h = w + 2*bleed_for(s), h + 2*bleed_for(s)
        on = s.gutter_on
        if on and (s.gutter_v or s.gutter_h):
            auto_cols = marks_rules.auto_count(available_w, cell_w, s.gap_x, s.gutter_v, on)
            auto_rows = marks_rules.auto_count(available_h, cell_h, s.gap_y, s.gutter_h, on)
        else:  # dokładnie dotychczasowy rachunek
            auto_cols = max(0, floor((available_w+s.gap_x+1e-8)/(cell_w+s.gap_x)))
            auto_rows = max(0, floor((available_h+s.gap_y+1e-8)/(cell_h+s.gap_y)))
        cols = s.columns if s.columns else auto_cols
        rows = s.rows if s.rows else auto_rows
        used_w = marks_rules.axis_length(cols, cell_w, s.gap_x, s.gutter_v, on)
        used_h = marks_rules.axis_length(rows, cell_h, s.gap_y, s.gutter_h, on)
        if cols < 1 or rows < 1 or used_w > available_w+1e-7 or used_h > available_h+1e-7:
            continue
        slots = []
        grid_x = s.margin_x + (available_w-used_w)/2
        grid_y = s.margin_y + (available_h-used_h)/2
        left = grid_x + bleed_for(s)
        top = grid_y + bleed_for(s)
        xs = marks_rules.axis_offsets(cols, cell_w, s.gap_x, s.gutter_v, on)
        ys = marks_rules.axis_offsets(rows, cell_h, s.gap_y, s.gutter_h, on)
        for row in range(rows):
            for col in range(cols):
                slots.append(Slot(left+xs[col], top+ys[row], w, h, angle, col, row))
        gutter_x = (marks_rules.gutter_center(grid_x, cols, cell_w, s.gap_x, s.gutter_v)
                    if marks_rules.gutter_applies(cols, s.gutter_v, on) else None)
        gutter_y = (marks_rules.gutter_center(grid_y, rows, cell_h, s.gap_y, s.gutter_h)
                    if marks_rules.gutter_applies(rows, s.gutter_h, on) else None)
        candidates.append(Geometry(cols, rows, angle, tuple(slots), cols*rows, gutter_x, gutter_y))
    if not candidates:
        raise ValueError('Użytki nie mieszczą się na arkuszu: zmniejsz wymiary/marginesy lub siatkę')
    return max(candidates, key=lambda g: (g.capacity, -(g.rotation == 90)))


def validate_job_roles(jobs: list[Job], documents: dict[str, fitz.Document]):
    """Validate page assignment even when the operator only requested preflight."""
    for job in jobs:
        if job.copies < 1:
            raise ValueError('Nakład musi być >= 1')
        if job.role not in PAGE_ROLES:
            raise ValueError(f'Nieznana rola pliku {Path(job.path).name}: {job.role}')
        count = len(documents[job.path])
        for number, role in job.page_roles.items():
            try:
                number_int = int(number)
            except (ValueError, TypeError):
                raise ValueError(f'Nieprawidłowy numer strony: {number!r}') from None
            if str(number_int) != number or number_int < 1 or number_int > count:
                raise ValueError(f'{Path(job.path).name}: strona {number!r} poza zakresem 1–{count}')
            if role not in PAGE_ROLES:
                raise ValueError(f'{Path(job.path).name}, strona {number}: nieznana rola {role!r}')


def _page_refs(jobs: list[Job], documents: dict[str, fitz.Document]) -> Iterator[SourcePage]:
    """Single-sided and standalone export: only Pomiń changes source order."""
    validate_job_roles(jobs, documents)
    for job in jobs:
        for _ in range(job.copies):
            for i in range(len(documents[job.path])):
                if job.role_for(i) != ROLE_SKIP:
                    yield SourcePage(job.path, i)


def _duplex_pairs(jobs: list[Job], documents: dict[str, fitz.Document]):
    """Build logical recto/verso pairs before putting them into sheet slots.

    - Normalnie: legacy consecutive pairs within each job/copy.
    - Przód: next Tył sparowany in global file/page order.
    - Tył wspólny: one PDF page repeated under all explicit fronts; any
      Normalnie pages are also interpreted as fronts when it exists.
    - Pomiń: excluded from both sides.

    Explicit backs never jump into a legacy Normalnie pair. Missing explicit
    backs are only allowed when *no* explicit backs were supplied (blank verso).
    """
    validate_job_roles(jobs, documents)
    shared_refs: set[SourcePage] = set()
    for job in jobs:
        for i in range(len(documents[job.path])):
            if job.role_for(i) == ROLE_SHARED:
                shared_refs.add(SourcePage(job.path, i))
    if len(shared_refs) > 1:
        raise ValueError('Może być tylko jedna strona oznaczona „Tył wspólny”.')
    shared = next(iter(shared_refs), None)

    pending: list[tuple[SourcePage, SourcePage | None] | SourcePage] = []
    explicit_fronts: list[SourcePage] = []
    explicit_backs: list[SourcePage] = []
    for job in jobs:
        for _ in range(job.copies):
            legacy: list[SourcePage] = []
            def flush_legacy():
                for k in range(0, len(legacy), 2):
                    pending.append((legacy[k], legacy[k+1] if k+1 < len(legacy) else None))
                legacy.clear()
            for i in range(len(documents[job.path])):
                source = SourcePage(job.path, i)
                role = job.role_for(i)
                if role == ROLE_AUTO and shared is None:
                    legacy.append(source)
                    continue
                flush_legacy()
                if role == ROLE_SKIP or role == ROLE_SHARED:
                    continue
                if role == ROLE_BACK:
                    explicit_backs.append(source)
                elif role in (ROLE_FRONT, ROLE_AUTO):
                    pending.append(source)  # fill verso only after all files are read
                    explicit_fronts.append(source)
            flush_legacy()

    if shared is not None and not explicit_fronts:
        raise ValueError('Ustawiono wspólny tył, ale nie ma żadnych przodów do wydruku.')
    if explicit_backs and not explicit_fronts:
        raise ValueError('Są przypisane tyły, ale brakuje stron oznaczonych jako przody.')
    if len(explicit_backs) > len(explicit_fronts):
        raise ValueError(f'Za dużo sparowanych tyłów: {len(explicit_backs)} na {len(explicit_fronts)} przodów.')
    if 0 < len(explicit_backs) < len(explicit_fronts) and shared is None:
        raise ValueError(f'Tyłów jest {len(explicit_backs)}, przodów {len(explicit_fronts)}. '
                         'Dodaj brakujące tyły albo użyj „Tył wspólny”.')
    number = 0
    for pair in pending:
        if isinstance(pair, tuple):
            yield pair
        else:
            back = explicit_backs[number] if number < len(explicit_backs) else shared
            number += 1
            yield (pair, back)


def _flip_slot(slot: Slot, s: Settings) -> Slot:
    """Reorder back-side slots to match the physical sheet after a duplex flip."""
    landscape = s.sheet_w >= s.sheet_h
    flip_horizontal = (s.flip == 'Długa krawędź') != landscape
    if flip_horizontal:
        return Slot(s.sheet_w-slot.x-slot.w, slot.y, slot.w, slot.h,
                    slot.rotation, slot.col, slot.row)
    return Slot(slot.x, s.sheet_h-slot.y-slot.h, slot.w, slot.h,
                slot.rotation, slot.col, slot.row)


def _booklet_sides(jobs: list[Job], documents: dict[str, fitz.Document], s: Settings):
    """Saddle-stitched 2-up signature with blank-page padding to a multiple of 4."""
    if len(jobs) != 1:
        raise ValueError('Broszura 2-up: użyj jednego pliku PDF na raz')
    job = jobs[0]
    validate_job_roles(jobs, documents)
    if job.copies < 1:
        raise ValueError('Nakład musi być >= 1')
    refs = [SourcePage(job.path, i) for i in range(len(documents[job.path]))
            if job.role_for(i) != ROLE_SKIP]
    if not refs:
        raise ValueError('Brak stron broszury po wykluczeniu stron z montażu')
    refs += [None]*((-len(refs)) % 4)
    n = len(refs)
    required_w = 2*(s.trim_w+2*bleed_for(s)) + s.gap_x
    required_h = s.trim_h+2*bleed_for(s)
    if required_w > s.sheet_w - 2*s.margin_x or required_h > s.sheet_h - 2*s.margin_y:
        raise ValueError('Broszura 2-up nie mieści się: zmień arkusz albo format strony')
    left = (s.sheet_w - required_w)/2 + bleed_for(s)
    top = (s.sheet_h - required_h)/2 + bleed_for(s)
    slots = [Slot(left, top, s.trim_w, s.trim_h, 0, 0, 0),
             Slot(left+s.trim_w+2*bleed_for(s)+s.gap_x, top,
                  s.trim_w, s.trim_h, 0, 1, 0)]
    for _ in range(job.copies):
        for i in range(n//4):
            # Outside of folded sheet: last/first, inside: second/penultimate.
            front = (refs[n-1-2*i], refs[2*i])
            back = (refs[2*i+1], refs[n-2-2*i])
            yield SheetSide(i+1, 0, tuple(Placement(p, slot, 0) for p, slot in zip(front, slots)))
            yield SheetSide(i+1, 1, tuple(Placement(p, slot, 1) for p, slot in zip(back, slots)))


ECONOMIC_MAX_SHEETS = 10000


def economic_demands(jobs: list[Job], documents: dict[str, fitz.Document]) -> dict[SourcePage, int]:
    """Requested physical impressions per individual PDF page (not per file).

    A multipage PDF with copies=100 means 100 of EACH non-skipped page.
    Multiple entries referencing the same page are combined deterministically.
    Duplex-only role markers are deliberately rejected for this single-sided mode.
    """
    validate_job_roles(jobs, documents)
    quantities: dict[SourcePage, int] = {}
    for job in jobs:
        for page in range(len(documents[job.path])):
            role = job.role_for(page)
            if role not in (ROLE_AUTO, ROLE_SKIP):
                raise ValueError('Montaż ekonomiczny jest jednostronny. Usuń role przód/tył lub zmień tryb.')
            if role != ROLE_SKIP:
                ref = SourcePage(job.path, page)
                quantities[ref] = quantities.get(ref, 0) + job.copies
    if not quantities:
        raise ValueError('Brak stron do montażu ekonomicznego po pominięciu stron.')
    return quantities


def _economic_sides(jobs: list[Job], documents: dict[str, fitz.Document],
                    s: Settings) -> Iterator[SheetSide]:
    """Proportionally mix artworks with exact quantities and zero forced surplus.

    Each sheet is packed to capacity (except the last). We apportion the
    remaining quantity across the next sheet using largest remainders.
    This is a *single-gross-size, single-sided* layout, not mixed-size nesting.
    """
    remaining = economic_demands(jobs, documents)
    g = geometry(s)
    refs = tuple(remaining)  # keep input order for deterministic placements
    total = sum(remaining.values())
    minimum_sheets = (total + g.capacity - 1) // g.capacity
    if minimum_sheets > ECONOMIC_MAX_SHEETS:
        raise ValueError(f'Montaż ekonomiczny wymaga {minimum_sheets} arkuszy PDF. '
                         f'Limit bezpiecznego eksportu to {ECONOMIC_MAX_SHEETS}. '
                         'Podziel nakład na mniejsze partie.')
    sheet = 0
    while total:
        count = min(total, g.capacity)
        base = [count * remaining[ref] // total for ref in refs]
        # Hamilton apportionment; extra slots awarded by fractional remainder.
        unassigned = count - sum(base)
        ranked = sorted(range(len(refs)),
                        key=lambda i: (-(count * remaining[refs[i]] % total), i))
        for idx in ranked:
            if not unassigned:
                break
            if base[idx] < remaining[refs[idx]]:
                base[idx] += 1
                unassigned -= 1
        if unassigned or not sum(base) == count:
            raise RuntimeError('Nie udało się podzielić arkusza według nakładów.')
        placements = []
        for i, ref in enumerate(refs):
            placements.extend(ref for _ in range(base[i]))
            remaining[ref] -= base[i]
        sheet += 1
        yield SheetSide(sheet, 0, tuple(
            Placement(ref, g.slots[i], 0) for i, ref in enumerate(placements)))
        total -= count


@dataclass(frozen=True)
class EconomicLine:
    source: SourcePage
    requested: int
    planned: int

    @property
    def shortage(self) -> int:
        return max(0, self.requested-self.planned)

    @property
    def surplus(self) -> int:
        return max(0, self.planned-self.requested)


@dataclass(frozen=True)
class EconomicPattern:
    signature: tuple[SourcePage | None, ...]
    sheet_count: int
    first_sheet: int


@dataclass(frozen=True)
class EconomicReport:
    physical_sheets: int
    capacity: int
    filled_slots: int
    empty_slots: int
    lines: tuple[EconomicLine, ...]
    patterns: tuple[EconomicPattern, ...]

    @property
    def overproduction(self) -> int:
        return sum(line.surplus for line in self.lines)

    @property
    def shortage(self) -> int:
        return sum(line.shortage for line in self.lines)


def economic_report(project: Project, docs: dict[str, fitz.Document]) -> EconomicReport:
    """Audit ACTUAL final placements, including manual edits and blanks.

    The same project_sides iterator drives export, preview and this audit.
    """
    if project.settings.mode != 'Ekonomiczny':
        raise ValueError('Raport nakładów jest dostępny tylko w trybie Ekonomiczny.')
    expected = economic_demands(project.jobs, docs)
    actual: Counter[SourcePage] = Counter()
    patterns: dict[tuple[tuple, ...], list] = {}
    sheets = 0
    occupied = 0
    cap = geometry(project.settings).capacity
    for side in project_sides(project, docs):
        sheets += 1
        # Keep individual turns/displacements in the pattern key. Two sheets
        # with identical artworks but different manual geometry are NOT one template.
        pattern = tuple((p.source, round(p.slot.x, 4), round(p.slot.y, 4),
                         round(p.slot.w, 4), round(p.slot.h, 4), p.slot.rotation)
                        for p in side.placements)
        pattern += ((None,),)*(cap-len(pattern))
        if pattern not in patterns:
            refs = tuple(p.source for p in side.placements) + (None,)*(cap-len(side.placements))
            patterns[pattern] = [0, sheets, refs]
        patterns[pattern][0] += 1
        for p in side.placements:
            if p.source is not None:
                actual[p.source] += 1
                occupied += 1
    unexpected = [ref for ref in actual if ref not in expected]
    ordered = list(expected) + unexpected
    lines = tuple(EconomicLine(ref, expected.get(ref, 0), actual.get(ref, 0)) for ref in ordered)
    return EconomicReport(sheets, cap, occupied, sheets*cap-occupied, lines,
                          tuple(EconomicPattern(v[2], v[0], v[1]) for v in patterns.values()))

def plan_sides(jobs: list[Job], documents: dict[str, fitz.Document], s: Settings) -> Iterator[SheetSide]:
    if not jobs:
        return
    if s.mode == 'Broszura':
        yield from _booklet_sides(jobs, documents, s)
        return
    if s.mode == 'Ekonomiczny':
        yield from _economic_sides(jobs, documents, s)
        return
    g = geometry(s)
    if s.mode == 'Jednostronnie':
        iterator = iter(_page_refs(jobs, documents))
        sheet_no = 0
        while group := tuple(islice(iterator, g.capacity)):
            sheet_no += 1
            yield SheetSide(sheet_no, 0, tuple(Placement(p, g.slots[i], 0)
                                                for i, p in enumerate(group)))
    else:
        iterator = iter(_duplex_pairs(jobs, documents))
        sheet_no = 0
        while group := tuple(islice(iterator, g.capacity)):
            sheet_no += 1
            yield SheetSide(sheet_no, 0, tuple(Placement(pair[0], g.slots[i], 0)
                                                for i, pair in enumerate(group)))
            yield SheetSide(sheet_no, 1, tuple(Placement(pair[1], _flip_slot(g.slots[i], s), 1)
                                                for i, pair in enumerate(group)))


def _manual_key(side: SheetSide, index: int) -> str:
    return f'{side.sheet_number}:{side.side}:{index}'


def _slot_from_edit(base: Slot, entry: dict, settings: Settings) -> Slot:
    """Apply a rigid 0.1-mm transform to a single use, retaining its centre on rotation.

    Rotation is relative to automatic layout; 90/270 swap its net width/height.
    Only coordinates change: PDF source vectors and print size are preserved.
    """
    angle = entry.get('rotate', 0)
    dx = entry.get('dx', 0.0)
    dy = entry.get('dy', 0.0)
    if type(angle) is not int or angle not in (0, 90, 180, 270):
        raise ValueError('Ręczny obrót musi wynosić 0, 90, 180 lub 270°.')
    for name, value in (('X', dx), ('Y', dy)):
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError(f'Niepoprawne przesunięcie {name} użytku.')
        if abs(value * 10 - round(value * 10)) > 1e-6:
            raise ValueError(f'Przesunięcie {name} musi być wielokrotnością 0,1 mm.')
    w, h = (base.h, base.w) if angle in (90, 270) else (base.w, base.h)
    x = base.x + (base.w - w) / 2 + dx
    y = base.y + (base.h - h) / 2 + dy
    bleed = bleed_for(settings)
    if x < bleed - 1e-5 or y < bleed - 1e-5 or (x+w+bleed > settings.sheet_w+1e-5
            or y+h+bleed > settings.sheet_h+1e-5):
        raise ValueError('Użytek ze spadami wychodzi poza arkusz. Zmniejsz przesunięcie lub obrót.')
    return Slot(x, y, w, h, (base.rotation + angle) % 360, base.col, base.row)


def _complete_side(side: SheetSide, s: Settings, needed: int) -> SheetSide:
    """Add addressable empty slots to a partially filled sheet, without new pages."""
    if s.mode == 'Broszura':
        if needed > 2:
            raise ValueError('Broszura pozwala na dwa użytki w jednym arkuszu.')
        return side  # booklet already includes two cells (also when blank)
    g = geometry(s)
    if needed > g.capacity:
        raise ValueError(f'Pole ręcznego montażu {needed} wykracza poza siatkę {g.capacity}.')
    items = list(side.placements)
    for i in range(len(items), needed):
        slot = g.slots[i]
        if side.side == 1 and s.mode == 'Dwustronnie':
            slot = _flip_slot(slot, s)
        items.append(Placement(None, slot, side.side))
    return SheetSide(side.sheet_number, side.side, tuple(items))


def apply_overrides(side: SheetSide, project: Project, sources: dict[str, fitz.Document],
                    *, full_grid: bool = False) -> SheetSide:
    """Apply identical layout edits to preview and export, even in initially empty cells."""
    prefix = f'{side.sheet_number}:{side.side}:'
    used_indices = []
    for key in project.overrides:
        if key.startswith(prefix):
            try:
                i = int(key[len(prefix):])
            except ValueError:
                raise ValueError(f'Niepoprawny klucz ręcznej pozycji: {key}') from None
            if i < 0:
                raise ValueError(f'Niepoprawny klucz ręcznej pozycji: {key}')
            used_indices.append(i)
    capacity = 2 if project.settings.mode == 'Broszura' else geometry(project.settings).capacity
    wanted = capacity if full_grid else max(len(side.placements), max(used_indices, default=-1)+1)
    side = _complete_side(side, project.settings, wanted)
    if not project.overrides:
        return side
    items = list(side.placements)
    for i, placement in enumerate(items):
        entry = project.overrides.get(_manual_key(side, i))
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise ValueError('Niepoprawne ręczne ustawienia użytku.')
        ref = placement.source
        if entry.get('blank', False):
            ref = None
        elif 'path' in entry or 'page' in entry:
            path = entry.get('path')
            page = entry.get('page')
            if path not in sources or type(page) is not int or not (0 <= page < len(sources[path])):
                raise ValueError(f'Ręcznie wybrana strona nie istnieje: {path}, {page}')
            ref = SourcePage(path, page)
        slot = _slot_from_edit(placement.slot, entry, project.settings)
        items[i] = Placement(ref, slot, placement.side)
    return SheetSide(side.sheet_number, side.side, tuple(items))


def calibrate_verso(side: SheetSide, s: Settings) -> SheetSide:
    """Move back-side content/marks in *physical sheet coordinates*.

    Slots have already been flipped and manually transformed. Apply calibration
    last and only once to the output geometry; source PDF vectors stay intact.
    Recto, booklet and standalone exports are intentionally unaffected.
    """
    if side.side != 1 or s.mode != 'Dwustronnie':
        return side
    x, y = s.verso_shift_x, s.verso_shift_y
    if not x and not y:
        return side
    b = bleed_for(s)
    items = []
    for p in side.placements:
        slot = p.slot
        shifted = Slot(slot.x + x, slot.y + y, slot.w, slot.h,
                       slot.rotation, slot.col, slot.row)
        if p.source is not None and (shifted.x-b < -1e-5 or shifted.y-b < -1e-5 or
                shifted.x+shifted.w+b > s.sheet_w+1e-5 or
                shifted.y+shifted.h+b > s.sheet_h+1e-5):
            raise ValueError('Kalibracja verso przesuwa użytek ze spadami poza arkusz. Zmniejsz offset X/Y.')
        items.append(Placement(p.source, shifted, p.side))
    return SheetSide(side.sheet_number, side.side, tuple(items))


def project_sides(project: Project, sources: dict[str, fitz.Document]):
    for side in plan_sides(project.jobs, sources, project.settings):
        edited = apply_overrides(side, project, sources)
        yield calibrate_verso(edited, project.settings)


def _edit_entry(project: Project, side: SheetSide, index: int) -> dict:
    if not 0 <= index < len(side.placements):
        raise IndexError('Nieprawidłowy numer użytku')
    return project.overrides.setdefault(_manual_key(side, index), {})


def assign_slot(project: Project, side: SheetSide, index: int, source: SourcePage | None):
    """Replace only the artwork; preserve per-cell rotation and movement."""
    entry = _edit_entry(project, side, index)
    entry.pop('path', None)
    entry.pop('page', None)
    entry.pop('blank', None)
    if source is None:
        entry['blank'] = True
    else:
        entry.update(path=source.path, page=source.index)


def swap_slots(project: Project, side: SheetSide, a: int, b: int):
    """Swap contents between two cells, keeping each cell's own transforms."""
    if not 0 <= a < len(side.placements) or not 0 <= b < len(side.placements):
        raise IndexError('Nieprawidłowy numer użytku')
    if a == b:
        return
    assign_slot(project, side, a, side.placements[b].source)
    assign_slot(project, side, b, side.placements[a].source)


def set_slot_transform(project: Project, side: SheetSide, index: int, *,
                       dx: float | None = None, dy: float | None = None,
                       rotate: int | None = None):
    """Set absolute displacement (0.1 mm grid) and relative right-angle rotation.

    Values replace existing transforms rather than accumulate; this prevents
    pointer-drag rounding drift. The active, unedited slot is not the transform
    origin: the original regular-grid slot is always the origin.
    """
    entry = _edit_entry(project, side, index)
    updated = dict(entry)
    if dx is not None:
        updated['dx'] = float(dx)
    if dy is not None:
        updated['dy'] = float(dy)
    if rotate is not None:
        updated['rotate'] = rotate
    # Validate the exact transform against the original regular grid.
    sources = None
    base = None
    if project.settings.mode == 'Broszura':
        # Booklet base uses the same relative rotation, but different base slots.
        # Recover the original from a per-cell editor's already-adjusted slot.
        base = _undo_slot_edit(side.placements[index].slot, entry)
    else:
        normal = geometry(project.settings).slots[index]
        if side.side == 1 and project.settings.mode == 'Dwustronnie':
            normal = _flip_slot(normal, project.settings)
        base = normal
    _slot_from_edit(base, updated, project.settings)
    project.overrides[_manual_key(side, index)] = updated


def _undo_slot_edit(slot: Slot, entry: dict) -> Slot:
    """Recover booklet's unmodified cell from its currently edited geometry."""
    rotate = entry.get('rotate', 0)
    w, h = (slot.h, slot.w) if rotate in (90, 270) else (slot.w, slot.h)
    x = slot.x - (w-slot.w)/2 - entry.get('dx', 0)
    y = slot.y - (h-slot.h)/2 - entry.get('dy', 0)
    return Slot(x, y, w, h, (slot.rotation-rotate) % 360, slot.col, slot.row)


def reset_slot(project: Project, side: SheetSide, index: int):
    """Restore fully automatic contents AND unmodified geometry for one cell."""
    if not 0 <= index < len(side.placements):
        raise IndexError('Nieprawidłowy numer użytku')
    project.overrides.pop(_manual_key(side, index), None)


def overlapping_uses(side: SheetSide, s: Settings) -> list[tuple[int, int]]:
    """Detect collisions of PRINTED gross rectangles (net use plus bleed)."""
    b = bleed_for(s)
    result = []
    for i, a in enumerate(side.placements):
        if a.source is None: continue
        ra = (a.slot.x-b,a.slot.y-b,a.slot.x+a.slot.w+b,a.slot.y+a.slot.h+b)
        for j in range(i+1,len(side.placements)):
            q=side.placements[j]
            if q.source is None: continue
            rb=(q.slot.x-b,q.slot.y-b,q.slot.x+q.slot.w+b,q.slot.y+q.slot.h+b)
            if min(ra[2],rb[2])-max(ra[0],rb[0]) > 1e-5 and min(ra[3],rb[3])-max(ra[1],rb[1]) > 1e-5:
                result.append((i,j))
    return result


def _draw_marks(page: fitz.Page, slot: Slot, s: Settings):
    """Create slim vector trim marks separated from bleed when space permits."""
    x, y, w, h = slot.x, slot.y, slot.w, slot.h
    # Do not print black into bleed. Each mark begins `mark_offset` (default 0.8 mm) after bleed.
    offset = bleed_for(s) + s.mark_offset
    length = s.mark_length
    width = s.mark_width_pt
    for cx in (x, x+w):
        direction = -1 if cx == x else 1
        a, b = cx+direction*offset, cx+direction*(offset+length)
        if min(a, b) >= 0 and max(a, b) <= s.sheet_w:
            for yy in (y, y+h):
                page.draw_line((pt(a), pt(yy)), (pt(b), pt(yy)), color=(0,0,0), width=width)
    for cy in (y, y+h):
        direction = -1 if cy == y else 1
        a, b = cy+direction*offset, cy+direction*(offset+length)
        if min(a, b) >= 0 and max(a, b) <= s.sheet_h:
            for xx in (x, x+w):
                page.draw_line((pt(xx), pt(a)), (pt(xx), pt(b)), color=(0,0,0), width=width)


def gutter_mark_lines(s: Settings) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Odcinki znaczników wycinki w mm ((x0, y0), (x1, y1)); pusta lista, gdy wycinki nie ma (H-23)."""
    if not (s.gutter_on and s.gutter_marks) or s.mode == 'Broszura':
        return []
    g = geometry(s)
    lines = []
    if g.gutter_x is not None:
        for a, b in marks_rules.gutter_mark_segments(g.gutter_x, s.margin_y, s.sheet_h - s.margin_y,
                                                     s.gutter_mark_length):
            lines.append(((g.gutter_x, a), (g.gutter_x, b)))
    if g.gutter_y is not None:
        for a, b in marks_rules.gutter_mark_segments(g.gutter_y, s.margin_x, s.sheet_w - s.margin_x,
                                                     s.gutter_mark_length):
            lines.append(((a, g.gutter_y), (b, g.gutter_y)))
    return lines


def gutter_notes(s: Settings) -> list[str]:
    """Wyjaśnienie, dlaczego włączona wycinka nie została uwzględniona (zamiast cichego pominięcia)."""
    if not s.gutter_on or s.mode == 'Broszura':
        return ['Wycinka nie dotyczy trybu Broszura.'] if s.gutter_on and (s.gutter_v or s.gutter_h) else []
    g = geometry(s)
    notes = []
    if s.gutter_v > 0 and g.gutter_x is None:
        notes.append(f'Wycinka pionowa pominięta: liczba kolumn ({g.cols}) nie jest parzysta.')
    if s.gutter_h > 0 and g.gutter_y is None:
        notes.append(f'Wycinka pozioma pominięta: liczba wierszy ({g.rows}) nie jest parzysta.')
    return notes


def _rotate_point(x: float, y: float, width: float, height: float,
                  angle: int) -> tuple[float, float]:
    """Coordinates relative to TrimBox; positive angles follow PDF view rotation."""
    if angle == 0:
        return x, y
    if angle == 90:
        return height-y, x
    if angle == 180:
        return width-x, height-y
    if angle == 270:
        return y, width-x
    raise ValueError('Obrót musi być wielokrotnością 90°')


def scaling_layout(source_w: float, source_h: float, target_w: float,
                   target_h: float, mode: str) -> tuple[float, float, float]:
    """Return uniform source-to-target scale and centered displacement.

    Arguments must use the same unit, e.g. all mm or all PDF points.
    The output is (scale, x_offset, y_offset) in those units. Positive
    offsets indicate letterboxing; negative offsets indicate cropping.
    """
    if min(source_w, source_h, target_w, target_h) <= 0:
        raise ValueError('Nieprawidłowy rozmiar strony do skalowania')
    if mode == 'Dopasuj':
        scale = min(target_w/source_w, target_h/source_h)
    elif mode == 'Wypełnij':
        scale = max(target_w/source_w, target_h/source_h)
    elif mode in ('Bez skalowania', 'Kadruj 1:1'):
        scale = 1.0
    else:
        raise ValueError('Nieznany sposób skalowania PDF')
    return scale, (target_w-source_w*scale)/2, (target_h-source_h*scale)/2


def _inverse_rotate_point(x: float, y: float, width: float,
                          height: float, angle: int) -> tuple[float, float]:
    """Undo _rotate_point, all in unrotated source coordinates."""
    if angle == 0:
        return x, y
    if angle == 90:
        return y, height-x
    if angle == 180:
        return width-x, height-y
    if angle == 270:
        return width-y, x
    raise ValueError('Obrót musi być wielokrotnością 90°')


def crop_offsets(jobs: list[Job]) -> dict[str, tuple[float, float]]:
    """Shared per-path crop positions, including safety for duplicate source paths."""
    offsets = {}
    for job in jobs:
        x, y = float(job.crop_x), float(job.crop_y)
        if not isfinite(x) or not isfinite(y):
            raise ValueError(f'{Path(job.path).name}: niepoprawne przesunięcie kadru')
        if abs(x)>10000 or abs(y)>10000:
            raise ValueError(f'{Path(job.path).name}: przesunięcie kadru poza limitem')
        if job.path in offsets and offsets[job.path] != (x, y):
            raise ValueError(f'{Path(job.path).name}: ten sam PDF ma różne kadry w kilku pozycjach listy')
        offsets[job.path] = (x, y)
    return offsets


def crop_centre(source_w: float, source_h: float, gross_w: float, gross_h: float,
                x: float, y: float) -> None:
    """Reject missing real bleed caused by moving the crop out of source boundaries."""
    if abs(x) > (source_w-gross_w)/2 + .02 or abs(y) > (source_h-gross_h)/2 + .02:
        raise ValueError(f'Kadr + spad {gross_w:g} × {gross_h:g} mm wychodzi poza oryginał '
                         f'{source_w:.2f} × {source_h:.2f} mm przy X={x:g}, Y={y:g} mm.')


def _place_pdf(target: fitz.Page, p: SourcePage, slot: Slot, s: Settings,
               sources: dict[str, fitz.Document],
               offsets: dict[str, tuple[float, float]] | None = None):
    original = sources[p.path][p.index]
    trim = fitz.Rect(original.trimbox)
    media = media_rect(original)
    original_angle = original.rotation
    apparent_w, apparent_h = ((mm(trim.height), mm(trim.width))
                              if original_angle in (90, 270)
                              else (mm(trim.width), mm(trim.height)))
    if s.scale_mode == 'Kadruj 1:1' and not s.auto_source and s.source_w > 0:
        if abs(apparent_w - s.source_w) > .5 or abs(apparent_h - s.source_h) > .5:
            raise ValueError(
                f'{Path(p.path).name}, strona {p.index+1}: rzeczywisty oryginał '
                f'{apparent_w:.2f} × {apparent_h:.2f} mm różni się od ustawionego '
                f'{s.source_w:g} × {s.source_h:g} mm. Popraw rozmiar oryginału.')
    if s.scale_mode == 'Bez skalowania' and (
        abs(apparent_w-s.trim_w) > 0.5 or abs(apparent_h-s.trim_h) > 0.5
    ):
        raise ValueError(
            f'{Path(p.path).name}, strona {p.index+1}: TrimBox {apparent_w:.2f} × '
            f'{apparent_h:.2f} mm nie odpowiada {s.trim_w:g} × {s.trim_h:g} mm. '
            'Wybierz skalowanie PDF (Dopasuj / Wypełnij) albo ustaw poprawny format.')
    if trim.is_empty or any(abs(a-b) > .05 for a,b in zip(trim, trim & media)):
        raise ValueError(f'{Path(p.path).name}: TrimBox poza MediaBox')

    if s.scale_mode == 'Kadruj 1:1':
        # The selected physical source PDF dimensions are NOT its finished dimensions.
        # Crop the centered target net rectangle at 100% with no geometric scaling.
        # The existing bleed-placement code below requests the margin outside it.
        target_w = pt(s.trim_h if original_angle in (90, 270) else s.trim_w)
        target_h = pt(s.trim_w if original_angle in (90, 270) else s.trim_h)
        gross_w, gross_h = gross_dimensions(s)
        if apparent_w + .02 < gross_w or apparent_h + .02 < gross_h:
            raise ValueError(
                f'{Path(p.path).name}, strona {p.index+1}: oryginał jest za mały '
                f'na użytek ze spadami {gross_w:g} × {gross_h:g} mm. '
                'Kadrowanie nie może utworzyć brakującej grafiki.')
        if target_w > trim.width + .02 or target_h > trim.height + .02:
            raise ValueError(
                f'{Path(p.path).name}, strona {p.index+1}: oryginał jest za mały '
                f'na kadrowanie 1:1 do {s.trim_w:g} × {s.trim_h:g} mm.')
        shift_x, shift_y = (offsets or {}).get(p.path, (0.0, 0.0))
        crop_centre(apparent_w, apparent_h, gross_w, gross_h, shift_x, shift_y)
        source_w, source_h = mm(trim.width), mm(trim.height)
        new_x, new_y = _inverse_rotate_point(
            apparent_w/2 + shift_x, apparent_h/2 + shift_y,
            source_w, source_h, original_angle)
        cx = trim.x0 + pt(new_x)
        cy = trim.y0 + pt(new_y)
        trim = fitz.Rect(cx-target_w/2, cy-target_h/2, cx+target_w/2, cy+target_h/2)

    bleedbox = fitz.Rect(original.bleedbox)
    limit = media
    if (s.scale_mode != 'Kadruj 1:1' and bleedbox.contains(trim)
            and bleedbox != trim and bleedbox != original.cropbox):
        limit = bleedbox & media
    angle = (original_angle + slot.rotation) % 360
    final_width = trim.width if angle in (0, 180) else trim.height
    final_height = trim.height if angle in (0, 180) else trim.width
    dest_w, dest_h = pt(slot.w), pt(slot.h)
    factor, dx, dy = scaling_layout(final_width, final_height, dest_w, dest_h,
                                    ('Bez skalowania' if s.scale_mode == 'Kadruj 1:1' else s.scale_mode))
    # For exact-size source PDFs tolerate printer/export rounding <=0.5mm
    # without stretching artwork in opposite dimensions.
    base_x = pt(slot.x) + dx
    base_y = pt(slot.y) + dy

    # Required source bleed becomes larger when shrinking a source (e.g. A4
    # -> A6 needs 4mm source bleed to supply 2mm at output). Missing areas
    # stay white: the engine never invents an extended image.
    needed = pt(bleed_for(s))/factor
    desired = fitz.Rect(trim.x0-needed, trim.y0-needed,
                        trim.x1+needed, trim.y1+needed)

    # The 'Wypełnij' mode enlarges and crops to the target cell. Transform
    # target cell limits backwards, then clip the source to that range, so
    # content never bleeds into neighboring imposition cells.
    allowed_x0 = (pt(slot.x-bleed_for(s))-base_x)/factor
    allowed_y0 = (pt(slot.y-bleed_for(s))-base_y)/factor
    allowed_x1 = (pt(slot.x+slot.w+bleed_for(s))-base_x)/factor
    allowed_y1 = (pt(slot.y+slot.h+bleed_for(s))-base_y)/factor
    orig_corners = [_inverse_rotate_point(x, y, trim.width, trim.height, angle)
                    for x, y in ((allowed_x0, allowed_y0),
                                 (allowed_x0, allowed_y1),
                                 (allowed_x1, allowed_y0),
                                 (allowed_x1, allowed_y1))]
    bounds = fitz.Rect(trim.x0 + min(x for x, _ in orig_corners),
                       trim.y0 + min(y for _, y in orig_corners),
                       trim.x0 + max(x for x, _ in orig_corners),
                       trim.y0 + max(y for _, y in orig_corners))
    visible = desired & limit & bounds
    if s.trim_crop and s.trim_crop_pt > 0:
        # Docięcie TrimBox: krawędź liczona w orientacji strony widocznej dla operatora (po /Rotate).
        side_name = marks_rules.trim_crop_side(p.index + 1)
        tw, th = trim.width, trim.height
        aw, ah = (th, tw) if original_angle in (90, 270) else (tw, th)
        big = 1e6
        x0a, x1a = (s.trim_crop_pt, big) if side_name == 'left' else (-big, aw - s.trim_crop_pt)
        kept = [_inverse_rotate_point(xa, ya, tw, th, original_angle)
                for xa, ya in ((x0a, -big), (x1a, -big), (x0a, ah + big), (x1a, ah + big))]
        visible = visible & fitz.Rect(trim.x0 + min(x for x, _ in kept), trim.y0 + min(y for _, y in kept),
                                      trim.x0 + max(x for x, _ in kept), trim.y0 + max(y for _, y in kept))
    if visible.is_empty or visible.width <= 0 or visible.height <= 0:
        raise ValueError(f'{Path(p.path).name}: nieprawidłowy obszar po skalowaniu i kadrowaniu')

    corners = [(visible.x0, visible.y0), (visible.x1, visible.y0),
               (visible.x0, visible.y1), (visible.x1, visible.y1)]
    rotated = [_rotate_point(x-trim.x0, y-trim.y0, trim.width, trim.height, angle)
               for x, y in corners]
    box = fitz.Rect(base_x + min(x for x, _ in rotated)*factor,
                    base_y + min(y for _, y in rotated)*factor,
                    base_x + max(x for x, _ in rotated)*factor,
                    base_y + max(y for _, y in rotated)*factor)
    old_crop = fitz.Rect(original.cropbox)
    try:
        original.set_rotation(0)
        original.set_cropbox(media)
        target.show_pdf_page(box, sources[p.path], p.index,
                             clip=visible, rotate=angle, keep_proportion=True)
    finally:
        original.set_cropbox(old_crop)
        original.set_rotation(original_angle)


def render_side(side: SheetSide, sources: dict[str, fitz.Document], s: Settings,
                destination: fitz.Document | None = None,
                offsets: dict[str, tuple[float, float]] | None = None) -> fitz.Document:
    out = destination if destination is not None else fitz.open()
    target = out.new_page(width=pt(s.sheet_w), height=pt(s.sheet_h))
    for item in side.placements:
        if item.source is not None:
            _place_pdf(target, item.source, item.slot, s, sources, offsets)
        if s.crop_marks and item.source is not None:
            _draw_marks(target, item.slot, s)
        if s.show_page_labels:
            txt = f'{item.source.index+1}  ' if item.source else 'PUSTA  '
            target.insert_text((pt(item.slot.x+1), pt(item.slot.y+item.slot.h-1)),
                               txt, fontsize=6, color=(.3,.3,.3), overlay=True)
    for (x0, y0), (x1, y1) in gutter_mark_lines(s):
        target.draw_line((pt(x0), pt(y0)), (pt(x1), pt(y1)), color=(0, 0, 0), width=s.gutter_mark_pt)
    return out


def open_sources(jobs: list[Job]) -> dict[str, fitz.Document]:
    sources = {}
    try:
        for job in jobs:
            if job.path not in sources:
                if not Path(job.path).is_file():
                    raise FileNotFoundError(f'Brak pliku: {job.path}')
                try:
                    doc = fitz.open(job.path)
                except Exception as exc:  # FileDataError itp. — plik nie jest PDF albo jest uszkodzony
                    raise ValueError(f'Plik nie jest poprawnym PDF albo jest uszkodzony: {job.path}') from exc
                if not doc.is_pdf or doc.needs_pass or len(doc) == 0:
                    doc.close()
                    raise ValueError(f'Nieobsługiwany lub zabezpieczony PDF: {job.path}')
                sources[job.path] = doc
        return sources
    except Exception:
        for doc in sources.values():
            doc.close()
        raise


# „Wykonaj impozycję” w Impozycjonerze 4: wszystkie arkusze, tylko aktywny albo wszystkie oprócz aktywnego.
RUN_ALL = 'Wszystkie arkusze'
RUN_ACTIVE = 'Tylko aktywny arkusz'
RUN_EXCEPT_ACTIVE = 'Wszystkie oprócz aktywnego'
RUN_MODES = (RUN_ALL, RUN_ACTIVE, RUN_EXCEPT_ACTIVE)


def select_sides(sides, run_mode: str = RUN_ALL, active_sheet: int | None = None):
    """Filtruj strony arkuszy wg trybu wykonania. Arkusz = numer arkusza (recto i verso razem)."""
    if run_mode not in RUN_MODES:
        raise ValueError(f'Nieznany tryb wykonania impozycji: {run_mode}')
    if run_mode == RUN_ALL:
        yield from sides
        return
    if active_sheet is None or active_sheet < 1:
        raise ValueError('Wybierz aktywny arkusz w podglądzie')
    keep = (lambda n: n == active_sheet) if run_mode == RUN_ACTIVE else (lambda n: n != active_sheet)
    yield from (side for side in sides if keep(side.sheet_number))


METADATA_FIELDS = ('author', 'title', 'subject', 'keywords')


def output_metadata(output: str, fields: dict[str, str]) -> dict[str, str]:
    """Metadane wyniku jak w Ustawieniach Impozycjonera 4: Autor, Tytuł, Temat, Słowa kluczowe;
    puste pole = nazwa pliku wynikowego."""
    unknown = set(fields) - set(METADATA_FIELDS)
    if unknown:
        raise ValueError(f'Nieznane pole metadanych: {", ".join(sorted(unknown))}')
    name = Path(output).stem
    result = {key: (str(fields.get(key) or '').strip() or name) for key in METADATA_FIELDS}
    result['creator'] = 'Impozycjoner Studio 0.4.1'
    return result


def export_pdf(project: Project, output: str, metadata: dict[str, str] | None = None,
               run_mode: str = RUN_ALL, active_sheet: int | None = None):
    """Domyślnie (bez metadanych, wszystkie arkusze) zachowanie jest takie jak w 0.4.1."""
    validate(project.settings)
    if not project.jobs:
        raise ValueError('Dodaj co najmniej jeden plik PDF')
    sources = open_sources(project.jobs)
    offsets = crop_offsets(project.jobs)
    out = fitz.open()
    try:
        if project.settings.mode == 'Ekonomiczny':
            audit = economic_report(project, sources)
            if audit.overproduction or audit.shortage:
                raise ValueError(f'Ręczne zmiany naruszają nakłady: nadprodukcja {audit.overproduction}, '
                                 f'brakuje {audit.shortage}. Przywróć przypisania lub zamień użytki.')
        count = 0
        for side in select_sides(project_sides(project, sources), run_mode, active_sheet):
            render_side(side, sources, project.settings, out, offsets)
            count += 1
        if count == 0:
            raise ValueError('Brak stron do montażu' if run_mode == RUN_ALL
                             else f'Brak arkuszy do wykonania w trybie „{run_mode}”')
        out.set_metadata(output_metadata(output, metadata) if metadata is not None else
                         {'title':'Impozycjoner Studio - montaż PDF',
                          'creator':'Impozycjoner Studio 0.4.1'})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        out.save(output, garbage=3, deflate=True)
        return count
    finally:
        out.close()
        for doc in sources.values():
            doc.close()


def export_pages(project: Project, output: str, metadata: dict[str, str] | None = None) -> int:
    """Produce one original logical page per output page at target net size.

    When bleed > 0, the physical MediaBox includes bleed and TrimBox is
    precisely the requested net format. No crop marks are added.
    """
    validate(project.settings)
    if not project.jobs:
        raise ValueError('Dodaj co najmniej jeden plik PDF')
    s = project.settings
    sources = open_sources(project.jobs)
    offsets = crop_offsets(project.jobs)
    out = fitz.open()
    try:
        for source in _page_refs(project.jobs, sources):
            w = s.trim_w + 2*bleed_for(s)
            h = s.trim_h + 2*bleed_for(s)
            page = out.new_page(width=pt(w), height=pt(h))
            slot = Slot(bleed_for(s), bleed_for(s), s.trim_w, s.trim_h, 0, 0, 0)
            _place_pdf(page, source, slot, s, sources, offsets)
            if bleed_for(s):
                page.set_trimbox(fitz.Rect(pt(bleed_for(s)), pt(bleed_for(s)),
                                           pt(bleed_for(s)+s.trim_w), pt(bleed_for(s)+s.trim_h)))
                page.set_bleedbox(page.rect)
        if len(out) == 0:
            raise ValueError('Brak stron do eksportu')
        out.set_metadata(output_metadata(output, metadata) if metadata is not None else
                         {'title':'Impozycjoner Studio - strony w formacie docelowym',
                          'creator':'Impozycjoner Studio 0.4.1'})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        out.save(output, garbage=3, deflate=True)
        return len(out)
    finally:
        out.close()
        for doc in sources.values():
            doc.close()


def preview(project: Project, pixels: int = 1200, index: int = 0):
    """Returns (PIL.Image, number represented). Lazy: only the requested sheet."""
    from PIL import Image
    validate(project.settings)
    sources = open_sources(project.jobs)
    offsets = crop_offsets(project.jobs)
    try:
        sides = project_sides(project, sources)
        selected = next(islice(sides, index, index+1), None)
        out = fitz.open()
        try:
            if selected is None:
                out.new_page(width=pt(project.settings.sheet_w), height=pt(project.settings.sheet_h))
            else:
                render_side(selected, sources, project.settings, out, offsets)
            page = out[0]
            zoom = min(pixels/page.rect.width, pixels/page.rect.height, 2)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom,zoom), alpha=False)
            return Image.frombytes('RGB', (pix.width,pix.height),pix.samples), selected
        finally:
            out.close()
    finally:
        for doc in sources.values():
            doc.close()


def editor_preview(project: Project, pixels: int = 1200, index: int = 0):
    """Renders a full empty-cell grid for mouse editing, without adding blank sheets."""
    from PIL import Image
    validate(project.settings)
    sources = open_sources(project.jobs)
    offsets = crop_offsets(project.jobs)
    try:
        selected = next(islice(plan_sides(project.jobs, sources, project.settings), index, index+1), None)
        if selected is None:
            return None, None
        selected = calibrate_verso(apply_overrides(selected, project, sources, full_grid=True), project.settings)
        out = fitz.open()
        try:
            render_side(selected, sources, project.settings, out, offsets)
            page = out[0]
            zoom = min(pixels/page.rect.width, pixels/page.rect.height, 2)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False)
            return Image.frombytes('RGB', (pix.width,pix.height),pix.samples), selected
        finally:
            out.close()
    finally:
        for d in sources.values(): d.close()


def save_project(project: Project, path: str):
    """.psimp = zip project. Original input PDFs are linked, not embedded."""
    root = Path(path).resolve().parent
    jobs = []
    for j in project.jobs:
        f = Path(j.path).resolve()
        try:
            file_path = str(f.relative_to(root))
        except ValueError:
            file_path = str(f)
        jobs.append({'path':file_path,'copies':j.copies,
                     'role':j.role,'page_roles':j.page_roles,
                     'crop_x':j.crop_x,'crop_y':j.crop_y})
    relative_overrides = {}
    for key, entry in project.overrides.items():
        copied = dict(entry)
        if copied.get('path'):
            absolute = Path(copied['path']).resolve()
            try:
                copied['path'] = str(absolute.relative_to(root))
            except ValueError:
                copied['path'] = str(absolute)
        relative_overrides[key] = copied
    payload = {'format':'psimp','version':2, 'settings':asdict(project.settings), 'jobs':jobs, 'overrides':relative_overrides}
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.json', json.dumps(payload,ensure_ascii=False,indent=2))


def load_project(path: str) -> Project:
    with zipfile.ZipFile(path, 'r') as z:
        data = json.loads(z.read('project.json'))
    if data.get('format') != 'psimp':
        raise ValueError('Nieznany format projektu')
    base = Path(path).resolve().parent
    settings = Settings(**data['settings'])
    jobs = [Job(path=str((base / j['path']).resolve()) if not Path(j['path']).is_absolute()
                else str(Path(j['path']).resolve()), copies=int(j['copies']),
                role=j.get('role', ROLE_AUTO), page_roles=dict(j.get('page_roles', {})),
                crop_x=float(j.get('crop_x', 0)), crop_y=float(j.get('crop_y', 0)))
            for j in data.get('jobs', [])]
    overrides = data.get('overrides', {})
    if not isinstance(overrides, dict):
        raise ValueError('Niepoprawny format ręcznych zmian arkusza')
    # Stored paths follow the same relative-path convention as source jobs.
    for entry in overrides.values():
        if isinstance(entry, dict) and entry.get('path') and not Path(entry['path']).is_absolute():
            entry['path'] = str((base / entry['path']).resolve())
    return Project(settings, jobs, overrides)


def source_summary(path: str) -> tuple[int, float, float]:
    with fitz.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass or not len(doc):
            raise ValueError('Plik nie jest poprawnym niezabezpieczonym PDF')
        b = doc[0].trimbox
        return (len(doc), round(mm(b.height), 2), round(mm(b.width), 2)) if doc[0].rotation in (90,270) else (len(doc), round(mm(b.width),2), round(mm(b.height),2))
