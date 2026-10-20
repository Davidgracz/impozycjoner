"""Skalowanie i kadrowanie: A4 → A6 + 1,5 mm spadu, przycinanie białych marginesów, „Dodaj spady”, „Skaluj strony”.

Zachowanie narzędzi „Dodaj spady” i „Skaluj strony” odtworzono z tekstów okien Impozycjonera 4 (E1) i metadanych
wywołań biblioteki PDF (REA, statycznie). Wykrywanie białych marginesów i tryb „Wypełnij ze spadem” to rozszerzenia
Studio (H-26, H-27 w docs/imp4-wersja-finalna.md).
"""
from dataclasses import replace

import pymupdf as fitz
import pytest

import pageops
import pdftools
import whitecrop
from engine import FILL_GROSS, Job, Project, Settings, export_pages, export_pdf, geometry, pt, validate
from job_templates import BUILTIN, apply_template, read_template

GREEN = (0.1, 0.6, 0.2)


def a4(folder, name='ulotka_A4.pdf', white_margin=0.0):
    """A4 z grafiką na zielonym tle; `white_margin` mm białej ramki (niepomalowanej) wokół tła."""
    doc = fitz.open()
    page = doc.new_page(width=pt(210), height=pt(297))
    m = pt(white_margin)
    page.draw_rect(fitz.Rect(m, m, pt(210) - m, pt(297) - m), color=None, fill=GREEN)
    page.insert_text((pt(30), pt(60)), 'ULOTKA', fontsize=40, color=(1, 1, 1))
    path = folder / name
    doc.save(path)
    doc.close()
    return str(path)


def pixel(path, x_mm, y_mm, index=0):
    with fitz.open(path) as doc:
        pix = doc[index].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
        return pix.pixel(int(pt(x_mm) * 4), int(pt(y_mm) * 4))


def is_green(rgb):
    return rgb[1] > 120 and rgb[0] < 80


A6_SHEET = dict(sheet_w=120, sheet_h=163, trim_w=105, trim_h=148, bleed=1.5, margin_x=4, margin_y=4,
                gap_x=0, gap_y=0, columns=1, rows=1, crop_marks=False)


# --- scenariusz użytkownika: A4 → A6 + 1,5 mm -----------------------------------------------------

def test_fill_mode_without_bleed_leaves_white_but_fill_gross_does_not(tmp_path):
    src = a4(tmp_path)
    slot = geometry(Settings(**A6_SHEET)).slots[0]
    edge_x, mid_y = slot.x - 1.2, slot.y + slot.h / 2              # w spadzie, 1,2 mm za linią cięcia
    old = tmp_path / 'wypelnij.pdf'
    export_pdf(Project(Settings(**A6_SHEET, scale_mode='Wypełnij'), [Job(src)]), str(old))
    assert pixel(old, edge_x, mid_y) == (255, 255, 255)           # brak spadu w A4 → biały pasek
    new = tmp_path / 'wypelnij_ze_spadem.pdf'
    export_pdf(Project(Settings(**A6_SHEET, scale_mode=FILL_GROSS), [Job(src)]), str(new))
    assert is_green(pixel(new, edge_x, mid_y))                     # spad powstał z grafiki
    assert pixel(new, slot.x - 2.0, mid_y) == (255, 255, 255)     # ale nic nie wychodzi poza brutto


def test_white_margin_is_trimmed_before_scaling(tmp_path):
    src = a4(tmp_path, white_margin=10)
    slot = geometry(Settings(**A6_SHEET)).slots[0]
    inside_x, mid_y = slot.x + 0.5, slot.y + slot.h / 2           # 0,5 mm wewnątrz netto
    plain = tmp_path / 'bez_przyciecia.pdf'
    export_pdf(Project(Settings(**A6_SHEET, scale_mode=FILL_GROSS), [Job(src)]), str(plain))
    assert pixel(plain, inside_x, mid_y) == (255, 255, 255)       # biała ramka trafiła na użytek
    trimmed = tmp_path / 'przyciete.pdf'
    export_pdf(Project(Settings(**A6_SHEET, scale_mode=FILL_GROSS, white_trim=True), [Job(src)]), str(trimmed))
    for x, y in ((inside_x, mid_y), (slot.x - 1.2, mid_y), (slot.x + slot.w / 2, slot.y - 1.2),
                 (slot.x + slot.w + 1.2, mid_y), (slot.x + slot.w / 2, slot.y + slot.h + 1.2)):
        assert is_green(pixel(trimmed, x, y)), (x, y)


