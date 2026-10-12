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


def make_offset_mediabox_source(folder: Path, name: str, count: int = 1,
                                offset_x: float = 36, offset_y: float = 45):
    """PDF whose raw MediaBox has a non-zero origin (common in DTP exports)."""
    from engine import pt
    document = fitz.open()
    media_w, media_h = pt(94), pt(54)
    b = pt(2)
    for i in range(count):
        page = document.new_page(width=media_w, height=media_h)
        # These are raw PDF coordinates; PyMuPDF normalizes only the y
        # coordinates of TrimBox and BleedBox, not MediaBox.
        document.xref_set_key(page.xref, 'MediaBox',
            f'[{offset_x} {offset_y} {offset_x+media_w} {offset_y+media_h}]')
        document.xref_set_key(page.xref, 'CropBox',
            f'[{offset_x} {offset_y} {offset_x+media_w} {offset_y+media_h}]')
        document.xref_set_key(page.xref, 'TrimBox',
            f'[{offset_x+b} {offset_y+b} {offset_x+media_w-b} {offset_y+media_h-b}]')
        document.xref_set_key(page.xref, 'BleedBox',
            f'[{offset_x} {offset_y} {offset_x+media_w} {offset_y+media_h}]')
        page = document.reload_page(page)
        page.insert_text((pt(15), pt(20)), f'OFFSET-{i+1}', fontsize=12)
    filename = folder / name
    document.save(filename)
    document.close()
    return str(filename)


def test_media_box_normalization_and_22_page_preflight(tmp_path):
    from engine import media_rect
    from preflight import inspect_project
    src = make_offset_mediabox_source(tmp_path, 'offset-22.pdf', count=22)
    with fitz.open(src) as doc:
        assert doc[0].mediabox.y0 == 45
        assert doc[0].trimbox.y0 < doc[0].mediabox.y0
        assert media_rect(doc[0]).contains(doc[0].trimbox)
    s = Settings(bleed=2, crop_marks=False)
    report = inspect_project(Project(s, [Job(src)]))
    assert report.checked_pages == 22
    assert report.errors == 0, report.to_text()
    assert report.warnings == 0, report.to_text()


def test_offset_mediabox_exports_without_dropping_page_or_bleed(tmp_path):
    from preflight import inspect_project
    src = make_offset_mediabox_source(tmp_path, 'offset-negative.pdf',
                                      offset_x=-22, offset_y=-67)
    s = Settings(bleed=2, crop_marks=False)
    report = inspect_project(Project(s,[Job(src)]))
    assert report.errors == 0, report.to_text()
    output = tmp_path / 'offset-out.pdf'
    assert export_pdf(Project(s,[Job(src)]), str(output)) == 1
    with fitz.open(output) as doc:
        assert len(doc) == 1
        assert 'OFFSET-1' in doc[0].get_text(), doc[0].get_text()


def test_truly_invalid_trimbox_outside_media_is_rejected(tmp_path):
    from preflight import inspect_project
    src = make_offset_mediabox_source(tmp_path, 'invalid-offset.pdf')
    with fitz.open(src) as doc:
        page = doc[0]
        # Extend 15pt beyond MediaBox right edge.
        media = page.mediabox
        doc.xref_set_key(page.xref, 'TrimBox',
            f'[{media.x0+5} {media.y0+5} {media.x1+15} {media.y1-5}]')
        doc.saveIncr()
    report = inspect_project(Project(Settings(bleed=0),[Job(src)]))
    assert any(f.code == 'TRIMBOX' for f in report.findings)


def test_a4_to_a6_22_pages_fit_preserves_page_order_and_vectors(tmp_path):
    from engine import export_pages
    from preflight import inspect_project
    source=make_source(tmp_path, 'a4-22.pdf', 22, w=210, h=297)
    s=Settings(trim_w=105, trim_h=148, bleed=0, scale_mode='Dopasuj',
               crop_marks=False)
    project=Project(s,[Job(source)])
    report=inspect_project(project)
    assert report.checked_pages == 22
    assert report.errors == 0, report.to_text()
    target=tmp_path/'a6-22.pdf'
    assert export_pages(project,str(target)) == 22
    with fitz.open(target) as document:
        assert len(document) == 22
        for i,p in enumerate(document):
            assert abs(p.rect.width - 105*72/25.4)<.05
            assert abs(p.rect.height - 148*72/25.4)<.05
            assert f'page-{i+1}' in p.get_text()
            assert not p.get_images(full=True)


