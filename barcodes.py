"""Kody kreskowe EAN-13 i EAN-8 (F-NAR-EAN13): kodowanie wg publicznej normy GS1.

Czysta część (cyfra kontrolna, wzór modułów) działa bez PyMuPDF. Rysowanie tworzy kreski
jako wektorowe prostokąty w kolorze K=100 % — nie adnotacje i nie bitmapy.

Z tekstów oryginału (E1, P-44): wartość EAN-13 ma 12 albo 13 cyfr, EAN-8 — 7 albo 8;
kody czyta się z pliku tekstowego, a plik bez żadnego poprawnego wiersza jest błędem.
Wymiary nominalne (moduł 0,33 mm, wysokość kresek 22,85 mm, strefy ciszy 11/7 modułów)
pochodzą z normy, nie z oryginału.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_L = ('0001101', '0011001', '0010011', '0111101', '0100011',
      '0110001', '0101111', '0111011', '0110111', '0001011')
_G = tuple(code[::-1].translate(str.maketrans('01', '10')) for code in _L)
_R = tuple(code.translate(str.maketrans('01', '10')) for code in _L)
# Pierwsza cyfra EAN-13 wybiera parzystość (L/G) sześciu cyfr lewej połowy.
_PARITY = ('LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG',
           'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL')

MODULE_MM = 0.33
BAR_HEIGHT_MM = 22.85
GUARD_EXTRA_MM = 1.65  # kreski ograniczające są dłuższe o 5 modułów


def check_digit(digits: str) -> int:
    """Cyfra kontrolna GS1 (wagi 3,1,3,… od prawej)."""
    if not digits.isdigit() or not digits.isascii():
        raise ValueError('Kod może zawierać tylko cyfry')
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def normalize(value: str, kind: str = 'EAN13') -> str:
    """Pełny kod z cyfrą kontrolną; przy pełnej długości cyfra kontrolna musi się zgadzać."""
    data_len = {'EAN13': 12, 'EAN8': 7}.get(kind)
    if data_len is None:
        raise ValueError(f'Nieznany rodzaj kodu: {kind}')
    value = value.strip()
    if not value.isdigit() or not value.isascii():
        raise ValueError(f'{kind}: kod może zawierać tylko cyfry: „{value}”')
    if len(value) == data_len:
        return value + str(check_digit(value))
    if len(value) == data_len + 1:
        expected = check_digit(value[:-1])
        if int(value[-1]) != expected:
            raise ValueError(f'{kind}: błędna cyfra kontrolna w „{value}” (powinna być {expected})')
        return value
    name = 'EAN-13' if kind == 'EAN13' else 'EAN-8'
    raise ValueError(f'{name}: wartość musi mieć {data_len} albo {data_len + 1} cyfr: „{value}”')


def modules(code: str) -> str:
    """Wzór modułów (1 = kreska) bez stref ciszy: 95 modułów dla EAN-13, 67 dla EAN-8."""
    if len(code) == 13:
        parity = _PARITY[int(code[0])]
        left = ''.join((_L if p == 'L' else _G)[int(d)] for p, d in zip(parity, code[1:7]))
        right = ''.join(_R[int(d)] for d in code[7:])
    elif len(code) == 8:
        left = ''.join(_L[int(d)] for d in code[:4])
        right = ''.join(_R[int(d)] for d in code[4:])
    else:
        raise ValueError('Podaj pełny kod EAN-13 (13 cyfr) albo EAN-8 (8 cyfr)')
    return '101' + left + '01010' + right + '101'


def guard_positions(code: str) -> set[int]:
    """Indeksy modułów kresek ograniczających (rysowanych dłużej)."""
    total = 95 if len(code) == 13 else 67
    middle = total // 2 - 2
    return {0, 1, 2, middle, middle + 1, middle + 2, middle + 3, middle + 4,
            total - 3, total - 2, total - 1}


def bars(pattern: str) -> list[tuple[int, int]]:
    """Ciągi kresek jako (pierwszy moduł, szerokość w modułach)."""
    result, start = [], None
    for i, bit in enumerate(pattern + '0'):
        if bit == '1' and start is None:
            start = i
        elif bit != '1' and start is not None:
            result.append((start, i - start))
            start = None
    return result


def read_codes(text: str, kind: str = 'EAN13') -> tuple[list[str], list[tuple[int, str]]]:
    """Kody z pliku tekstowego: jeden na wiersz; puste wiersze pomijane.

    Zwraca (poprawne kody, [(numer wiersza, komunikat), …]). H-20: błędne wiersze są
    raportowane i pomijane, a brak jakiegokolwiek poprawnego kodu jest błędem.
    """
    good, bad = [], []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            good.append(normalize(line, kind))
        except ValueError as exc:
            bad.append((number, str(exc)))
    if not good:
        raise ValueError('Żaden wiersz pliku nie zawiera poprawnego kodu '
                         + ('EAN-13' if kind == 'EAN13' else 'EAN-8'))
    return good, bad


@dataclass(frozen=True)
class BarcodeStyle:
    module_mm: float = MODULE_MM
    height_mm: float = BAR_HEIGHT_MM
    human_readable: bool = True


def symbol_size(code: str, style: BarcodeStyle = BarcodeStyle()) -> tuple[float, float]:
    """Wymiar symbolu w mm ze strefami ciszy (EAN-13: 11 + 95 + 7, EAN-8: 7 + 67 + 7 modułów)."""
    width_modules = 113 if len(code) == 13 else 81
    text_mm = 3.0 if style.human_readable else 0.0
    return width_modules * style.module_mm, style.height_mm + GUARD_EXTRA_MM + text_mm


def draw(page, x_mm: float, y_mm: float, code: str, style: BarcodeStyle = BarcodeStyle()):
    """Narysuj kod na stronie PyMuPDF; (x, y) = lewy górny róg symbolu ze strefą ciszy."""
    from engine import pt
    quiet = 11 if len(code) == 13 else 7
    pattern = modules(code)
    guards = guard_positions(code)
    shape = page.new_shape()
    for start, width in bars(pattern):
        long = start in guards
        x0 = x_mm + (quiet + start) * style.module_mm
        height = style.height_mm + (GUARD_EXTRA_MM if long else 0)
        shape.draw_rect((pt(x0), pt(y_mm), pt(x0 + width * style.module_mm), pt(y_mm + height)))
    shape.finish(color=None, fill=(0, 0, 0, 1), width=0)
    shape.commit()
    if style.human_readable:
        size = pt(style.module_mm * 7 * 1.15)
        baseline = pt(y_mm + style.height_mm + GUARD_EXTRA_MM + 1.0)
        if len(code) == 13:
            groups = [(code[0], -quiet + 2), (code[1:7], 3 + 4), (code[7:], 50 + 4)]
        else:
            groups = [(code[:4], 3 + 4), (code[4:], 36 + 4)]
        for text, offset in groups:
            page.insert_text((pt(x_mm + (quiet + offset) * style.module_mm), baseline), text,
                             fontsize=size, fontname='cour', color=(0, 0, 0, 1))


def export_pdf(codes: list[str], output: str, style: BarcodeStyle = BarcodeStyle()) -> int:
    """Każdy kod na osobnej stronie o wymiarze symbolu (do dalszej impozycji). Zwraca liczbę stron."""
    from engine import pt
    import pymupdf as fitz
    if not codes:
        raise ValueError('Brak kodów do wygenerowania')
    out = fitz.open()
    try:
        for code in codes:
            w, h = symbol_size(code, style)
            page = out.new_page(width=pt(w), height=pt(h + 2))
            draw(page, 0, 1, code, style)
        out.set_metadata({'title': 'Kody EAN', 'creator': 'Impozycjoner Studio'})
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        out.save(output, garbage=3, deflate=True)
        return len(out)
    finally:
        out.close()
