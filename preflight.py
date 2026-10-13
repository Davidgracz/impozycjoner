"""Fast, conservative PDF production checks (no claim of full PDF/X conformance).

All measurements are in millimetres unless stated.  The preflight results are
advisory, while source-size verification in the imposition engine is mandatory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
import json

import pymupdf as fitz

from engine import Job, Project, Settings, mm, media_rect, open_sources, scaling_layout, validate, bleed_for, gross_dimensions, validate_job_roles, _duplex_pairs, project_sides, overlapping_uses, plan_sides, ROLE_AUTO, ROLE_SKIP


@dataclass(frozen=True)
class Finding:
    level: str  # BŁĄD / UWAGA / INFO
    path: str
    page: int
    code: str
    message: str


@dataclass(frozen=True)
class ImageIssue:
    """One physical image occurrence. Exposed in JSON even when UI is grouped."""
    path: str
    page: int
    dpi: float
    native_dpi: float
    image_width_px: int
    image_height_px: int
    bbox_pt: tuple[float, float, float, float]
    scale_percent: float


@dataclass(frozen=True)
class FormatRange:
    path: str
    first_page: int
    last_page: int
    width_mm: float
    height_mm: float
    format_name: str


@dataclass
class PreflightReport:
    checked_pages: int
    total_pages: int
    findings: list[Finding]
    image_issues: list[ImageIssue] = field(default_factory=list)
    format_ranges: list[FormatRange] = field(default_factory=list)
    min_dpi: int = 200

    @property
    def errors(self) -> int:
        return sum(item.level == 'BŁĄD' for item in self.findings)

    @property
    def warnings(self) -> int:
        return sum(item.level == 'UWAGA' for item in self.findings)

    def to_text(self) -> str:
        lines = [
            'IMPOZYCJONER STUDIO — RAPORT PREFLIGHT',
            f'Sprawdzono stron: {self.checked_pages}/{self.total_pages}',
            f'Błędy: {self.errors}, uwagi: {self.warnings}',
            f'Obrazy poniżej {self.min_dpi} DPI po skalowaniu: {len(self.image_issues)} '
            'Szczegóły poszczególnych obrazów są dostępne w raporcie JSON.',
            '',
        ]
        if not self.findings:
            lines.append('Nie wykryto problemów w zakresie wykonywanych kontroli.')
        for finding in self.findings:
            page = f', strona {finding.page}' if finding.page else ''
            lines.append(f'[{finding.level}] {Path(finding.path).name}{page} [{finding.code}]: {finding.message}')
        lines += ['', 'Zakres: geometria stron, spady, proporcje, podstawowe DPI obrazów i zasoby fontów.',
                  'To NIE jest pełna certyfikacja PDF/X ani kontrola separacji CMYK / kolorów spot.',
                  'Przed nakładem sprawdź wydruk próbny oraz duplex.']
        return '\n'.join(lines) + '\n'

    def to_json(self) -> str:
        return json.dumps({
            'format': 'impozycjoner-preflight', 'version': 1,
            'checked_pages': self.checked_pages, 'total_pages': self.total_pages,
            'errors': self.errors, 'warnings': self.warnings,
            'findings': [asdict(f) for f in self.findings],
            'min_dpi': self.min_dpi,
            'image_issues': [asdict(x) for x in self.image_issues],
            'format_ranges': [asdict(x) for x in self.format_ranges],
        }, ensure_ascii=False, indent=2)


def _distance_box(outer: fitz.Rect, inner: fitz.Rect) -> tuple[float, float, float, float]:
    return tuple(mm(v) for v in (
        inner.x0 - outer.x0, inner.y0 - outer.y0,
        outer.x1 - inner.x1, outer.y1 - inner.y1))


def _size(page: fitz.Page) -> tuple[float, float]:
    box = page.trimbox
    return (mm(box.height), mm(box.width)) if page.rotation in (90, 270) else (mm(box.width), mm(box.height))


def _format_name(w: float, h: float) -> str:
    """Human label only; do not change precise dimensions used for imposition."""
    standards = (("A4", 210, 297), ("A5", 148, 210), ("A6", 105, 148))
    for name, sw, sh in standards:
        if abs(w-sw) <= .8 and abs(h-sh) <= .8:
            return f'{name} pion'
        if abs(w-sh) <= .8 and abs(h-sw) <= .8:
            return f'{name} poziom'
    return f'{w:.1f} × {h:.1f} mm'


def _range_text(item: FormatRange) -> str:
    pages = str(item.first_page) if item.first_page == item.last_page else f'{item.first_page}–{item.last_page}'
    return f'str. {pages}: {item.format_name} ({item.width_mm:.2f} × {item.height_mm:.2f} mm)'


def inspect_project(project: Project, *, min_dpi: int = 200,
                    max_pages: int = 1000) -> PreflightReport:
    """Inspect each unique PDF page once, regardless of requested copy count.

    Returns a partial-results note when max_pages is reached. It does not
    attempt expensive interpretation of all PDF colors or embedded ICC profiles.
    """
    validate(project.settings)
    if not project.jobs:
        raise ValueError('Dodaj plik PDF przed kontrolą preflight')
    docs = open_sources(project.jobs)
    s = project.settings
    findings: list[Finding] = []
    image_issues: list[ImageIssue] = []
    format_ranges: list[FormatRange] = []
    checked = 0
    total = sum(len(doc) for doc in docs.values())
    try:
        # In duplex, an invalid front/back mapping must block export even when
        # all source PDFs themselves pass geometry/prepress checks.
        try:
            validate_job_roles(project.jobs, docs)
            if s.mode == 'Dwustronnie':
                sum(1 for _ in _duplex_pairs(project.jobs, docs))
            elif s.mode != 'Dwustronnie' and any(
                j.role not in (ROLE_AUTO, ROLE_SKIP) or any(
                    role not in (ROLE_AUTO, ROLE_SKIP) for role in j.page_roles.values()
                ) for j in project.jobs
            ):
                findings.append(Finding('BŁĄD', project.jobs[0].path, 0, 'ROLE',
                    'Przypisano role przód/tył, ale tryb nie jest ustawiony na Dwustronnie. '
                    'Zmień tryb montażu na Dwustronnie, żeby uniknąć pomyłki przy druku.'))
        except ValueError as exc:
            findings.append(Finding('BŁĄD', project.jobs[0].path, 0, 'ROLE', str(exc)))
        for path, doc in docs.items():
            runs: list[FormatRange] = []
            for page_no in range(len(doc)):
                if checked >= max_pages:
                    findings.append(Finding('UWAGA', path, 0, 'LIMIT',
                        f'Limit {max_pages} stron: pozostałe strony nie zostały sprawdzone.'))
                    return PreflightReport(checked, total, findings, image_issues, format_ranges + runs, min_dpi)
                page = doc[page_no]
                checked += 1
                pnum = page_no + 1
                label = lambda severity, code, message: findings.append(
                    Finding(severity, path, pnum, code, message))
                trim = page.trimbox
                media = media_rect(page)
                bleed = page.bleedbox
                if trim.is_empty or any(abs(a-b) > .05 for a,b in zip(trim, trim & media)):
                    label('BŁĄD', 'TRIMBOX', 'TrimBox jest poza MediaBox albo jest pusty.')
                    continue
                width, height = _size(page)
                if runs and abs(runs[-1].width_mm - width) <= .5 and abs(runs[-1].height_mm - height) <= .5:
                    runs[-1] = replace(runs[-1], last_page=pnum)
                else:
                    runs.append(FormatRange(path, pnum, pnum, round(width, 2), round(height, 2),
                                            _format_name(width, height)))
                if s.scale_mode == 'Bez skalowania' and (abs(width-s.trim_w) > .5 or abs(height-s.trim_h) > .5):
                    label('BŁĄD', 'FORMAT',
                          f'TrimBox: {width:.2f} × {height:.2f} mm; docelowo: {s.trim_w:g} × {s.trim_h:g} mm. '
                          'Wybierz tryb skalowania lub dopasuj rozmiar.')
                if s.scale_mode == 'Kadruj 1:1' and s.source_w > 0 and (
                    abs(width-s.source_w) > .5 or abs(height-s.source_h) > .5
                ):
                    label('BŁĄD', 'ORYGINAL',
                          f'Oryginał PDF ma {width:.2f} × {height:.2f} mm, a ustawiono '
                          f'{s.source_w:g} × {s.source_h:g} mm. Kadrowanie 1:1 wymaga zgodności.')
                if s.scale_mode == 'Kadruj 1:1' and s.gross_w > 0:
                    gw, gh = gross_dimensions(s)
                    if width + .02 < gw or height + .02 < gh:
                        label('BŁĄD', 'BRUTTO',
                              f'Oryginał {width:.2f} × {height:.2f} mm jest za mały '
                              f'na użytek ze spadami {gw:g} × {gh:g} mm.')
                if s.scale_mode == 'Kadruj 1:1':
                    if width + .02 < s.trim_w or height + .02 < s.trim_h:
                        label('BŁĄD', 'KADROWANIE',
                              f'Oryginał {width:.2f} × {height:.2f} mm jest za mały '
                              f'na format netto {s.trim_w:g} × {s.trim_h:g} mm w skali 1:1.')
                    else:
                        label('INFO', 'KADROWANIE',
                              f'Centralne kadrowanie 1:1: z oryginału {width:.2f} × {height:.2f} mm '
                              f'pozostanie użytek {gross_dimensions(s)[0]:g} × {gross_dimensions(s)[1]:g} mm, netto {s.trim_w:g} × {s.trim_h:g} mm, '
                              f'z dodatkowym spadem {bleed_for(s):g} mm na stronę.')
                    factor, dx, dy = 1.0, (s.trim_w-width)/2, (s.trim_h-height)/2
                else:
                    factor, dx, dy = scaling_layout(width, height, s.trim_w, s.trim_h,
                                                    s.scale_mode)
                if s.scale_mode not in ('Bez skalowania', 'Kadruj 1:1'):
                    # Positive offsets = white border; negative = trimmed content.
                    extra = (f'białe marginesy do {max(dx,dy):.2f} mm' if dx > .2 or dy > .2
                             else f'przycięcie do {-min(dx,dy):.2f} mm' if dx < -.2 or dy < -.2
                             else 'brak istotnego przycięcia')
                    label('UWAGA' if min(dx,dy) < -.2 else 'INFO', 'SKALA',
                          f'{width:.2f} × {height:.2f} mm → {s.trim_w:g} × {s.trim_h:g} mm; '
                          f'{factor*100:.2f}%, {s.scale_mode.lower()}; {extra}.')
                # BleedBox may legitimately equal TrimBox: check actual media
                # envelope as well, but never assert that ink really fills it.
                avail = media
                if bleed.contains(trim) and bleed != trim and bleed != page.cropbox:
                    avail = bleed & media
                distances = _distance_box(avail, trim)
                if s.scale_mode == 'Kadruj 1:1':
                    distances = ((width-s.trim_w)/2, (height-s.trim_h)/2,
                                 (width-s.trim_w)/2, (height-s.trim_h)/2)
                if bleed_for(s) > 0 and min(distances)*factor < bleed_for(s) - .15:
                    label('UWAGA', 'SPAD',
                          'Dostępny obszar poza TrimBox (lewo/góra/prawo/dół): '
                          + '/'.join(f'{max(0,v*factor):.2f}' for v in distances) +
                          f' mm po skalowaniu; wymagany spad: {bleed_for(s):g} mm. Brakujący obszar pozostanie biały.')
                if page.rotation:
                    label('INFO', 'ROTACJA', f'Źródłowe /Rotate = {page.rotation}°.')
                try:
                    low_dpi_on_page: list[float] = []
                    for image in page.get_image_info(hashes=False, xrefs=False):
                        box = fitz.Rect(image['bbox'])
                        if box.width <= .5 or box.height <= .5:
                            continue
                        native_dpi = min(image['width'] * 72 / box.width,
                                         image['height'] * 72 / box.height)
                        dpi = native_dpi / factor
                        if dpi < min_dpi:
                            low_dpi_on_page.append(dpi)
                            image_issues.append(ImageIssue(
                                path, pnum, round(dpi, 1), round(native_dpi, 1),
                                int(image['width']), int(image['height']),
                                tuple(round(float(v), 2) for v in box), round(factor * 100, 2)))
                    if low_dpi_on_page:
                        count = len(low_dpi_on_page)
                        noun = 'obraz' if count == 1 else 'obrazy' if 2 <= count <= 4 else 'obrazów'
                        label('UWAGA', 'DPI',
                              f'{count} {noun} poniżej {min_dpi} DPI po skalowaniu; '
                              f'najniższe ~{min(low_dpi_on_page):.0f} DPI. '
                              'Szczegóły poszczególnych obrazów: eksport raportu JSON.')
                except (ValueError, RuntimeError, KeyError) as exc:
                    label('UWAGA', 'OBRAZY', f'Nie udało się sprawdzić wszystkich obrazów: {exc}')
                try:
                    base14 = {'courier','courier-bold','courier-oblique','courier-boldoblique',
                              'helvetica','helvetica-bold','helvetica-oblique','helvetica-boldoblique',
                              'times-roman','times-bold','times-italic','times-bolditalic',
                              'symbol','zapfdingbats'}
                    seen = set()
                    for font in doc.get_page_fonts(page_no):
                        xref, _, _, name = font[:4]
                        if xref in seen or name.lower() in base14:
                            continue
                        seen.add(xref)
                        if xref > 0 and not doc.extract_font(xref)[-1]:
                            label('UWAGA', 'FONT', f'Font {name} może nie być osadzony.')
                except (ValueError, RuntimeError) as exc:
                    label('UWAGA', 'FONT', f'Nie udało się zweryfikować fontów: {exc}')
            format_ranges.extend(runs)
            distinct_sizes: list[FormatRange] = []
            for run in runs:
                if not any(abs(run.width_mm - item.width_mm) <= .5 and
                           abs(run.height_mm - item.height_mm) <= .5 for item in distinct_sizes):
                    distinct_sizes.append(run)
            if len(distinct_sizes) > 1:
                sample = '; '.join(_range_text(run) for run in runs[:8])
                if len(runs) > 8:
                    sample += f'; … ({len(runs)} przedziałów)'
                findings.insert(0, Finding('UWAGA', path, 0, 'MIESZANE_FORMATY',
                    f'PDF zawiera różne formaty: {sample}. '
                    f'Docelowy format: {s.trim_w:g} × {s.trim_h:g} mm. '
                    'Sprawdź, czy zamierzone jest pomniejszanie/powiększanie stron.'))
        # Also validate all effective verso positions after global duplex
        # calibration: a translated back use must not be clipped off-sheet.
        if s.mode == 'Dwustronnie' and (s.verso_shift_x or s.verso_shift_y):
            findings.append(Finding('INFO', '', 0, 'KALIBRACJA_VERSO',
                f'Kalibracja rewersu: X={s.verso_shift_x:+.1f} mm, '
                f'Y={s.verso_shift_y:+.1f} mm; kierunek: {s.flip}. '
                'Przesunięcie dotyczy tylko wydrukowanego tyłu.'))
        # Check manually edited and globally calibrated sheet geometry.
        # Overlaps remain warnings; leaving the sheet is a fatal error.
        if project.overrides or (s.mode == 'Dwustronnie' and (s.verso_shift_x or s.verso_shift_y)):
            affected = set()
            for key in project.overrides:
                try:
                    number, side, index = map(int, key.split(':'))
                    affected.add((number, side))
                except (ValueError, TypeError):
                    findings.append(Finding('BŁĄD', '', 0, 'RECZNY_KLUCZ',
                                            f'Nieprawidłowy ręczny użytek: {key!r}'))
            if s.mode == 'Dwustronnie' and (s.verso_shift_x or s.verso_shift_y):
                # All verso sheets, not just those with manual assignments.
                affected.update((sheet.sheet_number, sheet.side)
                                for sheet in plan_sides(project.jobs, docs, s) if sheet.side == 1)
            if affected:
                pending = set(affected)
                try:
                    for side in project_sides(project, docs):
                        ident = (side.sheet_number, side.side)
                        if ident in pending:
                            pending.remove(ident)
                            for a, b in overlapping_uses(side, s):
                                findings.append(Finding('UWAGA', '', 0, 'NAKLADANIE_UZYTKOW',
                                    f'Arkusz {side.sheet_number}, {"recto" if side.side == 0 else "verso"}: '
                                    f'użytki {a+1} i {b+1} nachodzą na siebie wraz ze spadami.'))
                        if not pending:
                            break
                except ValueError as exc:
                    findings.append(Finding('BŁĄD', '', 0, 'RECZNY_MONTAZ', str(exc)))
        return PreflightReport(checked, total, findings, image_issues, format_ranges, min_dpi)
    finally:
        for doc in docs.values():
            doc.close()
