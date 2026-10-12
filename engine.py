"""Impozycjoner Studio 0.2.0 - original PDF imposition engine.

Uses PDF form XObjects via PyMuPDF. No source pages are rasterized during export.
Units exposed to the operator are millimetres; PyMuPDF operates in points.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import islice
from math import floor, isfinite
from pathlib import Path
from typing import Iterator
import json
import zipfile

import pymupdf as fitz

PT_PER_MM = 72.0 / 25.4


def pt(mm: float) -> float:
    return mm * PT_PER_MM


def mm(points: float) -> float:
    return points / PT_PER_MM


@dataclass
class Job:
    path: str
    copies: int = 1


@dataclass
class Settings:
    sheet_w: float = 450
    sheet_h: float = 320
    trim_w: float = 90
    trim_h: float = 50
    bleed: float = 2
    margin_x: float = 6
    margin_y: float = 6
    gap_x: float = 5
    gap_y: float = 5
    rotation: str = "Auto"  # Auto, 0, 90
    columns: int = 0          # 0 = automatic
    rows: int = 0
    mode: str = "Jednostronnie"  # Jednostronnie | Dwustronnie | Broszura
    flip: str = "Długa krawędź"
    crop_marks: bool = True
    show_page_labels: bool = False


@dataclass
class Project:
    settings: Settings = field(default_factory=Settings)
    jobs: list[Job] = field(default_factory=list)


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


def validate(settings: Settings):
    for key in ('sheet_w', 'sheet_h', 'trim_w', 'trim_h'):
        if not isfinite(getattr(settings, key)) or getattr(settings, key) <= 0:
            raise ValueError(f'{key}: wymiar musi być większy od zera')
    for key in ('bleed', 'margin_x', 'margin_y', 'gap_x', 'gap_y'):
        if not isfinite(getattr(settings, key)) or getattr(settings, key) < 0:
            raise ValueError(f'{key}: wartość nie może być ujemna')
    if settings.columns < 0 or settings.rows < 0:
        raise ValueError('Liczba kolumn/wierszy musi być dodatnia')
    if settings.rotation not in ('Auto', '0', '90', '180', '270'):
        raise ValueError('Nieznana orientacja')
    if settings.mode not in ('Jednostronnie', 'Dwustronnie', 'Broszura'):
        raise ValueError('Nieznany tryb montażu')
    if settings.flip not in ('Długa krawędź', 'Krótka krawędź'):
        raise ValueError('Nieznana metoda odwracania')


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
        cell_w, cell_h = w + 2*s.bleed, h + 2*s.bleed
        auto_cols = max(0, floor((available_w+s.gap_x+1e-8)/(cell_w+s.gap_x)))
        auto_rows = max(0, floor((available_h+s.gap_y+1e-8)/(cell_h+s.gap_y)))
        cols = s.columns if s.columns else auto_cols
        rows = s.rows if s.rows else auto_rows
        used_w = cols*cell_w + (cols-1)*s.gap_x
        used_h = rows*cell_h + (rows-1)*s.gap_y
        if cols < 1 or rows < 1 or used_w > available_w+1e-7 or used_h > available_h+1e-7:
            continue
        slots = []
        left = s.margin_x + (available_w-used_w)/2 + s.bleed
        top = s.margin_y + (available_h-used_h)/2 + s.bleed
        for row in range(rows):
            for col in range(cols):
                slots.append(Slot(left+col*(cell_w+s.gap_x),
                                  top+row*(cell_h+s.gap_y), w, h, angle, col, row))
        candidates.append(Geometry(cols, rows, angle, tuple(slots), cols*rows))
    if not candidates:
        raise ValueError('Użytki nie mieszczą się na arkuszu: zmniejsz wymiary/marginesy lub siatkę')
    return max(candidates, key=lambda g: (g.capacity, -(g.rotation == 90)))


def _page_refs(jobs: list[Job], documents: dict[str, fitz.Document]) -> Iterator[SourcePage]:
    for job in jobs:
        if job.copies < 1:
            raise ValueError('Nakład musi być >= 1')
        doc = documents[job.path]
        for _ in range(job.copies):
            for i in range(len(doc)):
                yield SourcePage(job.path, i)


def _duplex_pairs(jobs: list[Job], documents: dict[str, fitz.Document]):
    """Each input PDF represents one logical job; duplex pairs do not cross jobs."""
    for job in jobs:
        if job.copies < 1:
            raise ValueError('Nakład musi być >= 1')
        doc = documents[job.path]
        for _ in range(job.copies):
            for i in range(0, len(doc), 2):
                yield (SourcePage(job.path, i),
                       SourcePage(job.path, i+1) if i+1 < len(doc) else None)


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
    if job.copies < 1:
        raise ValueError('Nakład musi być >= 1')
    refs = [SourcePage(job.path, i) for i in range(len(documents[job.path]))]
    refs += [None]*((-len(refs)) % 4)
    n = len(refs)
    required_w = 2*(s.trim_w+2*s.bleed) + s.gap_x
    required_h = s.trim_h+2*s.bleed
    if required_w > s.sheet_w - 2*s.margin_x or required_h > s.sheet_h - 2*s.margin_y:
        raise ValueError('Broszura 2-up nie mieści się: zmień arkusz albo format strony')
    left = (s.sheet_w - required_w)/2 + s.bleed
    top = (s.sheet_h - required_h)/2 + s.bleed
    slots = [Slot(left, top, s.trim_w, s.trim_h, 0, 0, 0),
             Slot(left+s.trim_w+2*s.bleed+s.gap_x, top,
                  s.trim_w, s.trim_h, 0, 1, 0)]
    for _ in range(job.copies):
        for i in range(n//4):
            # Outside of folded sheet: last/first, inside: second/penultimate.
            front = (refs[n-1-2*i], refs[2*i])
            back = (refs[2*i+1], refs[n-2-2*i])
            yield SheetSide(i+1, 0, tuple(Placement(p, slot, 0) for p, slot in zip(front, slots)))
            yield SheetSide(i+1, 1, tuple(Placement(p, slot, 1) for p, slot in zip(back, slots)))


def plan_sides(jobs: list[Job], documents: dict[str, fitz.Document], s: Settings) -> Iterator[SheetSide]:
    if not jobs:
        return
    if s.mode == 'Broszura':
        yield from _booklet_sides(jobs, documents, s)
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


def _draw_marks(page: fitz.Page, slot: Slot, s: Settings):
    """Create slim vector trim marks separated from bleed when space permits."""
    x, y, w, h = slot.x, slot.y, slot.w, slot.h
    # Do not print black into bleed. Each mark begins 0.8mm after bleed.
    offset = s.bleed + 0.8
    length = 3.0
    rect = ((0, 0, s.sheet_w, s.sheet_h))
    for cx in (x, x+w):
        direction = -1 if cx == x else 1
        a, b = cx+direction*offset, cx+direction*(offset+length)
        if min(a, b) >= 0 and max(a, b) <= s.sheet_w:
            for yy in (y, y+h):
                page.draw_line((pt(a), pt(yy)), (pt(b), pt(yy)), color=(0,0,0), width=0.25)
    for cy in (y, y+h):
        direction = -1 if cy == y else 1
        a, b = cy+direction*offset, cy+direction*(offset+length)
        if min(a, b) >= 0 and max(a, b) <= s.sheet_h:
            for xx in (x, x+w):
                page.draw_line((pt(xx), pt(a)), (pt(xx), pt(b)), color=(0,0,0), width=0.25)


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


def _place_pdf(target: fitz.Page, p: SourcePage, slot: Slot, s: Settings,
               sources: dict[str, fitz.Document]):
    original = sources[p.path][p.index]
    trim = fitz.Rect(original.trimbox)
    media = fitz.Rect(original.mediabox)
    original_angle = original.rotation
    apparent_w, apparent_h = ((mm(trim.height), mm(trim.width))
                              if original_angle in (90, 270)
                              else (mm(trim.width), mm(trim.height)))
    if abs(apparent_w-s.trim_w) > 0.5 or abs(apparent_h-s.trim_h) > 0.5:
        raise ValueError(
            f'{Path(p.path).name}, strona {p.index+1}: TrimBox {apparent_w:.2f} × '
            f'{apparent_h:.2f} mm nie odpowiada {s.trim_w:g} × {s.trim_h:g} mm. '
            'Popraw format lub przygotuj PDF w prawidłowym rozmiarze.')
    if trim.is_empty or any(abs(a-b) > .05 for a,b in zip(trim, trim & media)):
        raise ValueError(f'{Path(p.path).name}: TrimBox poza MediaBox')

    # Respect explicitly larger BleedBox while handling PDFs without one.
    bleedbox = fitz.Rect(original.bleedbox)
    limit = media
    if bleedbox.contains(trim) and bleedbox != trim and bleedbox != original.cropbox:
        limit = bleedbox & media
    desired = fitz.Rect(trim.x0-pt(s.bleed), trim.y0-pt(s.bleed),
                        trim.x1+pt(s.bleed), trim.y1+pt(s.bleed))
    visible = desired & limit
    if visible.is_empty or visible.width <= 0 or visible.height <= 0:
        raise ValueError(f'{Path(p.path).name}: nieprawidłowy obszar spadów')

    angle = (original_angle + slot.rotation) % 360
    # The target destination encloses exactly the surviving part of the bleed
    # rectangle. Transform all corners so asymmetric/missing bleed and rotation
    # are represented correctly; no stretching into the missing bleed area.
    corners = [(visible.x0, visible.y0), (visible.x1, visible.y0),
               (visible.x0, visible.y1), (visible.x1, visible.y1)]
    rotated = [_rotate_point(x-trim.x0, y-trim.y0, trim.width, trim.height, angle)
               for x,y in corners]
    final_width = trim.width if angle in (0, 180) else trim.height
    final_height = trim.height if angle in (0, 180) else trim.width
    sx, sy = pt(slot.w)/final_width, pt(slot.h)/final_height
    box = fitz.Rect(pt(slot.x) + min(x for x,_ in rotated)*sx,
                    pt(slot.y) + min(y for _,y in rotated)*sy,
                    pt(slot.x) + max(x for x,_ in rotated)*sx,
                    pt(slot.y) + max(y for _,y in rotated)*sy)
    # PyMuPDF's clip coordinates refer to the displayed CropBox. Temporarily
    # expose the full MediaBox, otherwise a valid bleed outside CropBox is lost.
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
                destination: fitz.Document | None = None) -> fitz.Document:
    out = destination if destination is not None else fitz.open()
    target = out.new_page(width=pt(s.sheet_w), height=pt(s.sheet_h))
    for item in side.placements:
        if item.source is not None:
            _place_pdf(target, item.source, item.slot, s, sources)
        if s.crop_marks:
            _draw_marks(target, item.slot, s)
        if s.show_page_labels:
            txt = f'{item.source.index+1}  ' if item.source else 'PUSTA  '
            target.insert_text((pt(item.slot.x+1), pt(item.slot.y+item.slot.h-1)),
                               txt, fontsize=6, color=(.3,.3,.3), overlay=True)
    return out


def open_sources(jobs: list[Job]) -> dict[str, fitz.Document]:
    sources = {}
    try:
        for job in jobs:
            if job.path not in sources:
                if not Path(job.path).is_file():
                    raise FileNotFoundError(f'Brak pliku: {job.path}')
                doc = fitz.open(job.path)
                if not doc.is_pdf or doc.needs_pass or len(doc) == 0:
                    doc.close()
                    raise ValueError(f'Nieobsługiwany lub zabezpieczony PDF: {job.path}')
                sources[job.path] = doc
        return sources
    except Exception:
        for doc in sources.values():
            doc.close()
        raise


def export_pdf(project: Project, output: str):
    validate(project.settings)
    if not project.jobs:
        raise ValueError('Dodaj co najmniej jeden plik PDF')
    sources = open_sources(project.jobs)
    out = fitz.open()
    try:
        count = 0
        for side in plan_sides(project.jobs, sources, project.settings):
            render_side(side, sources, project.settings, out)
            count += 1
        if count == 0:
            raise ValueError('Brak stron do montażu')
        out.set_metadata({'title':'Impozycjoner Studio - montaż PDF',
                          'creator':'Impozycjoner Studio 0.2.0'})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        out.save(output, garbage=3, deflate=True)
        return count
    finally:
        out.close()
        for doc in sources.values():
            doc.close()


def preview(project: Project, pixels: int = 1200, index: int = 0):
    """Returns (PIL.Image, number represented). Lazy: only the requested sheet."""
    from PIL import Image
    validate(project.settings)
    sources = open_sources(project.jobs)
    try:
        sides = plan_sides(project.jobs, sources, project.settings)
        selected = next(islice(sides, index, index+1), None)
        out = fitz.open()
        try:
            if selected is None:
                out.new_page(width=pt(project.settings.sheet_w), height=pt(project.settings.sheet_h))
            else:
                render_side(selected, sources, project.settings, out)
            page = out[0]
            zoom = min(pixels/page.rect.width, pixels/page.rect.height, 2)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom,zoom), alpha=False)
            return Image.frombytes('RGB', (pix.width,pix.height),pix.samples), selected
        finally:
            out.close()
    finally:
        for doc in sources.values():
            doc.close()


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
        jobs.append({'path':file_path,'copies':j.copies})
    payload = {'format':'psimp','version':1, 'settings':asdict(project.settings), 'jobs':jobs}
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
                else str(Path(j['path']).resolve()), copies=int(j['copies']))
            for j in data.get('jobs', [])]
    return Project(settings, jobs)


def source_summary(path: str) -> tuple[int, float, float]:
    with fitz.open(path) as doc:
        if not doc.is_pdf or doc.needs_pass or not len(doc):
            raise ValueError('Plik nie jest poprawnym niezabezpieczonym PDF')
        b = doc[0].trimbox
        return (len(doc), round(mm(b.height), 2), round(mm(b.width), 2)) if doc[0].rotation in (90,270) else (len(doc), round(mm(b.width),2), round(mm(b.height),2))