def test_scaling_explicitly_opt_in_and_project_roundtrip(tmp_path):
    from preflight import inspect_project
    source=make_source(tmp_path,'large.pdf',1,w=210,h=297)
    s=Settings(trim_w=105,trim_h=148,bleed=0)
    project=Project(s,[Job(source)])
    report=inspect_project(project)
    assert report.errors==1
    assert any(f.code=='FORMAT' for f in report.findings)
    s.scale_mode='Dopasuj'
    file=tmp_path/'project.psimp'
    save_project(project,str(file))
    assert load_project(str(file)).settings.scale_mode=='Dopasuj'
    assert inspect_project(project).errors==0


def test_a4_to_a6_as_imposition_not_only_standalone(tmp_path):
    src=make_source(tmp_path,'book.pdf',4,w=210,h=297)
    s=Settings(sheet_w=320,sheet_h=225,trim_w=105,trim_h=148,bleed=0,
               margin_x=5,margin_y=5,gap_x=4,gap_y=4,scale_mode='Dopasuj',
               crop_marks=False)
    out=tmp_path/'imposition.pdf'
    assert export_pdf(Project(s,[Job(src)]),str(out))==1
    with fitz.open(out) as doc:
        page=doc[0]
        for i in range(1,5):
            assert f'page-{i}' in page.get_text()


def test_fill_mode_crops_to_target_without_stretch_or_spill(tmp_path):
    from engine import pt, export_pages
    from preflight import inspect_project
    # Square source deliberately fills an oblong target by cropping top/bottom.
    src=make_source(tmp_path,'square.pdf',1,w=100,h=100)
    settings=Settings(trim_w=100,trim_h=50,bleed=0,
                      scale_mode='Wypełnij',crop_marks=False)
    report=inspect_project(Project(settings,[Job(src)]))
    assert report.errors==0
    assert any(f.code=='SKALA' and f.level=='UWAGA' for f in report.findings)
    dest=tmp_path/'filled.pdf'
    assert export_pages(Project(settings,[Job(src)]),str(dest))==1
    with fitz.open(dest) as doc:
        assert abs(doc[0].rect.width-pt(100))<.05
        assert abs(doc[0].rect.height-pt(50))<.05
        # Red block at y=5 should be cropped, not displaced into output page.
        px=doc[0].get_pixmap(matrix=fitz.Matrix(2,2))
        at=lambda x,y: px.pixel(int(pt(x)*2),int(pt(y)*2))[:3]
        assert all(v>245 for v in at(10,10))
        assert 'page-1' not in doc[0].get_text()  # text y=30 also outside crop


def test_scaled_bleed_uses_output_mm_not_source_mm(tmp_path):
    from preflight import inspect_project
    src=make_bleeded_source(tmp_path)
    # Source has 2mm bleed. Shrinking 90x50 -> 45x25 yields only 1mm
    # of physical bleed in output, insufficient for required 2mm.
    s=Settings(trim_w=45,trim_h=25,bleed=2,scale_mode='Dopasuj')
    report=inspect_project(Project(s,[Job(src)]))
    assert report.errors==0
    assert any(f.code=='SPAD' for f in report.findings)


def test_scaling_rotated_source_and_shifted_mediabox(tmp_path):
    from engine import export_pages
    from preflight import inspect_project
    src=make_offset_mediabox_source(tmp_path,'shifted-scaled.pdf',count=3,
                                     offset_x=-22,offset_y=-67)
    s=Settings(trim_w=45,trim_h=25,bleed=0,scale_mode='Dopasuj')
    project=Project(s,[Job(src)])
    assert inspect_project(project).errors==0
    output=tmp_path/'shifted-output.pdf'
    assert export_pages(project,str(output))==3
    with fitz.open(output) as doc:
        assert all(f'OFFSET-{i+1}' in doc[i].get_text() for i in range(3))
    rotated=make_bleeded_source(tmp_path,angle=90)
    s=Settings(trim_w=25,trim_h=45,bleed=0,scale_mode='Dopasuj')
    pr=Project(s,[Job(rotated)])
    assert inspect_project(pr).errors==0
    output=tmp_path/'rotated-small.pdf'
    assert export_pages(pr,str(output))==1


