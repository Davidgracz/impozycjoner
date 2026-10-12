"""Integration tests: run with `python -m pytest -q`."""
from pathlib import Path
import tempfile
import zipfile

import pymupdf as fitz
import pytest

from engine import Job, Settings, Project, export_pdf, geometry, load_project, save_project, preview


def make_source(folder: Path, name: str, n: int, w: float = 90, h: float = 50) -> str:
    f=folder/name
    doc=fitz.open()
    for i in range(n):
        page=doc.new_page(width=w*72/25.4,height=h*72/25.4)
        page.insert_text((20,30),f'page-{i+1}')
        page.draw_rect((5,5,15,15), color=(1,0,0),fill=(1,0,0))
    doc.save(f)
    doc.close()
    return str(f)


def test_auto_grid_for_sra3():
    g=geometry(Settings())
    assert (g.cols,g.rows,g.capacity,g.rotation)==(7,3,21,90)


def test_auto_rotation():
    s=Settings(sheet_w=210,sheet_h=297,trim_w=90,trim_h=50,
               margin_x=5,margin_y=5,gap_x=2,gap_y=2,bleed=0,rotation='Auto')
    g=geometry(s)
    assert g.capacity>=8


def test_export_preserves_text_and_dimensions(tmp_path):
    src=make_source(tmp_path,'source.pdf',3)
    project=Project(Settings(crop_marks=False),[Job(src,8)])
    result=tmp_path/'result.pdf'
    n=export_pdf(project,str(result))
    assert n==2  # 24 impressions, 21+3
    with fitz.open(result) as doc:
        assert len(doc)==2
        assert abs(doc[0].rect.width-450*72/25.4)<.1
        assert 'page-1' in doc[0].get_text()
        assert 'page-3' in doc[1].get_text()
        assert doc[0].get_images(full=True) == []  # input contains only vector content


def test_duplex_pairing(tmp_path):
    src=make_source(tmp_path,'duplex.pdf',4)
    s=Settings(sheet_w=100,sheet_h=75,trim_w=90,trim_h=50,bleed=0,
               gap_x=0,gap_y=0,margin_x=4,margin_y=4,mode='Dwustronnie',crop_marks=False)
    # sheet fits one item, so output sheets = 2, PDF pages = 4
    # width 100 fits 90, height 75 fits 50
    out=tmp_path/'duplex-out.pdf'
    assert export_pdf(Project(s,[Job(src,1)]),str(out))==4
    with fitz.open(out) as doc:
        assert 'page-1' in doc[0].get_text()
        assert 'page-2' in doc[1].get_text()
        assert 'page-3' in doc[2].get_text()
        assert 'page-4' in doc[3].get_text()


def test_booklet_order(tmp_path):
    src=make_source(tmp_path,'book.pdf',8)
    s=Settings(sheet_w=200,sheet_h=70,trim_w=90,trim_h=50,bleed=0,
               margin_x=4,margin_y=4,gap_x=4,mode='Broszura',crop_marks=False)
    out=tmp_path/'booklet.pdf'
    assert export_pdf(Project(s,[Job(src,1)]),str(out)) == 4
    with fitz.open(out) as doc:
        assert 'page-8' in doc[0].get_text() and 'page-1' in doc[0].get_text()
        assert 'page-2' in doc[1].get_text() and 'page-7' in doc[1].get_text()
        assert 'page-6' in doc[2].get_text() and 'page-3' in doc[2].get_text()
        assert 'page-4' in doc[3].get_text() and 'page-5' in doc[3].get_text()


def test_project_roundtrip_with_relative_paths(tmp_path):
    source=make_source(tmp_path,'a.pdf',1)
    f=tmp_path/'test.psimp'
    project=Project(Settings(trim_w=70),[Job(source,3)])
    save_project(project,str(f))
    with zipfile.ZipFile(f) as z:
        assert 'project.json' in z.namelist()
        assert '"a.pdf"' in z.read('project.json').decode('utf-8')
    saved=load_project(str(f))
    assert saved.jobs[0].path==source
    assert saved.jobs[0].copies==3
    assert saved.settings.trim_w==70


