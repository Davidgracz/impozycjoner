"""Reguły znaczników wzorowane na Impozycjonerze 4 — czysta logika (bez PyMuPDF i Tk).

Z tekstów okien oryginału (własne streszczenie, zob. docs/imp4-wersja-finalna.md):
  * Wycinka środkowa: szerokość pionowa i pozioma [mm], grubość znacznika [pt], znacznik o zadanej długości
    albo przez całe pole zadruku. Wycinka jest uwzględniana tylko, gdy to technicznie możliwe — pionowa wymaga
    parzystej liczby kolumn (pozioma, analogicznie, parzystej liczby wierszy).
  * Dodatkowe docięcie TrimBox („crop”): „włosowe” przycięcie o zadaną liczbę punktów — z lewej strony na stronach
    parzystych, z prawej na nieparzystych — aby ukryć skrawek sąsiedniej strony.
  * Dodatkowy odstęp znaczników od użytków [mm].

Decyzje własne (hipotezy, do sprawdzenia na działającym oryginale):
  H-22 wycinka zastępuje odstęp między środkowymi kolumnami (wierszami); przy automatycznej siatce wybieramy
       największą liczbę kolumn, która mieści się razem z wycinką — może to być liczba nieparzysta (bez wycinki);
  H-23 znacznik wycinki to linia w osi wycinki: dwa odcinki o zadanej długości od górnej i dolnej (lewej i prawej)
       krawędzi pola zadruku albo, przy długości 0, jedna linia przez całe pole zadruku;
  H-24 docięcie TrimBox usuwa z danej krawędzi strony także spad (strona jest przycięta tuż za linią cięcia);
  H-25 odstęp znaczników cięcia liczony od krawędzi spadu (brutto); domyślnie 0,8 mm jak dotąd.
"""
from __future__ import annotations

from math import floor


def gutter_applies(count: int, width: float, enabled: bool = True) -> bool:
    """Czy wycinka w danej osi jest możliwa: włączona, szerokość > 0 i parzysta liczba (≥ 2) kolumn/wierszy."""
    return bool(enabled) and width > 0 and count >= 2 and count % 2 == 0


def axis_length(count: int, cell: float, gap: float, gutter: float = 0.0, enabled: bool = False) -> float:
    """Długość zajęta przez `count` użytków w jednej osi (z odstępami i ewentualną wycinką)."""
    if count < 1:
        return 0.0
    used = count * cell + (count - 1) * gap
    if gutter_applies(count, gutter, enabled):
        used += gutter - gap
    return used


def axis_offsets(count: int, cell: float, gap: float, gutter: float = 0.0, enabled: bool = False) -> list[float]:
    """Położenie początku każdego użytku względem początku siatki."""
    extra = gutter - gap if gutter_applies(count, gutter, enabled) else 0.0
    return [i * (cell + gap) + (extra if i >= count // 2 and extra else 0.0) for i in range(count)]


def auto_count(available: float, cell: float, gap: float, gutter: float = 0.0, enabled: bool = False) -> int:
    """Największa liczba użytków mieszcząca się w osi razem z wycinką (H-22)."""
    if cell <= 0:
        return 0
    upper = max(0, floor((available + gap + 1e-8) / (cell + gap))) + 1
    for count in range(upper, 0, -1):
        if axis_length(count, cell, gap, gutter, enabled) <= available + 1e-7:
            return count
    return 0


def gutter_center(start: float, count: int, cell: float, gap: float, gutter: float) -> float:
    """Oś wycinki (środek odstępu między środkowymi użytkami); `start` = początek siatki."""
    half = count // 2
    return start + half * cell + (half - 1) * gap + gutter / 2


def gutter_mark_segments(center: float, area_start: float, area_end: float,
                         length: float) -> list[tuple[float, float]]:
    """Odcinki znacznika wycinki wzdłuż osi (H-23): przy długości 0 — przez całe pole zadruku."""
    if area_end <= area_start:
        return []
    if length <= 0 or 2 * length >= area_end - area_start:
        return [(area_start, area_end)]
    return [(area_start, area_start + length), (area_end - length, area_end)]


def trim_crop_side(page_number: int) -> str:
    """Strona, z której przycina się TrimBox: parzyste — z lewej, nieparzyste — z prawej."""
    if page_number < 1:
        raise ValueError('Numer strony liczy się od 1')
    return 'left' if page_number % 2 == 0 else 'right'