def test_mixed_a4_a6_pages_are_reported_as_distinct_ranges(tmp_path):
    """Regression: a client PDF with 12 A4 pages and 10 A6 pages."""
    from preflight import inspect_project
    from engine import pt
    src = tmp_path / 'mixed.pdf'
    d = fitz.open()
    for number in range(22):
        w, h = (210.08, 297.13) if number < 12 else (105.04, 147.90)
        p = d.new_page(width=pt(w), height=pt(h))
        p.insert_text((20, 30), f'card-{number+1}')
    d.save(src)
    d.close()
    report = inspect_project(Project(Settings(trim_w=210, trim_h=297,
                                               scale_mode='Dopasuj', bleed=0), [Job(str(src))]))
    assert report.errors == 0, report.to_text()
    warnings = [f for f in report.findings if f.code == 'MIESZANE_FORMATY']
    assert len(warnings) == 1
    assert '1–12' in warnings[0].message
    assert '13–22' in warnings[0].message
    assert 'A4' in warnings[0].message and 'A6' in warnings[0].message
    assert len(report.format_ranges) == 2
    assert report.warnings == 1


def test_dpi_grouped_per_page_and_preserved_individually_in_json(tmp_path):
    import io
    import json
    from PIL import Image
    from engine import pt
    from preflight import inspect_project
    src = tmp_path / 'two-images.pdf'
    image = Image.new('RGB', (80, 80), (255, 0, 0))
    output = io.BytesIO()
    image.save(output, 'PNG')
    d = fitz.open()
    page = d.new_page(width=pt(105), height=pt(148))
    page.insert_image(fitz.Rect(10, 10, 150, 150), stream=output.getvalue())
    page.insert_image(fitz.Rect(155, 10, 295, 150), stream=output.getvalue())
    d.save(src)
    d.close()
    result = inspect_project(Project(Settings(trim_w=210, trim_h=297,
                                              scale_mode='Dopasuj', bleed=0), [Job(str(src))]))
    dpi_findings = [f for f in result.findings if f.code == 'DPI']
    assert len(dpi_findings) == 1, result.to_text()
    assert '2 obrazy' in dpi_findings[0].message
    assert len(result.image_issues) == 2
    assert result.image_issues[0].dpi < result.image_issues[0].native_dpi
    assert result.image_issues[0].scale_percent > 190
    data = json.loads(result.to_json())
    assert len(data['image_issues']) == 2
    assert data['image_issues'][0]['image_width_px'] == 80
    assert data['warnings'] == 1


def test_dpi_calculated_after_downscaling(tmp_path):
    """Downsizing improves effective DPI without changing the source pixels."""
    import io
    from PIL import Image
    from engine import pt
    from preflight import inspect_project
    src = tmp_path / 'hi_after_scale.pdf'
    img = Image.new('RGB', (160, 160), (0, 255, 0))
    output = io.BytesIO()
    img.save(output, 'PNG')
    d = fitz.open()
    page = d.new_page(width=pt(210), height=pt(297))
    page.insert_image(fitz.Rect(10, 10, 120, 120), stream=output.getvalue())
    d.save(src)
    d.close()
    src_report = inspect_project(Project(Settings(trim_w=210, trim_h=297,
                                                   scale_mode='Bez skalowania', bleed=0), [Job(str(src))]))
    down_report = inspect_project(Project(Settings(trim_w=105, trim_h=148,
                                                    scale_mode='Dopasuj', bleed=0), [Job(str(src))]))
    assert any(f.code == 'DPI' for f in src_report.findings)
    assert all(f.code != 'DPI' for f in down_report.findings)
    assert down_report.errors == 0


# 0.2.4 — operator-controlled recto/verso mapping regression tests.
def _collect_duplex_pairs(project):
    from engine import _duplex_pairs, open_sources
    docs = open_sources(project.jobs)
    try:
        return [(None if f is None else (Path(f.path).name, f.index + 1),
                 None if b is None else (Path(b.path).name, b.index + 1))
                for f, b in _duplex_pairs(project.jobs, docs)]
    finally:
        for d in docs.values():
            d.close()


