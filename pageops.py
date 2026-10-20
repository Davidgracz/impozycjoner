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


def bleed_pieces(width: float, height: float, bleed: tuple[float, float, float, float],
                 strip: tuple[float, float, float, float],
                 offset: tuple[float, float, float, float]):
    """Kawałki spadu z narzędzia „Dodaj spady” (wartości L, P, G, D; jednostka dowolna, wspólna).

    E1: dla każdej krawędzi podaje się dodawany spad, szerokość wycinka i odległość wycinka od krawędzi
    PDF (MediaBox). REA (metadane wywołań): fragmenty tej samej strony są przycinane i rozciągane do
    zadanych wymiarów. H-27: wycinek [odległość, odległość + szerokość] jest rozciągany na pas od nowej
    krawędzi (z dodanym spadem) do początku wycinka — pas zakrywa też biały margines strony; narożniki
    powstają z narożnego kwadratu wycinków. Zwraca listę (cel, źródło) prostokątów (x0, y0, x1, y1);
    cel we współrzędnych nowej strony (lewy górny róg = 0), źródło we współrzędnych strony wejściowej.
    """
    names = ('lewy', 'prawy', 'górny', 'dolny')
    for values, what in ((bleed, 'Spad'), (strip, 'Szerokość wycinka'), (offset, 'Odległość wycinka')):
        if len(values) != 4 or any(v < 0 for v in values):
            raise ValueError(f'{what}: podaj 4 wartości ≥ 0 (lewy, prawy, górny, dolny)')
    for i in range(4):
        if (bleed[i] > 0 or offset[i] > 0) and strip[i] <= 0:
            raise ValueError(f'Krawędź {names[i]}: szerokość wycinka musi być większa od zera')
    l, r, t, b = bleed
    sl, sr, st, sb = strip
    ol, or_, ot, ob = offset
    W, H = width, height
    if ol + sl + or_ + sr > W or ot + st + ob + sb > H:
        raise ValueError('Wycinki zachodzą na siebie: zmniejsz szerokość lub odległość wycinków')
    # kolumny i wiersze: (cel od, cel do, źródło od, źródło do)
    cols = [(0, l + ol, ol, ol + sl),                          # lewy pas
            (l + ol, l + W - or_, ol, W - or_),                # środek
            (l + W - or_, l + W + r, W - or_ - sr, W - or_)]   # prawy pas
    rows = [(0, t + ot, ot, ot + st),
            (t + ot, t + H - ob, ot, H - ob),
            (t + H - ob, t + H + b, H - ob - sb, H - ob)]
    pieces = []
    for ci, (cx0, cx1, sx0, sx1) in enumerate(cols):
        for ri, (cy0, cy1, sy0, sy1) in enumerate(rows):
            if ci == 1 and ri == 1:
                continue  # środek strony zostaje bez zmian
            if cx1 - cx0 <= 1e-9 or cy1 - cy0 <= 1e-9:
                continue
            pieces.append(((cx0, cy0, cx1, cy1), (sx0, sy0, sx1, sy1)))
    return pieces


def scale_factors(box_w: float, box_h: float, width: float | None, height: float | None,
                  percent: bool = False) -> tuple[float, float]:
    """Skale X/Y narzędzia „Skaluj strony”: do wymiarów wprost albo procentowo.

    E1: każdy wymiar jest „określony” albo „proporcjonalny” (None = proporcjonalny do drugiego).
    """
    if width is None and height is None:
        raise ValueError('Podaj co najmniej jeden wymiar (drugi może być proporcjonalny)')
    for value in (width, height):
        if value is not None and value <= 0:
            raise ValueError('Wymiar i procent muszą być większe od zera')
    if percent:
        sx = width / 100 if width is not None else None
        sy = height / 100 if height is not None else None
    else:
        sx = width / box_w if width is not None else None
        sy = height / box_h if height is not None else None
    sx = sy if sx is None else sx
    sy = sx if sy is None else sy
    if sx > 20 or sy > 20:
        raise ValueError('Skala większa niż 2000% — sprawdź wpisane wymiary')
    return sx, sy


def rotation_for(page: int, current: int, angle: int, even_extra_180: bool = False) -> int:
    """Obrót strony po narzędziu „Obróć strony” (H-18: kąt dodaje się do bieżącego /Rotate)."""
    if angle not in (0, 90, 180, 270) or current % 90:
        raise ValueError('Obrót musi wynosić 0°, 90°, 180° albo 270°')
    extra = 180 if even_extra_180 and page % 2 == 0 else 0
    return (current + angle + extra) % 360
