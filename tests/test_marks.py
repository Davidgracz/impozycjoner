"""Znaczniki wzorowane na Impozycjonerze 4: wycinka środkowa, docięcie TrimBox, parametry linii cięcia.

Reguły z tekstów oryginału: wycinka pionowa tylko przy parzystej liczbie kolumn; docięcie TrimBox z lewej na stronach
parzystych i z prawej na nieparzystych. Pozostałe zachowania to hipotezy H-22…H-25 (marks.py,
docs/imp4-wersja-finalna.md). Wartości domyślne muszą dawać wynik identyczny jak przed zmianą.
"""
from dataclasses import asdict, replace
import json
import zipfile

import pymupdf as fitz
import pytest

import marks
from engine import (Job, Project, Settings, export_pdf, geometry, gutter_mark_lines, gutter_notes,
                    load_project, pt)
from preflight import inspect_project


# --- czyste reguły -----------------------------------------------------------------------------

def test_gutter_only_for_even_counts():
    assert marks.gutter_applies(4, 10)
    assert not marks.gutter_applies(3, 10)
    assert not marks.gutter_applies(1, 10)
    assert not marks.gutter_applies(4, 0)
    assert not marks.gutter_applies(4, 10, enabled=False)


def test_axis_with_gutter_replaces_middle_gap():
    # 4 użytki po 50 mm, odstęp 5 mm, wycinka 20 mm: 4*50 + 2*5 + 20 = 230
    assert marks.axis_length(4, 50, 5, 20, True) == 230
    assert marks.axis_offsets(4, 50, 5, 20, True) == [0, 55, 125, 180]
    # nieparzysta liczba: wycinki nie ma
    assert marks.axis_length(3, 50, 5, 20, True) == 160
    assert marks.axis_offsets(3, 50, 5, 20, True) == [0, 55, 110]


def test_h22_auto_count_fits_gutter():
    # bez wycinki mieszczą się 4 (4*50+3*5=215 <= 220); z wycinką 20 mm 4 kolumny = 230 > 220 → 3 (bez wycinki)
    assert marks.auto_count(220, 50, 5) == 4
    assert marks.auto_count(220, 50, 5, 20, True) == 3
    assert marks.auto_count(230, 50, 5, 20, True) == 4


def test_h23_gutter_mark_segments():
    assert marks.gutter_mark_segments(100, 10, 310, 5) == [(10, 15), (305, 310)]
    assert marks.gutter_mark_segments(100, 10, 310, 0) == [(10, 310)]
    assert marks.gutter_mark_segments(100, 10, 18, 5) == [(10, 18)]


def test_trim_crop_side_even_left_odd_right():
    assert marks.trim_crop_side(2) == 'left'
    assert marks.trim_crop_side(1) == 'right'
    with pytest.raises(ValueError):
        marks.trim_crop_side(0)


# --- geometria ------------------------------------------------------------------------------------

BASE = dict(sheet_w=330, sheet_h=120, trim_w=70, trim_h=40, bleed=0, margin_x=5, margin_y=5,
            gap_x=5, gap_y=5, rotation='0', crop_marks=False)


def test_default_geometry_unchanged():
    old = geometry(Settings(**BASE))
    same = geometry(Settings(**BASE, gutter_v=20, gutter_on=False))
    assert old == same
    assert (old.gutter_x, old.gutter_y) == (None, None)


def test_vertical_gutter_with_four_columns_centred():
    s = Settings(**BASE, gutter_on=True, gutter_v=20)
    g = geometry(s)
    assert (g.cols, g.rows) == (4, 2)
    xs = sorted({slot.x for slot in g.slots})
    assert [round(b - a, 6) for a, b in zip(xs, xs[1:])] == [75, 90, 75]   # 70 + odstęp 5 / 70 + wycinka 20
    assert g.gutter_x == pytest.approx(165)                                 # środek arkusza 330 mm
    assert gutter_notes(s) == []


def test_vertical_gutter_skipped_for_odd_columns_with_note():
    s = Settings(**BASE, gutter_on=True, gutter_v=20, columns=3)
    g = geometry(s)
    assert g.gutter_x is None
    assert 'kolumn (3)' in gutter_notes(s)[0]
    assert gutter_mark_lines(s) == []


def test_horizontal_gutter_and_manual_grid_that_does_not_fit():
    s = Settings(**BASE, gutter_on=True, gutter_h=10)
    g = geometry(s)
    ys = sorted({slot.y for slot in g.slots})
    assert round(ys[1] - ys[0], 6) == 50                                     # 40 + wycinka 10
    with pytest.raises(ValueError):
        geometry(Settings(**dict(BASE, gutter_on=True, gutter_v=200, columns=4)))


def test_invalid_values_rejected():
    for bad in ({'gutter_v': -1}, {'trim_crop_pt': 25}, {'mark_length': 0}, {'mark_width_pt': 9}):
        with pytest.raises(ValueError):
            geometry(Settings(**dict(BASE, **bad)))


