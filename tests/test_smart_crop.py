"""Smart original / bleed / final-size and per-PDF crop acceptance tests."""
import json
import zipfile
from pathlib import Path

import pymupdf as fitz
import pytest

from engine import (Job, Project, Settings, bleed_for, crop_centre, crop_offsets,
                    export_pdf, export_pages, gross_dimensions, load_project,
                    pt, save_project)
from preflight import inspect_project


def make_pdf(tmp_path, name='source.pdf', w=110, h=70, tag='SOURCE'):
    path = tmp_path / name
    doc=fitz.open()
    page=doc.new_page(width=pt(w), height=pt(h))
    # Guide written on the vector PDF to measure crop displacement.
    page.insert_text((pt(32),pt(32)),tag,fontsize=14)
    page.draw_rect(fitz.Rect(pt(35),pt(36),pt(50),pt(48)),color=(1,0,0), fill=(1,0,0))
    doc.save(path)
    doc.close()
    return str(path)


def cfg():
    return Settings(trim_w=93,trim_h=53,bleed=1.5,gross_w=96,gross_h=56,
                    auto_gross=True,auto_source=True,scale_mode='Kadruj 1:1',crop_marks=False)


def test_auto_gross_updates_from_net_and_spad():
    s=cfg()
    s.gross_w=110
    s.gross_h=60
    assert gross_dimensions(s)==(96,56)
    assert bleed_for(s)==1.5
    s.bleed=2.5
    assert gross_dimensions(s)==(98,58)


def test_old_projects_retain_manual_gross():
    s=Settings(trim_w=93,trim_h=53,bleed=3,gross_w=96,gross_h=56,scale_mode='Kadruj 1:1')
    assert not s.auto_gross
    assert gross_dimensions(s)==(96,56)
    assert bleed_for(s)==1.5


def test_per_file_original_detection_allows_different_source_sizes(tmp_path):
    first=make_pdf(tmp_path,'small.pdf',110,70,'ALFA')
    second=make_pdf(tmp_path,'big.pdf',130,80,'BETA')
    project=Project(cfg(),[Job(first),Job(second)])
    assert inspect_project(project).errors==0
    output=tmp_path/'merged.pdf'
    assert export_pages(project,str(output))==2
    with fitz.open(output) as d:
        assert len(d)==2
        for pg in d:
            assert pg.rect.width==pytest.approx(pt(96),abs=.05)
            assert pg.trimbox.width==pytest.approx(pt(93),abs=.05)
        assert 'ALFA' in d[0].get_text()
        assert 'BETA' in d[1].get_text()


def test_crop_offset_shifts_original_content_in_vector_output(tmp_path):
    source=make_pdf(tmp_path)
    s=cfg()
    s.margin_x=s.margin_y=5
    original=Project(s,[Job(source,crop_x=0,crop_y=0)])
    moved=Project(s,[Job(source,crop_x=3,crop_y=-2)])
    a,b=tmp_path/'a.pdf',tmp_path/'b.pdf'
    export_pages(original,str(a))
    export_pages(moved,str(b))
    with fitz.open(a) as d1,fitz.open(b) as d2:
        pos1=d1[0].search_for('SOURCE')[0]
        pos2=d2[0].search_for('SOURCE')[0]
        assert pos2.x0-pos1.x0==pytest.approx(-pt(3),abs=.10)
        assert pos2.y0-pos1.y0==pytest.approx(pt(2),abs=.10)
        assert len(d2[0].get_images(full=True))==0


def test_crop_offset_export_sheet_matches_standalone(tmp_path):
    source=make_pdf(tmp_path)
    p=Project(cfg(),[Job(source,crop_x=3,crop_y=-2)])
    output=tmp_path/'montage.pdf'
    assert export_pdf(p,str(output))==1
    with fitz.open(output) as doc:
        assert 'SOURCE' in doc[0].get_text()


@pytest.mark.parametrize('x,y',[(8,0),(-8,0),(0,8),(0,-8)])
def test_out_of_bounds_cropping_fails_preflight_and_export(tmp_path,x,y):
    source=make_pdf(tmp_path)
    project=Project(cfg(),[Job(source,crop_x=x,crop_y=y)])
    report=inspect_project(project)
    assert any(f.code=='POZYCJA_KADRU' and f.level=='BŁĄD' for f in report.findings)
    with pytest.raises(ValueError,match='wychodzi poza oryginał'):
        export_pages(project,str(tmp_path/'result.pdf'))


def test_legal_near_edge_crop(tmp_path):
    source=make_pdf(tmp_path)
    project=Project(cfg(),[Job(source,crop_x=7,crop_y=-7)])
    assert inspect_project(project).errors==0
    assert export_pages(project,str(tmp_path/'ok.pdf'))==1


def test_save_load_preserves_auto_mode_and_per_file_crops(tmp_path):
    source=make_pdf(tmp_path)
    p=Project(cfg(),[Job(source,crop_x=3.1,crop_y=-2.2)])
    filename=tmp_path/'project.psimp'
    save_project(p,str(filename))
    loaded=load_project(str(filename))
    assert loaded.settings.auto_gross is True
    assert loaded.settings.auto_source is True
    assert (loaded.jobs[0].crop_x,loaded.jobs[0].crop_y)==(3.1,-2.2)


def test_duplicate_path_with_incompatible_crop_fails():
    with pytest.raises(ValueError,match='różne kadry'):
        crop_offsets([Job('abc.pdf',crop_x=1),Job('abc.pdf',crop_x=2)])


def test_real_settings_without_auto_source_keep_strict_manual_original(tmp_path):
    path=make_pdf(tmp_path)
    s=cfg()
    s.auto_source=False
    s.source_w=109
    s.source_h=70
    p=Project(s,[Job(path)])
    assert any(f.code=='ORYGINAL' and f.level=='BŁĄD' for f in inspect_project(p).findings)
    with pytest.raises(ValueError,match='różni się'):
        export_pages(p,str(tmp_path/'no.pdf'))
