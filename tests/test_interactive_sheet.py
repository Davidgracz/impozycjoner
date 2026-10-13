"""Regression tests for v0.3.5 interactive manual sheet geometry.

No vector artwork is rasterized in production PDFs, and the same project_sides
placements must drive visual preview, exported PDF, and serialized projects.
"""
from pathlib import Path
import json
import zipfile

import pymupdf as fitz
import pytest

from engine import (Job, Project, Settings, SourcePage, open_sources, project_sides,
                    assign_slot, swap_slots, set_slot_transform, reset_slot,
                    save_project, load_project, export_pdf, preview, pt)


def source_pdf(path, pages=4):
    doc=fitz.open()
    for i in range(pages):
        p=doc.new_page(width=pt(93),height=pt(53))
        p.insert_text((15,25),f'DOC{str(i+1)}',fontsize=13)
        p.draw_circle((pt(10),pt(10)),pt(2),color=(1,0,0),fill=(1,0,0))
    doc.save(path)
    doc.close()
    return str(path)


def job_settings(mode='Jednostronnie'):
    return Settings(sheet_w=250,sheet_h=210,trim_w=93,trim_h=53,
                    gross_w=96,gross_h=56,bleed=1.5,
                    margin_x=8,margin_y=8,gap_x=5,gap_y=5,
                    rotation='0',rows=2,mode=mode,crop_marks=False,
                    scale_mode='Bez skalowania')


def side_at(project,idx):
    docs=open_sources(project.jobs)
    try:
        return list(project_sides(project,docs))[idx]
    finally:
        for d in docs.values(): d.close()


def test_exact_tenths_rotate_and_proportions(tmp_path):
    source=source_pdf(tmp_path/'source.pdf')
    project=Project(job_settings(),[Job(source)])
    before=side_at(project,0)
    set_slot_transform(project,before,0,dx=2.3,dy=-1.7,rotate=90)
    after=side_at(project,0)
    a=before.placements[0].slot;b=after.placements[0].slot
    assert b.w==a.h and b.h==a.w
    assert b.rotation==90
    assert b.x==pytest.approx(a.x+(a.w-b.w)/2+2.3)
    assert b.y==pytest.approx(a.y+(a.h-b.h)/2-1.7)
    assert after.placements[0].source==before.placements[0].source
    assert after.placements[1].slot==before.placements[1].slot
    assert project.overrides['1:0:0']['rotate']==90
    assert project.overrides['1:0:0']['dx']==2.3


def test_invalid_out_of_bounds_transform_does_not_override(tmp_path):
    project=Project(job_settings(),[Job(source_pdf(tmp_path/'x.pdf'))])
    side=side_at(project,0)
    with pytest.raises(ValueError,match='poza arkusz'):
        set_slot_transform(project,side,0,dx=-200)
    assert project.overrides.get('1:0:0',{})=={}
    with pytest.raises(ValueError,match='0,1'):
        set_slot_transform(project,side,0,dx=.15)
    with pytest.raises(ValueError,match='90'):
        set_slot_transform(project,side,0,rotate=45)


def test_assign_keep_transform_and_swap_keep_cell_offsets(tmp_path):
    source=source_pdf(tmp_path/'source.pdf')
    project=Project(job_settings(),[Job(source)])
    side=side_at(project,0)
    set_slot_transform(project,side,0,dx=1.2,dy=.5,rotate=180)
    assign_slot(project,side,0,SourcePage(source,3))
    side=side_at(project,0)
    assert side.placements[0].slot.rotation==180
    assert side.placements[0].source.index==3
    swap_slots(project,side,0,1)
    final=side_at(project,0)
    assert final.placements[0].source.index==1
    assert final.placements[1].source.index==3
    assert final.placements[0].slot.rotation==180
    reset_slot(project,final,0)
    restored=side_at(project,0)
    assert restored.placements[0].slot==side.placements[1].slot.__class__(
        side.placements[0].slot.x-1.2,side.placements[0].slot.y-.5,
        side.placements[0].slot.w,side.placements[0].slot.h,0,0,0)
    assert restored.placements[0].source.index==0


def test_recto_verso_are_independent_and_serialized(tmp_path):
    source=source_pdf(tmp_path/'source.pdf')
    project=Project(job_settings('Dwustronnie'),[Job(source)])
    front=side_at(project,0);back=side_at(project,1)
    set_slot_transform(project,front,0,dx=1.1,rotate=90)
    set_slot_transform(project,back,0,dy=-1.2,rotate=270)
    assign_slot(project,back,0,SourcePage(source,3))
    path=tmp_path/'layout.psimp';save_project(project,str(path))
    reloaded=load_project(str(path))
    assert reloaded.overrides==project.overrides
    recto=side_at(reloaded,0);verso=side_at(reloaded,1)
    assert recto.placements[0].slot.rotation==90
    assert verso.placements[0].slot.rotation==270
    assert recto.placements[0].source.index==0
    assert verso.placements[0].source.index==3
    assert recto.placements[0].slot.x==pytest.approx(front.placements[0].slot.x+(93-53)/2+1.1)
    assert verso.placements[0].slot.y!=back.placements[0].slot.y