# --- PDF ------------------------------------------------------------------------------------------

def make_pdf(folder, name, pages, w=70, h=40, fill=True):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=pt(w), height=pt(h))
        if fill:  # czerwony pas przy lewej i niebieski przy prawej krawędzi (po 3 pt)
            page.draw_rect(fitz.Rect(0, 0, 3, page.rect.height), color=None, fill=(1, 0, 0))
            page.draw_rect(fitz.Rect(page.rect.width - 3, 0, page.rect.width, page.rect.height),
                           color=None, fill=(0, 0, 1))
        page.insert_text((20, 30), f'page-{i + 1}')
    path = folder / name
    doc.save(path)
    doc.close()
    return str(path)


def lines(page):
    return [item for d in page.get_drawings() for item in d['items'] if item[0] == 'l']


def test_gutter_marks_in_pdf(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 8, fill=False)
    s = Settings(**BASE, gutter_on=True, gutter_v=20, gutter_mark_length=5)
    out = tmp_path / 'o.pdf'
    export_pdf(Project(s, [Job(src)]), str(out))
    with fitz.open(out) as doc:
        found = lines(doc[0])
    assert len(found) == 2
    for _, p0, p1 in found:
        assert p0.x == pytest.approx(pt(165)) and p1.x == pytest.approx(pt(165))
    assert sorted(round(abs(p1.y - p0.y) * 25.4 / 72, 3) for _, p0, p1 in found) == [5, 5]


def test_cut_mark_parameters(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 1, fill=False)
    s = Settings(**dict(BASE, crop_marks=True, columns=1, rows=1), mark_offset=2, mark_length=4, mark_width_pt=0.5)
    out = tmp_path / 'o.pdf'
    export_pdf(Project(s, [Job(src)]), str(out))
    with fitz.open(out) as doc:
        drawings = doc[0].get_drawings()
    widths = {round(d['width'], 3) for d in drawings if any(i[0] == 'l' for i in d['items'])}
    assert widths == {0.5}
    lengths = {round(abs((p1 - p0).x) + abs((p1 - p0).y), 3)
               for d in drawings for kind, p0, p1 in [i for i in d['items'] if i[0] == 'l']}
    assert lengths == {round(pt(4), 3)}


def colour_at(path, x_pt, y_pt):
    with fitz.open(path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4), alpha=False)
        return pix.pixel(int(x_pt * 4), int(y_pt * 4))


def test_trim_crop_left_on_even_right_on_odd(tmp_path):
    src = make_pdf(tmp_path, 'k.pdf', 2)
    base = dict(BASE, sheet_w=170, sheet_h=60, columns=2, rows=1, margin_x=5, margin_y=10, gap_x=20)
    plain, cropped = tmp_path / 'plain.pdf', tmp_path / 'crop.pdf'
    export_pdf(Project(Settings(**base), [Job(src)]), str(plain))
    export_pdf(Project(Settings(**base, trim_crop=True, trim_crop_pt=2.5), [Job(src)]), str(cropped))
    g = geometry(Settings(**base))
    left1, left2 = (pt(slot.x) for slot in g.slots)
    w = pt(70)
    y = pt(30)
    # bez docięcia: obie strony mają czerwony pas z lewej i niebieski z prawej
    assert colour_at(plain, left1 + 1, y)[0] > 200 and colour_at(plain, left2 + w - 1, y)[2] > 200
    # strona 1 (nieparzysta): ucięta z prawej, lewa krawędź bez zmian
    assert colour_at(cropped, left1 + 1, y)[0] > 200
    assert colour_at(cropped, left1 + w - 1, y) == (255, 255, 255)
    # strona 2 (parzysta): ucięta z lewej, prawa krawędź bez zmian
    assert colour_at(cropped, left2 + 1, y) == (255, 255, 255)
    assert colour_at(cropped, left2 + w - 1, y)[2] > 200


def test_old_project_without_new_fields_loads_with_defaults(tmp_path):
    settings = asdict(Settings(**BASE))
    for key in ('mark_offset', 'mark_length', 'mark_width_pt', 'gutter_on', 'gutter_v', 'gutter_h',
                'gutter_marks', 'gutter_mark_length', 'gutter_mark_pt', 'trim_crop', 'trim_crop_pt'):
        settings.pop(key)
    path = tmp_path / 'stary.psimp'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('project.json', json.dumps({'format': 'psimp', 'version': 1, 'settings': settings, 'jobs': []}))
    loaded = load_project(str(path))
    assert loaded.settings == Settings(**BASE)


def test_preflight_reports_skipped_gutter(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 3, fill=False)
    s = Settings(**BASE, gutter_on=True, gutter_v=20, columns=3)
    codes = [f.code for f in inspect_project(Project(s, [Job(src)])).findings]
    assert 'WYCINKA' in codes
