"""Fast, conservative PDF production checks (no claim of full PDF/X conformance).

All measurements are in millimetres unless stated.  The preflight results are
advisory, while source-size verification in the imposition engine is mandatory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import pymupdf as fitz

from engine import Job, Project, Settings, mm, media_rect, open_sources, validate


@dataclass(frozen=True)
class Finding:
    level: str  # BŁĄD / UWAGA / INFO
    path: str
    page: int
    code: str
    message: str


@dataclass
class PreflightReport:
    checked_pages: int
    total_pages: int
    findings: list[Finding]

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
        }, ensure_ascii=False, indent=2)


def _distance_box(outer: fitz.Rect, inner: fitz.Rect) -> tuple[float, float, float, float]:
    return tuple(mm(v) for v in (
        inner.x0 - outer.x0, inner.y0 - outer.y0,
        outer.x1 - inner.x1, outer.y1 - inner.y1))


def _size(page: fitz.Page) -> tuple[float, float]:
    box = page.trimbox
    return (mm(box.height), mm(box.width)) if page.rotation in (90, 270) else (mm(box.width), mm(box.height))


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
    checked = 0
    total = sum(len(doc) for doc in docs.values())
    try:
        for path, doc in docs.items():
            for page_no in range(len(doc)):
                if checked >= max_pages:
                    findings.append(Finding('UWAGA', path, 0, 'LIMIT',
                        f'Limit {max_pages} stron: pozostałe strony nie zostały sprawdzone.'))
                    return PreflightReport(checked, total, findings)
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
                if abs(width - s.trim_w) > .5 or abs(height - s.trim_h) > .5:
                    label('BŁĄD', 'FORMAT',
                          f'TrimBox: {width:.2f} × {height:.2f} mm; montaż: {s.trim_w:g} × {s.trim_h:g} mm. '
                          'Nie skalujemy strony niejawnie.')
                # BleedBox may legitimately equal TrimBox: check actual media
                # envelope as well, but never assert that ink really fills it.
                avail = media
                if bleed.contains(trim) and bleed != trim and bleed != page.cropbox:
                    avail = bleed & media
                distances = _distance_box(avail, trim)
                if s.bleed > 0 and min(distances) < s.bleed - .15:
                    label('UWAGA', 'SPAD',
                          'Dostępny obszar poza TrimBox (lewo/góra/prawo/dół): '
                          + '/'.join(f'{max(0,v):.2f}' for v in distances) +
                          f' mm; wymagany spad: {s.bleed:g} mm. Brakujący obszar pozostanie biały.')
                if page.rotation:
                    label('INFO', 'ROTACJA', f'Źródłowe /Rotate = {page.rotation}°.')
                try:
                    for image in page.get_image_info(hashes=False, xrefs=False):
                        box = fitz.Rect(image['bbox'])
                        if box.width <= .5 or box.height <= .5:
                            continue
                        dpi_x = image['width'] * 72 / box.width
                        dpi_y = image['height'] * 72 / box.height
                        dpi = min(dpi_x, dpi_y)
                        if dpi < min_dpi:
                            label('UWAGA', 'DPI', f'Obraz ~{dpi:.0f} DPI (minimalnie {min_dpi} DPI).')
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
        return PreflightReport(checked, total, findings)
    finally:
        for doc in docs.values():
            doc.close()