def test_single_pages_export_a6_with_bleed(tmp_path):
    src = a4(tmp_path, white_margin=8)
    out = tmp_path / 'strony_A6.pdf'
    s = Settings(**dict(A6_SHEET, columns=0, rows=0), scale_mode=FILL_GROSS, white_trim=True)
    assert export_pages(Project(s, [Job(src)]), str(out)) == 1
    with fitz.open(out) as doc:
        page = doc[0]
        assert page.rect.width == pytest.approx(pt(108)) and page.rect.height == pytest.approx(pt(151))
        assert tuple(page.trimbox) == pytest.approx(tuple(fitz.Rect(pt(1.5), pt(1.5), pt(106.5), pt(149.5))), abs=0.01)
    for x, y in ((0.3, 75), (107.7, 75), (54, 0.3), (54, 150.7)):  # same krawędzie spadu
        assert is_green(pixel(out, x, y)), (x, y)


def test_white_trim_needs_scaling_mode():
    for mode in ('Bez skalowania', 'Kadruj 1:1'):
        with pytest.raises(ValueError):
            validate(Settings(scale_mode=mode, white_trim=True))
    validate(Settings(scale_mode=FILL_GROSS, white_trim=True))
    with pytest.raises(ValueError):
        validate(Settings(scale_mode=FILL_GROSS, white_level=0))


# --- wykrywanie białych marginesów ----------------------------------------------------------------

def test_content_rect_finds_margin_within_half_mm(tmp_path):
    src = a4(tmp_path, white_margin=10)
    with fitz.open(src) as doc:
        page = doc[0]
        rect = whitecrop.content_rect(page, fitz.Rect(page.trimbox))
    for got, want in zip(rect, (pt(10), pt(10), pt(200), pt(287))):
        assert abs(got - want) <= pt(0.5)


def test_blank_page_keeps_whole_area(tmp_path):
    doc = fitz.open()
    doc.new_page(width=200, height=100)
    doc.save(tmp_path / 'pusta.pdf')
    doc.close()
    with fitz.open(tmp_path / 'pusta.pdf') as doc:
        assert whitecrop.content_rect(doc[0], doc[0].rect) == doc[0].rect


# --- „Dodaj spady” (jak w Imp4) ------------------------------------------------------------------

def test_bleed_pieces_geometry():
    pieces = pageops.bleed_pieces(100, 50, (3, 3, 3, 3), (1, 1, 1, 1), (5, 5, 5, 5))
    assert len(pieces) == 8                                        # 4 krawędzie + 4 narożniki
    left = [p for p in pieces if p[0][0] == 0 and p[0][1] == 8]
    assert left == [((0, 8, 8, 48), (5, 5, 6, 45))]               # wycinek 5–6 mm rozciągnięty na 0–8 mm
    assert len(pageops.bleed_pieces(100, 50, (3, 0, 0, 0), (1, 1, 1, 1), (0, 0, 0, 0))) == 1
    for bad in (((3, 3, 3, 3), (0, 1, 1, 1), (0, 0, 0, 0)), ((3, 3, 3, 3), (60, 60, 1, 1), (0, 0, 0, 0)),
                ((-1, 0, 0, 0), (1, 1, 1, 1), (0, 0, 0, 0))):
        with pytest.raises(ValueError):
            pageops.bleed_pieces(100, 50, *bad)