def test_024_two_files_front_and_repeated_shared_back(tmp_path):
    from engine import ROLE_FRONT, ROLE_SHARED
    a = make_source(tmp_path, 'fronts.pdf', 7)
    b = make_source(tmp_path, 'backs.pdf', 1)
    pr = Project(Settings(mode='Dwustronnie', bleed=0),
                 [Job(a, 1, role=ROLE_FRONT), Job(b, 1, role=ROLE_SHARED)])
    pairs = _collect_duplex_pairs(pr)
    assert len(pairs) == 7
    assert [x[0][1] for x in pairs] == list(range(1,8))
    assert [x[1] for x in pairs] == [('backs.pdf',1)]*7


def test_024_one_page_common_back_rest_auto_fronts(tmp_path):
    from engine import ROLE_SHARED
    f = make_source(tmp_path,'mix.pdf',22)
    pr=Project(Settings(mode='Dwustronnie',bleed=0),
               [Job(f,page_roles={'13':ROLE_SHARED})])
    pairs = _collect_duplex_pairs(pr)
    assert len(pairs)==21
    assert [p[0][1] for p in pairs]==list(range(1,13))+list(range(14,23))
    assert all(pair[1] == ('mix.pdf',13) for pair in pairs)


def test_024_separate_front_back_files_position_order(tmp_path):
    from engine import ROLE_FRONT, ROLE_BACK
    front=make_source(tmp_path,'f.pdf',3)
    back=make_source(tmp_path,'b.pdf',3)
    pr=Project(Settings(mode='Dwustronnie',bleed=0),
               [Job(front,role=ROLE_FRONT),Job(back,role=ROLE_BACK)])
    assert _collect_duplex_pairs(pr)==[(('f.pdf',i),('b.pdf',i)) for i in range(1,4)]


def test_024_auto_duplex_backward_compatible_with_odd_page(tmp_path):
    path=make_source(tmp_path,'automatic.pdf',5)
    pr=Project(Settings(mode='Dwustronnie',bleed=0), [Job(path)])
    assert _collect_duplex_pairs(pr)==[(('automatic.pdf',1),('automatic.pdf',2)),
                                      (('automatic.pdf',3),('automatic.pdf',4)),
                                      (('automatic.pdf',5),None)]


def test_024_mixed_roles_do_not_cross_legacy_job_boundaries(tmp_path):
    from engine import ROLE_FRONT, ROLE_BACK
    normal=make_source(tmp_path,'normal.pdf',3)
    fronts=make_source(tmp_path,'front.pdf',2)
    backs=make_source(tmp_path,'back.pdf',2)
    pr=Project(Settings(mode='Dwustronnie',bleed=0),
               [Job(normal),Job(fronts,role=ROLE_FRONT),Job(backs,role=ROLE_BACK)])
    assert _collect_duplex_pairs(pr)==[(('normal.pdf',1),('normal.pdf',2)),
                                      (('normal.pdf',3),None),
                                      (('front.pdf',1),('back.pdf',1)),
                                      (('front.pdf',2),('back.pdf',2))]


def test_024_roles_persist_in_project_and_load_old_projects(tmp_path):
    from engine import ROLE_SHARED, ROLE_FRONT
    a=make_source(tmp_path,'card.pdf',4)
    pr=Project(Settings(mode='Dwustronnie'), [Job(a,2,role=ROLE_FRONT,page_roles={'4':ROLE_SHARED})])
    name=tmp_path/'roles.psimp'
    save_project(pr,str(name))
    restored=load_project(str(name))
    assert restored.jobs[0].role==ROLE_FRONT
    assert restored.jobs[0].page_roles=={'4':ROLE_SHARED}
    old=tmp_path/'old.psimp'
    import json
    with zipfile.ZipFile(old,'w') as z:
        z.writestr('project.json',json.dumps({'format':'psimp','version':1,
            'settings':vars(Settings()),'jobs':[{'path':'card.pdf','copies':1}]}))
    assert load_project(str(old)).jobs[0].role == 'Normalnie'


