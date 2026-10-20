"""Funkcje okna głównego wzorowane na Impozycjonerze 4 (odczyt zasobów oryginału, zob.
docs/imp4-wersja-finalna.md): tryby „Wykonaj impozycję”, nazwa i metadane pliku wynikowego,
menu tabeli stron, czytelny błąd dla plików nie-PDF.
"""
from pathlib import Path

import pymupdf as fitz
import pytest

import table_actions
from engine import (Job, Project, Settings, SheetSide, Placement, SourcePage, Slot, RUN_ACTIVE, RUN_ALL,
                    RUN_EXCEPT_ACTIVE, ROLE_AUTO, ROLE_SKIP, export_pdf, open_sources, output_metadata,
                    select_sides)
from naming import FORBIDDEN_OUTPUT_CHARS, add_imposition_phrase, output_name_problem


def side(number, side_no=0, sources=()):
    slot = Slot(0, 0, 10, 10, 0, 0, 0)
    return SheetSide(number, side_no, tuple(Placement(s, slot, side_no) for s in sources))


# --- „Wykonaj impozycję”: wszystkie / tylko aktywny / oprócz aktywnego --------------------------

def test_select_sides_modes_keep_recto_and_verso_together():
    sides = [side(1, 0), side(1, 1), side(2, 0), side(2, 1), side(3, 0), side(3, 1)]
    assert list(select_sides(sides)) == sides
    assert [(s.sheet_number, s.side) for s in select_sides(sides, RUN_ACTIVE, 2)] == [(2, 0), (2, 1)]
    assert [s.sheet_number for s in select_sides(sides, RUN_EXCEPT_ACTIVE, 2)] == [1, 1, 3, 3]
    with pytest.raises(ValueError):
        list(select_sides(sides, RUN_ACTIVE, None))
    with pytest.raises(ValueError):
        list(select_sides(sides, 'coś'))


def make_pdf(folder: Path, name: str, pages: int, w=90, h=50) -> str:
    path = folder / name
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=w * 72 / 25.4, height=h * 72 / 25.4)
        page.insert_text((10, 20), f'page-{i + 1}')
    doc.save(path)
    doc.close()
    return str(path)


def two_up_project(src):
    s = Settings(sheet_w=190, sheet_h=60, trim_w=90, trim_h=50, bleed=0, margin_x=4, margin_y=4,
                 gap_x=0, gap_y=0, crop_marks=False)
    return Project(s, [Job(src)])


def test_export_only_active_and_all_but_active(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 6)          # 2 użytki na arkusz → 3 arkusze
    project = two_up_project(src)
    assert export_pdf(project, str(tmp_path / 'all.pdf')) == 3
    assert export_pdf(project, str(tmp_path / 'one.pdf'), run_mode=RUN_ACTIVE, active_sheet=2) == 1
    with fitz.open(tmp_path / 'one.pdf') as doc:
        assert 'page-3' in doc[0].get_text() and 'page-4' in doc[0].get_text()
    assert export_pdf(project, str(tmp_path / 'rest.pdf'), run_mode=RUN_EXCEPT_ACTIVE, active_sheet=2) == 2
    with pytest.raises(ValueError):
        export_pdf(project, str(tmp_path / 'none.pdf'), run_mode=RUN_ACTIVE, active_sheet=9)


# --- Plik wynikowy: nazwa i metadane --------------------------------------------------------------

def test_output_name_rules():
    for ch in FORBIDDEN_OUTPUT_CHARS:
        assert output_name_problem(f'a{ch}b.pdf') is not None
    assert output_name_problem('montaz.pdf', ['C:/x/wejscie.pdf']) is None
    assert output_name_problem('Wejscie.PDF', ['C:/x/wejscie.pdf']) is not None
    assert output_name_problem('.pdf') is not None
    assert add_imposition_phrase('montaz.pdf') == 'montaz--IMPOZYCJONER.pdf'
    assert add_imposition_phrase('montaz--IMPOZYCJONER.pdf') == 'montaz--IMPOZYCJONER.pdf'


