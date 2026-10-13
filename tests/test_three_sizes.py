"""Three-stage original -> gross with bleed -> net workflow from print shop."""
import json
import zipfile

import pymupdf as fitz
import pytest

from engine import (Job, Project, Settings, bleed_for, export_pages, export_pdf,
                    geometry, gross_dimensions, load_project, pt, preview,
                    save_project, validate)
from preflight import inspect_project


def input_pdf(tmp_path, w=110, h=70):
    path = tmp_path / 'source.pdf'
    doc = fitz.open()
    p = doc.new_page(width=pt(w), height=pt(h))
    p.draw_rect(fitz.Rect(0, 0, pt(w), pt(h)), color=(1, 0, 0), width=1)
    # Center labels test: outside left margin is to be removed.
    p.insert_text((pt(2), pt(20)), 'REMOVED-LEFT', fontsize=7)
    p.insert_text((pt(25), pt(30)), 'IN-CROP-AREA', fontsize=9)
    doc.save(path)
    doc.close()
    return str(path)


def config():
    return Settings(sheet_w=450, sheet_h=320, source_w=110, source_h=70,
                    gross_w=96, gross_h=56, trim_w=93, trim_h=53,
                    bleed=2, scale_mode='Kadruj 1:1', crop_marks=False)


def test_three_sizes_derive_standard_1_5mm_bleed():
    s = config()
    validate(s)
    assert bleed_for(s) == pytest.approx(1.5)
    assert gross_dimensions(s) == (96, 56)
    g = geometry(s)
    for slot in g.slots:
        assert (slot.w, slot.h) in ((93, 53), (53, 93))


def test_export_pdf_exact_gross_trim_and_vector(tmp_path):
    p = Project(config(), [Job(input_pdf(tmp_path))])
    output = tmp_path / 'trimmed.pdf'
    assert export_pages(p, str(output)) == 1
    with fitz.open(output) as doc:
        page = doc[0]
        assert page.rect.width == pytest.approx(pt(96), abs=.04)
        assert page.rect.height == pytest.approx(pt(56), abs=.04)
        assert page.trimbox.width == pytest.approx(pt(93), abs=.04)
        assert page.trimbox.height == pytest.approx(pt(53), abs=.04)
        assert page.trimbox.x0 == pytest.approx(pt(1.5), abs=.04)
        assert page.trimbox.y0 == pytest.approx(pt(1.5), abs=.04)
        assert 'IN-CROP-AREA' in page.get_text()
        assert 'REMOVED-LEFT' not in page.get_text()
        assert len(page.get_images(full=True)) == 0


def test_montage_and_preview_share_same_three_sizes(tmp_path):
    p = Project(config(), [Job(input_pdf(tmp_path))])
    final = tmp_path / 'montage.pdf'
    assert export_pdf(p, str(final)) > 0
    pix, _ = preview(p, pixels=400)
    assert pix.width and pix.height
    with fitz.open(final) as doc:
        assert 'IN-CROP-AREA' in doc[0].get_text()
        assert 'REMOVED-LEFT' not in doc[0].get_text()


def test_project_roundtrip_preserves_three_sizes(tmp_path):
    project = Project(config(), [Job(input_pdf(tmp_path))])
    stored = tmp_path / 'example.psimp'
    save_project(project, str(stored))
    with zipfile.ZipFile(stored) as z:
        data=json.loads(z.read('project.json'))
        assert data['settings']['source_w'] == 110
        assert data['settings']['gross_w'] == 96
    loaded = load_project(str(stored))
    assert loaded.settings.source_h == 70
    assert loaded.settings.gross_h == 56
    assert loaded.settings.trim_h == 53
    assert bleed_for(loaded.settings) == pytest.approx(1.5)


def test_preflight_reads_original_gross_and_net(tmp_path):
    report=inspect_project(Project(config(),[Job(input_pdf(tmp_path))]))
    assert report.errors == 0, report.to_text()
    assert any(f.code=='KADROWANIE' for f in report.findings)
    assert '96 × 56' in report.to_text()
    assert '93 × 53' in report.to_text()


def test_explicit_original_mismatch_blocks_export_and_preflight(tmp_path):
    src=input_pdf(tmp_path)
    s=config()
    s.source_w=112
    p=Project(s,[Job(src)])
    report=inspect_project(p)
    assert any(f.code=='ORYGINAL' and f.level=='BŁĄD' for f in report.findings)
    with pytest.raises(ValueError, match='różni się'):
        export_pages(p,str(tmp_path/'bad.pdf'))


def test_gross_larger_than_original_blocks_export_and_preflight(tmp_path):
    src=input_pdf(tmp_path)
    s=config()
    s.gross_w=116
    s.gross_h=76
    p=Project(s,[Job(src)])
    report=inspect_project(p)
    assert any(f.code=='BRUTTO' and f.level=='BŁĄD' for f in report.findings)
    with pytest.raises(ValueError, match='za mały'):
        export_pages(p,str(tmp_path/'bad.pdf'))


def test_uneven_bleed_is_rejected():
    s=config()
    s.gross_h=57
    with pytest.raises(ValueError, match='jednakowy'):
        validate(s)


def test_backwards_compatible_crop_033_without_gross_fields(tmp_path):
    src=input_pdf(tmp_path)
    s=Settings(trim_w=93,trim_h=53,bleed=2,scale_mode='Kadruj 1:1')
    assert gross_dimensions(s) == (97,57)
    p=Project(s,[Job(src)])
    assert export_pages(p,str(tmp_path/'legacy.pdf')) == 1