def test_024_preflight_rejects_unmatched_backs_and_multiple_shared(tmp_path):
    from engine import ROLE_FRONT, ROLE_BACK, ROLE_SHARED
    from preflight import inspect_project
    f=make_source(tmp_path,'fronts.pdf',3)
    b=make_source(tmp_path,'backs.pdf',1)
    s=Settings(mode='Dwustronnie',bleed=0)
    unmatched=inspect_project(Project(s,[Job(f,role=ROLE_FRONT),Job(b,role=ROLE_BACK)]))
    assert unmatched.errors > 0
    assert any(x.code=='ROLE' for x in unmatched.findings)
    dup=inspect_project(Project(s,[Job(f,page_roles={'1':ROLE_SHARED,'2':ROLE_SHARED})]))
    assert any(x.code=='ROLE' and x.level=='BŁĄD' for x in dup.findings)


def test_024_shared_back_produces_matching_vector_verso_pdf(tmp_path):
    from engine import ROLE_SHARED
    p=make_source(tmp_path,'cards.pdf',4,w=90,h=50)
    s=Settings(mode='Dwustronnie',bleed=0,crop_marks=False)
    project=Project(s,[Job(p,page_roles={'3':ROLE_SHARED})])
    output=tmp_path/'mapped.pdf'
    assert export_pdf(project,str(output)) == 2  # 3 fronts / 21-up -> recto + verso
    with fitz.open(output) as doc:
        front=doc[0].get_text()
        back=doc[1].get_text()
        assert all(f'page-{n}' in front for n in (1,2,4))
        assert 'page-3' not in front
        assert back.count('page-3') == 3
        assert not doc[1].get_images(full=True)


def test_024_skip_single_and_overrides(tmp_path):
    from engine import ROLE_SKIP, ROLE_FRONT
    f=make_source(tmp_path,'skip.pdf',4)
    pr=Project(Settings(bleed=0,crop_marks=False),
               [Job(f,role=ROLE_FRONT,page_roles={'2':ROLE_SKIP})])
    from engine import export_pages
    out=tmp_path/'pages.pdf'
    assert export_pages(pr,str(out))==3
    with fitz.open(out) as d:
        assert len(d)==3
        assert 'page-2' not in ''.join(x.get_text() for x in d)


def test_024_invalid_page_role_index_is_rejected(tmp_path):
    from preflight import inspect_project
    f=make_source(tmp_path,'short.pdf',1)
    r=inspect_project(Project(Settings(bleed=0),[Job(f,page_roles={'2':'Przód'})]))
    assert any(x.code=='ROLE' and x.level=='BŁĄD' for x in r.findings)


def test_024_roles_require_duplex_mode_to_prevent_misprint(tmp_path):
    from engine import ROLE_FRONT
    from preflight import inspect_project
    f = make_source(tmp_path, 'front.pdf', 2)
    p = Project(Settings(mode='Jednostronnie',bleed=0),[Job(f,role=ROLE_FRONT)])
    result=inspect_project(p)
    assert result.errors>=1
    assert any(v.code=='ROLE' for v in result.findings)


def test_024_flip_mirrors_verso_slots_by_selected_edge(tmp_path):
    from engine import ROLE_FRONT, ROLE_SHARED, plan_sides, open_sources
    a=make_source(tmp_path,'a.pdf',5)
    b=make_source(tmp_path,'b.pdf',1)
    for edge in ('Długa krawędź','Krótka krawędź'):
        s=Settings(mode='Dwustronnie',bleed=0,flip=edge)
        jobs=[Job(a,role=ROLE_FRONT),Job(b,role=ROLE_SHARED)]
        docs=open_sources(jobs)
        try:
            sides=list(plan_sides(jobs,docs,s))
            assert len(sides)==2
            front,back=sides
            assert len(front.placements)==len(back.placements)==5
            for f,v in zip(front.placements,back.placements):
                assert v.source.path==b
                assert v.source.index==0
                if edge=='Długa krawędź':
                    assert abs(f.slot.x-v.slot.x)<.01
                    assert abs(s.sheet_h-f.slot.y-f.slot.h-v.slot.y)<.01
                else:
                    assert abs(f.slot.y-v.slot.y)<.01
                    assert abs(s.sheet_w-f.slot.x-f.slot.w-v.slot.x)<.01
        finally:
            for doc in docs.values():doc.close()
