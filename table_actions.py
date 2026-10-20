"""Czysta logika menu kontekstowego tabeli stron (wzorowane na Impozycjonerze 4), bez Tk i PyMuPDF.

Wiersz tabeli ma identyfikator „plik:strona” (oba numery od 0), np. „2:5”.
Oryginał ma w menu tabeli m.in.: zaznacz wszystkie / parzyste / nieparzyste, odwróć zaznaczenie,
znajdź pierwszy arkusz z tą stroną, usuń zaznaczone wiersze, ustaw rozmiar użytka równy stronie.
Decyzje własne: parzystość liczona wg numeru strony w PDF (kolumna SPDF); „usunięcie” strony
w Studio = rola „Pomiń” (plik PDF i numeracja pozostałych stron się nie zmieniają).
"""
from __future__ import annotations

SELECT_ALL = 'all'
SELECT_EVEN = 'even'
SELECT_ODD = 'odd'
SELECT_INVERT = 'invert'


def parse_row(iid: str) -> tuple[int, int]:
    job, page = iid.split(':')
    return int(job), int(page)


def select_rows(iids: list[str], which: str, current: list[str] = ()) -> list[str]:
    """Wiersze do zaznaczenia; `current` — dotychczasowe zaznaczenie (dla odwrócenia)."""
    if which == SELECT_ALL:
        return list(iids)
    if which == SELECT_INVERT:
        chosen = set(current)
        return [iid for iid in iids if iid not in chosen]
    if which in (SELECT_EVEN, SELECT_ODD):
        want = 0 if which == SELECT_EVEN else 1
        return [iid for iid in iids if (parse_row(iid)[1] + 1) % 2 == want]
    raise ValueError(f'Nieznany rodzaj zaznaczenia: {which}')


def first_side_with(sides, path: str, index: int) -> int | None:
    """Indeks pierwszej strony arkusza, na której jest dana strona PDF (None, gdy nie występuje)."""
    for number, side in enumerate(sides):
        for placement in side.placements:
            source = placement.source
            if source is not None and source.path == path and source.index == index:
                return number
    return None


def pages_by_job(iids: list[str]) -> dict[int, list[int]]:
    """Zaznaczone wiersze pogrupowane według pliku: {plik: [strony od 0, rosnąco]}."""
    result: dict[int, list[int]] = {}
    for iid in iids:
        job, page = parse_row(iid)
        result.setdefault(job, []).append(page)
    return {job: sorted(set(pages)) for job, pages in result.items()}


def set_skip(page_roles: dict[str, str], pages: list[int], skip: bool, skip_role: str,
             default_role: str, auto_role: str) -> dict[str, str]:
    """Nowe wyjątki ról pliku po pominięciu (skip=True) albo przywróceniu stron (od 0).

    Przywrócona strona dostaje rolę domyślną pliku, a gdy domyślną jest „Pomiń” — `auto_role`.
    Wyjątek równy roli domyślnej nie jest zapisywany.
    """
    roles = dict(page_roles)
    for page in pages:
        key = str(page + 1)
        if skip:
            target = skip_role
        elif roles.get(key, default_role) != skip_role:
            continue
        else:
            target = auto_role if default_role == skip_role else default_role
        if target == default_role:
            roles.pop(key, None)
        else:
            roles[key] = target
    return roles
