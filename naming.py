"""Reguły nazewnictwa plików wejściowych (czysty Python, bez PyMuPDF i Tk).

Pierwsza funkcja zgodności z Impozycjonerem 4: „liczba powtórzeń każdej strony
odczytywana z nazwy pliku” (F-AKC-REP w docs/feature-parity.md).

Źródło reguły (E1, własny opis tekstu pomocy oryginału, nie jego kodu):
  * bierze się część nazwy po OSTATNIM znaku „_”; gdy go nie ma — całą nazwę;
  * z tej części usuwa się wszystkie znaki inne niż cyfry;
  * brak cyfr oznacza 1.
Przykłady podane w pomocy oryginału (używane jako testy akceptacyjne):
  Arkusz_300s.pdf -> 300, Ulotka_dla_sklepu_500stron.pdf -> 500,
  Dyplom200.pdf -> 200, Instrukcja.pdf -> 1.

Brzmienie reguły jest dosłowne (E1): „usunięcie znaków innych niż cyfry” z wybranej
części nazwy, więc kilka grup cyfr łączy się w jedną liczbę (plik_5x10 → 510). Zachowanie
nie było obserwowane w działającym oryginale (brak E3).

Decyzje własne, NIE potwierdzone obserwacją oryginału (docs/behavior-spec.md):
  H-01 rozszerzenie „.pdf” nie jest częścią nazwy,
  H-02 cyfry to wyłącznie ASCII 0–9,
  H-03 pusta część po ostatnim „_” daje 1,
  H-04 katalogi w ścieżce są ignorowane (oba separatory: „/” i „\\”).
"""
from __future__ import annotations

from dataclasses import dataclass
import re

#: Górna granica akceptowana przez warstwę komend (jak przy polu „Nakład pliku”).
MAX_REPEATS = 1_000_000

_SEPARATORS = re.compile(r'[\\/]')
_PDF_EXTENSION = re.compile(r'\.pdf$', re.IGNORECASE)


@dataclass(frozen=True)
class RepeatParse:
    """Wynik odczytu liczby powtórzeń wraz z uzasadnieniem (do komunikatów w UI)."""

    count: int          # odczytana liczba; 1 gdy w nazwie nie ma cyfr
    stem: str           # nazwa bez katalogu i bez rozszerzenia .pdf
    fragment: str       # część nazwy, z której czytano cyfry
    digits: str         # cyfry wyłuskane z fragmentu ('' gdy brak)
    used_separator: bool  # czy wystąpił znak „_” (inaczej: cała nazwa)

    @property
    def found_digits(self) -> bool:
        return bool(self.digits)


def parse_repeats(filename: str) -> RepeatParse:
    """Odczytaj liczbę powtórzeń z nazwy (lub ścieżki) pliku. Nie waliduje zakresu."""
    if not isinstance(filename, str):
        raise TypeError('Nazwa pliku musi być tekstem')
    base = _SEPARATORS.split(filename)[-1]
    stem = _PDF_EXTENSION.sub('', base)
    used_separator = '_' in stem
    fragment = stem.rsplit('_', 1)[1] if used_separator else stem
    digits = ''.join(ch for ch in fragment if '0' <= ch <= '9')
    return RepeatParse(int(digits) if digits else 1, stem, fragment, digits, used_separator)


def repeats_from_filename(filename: str) -> int:
    """Skrót: sama liczba powtórzeń (1, gdy nazwa nie zawiera cyfr)."""
    return parse_repeats(filename).count