def test_metadata_empty_fields_are_file_name_and_default_unchanged(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 2)
    out = tmp_path / 'Ulotki_500.pdf'
    export_pdf(two_up_project(src), str(out), {'author': 'Drukarnia', 'title': '', 'subject': '', 'keywords': ' '})
    with fitz.open(out) as doc:
        meta = doc.metadata
    assert meta['author'] == 'Drukarnia'
    assert meta['title'] == meta['subject'] == meta['keywords'] == 'Ulotki_500'
    export_pdf(two_up_project(src), str(tmp_path / 'b.pdf'))
    with fitz.open(tmp_path / 'b.pdf') as doc:
        assert doc.metadata['title'] == 'Impozycjoner Studio - montaż PDF'
    with pytest.raises(ValueError):
        output_metadata('x.pdf', {'producer': 'x'})


def test_not_a_pdf_and_encrypted_are_value_errors(tmp_path):
    fake = tmp_path / 'tekst.pdf'
    fake.write_text('to nie jest PDF')
    locked = tmp_path / 'haslo.pdf'
    doc = fitz.open()
    doc.new_page()
    doc.save(locked, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw='a', owner_pw='b')
    doc.close()
    for path in (fake, locked):
        with pytest.raises(ValueError):
            open_sources([Job(str(path))])


# --- Menu tabeli stron ----------------------------------------------------------------------------

def test_select_rows():
    rows = ['0:0', '0:1', '0:2', '1:0', '1:1']
    assert table_actions.select_rows(rows, table_actions.SELECT_ALL) == rows
    assert table_actions.select_rows(rows, table_actions.SELECT_ODD) == ['0:0', '0:2', '1:0']
    assert table_actions.select_rows(rows, table_actions.SELECT_EVEN) == ['0:1', '1:1']
    assert table_actions.select_rows(rows, table_actions.SELECT_INVERT, ['0:1']) == ['0:0', '0:2', '1:0', '1:1']
    with pytest.raises(ValueError):
        table_actions.select_rows(rows, 'x')


def test_first_side_with_page():
    a, b = SourcePage('a.pdf', 0), SourcePage('a.pdf', 3)
    sides = [side(1, 0, (a, None)), side(2, 0, (a, b))]
    assert table_actions.first_side_with(sides, 'a.pdf', 3) == 1
    assert table_actions.first_side_with(sides, 'a.pdf', 0) == 0
    assert table_actions.first_side_with(sides, 'b.pdf', 0) is None


def test_skip_and_restore_pages():
    roles = table_actions.set_skip({}, [0, 2], True, ROLE_SKIP, ROLE_AUTO, ROLE_AUTO)
    assert roles == {'1': ROLE_SKIP, '3': ROLE_SKIP}
    assert table_actions.set_skip(roles, [0], False, ROLE_SKIP, ROLE_AUTO, ROLE_AUTO) == {'3': ROLE_SKIP}
    # plik domyślnie pominięty: przywrócenie zapisuje jawną rolę „Normalnie”
    assert table_actions.set_skip({}, [1], False, ROLE_SKIP, ROLE_SKIP, ROLE_AUTO) == {'2': ROLE_AUTO}
    # przywracanie strony, która nie jest pominięta, nic nie zmienia
    assert table_actions.set_skip({'2': 'Przód'}, [1], False, ROLE_SKIP, ROLE_AUTO, ROLE_AUTO) == {'2': 'Przód'}
    assert table_actions.pages_by_job(['1:3', '0:2', '1:0', '1:3']) == {1: [0, 3], 0: [2]}


def test_skipped_pages_leave_the_imposition(tmp_path):
    src = make_pdf(tmp_path, 'a.pdf', 4)
    project = two_up_project(src)
    project.jobs[0].page_roles = table_actions.set_skip({}, [1, 2], True, ROLE_SKIP, ROLE_AUTO, ROLE_AUTO)
    assert export_pdf(project, str(tmp_path / 'o.pdf')) == 1
    with fitz.open(tmp_path / 'o.pdf') as doc:
        text = doc[0].get_text()
    assert 'page-1' in text and 'page-4' in text and 'page-2' not in text
