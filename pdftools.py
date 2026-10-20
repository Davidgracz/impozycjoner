"""Narzędzia stron PDF (F-NAR-SPLIT, -MERGE, -EXTRACT, -ROTATE, -DUP, -SHUFFLE).

Logika kolejności i zakresów jest w `pageops.py` (testowana bez PyMuPDF); tutaj tylko kopiowanie
stron. Strony są przenoszone wektorowo (`insert_pdf`), bez rasteryzacji; plik wejściowy nigdy
nie jest nadpisywany. Każda funkcja zwraca listę zapisanych plików.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from naming import output_name_problem
import pageops


def _open(path: str):
    if not Path(path).is_file():
        raise FileNotFoundError(f'Brak pliku: {path}')
    try:
        doc = fitz.open(path)
    except Exception as exc:  # PyMuPDF zgłasza własne typy wyjątków dla plików nie-PDF
        raise ValueError(f'Plik nie jest poprawnym PDF: {Path(path).name}') from exc
    if not doc.is_pdf or doc.needs_pass or len(doc) == 0:
        doc.close()
        raise ValueError(f'Nieobsługiwany lub zabezpieczony hasłem PDF: {Path(path).name}')
    return doc


def _check_target(target: Path, inputs: list[str]):
    problem = output_name_problem(target.name, inputs)
    if problem:
        raise ValueError(problem)
    for source in inputs:
        if Path(source).resolve() == target.resolve():
            raise ValueError('Plik wynikowy nie może nadpisać pliku przetwarzanego.')


def _write(source, pages: list[int], target: Path, inputs: list[str]) -> str:
    """Zapisz strony `pages` (od 1, w podanej kolejności, mogą się powtarzać)."""
    _check_target(target, inputs)
    out = fitz.open()
    try:
        for number in pages:
            out.insert_pdf(source, from_page=number - 1, to_page=number - 1)
        target.parent.mkdir(parents=True, exist_ok=True)
        out.save(str(target), garbage=3, deflate=True)
    finally:
        out.close()
    return str(target)


def _stem(path: str) -> str:
    return Path(path).stem


def split_pages(path: str, folder: str, pages_text: str | None = None) -> list[str]:
    """Każda strona w osobnym pliku `nazwa--XX.pdf` (P-06, H-15)."""
    with _open(path) as doc:
        count = len(doc)
        pages = pageops.parse_page_ranges(pages_text, count) if pages_text else list(range(1, count + 1))
        return [_write(doc, [n], Path(folder) / f'{_stem(path)}{pageops.page_suffix(n, count)}.pdf', [path])
                for n in pages]


def merge(paths: list[str], output: str) -> list[str]:
    """Połącz pliki w kolejności listy (P-42: co najmniej dwa)."""
    if len(paths) < 2:
        raise ValueError('Wybierz co najmniej 2 pliki do połączenia')
    target = Path(output)
    _check_target(target, paths)
    docs = []
    try:
        for p in paths:
            docs.append(_open(p))
        out = fitz.open()
        try:
            for doc in docs:
                out.insert_pdf(doc)
            target.parent.mkdir(parents=True, exist_ok=True)
            out.save(str(target), garbage=3, deflate=True)
        finally:
            out.close()
    finally:
        for doc in docs:
            doc.close()
    return [str(target)]


def extract(path: str, folder: str, pages_text: str, each_separately: bool = False,
            remainder: bool = False) -> list[str]:
    """Wydziel strony z zakresu; opcjonalnie każdą osobno i/lub plik bez stron wydzielonych.

    H-16: nazwy `nazwa--wydzielone.pdf` i `nazwa--bez_wydzielonych.pdf` (oryginał ich nie opisuje).
    """
    with _open(path) as doc:
        count = len(doc)
        pages = pageops.parse_page_ranges(pages_text, count)
        folder_path = Path(folder)
        written = []
        if each_separately:
            written += [_write(doc, [n], folder_path / f'{_stem(path)}{pageops.page_suffix(n, count)}.pdf', [path])
                        for n in pages]
        else:
            written.append(_write(doc, pages, folder_path / f'{_stem(path)}--wydzielone.pdf', [path]))
        if remainder:
            rest = [n for n in range(1, count + 1) if n not in set(pages)]
            if not rest:
                raise ValueError('Wydzielono wszystkie strony — plik bez stron wydzielonych byłby pusty')
            written.append(_write(doc, rest, folder_path / f'{_stem(path)}--bez_wydzielonych.pdf', [path]))
        return written


def extract_even_odd(path: str, folder: str) -> list[str]:
    with _open(path) as doc:
        odd, even = pageops.even_odd(len(doc))
        return [_write(doc, odd, Path(folder) / f'{_stem(path)}--nieparzyste.pdf', [path]),
                _write(doc, even, Path(folder) / f'{_stem(path)}--parzyste.pdf', [path])]


def extract_cover(path: str, folder: str) -> list[str]:
    with _open(path) as doc:
        cover, body = pageops.cover_and_body(len(doc))
        return [_write(doc, cover, Path(folder) / f'{_stem(path)}--okladka.pdf', [path]),
                _write(doc, body, Path(folder) / f'{_stem(path)}--wklad.pdf', [path])]


def extract_chunks(path: str, folder: str, per_file: int) -> list[str]:
    """Wydziel zakresy: pliki po `per_file` stron (H-16: nazwy z numerem części `--XX`)."""
    with _open(path) as doc:
        parts = pageops.chunks(len(doc), per_file)
        return [_write(doc, part, Path(folder) / f'{_stem(path)}{pageops.page_suffix(i, len(parts))}.pdf', [path])
                for i, part in enumerate(parts, start=1)]


def rotate(path: str, output: str, angle: int, pages_text: str | None = None,
           even_extra_180: bool = False) -> list[str]:
    """Obróć strony z zakresu (H-18: kąt dodaje się do bieżącego obrotu strony)."""
    with _open(path) as doc:
        count = len(doc)
        pages = set(pageops.parse_page_ranges(pages_text, count) if pages_text else range(1, count + 1))
        target = Path(output)
        _check_target(target, [path])
        out = fitz.open()
        try:
            out.insert_pdf(doc)
            for number in pages:
                page = out[number - 1]
                page.set_rotation(pageops.rotation_for(number, page.rotation, angle, even_extra_180))
            target.parent.mkdir(parents=True, exist_ok=True)
            out.save(str(target), garbage=3, deflate=True)
        finally:
            out.close()
        return [str(target)]


def duplicate(path: str, output: str, times: int, pages_text: str | None = None) -> list[str]:
    """Powiel wskazane strony `times` razy (H-14)."""
    with _open(path) as doc:
        count = len(doc)
        pages = pageops.parse_page_ranges(pages_text, count) if pages_text else list(range(1, count + 1))
        return [_write(doc, pageops.duplicate_order(count, pages, times), Path(output), [path])]


def shuffle(path: str, output: str, leaves: bool = False) -> list[str]:
    """Tasuj strony albo kartki (P-41)."""
    with _open(path) as doc:
        return [_write(doc, pageops.shuffle_order(len(doc), leaves), Path(output), [path])]
