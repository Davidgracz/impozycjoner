"""Czysta logika narzędzi stron PDF (bez PyMuPDF i Tk): zakresy, kolejności, nazwy.

Narzędzia dodatkowe Impozycjonera 4 (F-NAR-* ). Źródło reguł (E1, własne
streszczenie tekstów okien oryginału, nie jego kodu):
  * zakres stron zapisuje się jak „-3, 6, 9-11, 15-”; dozwolone są tylko cyfry, przecinek i minus
    (P-40); „-3” to strony od pierwszej do 3, „15-” to od 15 do ostatniej;
  * tasowanie stron odwraca kolejność (1,2,3,4 → 4,3,2,1), tasowanie kartek odwraca kolejność kartek,
    zachowując przód i tył każdej kartki (1,2,3,4 → 3,4,1,2); kartki wymagają parzystej liczby stron,
    a dokumentu jednostronicowego nie da się przetasować (P-41);
  * podział zapisuje każdą stronę w osobnym pliku z dopiskiem „--XX” (P-06);
  * łączenie wymaga co najmniej dwóch plików (P-42);
  * wydzielenie okładki wymaga co najmniej 5 stron (P-43).
Decyzje własne (H-13…H-17 w docs/imp4-wersja-finalna.md) są oznaczone w docstringach.

Wszystkie numery stron w API są liczone od 1, jak w interfejsie.
"""
from __future__ import annotations

import re

_ALLOWED = re.compile(r'^[0-9,\-\s]*$')
_TOKEN = re.compile(r'^(\d*)\s*(-?)\s*(\d*)$')


def parse_page_ranges(text: str, count: int) -> list[int]:
    """Zakres stron w składni oryginału → posortowana lista numerów (H-13: bez powtórzeń, rosnąco).

    Spacje są tolerowane (H-13). Błędne wpisy dają ValueError z komunikatem po polsku.
    """
    if count < 1:
        raise ValueError('Dokument nie ma stron')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Podaj numery stron, np. -3, 6, 9-11, 15-')
    if not _ALLOWED.match(text):
        raise ValueError('W zakresie stron wolno używać tylko cyfr, przecinka i minusa')
    pages: set[int] = set()
    for raw in text.split(','):
        token = raw.strip()
        if not token:
            raise ValueError('Pusty element zakresu (dwa przecinki obok siebie albo przecinek na końcu)')
        match = _TOKEN.match(token)
        if not match or token == '-':
            raise ValueError(f'Nieprawidłowy element zakresu: „{token}”')
        first, dash, last = match.groups()
        if not dash and last:  # „1 2” — dwie liczby bez przecinka ani minusa
            raise ValueError(f'Brak przecinka albo minusa między liczbami: „{token}”')
        if not dash:
            lo = hi = int(first)
        else:
            lo = int(first) if first else 1
            hi = int(last) if last else count
        if lo < 1 or hi < 1:
            raise ValueError(f'Numer strony musi być większy od zera: „{token}”')
        if lo > hi:
            raise ValueError(f'Zakres musi rosnąć: „{token}”')
        if hi > count:
            raise ValueError(f'Strona {hi} nie istnieje — dokument ma {count} str.')
        pages.update(range(lo, hi + 1))
    return sorted(pages)


def shuffle_order(count: int, leaves: bool = False) -> list[int]:
    """Kolejność stron po tasowaniu (P-41). `leaves=True` tasuje kartki (pary stron)."""
    if count < 2:
        raise ValueError('Dokumentu z jedną stroną nie da się przetasować — wynik byłby taki sam')
    if not leaves:
        return list(range(count, 0, -1))
    if count % 2:
        raise ValueError('Tasowanie kartek wymaga parzystej liczby stron')
    order: list[int] = []
    for leaf in range(count // 2 - 1, -1, -1):
        order += [2 * leaf + 1, 2 * leaf + 2]
    return order


def duplicate_order(count: int, pages: list[int], times: int) -> list[int]:
    """Kolejność po powieleniu wskazanych stron `times` razy (H-14).

    H-14: każda wskazana strona występuje `times` razy pod rząd, w miejscu oryginału;
    pozostałe strony zostają pojedynczo.
    """
    if times < 2:
        raise ValueError('Liczba powieleń musi wynosić co najmniej 2')
    if times > 1000:
        raise ValueError('Liczba powieleń nie może przekraczać 1000')
    chosen = set(pages)
    if not chosen or min(chosen) < 1 or max(chosen) > count:
        raise ValueError('Wskaż strony istniejące w dokumencie')
    order: list[int] = []
    for page in range(1, count + 1):
        order += [page] * (times if page in chosen else 1)
    return order


def page_suffix(number: int, count: int) -> str:
    """Dopisek „--XX” (P-06). H-15: numer z zerami wiodącymi do co najmniej 2 cyfr
    (więcej, gdy dokument ma ≥ 100 stron), żeby pliki sortowały się w kolejności stron."""
    if not 1 <= number <= count:
        raise ValueError('Numer strony poza dokumentem')
    width = max(2, len(str(count)))
    return f'--{number:0{width}d}'


def chunks(count: int, per_file: int) -> list[list[int]]:
    """Podział na pliki po `per_file` stron; ostatni może być krótszy (H-16)."""
    if per_file < 1:
        raise ValueError('Liczba stron w pliku musi być większa od zera')
    if per_file >= count:
        raise ValueError('Liczba stron w pliku musi być mniejsza od liczby stron dokumentu')
    return [list(range(start, min(start + per_file, count + 1)))
            for start in range(1, count + 1, per_file)]


def cover_and_body(count: int) -> tuple[list[int], list[int]]:
    """Okładka i wkład (P-43, H-17): okładka = strony 1, 2, przedostatnia i ostatnia."""
    if count < 5:
        raise ValueError('Do wydzielenia okładki plik musi mieć co najmniej 5 stron')
    cover = [1, 2, count - 1, count]
    return cover, [p for p in range(1, count + 1) if p not in cover]


def even_odd(count: int) -> tuple[list[int], list[int]]:
    """Strony nieparzyste i parzyste osobno."""
    if count < 2:
        raise ValueError('Plik ma jedną stronę — wynik nie różniłby się od pliku wejściowego')
    return list(range(1, count + 1, 2)), list(range(2, count + 1, 2))


def rotation_for(page: int, current: int, angle: int, even_extra_180: bool = False) -> int:
    """Obrót strony po narzędziu „Obróć strony” (H-18: kąt dodaje się do bieżącego /Rotate)."""
    if angle not in (0, 90, 180, 270) or current % 90:
        raise ValueError('Obrót musi wynosić 0°, 90°, 180° albo 270°')
    extra = 180 if even_extra_180 and page % 2 == 0 else 0
    return (current + angle + extra) % 360
