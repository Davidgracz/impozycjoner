"""F-AKC-REP, krok 4: od nazwy pliku do gotowego PDF-a (wymaga PyMuPDF).

Test akceptacyjny przekrojowy: plik `Arkusz_2.pdf` (3 strony) → komenda „z nazwy”
→ eksport → każda strona występuje dokładnie 2 razy, pod rząd, w kolejności stron.
Wartości oczekiwane wynikają z reguły z pomocy oryginału (E1), nie z kodu.
"""
from pathlib import Path

import pytest

fitz = pytest.importorskip('pymupdf')

from commands import CommandStack, SetPageRepeat
from engine import Job, Project, Settings, export_pages, export_pdf, load_project, save_project

TWO_UP = dict(sheet_w=190, sheet_h=60, trim_w=90, trim_h=50, bleed=0,
              margin_x=4, margin_y=4, gap_x=0, gap_y=0, crop_marks=False)


def make_source(folder: Path, name: str, n: int, w: float = 90, h: float = 50) -> str:
    path = folder / name
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page(width=w * 72 / 25.4, height=h * 72 / 25.4)
        page.insert_text((20, 30), f'page-{i + 1}')
    doc.save(path)
    doc.close()
    return str(path)


def sheet_texts(pdf: Path) -> list[str]:
    with fitz.open(pdf) as doc:
        return [page.get_text() for page in doc]


def test_name_to_pdf_each_page_twice_in_order(tmp_path):
    src = make_source(tmp_path, 'Arkusz_2.pdf', 3)
    project = Project(Settings(**TWO_UP), [Job(src)])
    CommandStack(project).run(SetPageRepeat.from_filename(project, 0))
    assert project.jobs[0].page_repeat == 2

    out = tmp_path / 'out.pdf'
    assert export_pdf(project, str(out)) == 3          # 3 strony × 2 = 6 odbitek, 2 na arkusz
    texts = sheet_texts(out)
    for number, text in enumerate(texts, start=1):
        assert text.count(f'page-{number}') == 2, (number, text)
        assert sum(text.count(f'page-{k}') for k in (1, 2, 3)) == 2


def test_default_job_exports_exactly_like_before(tmp_path):
    src = make_source(tmp_path, 'Instrukcja.pdf', 3)   # bez cyfr ⇒ 1
    project = Project(Settings(**TWO_UP), [Job(src)])
    CommandStack(project).run(SetPageRepeat.from_filename(project, 0))
    assert project.jobs[0].page_repeat == 1
    out = tmp_path / 'out.pdf'
    assert export_pdf(project, str(out)) == 2          # 3 odbitki, 2 na arkusz
    texts = sheet_texts(out)
    assert 'page-1' in texts[0] and 'page-2' in texts[0] and 'page-3' in texts[1]


def test_single_page_export_follows_repeats(tmp_path):
    src = make_source(tmp_path, 'Dyplom_3.pdf', 2)
    project = Project(Settings(**TWO_UP), [Job(src)])
    CommandStack(project).run(SetPageRepeat.from_filename(project, 0))
    out = tmp_path / 'pages.pdf'
    assert export_pages(project, str(out)) == 6
    labels = ['page-1'] * 3 + ['page-2'] * 3
    assert [t.strip() for t in sheet_texts(out)] == labels


def test_repeat_survives_project_roundtrip_and_still_exports(tmp_path):
    src = make_source(tmp_path, 'karta.pdf', 1)
    project = Project(Settings(**TWO_UP), [Job(src, page_repeat=4)])
    name = tmp_path / 'karta.psimp'
    save_project(project, str(name))
    restored = load_project(str(name))
    assert restored.jobs[0].page_repeat == 4
    assert export_pdf(restored, str(tmp_path / 'karta-out.pdf')) == 2   # 4 odbitki, 2 na arkusz


def test_preflight_does_not_count_repeats_as_extra_pages(tmp_path):
    from preflight import inspect_project
    src = make_source(tmp_path, 'Arkusz_50.pdf', 2)
    project = Project(Settings(**TWO_UP), [Job(src, page_repeat=50)])
    report = inspect_project(project)
    assert report.errors == 0