def test_preview(tmp_path):
    src=make_source(tmp_path,'single.pdf',1)
    img,side=preview(Project(Settings(),[Job(src)]),pixels=700)
    assert img.width<=700 and img.height<=700
    assert side.sheet_number==1


def test_failure_on_impossible_grid():
    with pytest.raises(ValueError):
        geometry(Settings(sheet_w=30,sheet_h=30,trim_w=90,trim_h=50))


def make_bleeded_source(folder: Path, angle: int = 0, missing_bleed=False):
    """W/H net 90x50, physical media optionally includes 2mm bleed."""
    b=2
    file=folder/f'bleed-{angle}-{missing_bleed}.pdf'
    document=fitz.open()
    page=document.new_page(width=(90+2*b)*72/25.4, height=(50+2*b)*72/25.4)
    page.draw_rect(page.rect,color=(1,0,0),fill=(1,0,0))
    trim=fitz.Rect(b*72/25.4,b*72/25.4,(90+b)*72/25.4,(50+b)*72/25.4)
    page.draw_rect(trim,color=(0,0,1),fill=(0,0,1))
    page.set_trimbox(trim)
    if missing_bleed:
        page.set_mediabox(trim)
    page.set_rotation(angle)
    document.save(file)
    document.close()
    return str(file)


def test_rotated_bleed_90_keeps_bleed_vector(tmp_path):
    # Choose one slot to read exact locations in pixel space.
    src=make_bleeded_source(tmp_path)
    s=Settings(sheet_w=80,sheet_h=120,trim_w=90,trim_h=50,bleed=2,
               margin_x=5,margin_y=5,gap_x=0,gap_y=0,rotation='90',crop_marks=False)
    out=tmp_path/'rotated.pdf'
    assert export_pdf(Project(s,[Job(src)]),str(out)) == 1
    with fitz.open(out) as doc:
        page=doc[0]
        pix=page.get_pixmap(matrix=fitz.Matrix(2,2))
        # Blue is inside TrimBox, while red survives in the 2-mm bleed.
        from engine import geometry, pt
        slot=geometry(s).slots[0]
        def color_at(x,y):
            xx=int(pt(x)*2); yy=int(pt(y)*2)
            idx=(yy*pix.width+xx)*pix.n
            return pix.samples[idx:idx+3]
        assert color_at(slot.x+5,slot.y+5)[2] > 200
        assert color_at(slot.x-1,slot.y+5)[0] > 200
        assert not page.get_images(full=True)


def test_mismatched_format_is_rejected(tmp_path):
    src=make_source(tmp_path,'wrong.pdf',1,w=80,h=50)
    with pytest.raises(ValueError,match='TrimBox'):
        export_pdf(Project(Settings(),[Job(src)]), str(tmp_path/'out.pdf'))


def test_source_rotation_can_match_net_dimensions(tmp_path):
    src=make_bleeded_source(tmp_path,angle=90)
    s=Settings(sheet_w=100,sheet_h=125,trim_w=50,trim_h=90,bleed=2,
               rotation='0',margin_x=5,margin_y=5,crop_marks=False)
    out=tmp_path/'rot-src.pdf'
    assert export_pdf(Project(s,[Job(src)]),str(out)) == 1
    with fitz.open(out) as doc:
        assert len(doc)==1


def test_preflight_warning_missing_bleed_and_error_wrong_size(tmp_path):
    from preflight import inspect_project
    src=make_source(tmp_path,'bad.pdf',1,w=88,h=50)
    report=inspect_project(Project(Settings(),[Job(src,5)]))
    assert report.checked_pages==1
    assert report.errors>=1
    assert any(f.code=='FORMAT' for f in report.findings)
    assert any(f.code=='SPAD' for f in report.findings)
    assert 'BŁĄD' in report.to_text()
    assert 'findings' in report.to_json()


def test_preflight_checks_only_unique_source_pages(tmp_path):
    from preflight import inspect_project
    source=make_source(tmp_path,'valid.pdf',3)
    r=inspect_project(Project(Settings(bleed=0),[Job(source,100)]))
    assert r.checked_pages==3
    assert r.total_pages==3
    assert r.errors==0


def test_geometry_rotation_180_and_270():
    from engine import geometry
    s=Settings(rotation='180')
    assert geometry(s).rotation==180
    s.rotation='270'
    assert geometry(s).rotation==270