def test_export_matches_preview_and_stays_vector(tmp_path):
    source=source_pdf(tmp_path/'source.pdf')
    project=Project(job_settings(),[Job(source)])
    side=side_at(project,0)
    set_slot_transform(project,side,0,dx=.6,dy=2.4,rotate=180)
    set_slot_transform(project,side,1,dy=-.7)
    assign_slot(project,side,1,SourcePage(source,3))
    image,shown=preview(project,index=0,pixels=1000)
    assert shown.placements[0].slot.rotation==180
    assert shown.placements[1].source.index==3
    exported=tmp_path/'output.pdf'
    assert export_pdf(project,str(exported))==1
    with fitz.open(exported) as doc:
        assert doc[0].get_images(full=True)==[]
        assert 'DOC4' in doc[0].get_text()
        assert doc[0].rect.width==pytest.approx(pt(project.settings.sheet_w))
        pix=doc[0].get_pixmap(matrix=fitz.Matrix(image.width/doc[0].rect.width,
                                               image.height/doc[0].rect.height))
        from PIL import Image,ImageChops
        rendered=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        assert ImageChops.difference(rendered,image).getbbox() is None


def test_existing_psimp_entries_remain_compatible(tmp_path):
    source=source_pdf(tmp_path/'source.pdf')
    project=Project(job_settings(),[Job(source)])
    side=side_at(project,0)
    assign_slot(project,side,0,SourcePage(source,3))
    path=tmp_path/'old.psimp';save_project(project,str(path))
    loaded=load_project(str(path))
    restored=side_at(loaded,0)
    assert restored.placements[0].source.index==3
    assert restored.placements[0].slot==side.placements[0].slot


def test_taxi_unmodified_package():
    from taxi_generator import VERSION
    assert VERSION=='0.2.8'


def test_drop_into_physically_empty_cell_exports_it(tmp_path):
    from engine import editor_preview
    src=source_pdf(tmp_path/'one.pdf',pages=1)
    p=Project(job_settings(),[Job(src)])
    origin=side_at(p,0)
    assert len(origin.placements)==1
    image,interactive=editor_preview(p,index=0)
    assert len(interactive.placements)==4
    assert interactive.placements[3].source is None
    assign_slot(p,interactive,3,SourcePage(src,0))
    after=side_at(p,0)
    assert len(after.placements)==4
    assert after.placements[1].source is None
    assert after.placements[3].source.index==0
    out=tmp_path/'out.pdf';export_pdf(p,str(out))
    with fitz.open(out) as doc:
        assert len(doc)==1
        assert doc[0].get_text().count('DOC1')==2
    reset_slot(p,after,3)
    assert len(side_at(p,0).placements)==1


def test_new_rotated_blank_cell_and_duplex_back(tmp_path):
    from engine import editor_preview
    src=source_pdf(tmp_path/'one.pdf',pages=2)
    p=Project(job_settings('Dwustronnie'),[Job(src)])
    _,back=editor_preview(p,index=1)
    assert back.side==1
    assert len(back.placements)==4
    assign_slot(p,back,2,SourcePage(src,1))
    set_slot_transform(p,back,2,dx=1.0,rotate=90)
    _,reloaded=editor_preview(p,index=1)
    assert reloaded.placements[2].slot.rotation==90
    assert reloaded.placements[2].source.index==1
    assert side_at(p,0).placements[0].slot.rotation==0
    out=tmp_path/'out.pdf';export_pdf(p,str(out))
    with fitz.open(out) as d:
        assert 'DOC2' in d[1].get_text()


def test_crop_110_70_to_93_53_with_individual_rotation(tmp_path):
    src=tmp_path/'gross.pdf'
    d=fitz.open()
    page=d.new_page(width=pt(110),height=pt(70))
    page.insert_text((pt(20),pt(25)),'VECTOR-CROP',fontsize=12)
    d.save(src);d.close()
    s=job_settings()
    s.scale_mode='Kadruj 1:1'
    s.source_w,s.source_h=110,70
    p=Project(s,[Job(str(src))])
    side=side_at(p,0)
    set_slot_transform(p,side,0,dx=1.0,dy=1.0,rotate=90)
    out=tmp_path/'out.pdf'
    export_pdf(p,str(out))
    with fitz.open(out) as doc:
        assert len(doc)==1
        assert doc[0].get_images(full=True)==[]
        assert 'VECTOR-CROP' in doc[0].get_text()


def test_overlapping_uses_warns_but_preserves_operator_choice(tmp_path):
    from engine import overlapping_uses
    from preflight import inspect_project
    src=source_pdf(tmp_path/'source.pdf')
    project=Project(job_settings(),[Job(src)])
    side=side_at(project,0)
    assert overlapping_uses(side,project.settings)==[]
    set_slot_transform(project,side,0,dx=15.0)
    shifted=side_at(project,0)
    assert (0,1) in overlapping_uses(shifted,project.settings)
    report=inspect_project(project)
    assert any(f.code=='NAKLADANIE_UZYTKOW' for f in report.findings)
