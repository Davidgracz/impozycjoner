"""F-NAR-SPLIT, -MERGE, -EXTRACT, -ROTATE, -DUP, -SHUFFLE: testy przekrojowe PDF → PDF (PyMuPDF).

Kolejność stron sprawdzamy po tekście „page-N” wstawionym w każdą stronę źródła. Wartości
oczekiwane wynikają z reguł opisanych w pageops.py (E1/H), a nie z samego kodu narzędzi.
"""
from pathlib import Path

import pytest

fitz = pytest.importorskip('pymupdf')

import pdftools


def make_pdf(folder: Path, name: str, n: int) -> str:
    path = folder / name
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page(width=200, height=100)
        page.insert_text((20, 50), f'page-{i + 1}')
    doc.save(path)
    doc.close()
    return str(path)


def order(path) -> list[int]:
    with fitz.open(path) as doc:
        return [int(page.get_text().split('page-')[1].split()[0]) for page in doc]


def test_split_every_page_with_suffix(tmp_path):
    src = make_pdf(tmp_path, 'Ulotka.pdf', 12)
    files = pdftools.split_pages(src, str(tmp_path / 'out'))
    assert [Path(f).name for f in files][:2] == ['Ulotka--01.pdf', 'Ulotka--02.pdf']
    assert Path(files[-1]).name == 'Ulotka--12.pdf'
    assert [order(f) for f in files] == [[n] for n in range(1, 13)]


def test_split_range_only(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 5)
    files = pdftools.split_pages(src, str(tmp_path), '-2, 5')
    assert [Path(f).name for f in files] == ['a--01.pdf', 'a--02.pdf', 'a--05.pdf']


def test_merge_keeps_input_order_and_needs_two(tmp_path):
    a, b = make_pdf(tmp_path, 'a.pdf', 3), make_pdf(tmp_path, 'b.pdf', 4)
    out = tmp_path / 'razem.pdf'
    pdftools.merge([b, a], str(out))
    assert order(out) == [1, 2, 3, 4, 1, 2, 3]
    with pytest.raises(ValueError):
        pdftools.merge([a], str(tmp_path / 'x.pdf'))


def test_output_must_not_overwrite_input(tmp_path):
    a, b = make_pdf(tmp_path, 'a.pdf', 3), make_pdf(tmp_path, 'b.pdf', 3)
    with pytest.raises(ValueError):
        pdftools.merge([a, b], a)
    with pytest.raises(ValueError):
        pdftools.shuffle(a, a)
    assert order(a) == [1, 2, 3]


def test_extract_range_remainder_and_separately(tmp_path):
    src = make_pdf(tmp_path, 'k.pdf', 6)
    files = pdftools.extract(src, str(tmp_path), '2-3, 6', remainder=True)
    assert [order(f) for f in files] == [[2, 3, 6], [1, 4, 5]]
    files = pdftools.extract(src, str(tmp_path / 's'), '2, 4', each_separately=True)
    assert [Path(f).name for f in files] == ['k--02.pdf', 'k--04.pdf']
    with pytest.raises(ValueError):
        pdftools.extract(src, str(tmp_path), '1-', remainder=True)


def test_extract_even_odd_cover_chunks(tmp_path):
    src = make_pdf(tmp_path, 'b.pdf', 8)
    odd, even = pdftools.extract_even_odd(src, str(tmp_path))
    assert (order(odd), order(even)) == ([1, 3, 5, 7], [2, 4, 6, 8])
    cover, body = pdftools.extract_cover(src, str(tmp_path))
    assert (order(cover), order(body)) == ([1, 2, 7, 8], [3, 4, 5, 6])
    parts = pdftools.extract_chunks(src, str(tmp_path / 'c'), 3)
    assert [order(p) for p in parts] == [[1, 2, 3], [4, 5, 6], [7, 8]]


def test_rotate_range_and_even_extra(tmp_path):
    src = make_pdf(tmp_path, 'r.pdf', 4)
    out = tmp_path / 'r_obrot.pdf'
    pdftools.rotate(src, str(out), 90, '1-3', even_extra_180=True)
    with fitz.open(out) as doc:
        assert [p.rotation for p in doc] == [90, 270, 90, 0]
        assert doc[0].rect.width == pytest.approx(100)  # wymiar strony po obrocie
    assert order(out) == [1, 2, 3, 4]


def test_duplicate_and_shuffle(tmp_path):
    src = make_pdf(tmp_path, 'd.pdf', 4)
    out = tmp_path / 'd2.pdf'
    pdftools.duplicate(src, str(out), 2, '2')
    assert order(out) == [1, 2, 2, 3, 4]
    pdftools.shuffle(src, str(tmp_path / 's1.pdf'))
    assert order(tmp_path / 's1.pdf') == [4, 3, 2, 1]
    pdftools.shuffle(src, str(tmp_path / 's2.pdf'), leaves=True)
    assert order(tmp_path / 's2.pdf') == [3, 4, 1, 2]


def test_not_a_pdf_and_bad_range_leave_no_output(tmp_path):
    fake = tmp_path / 'tekst.pdf'
    fake.write_text('to nie jest PDF')
    with pytest.raises(ValueError):
        pdftools.split_pages(str(fake), str(tmp_path / 'o'))
    src = make_pdf(tmp_path, 'z.pdf', 3)
    with pytest.raises(ValueError):
        pdftools.split_pages(src, str(tmp_path / 'o'), '2-9')
    assert not (tmp_path / 'o').exists()
