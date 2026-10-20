"""Reguły nazwy pliku wynikowego (czysty Python, bez PyMuPDF i Tk).

Z tekstów okien Impozycjonera 4 (własne streszczenie, nie kopia): nazwa pliku wynikowego nie może
zawierać znaków # % & * : < > ? / \\ { } ani pionowej kreski i nie może być nazwą pliku
przetwarzanego; opcjonalnie dopisuje się stałą frazę „--IMPOZYCJONER”.
Decyzja własna: porównanie z plikami wejściowymi bez katalogu i bez rozróżniania wielkości liter.
"""
from __future__ import annotations

import re

FORBIDDEN_OUTPUT_CHARS = '#%&*:<>?/\\{}|'
IMPOSITION_PHRASE = '--IMPOZYCJONER'

_SEPARATORS = re.compile(r'[\\/]')
_PDF_EXTENSION = re.compile(r'\.pdf$', re.IGNORECASE)


def output_name_problem(name: str, inputs: list[str] = ()) -> str | None:
    """Komunikat błędu dla nazwy pliku wynikowego (bez katalogu) albo None, gdy nazwa jest poprawna."""
    if not isinstance(name, str) or not name.strip() or not _PDF_EXTENSION.sub('', name).strip():
        return 'Podaj nazwę pliku wynikowego.'
    bad = sorted({ch for ch in name if ch in FORBIDDEN_OUTPUT_CHARS})
    if bad:
        return ('Nazwa pliku wynikowego zawiera niedozwolone znaki: ' + ' '.join(bad)
                + '. Niedozwolone są: ' + ' '.join(FORBIDDEN_OUTPUT_CHARS) + '.')
    lowered = name.casefold()
    for source in inputs:
        if _SEPARATORS.split(source)[-1].casefold() == lowered:
            return 'Nazwa pliku wynikowego nie może być taka sama jak nazwa pliku przetwarzanego.'
    return None


def add_imposition_phrase(name: str) -> str:
    """Dopisz „--IMPOZYCJONER” przed rozszerzeniem .pdf (raz; ponowne wywołanie nic nie zmienia)."""
    stem = _PDF_EXTENSION.sub('', name)
    extension = name[len(stem):] or '.pdf'
    if stem.endswith(IMPOSITION_PHRASE):
        return stem + extension
    return stem + IMPOSITION_PHRASE + extension