def test_add_bleed_covers_white_margin(tmp_path):
    src = a4(tmp_path, white_margin=5)
    out = tmp_path / 'ze_spadami.pdf'
    pdftools.add_bleed(src, str(out), (3, 3, 3, 3), (1, 1, 1, 1), (5, 5, 5, 5))
    with fitz.open(out) as doc:
        page = doc[0]
        assert page.rect.width == pytest.approx(pt(216)) and page.rect.height == pytest.approx(pt(303))
        assert tuple(page.trimbox) == pytest.approx(tuple(fitz.Rect(pt(3), pt(3), pt(213), pt(300))), abs=0.01)
        assert tuple(page.bleedbox) == pytest.approx(tuple(page.rect), abs=0.01)
    for x, y in ((0.5, 150), (5, 150), (215.5, 150), (108, 0.5), (108, 302.5), (0.5, 0.5)):
        assert is_green(pixel(out, x, y)), (x, y)


def test_add_bleed_keeps_pages_outside_range_and_rejects_bad_input(tmp_path):
    doc = fitz.open()
    for _ in range(2):
        doc.new_page(width=pt(100), height=pt(50))
    doc.save(tmp_path / 'dwie.pdf')
    doc.close()
    out = tmp_path / 'dwie_spady.pdf'
    pdftools.add_bleed(str(tmp_path / 'dwie.pdf'), str(out), (2, 2, 2, 2), (1, 1, 1, 1), (0, 0, 0, 0), pages_text='2')
    with fitz.open(out) as result:
        assert result[0].rect.width == pytest.approx(pt(100))
        assert result[1].rect.width == pytest.approx(pt(104))
    with pytest.raises(ValueError):
        pdftools.add_bleed(str(tmp_path / 'dwie.pdf'), str(tmp_path / 'x.pdf'), (2, 2, 2, 2), (0, 0, 0, 0), (0, 0, 0, 0))


# --- „Skaluj strony” (jak w Imp4) ----------------------------------------------------------------

def test_scale_factors():
    assert pageops.scale_factors(210, 297, 105, None) == (0.5, 0.5)
    assert pageops.scale_factors(210, 297, None, 148.5) == (0.5, 0.5)
    assert pageops.scale_factors(210, 297, 105, 297) == (0.5, 1.0)
    assert pageops.scale_factors(210, 297, 50, None, percent=True) == (0.5, 0.5)
    for args in ((None, None), (0, None), (5000, None)):
        with pytest.raises(ValueError):
            pageops.scale_factors(210, 297, *args)


def test_scale_pages_a4_to_a6_and_centre_on_page(tmp_path):
    src = a4(tmp_path)
    out = tmp_path / 'a6.pdf'
    pdftools.scale_pages(src, str(out), 105, None)
    with fitz.open(out) as doc:
        assert doc[0].rect.width == pytest.approx(pt(105)) and doc[0].rect.height == pytest.approx(pt(148.5))
        assert 'ULOTKA' in doc[0].get_text()
        assert doc[0].get_images() == []                           # wektorowo, bez rasteryzacji
    centred = tmp_path / 'a6_na_108x151.pdf'
    pdftools.scale_pages(src, str(centred), 50, None, percent=True, page_size=(108, 151))
    with fitz.open(centred) as doc:
        page = doc[0]
        assert page.rect.width == pytest.approx(pt(108))
        assert tuple(page.trimbox) == pytest.approx(tuple(fitz.Rect(pt(1.5), pt(1.25), pt(106.5), pt(149.75))), abs=0.01)


# --- szablon pracy -------------------------------------------------------------------------------

def test_builtin_template_for_a4_to_a6():
    name = next(n for n in BUILTIN if 'A6 + 1,5 mm' in n)
    s = apply_template(Settings(), read_template(name))
    assert (s.trim_w, s.trim_h, s.bleed, s.scale_mode, s.white_trim) == (105, 148, 1.5, FILL_GROSS, True)
    validate(s)


def test_old_template_without_white_trim_still_loads():
    from job_templates import _clean
    values = dict(read_template(next(iter(BUILTIN)))['settings'])
    values.pop('white_trim')
    assert _clean(values)['white_trim'] is False
