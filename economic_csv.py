"""Simple auditable production report for single-sided economic gang-run."""
from __future__ import annotations

import csv
from pathlib import Path
from engine import EconomicReport


def write_economic_csv(report: EconomicReport, output: str | Path) -> None:
    """Export quantities and aggregated sheet patterns with Excel-friendly UTF-8 BOM."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['IMPOZYCJONER STUDIO 0.4.0 — MONTAŻ EKONOMICZNY'])
        writer.writerow(['Arkusze fizyczne', report.physical_sheets])
        writer.writerow(['Użytki na arkusz', report.capacity])
        writer.writerow(['Zajęte użytki', report.filled_slots])
        writer.writerow(['Puste użytki', report.empty_slots])
        writer.writerow(['Nadprodukcja', report.overproduction])
        writer.writerow(['Brakuje sztuk', report.shortage])
        writer.writerow([])
        writer.writerow(['Plik', 'Strona PDF', 'Zamówiono szt.', 'Na arkuszach szt.', 'Nadprodukcja', 'Brakuje'])
        for line in report.lines:
            writer.writerow([Path(line.source.path).name, line.source.index+1, line.requested,
                             line.planned, line.surplus, line.shortage])
        writer.writerow([])
        writer.writerow(['Typ arkusza', 'Ile arkuszy', 'Pierwszy arkusz PDF', 'Zawartość użytków (kolejność pól)'])
        for i, pattern in enumerate(report.patterns, 1):
            slots = ', '.join(f'{Path(ref.path).name} str.{ref.index+1}' if ref else 'PUSTE'
                              for ref in pattern.signature)
            writer.writerow([i, pattern.sheet_count, pattern.first_sheet, slots])
        writer.writerow([])
        writer.writerow(['UWAGA', 'W PDF jest każdy fizyczny arkusz dokładnie raz. Nie powielaj ich dodatkowo w sterowniku druku.'])
        writer.writerow(['UWAGA', 'Wersja 0.4.0 łączy projekty o jednym wspólnym formacie użytku, jednostronnie.'])
