"""v0.3.6: duplex calibration must affect back preview, export, print marks and projects."""
from pathlib import Path

import pymupdf as fitz
import pytest

from engine import (Job, Project, Settings, SourcePage, open_sources, project_sides,
                    editor_preview, export_pdf, load_project, preview, save_project, pt,
                    validate)
from preflight import inspect_project
from duplex_calibration import list_profiles, read_profile, store_profile, remove_profile


def source_pdf(path):
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page(width=pt(93), height=pt(53))
        page.insert_text((pt(5), pt(12)), f'NUM{i+1}', fontsize=14)
        page.draw_rect(fitz.Rect(pt(20),pt(24),pt(42),pt(35)), color=(1,0,0), width=.5)
    doc.save(path)
    doc.close()
    return str(path)


def settings(**updates):
    data = dict(sheet_w=230,sheet_h=160,trim_w=93,trim_h=53,bleed=1.5,
                margin_x=12,margin_y=12,gap_x=5,gap_y=5,
                mode='Dwustronnie',rotation='0',crop_marks=True,scale_mode='Bez skalowania')
    data.update(updates)
    return Settings(**data)


def all_sides(project):
    docs=open_sources(project.jobs)
    try:
        return list(project_sides(project, docs))
    finally:
        for d in docs.values():d.close()


def test_global_verso_shift_is_applied_only_once_after_side_flip(tmp_path):
    source=source_pdf(tmp_path/'a.pdf')
    base=Project(settings(),[Job(source)])
    corrected=Project(settings(verso_shift_x=.7,verso_shift_y=-.4),[Job(source)])
    before=all_sides(base); after=all_sides(corrected)
    assert len(before)==len(after)==2
    assert before[0]==after[0]
    for old,new in zip(before[1].placements,after[1].placements):
        assert new.slot.x==pytest.approx(old.slot.x+.7)
        assert new.slot.y==pytest.approx(old.slot.y-.4)
        assert (new.slot.w,new.slot.h,new.slot.rotation)==(old.slot.w,old.slot.h,old.slot.rotation)
        assert new.source==old.source


def test_no_shift_on_single_sided_or_booklet(tmp_path):
    source=source_pdf(tmp_path/'b.pdf')
    settings_single=settings(mode='Jednostronnie',verso_shift_x=1.2,verso_shift_y=-.5)
    base=Project(settings_single,[Job(source)])
    corrected=all_sides(base)
    settings_single.verso_shift_x=0
    settings_single.verso_shift_y=0
    assert corrected==all_sides(base)


def test_save_load_legacy_compatibility_and_json_profiles(tmp_path):
    source=source_pdf(tmp_path/'c.pdf')
    project=Project(settings(verso_shift_x=1.3,verso_shift_y=-.2),[Job(source)])
    dst=tmp_path/'calibrated.psimp'
    save_project(project,str(dst))
    loaded=load_project(str(dst))
    assert loaded.settings.verso_shift_x==1.3
    assert loaded.settings.verso_shift_y==-.2
    assert all_sides(project)==all_sides(loaded)
    # Old settings without these fields must still load, with zero calibration.
    import zipfile,json
    with zipfile.ZipFile(dst) as z: data=json.loads(z.read('project.json'))
    del data['settings']['verso_shift_x'];del data['settings']['verso_shift_y']
    legacy=tmp_path/'old.psimp'
    with zipfile.ZipFile(legacy,'w') as z:z.writestr('project.json',json.dumps(data))
    read=load_project(str(legacy))
    assert (read.settings.verso_shift_x,read.settings.verso_shift_y)==(0,0)

    profiles=tmp_path/'calibration_profiles.json'
    store_profile('Drukarnia SRA3',x=.7,y=-.4,flip='Długa krawędź',path=profiles)
    store_profile('Biuro laser',x=-.2,y=.1,flip='Krótka krawędź',path=profiles)
    assert list_profiles(path=profiles)==['Biuro laser','Drukarnia SRA3']
    assert read_profile('Drukarnia SRA3',path=profiles)=={'x':.7,'y':-.4,'flip':'Długa krawędź'}
    remove_profile('Biuro laser',path=profiles)
    assert list_profiles(path=profiles)==['Drukarnia SRA3']
    with pytest.raises(ValueError,match='0,1'):
        store_profile('Niepoprawny',x=.15,y=0,flip='Krótka krawędź',path=profiles)
    with pytest.raises(ValueError):
        store_profile('',x=.1,y=0,flip='Krótka krawędź',path=profiles)


def test_export_moves_verso_artwork_and_marks_and_leaves_recto_untouched(tmp_path):
    source=source_pdf(tmp_path/'d.pdf')
    base=Project(settings(),[Job(source)])
    corrected=Project(settings(verso_shift_x=1.2,verso_shift_y=.7),[Job(source)])
    a=tmp_path/'base.pdf';b=tmp_path/'calibrated.pdf'
    export_pdf(base,str(a)); export_pdf(corrected,str(b))
    with fitz.open(a) as original,fitz.open(b) as shifted:
        assert len(original)==len(shifted)==2
        assert original[0].get_pixmap().samples==shifted[0].get_pixmap().samples
        for page_no in (0,1):
            assert shifted[page_no].get_images(full=True)==[]  # vector source, no raster output
        # Compare bounding boxes of text positions on both verso pages.
        old=original[1].search_for('NUM2')[0]
        new=shifted[1].search_for('NUM2')[0]
        assert (new.x0-old.x0)/pt(1)==pytest.approx(1.2,abs=.03)
        assert (new.y0-old.y0)/pt(1)==pytest.approx(.7,abs=.03)
        assert original[1].get_pixmap().samples!=shifted[1].get_pixmap().samples
        assert original[0].get_drawings() == shifted[0].get_drawings()


def test_preflight_blocks_out_of_sheet_calibration_and_export(tmp_path):
    source=source_pdf(tmp_path/'e.pdf')
    s=settings(sheet_w=96,sheet_h=56,margin_x=0,margin_y=0,gap_x=0,gap_y=0,
               verso_shift_x=-.1,crop_marks=False)
    project=Project(s,[Job(source)])
    report=inspect_project(project)
    assert any(f.code=='RECZNY_MONTAZ' and f.level=='BŁĄD' for f in report.findings)
    with pytest.raises(ValueError,match='poza arkusz'):
        export_pdf(project,str(tmp_path/'invalid.pdf'))
    assert not (tmp_path/'invalid.pdf').exists()


@pytest.mark.parametrize('bad', [.15,float('inf'),float('nan'),21])
def test_reject_invalid_calibration(bad):
    with pytest.raises(ValueError):
        validate(settings(verso_shift_x=bad))


def test_editor_preview_includes_calibration(tmp_path):
    source=source_pdf(tmp_path/'g.pdf')
    project=Project(settings(verso_shift_x=.5,verso_shift_y=.3),[Job(source)])
    _,side=editor_preview(project,index=1)
    assert side is not None
    assert side.side==1
    assert side.placements[0].slot.x==pytest.approx(all_sides(project)[1].placements[0].slot.x)
    # Explicitly check underlying image rendered too.
    _,p=preview(project,index=1)
    assert p.placements[0].slot.x==pytest.approx(side.placements[0].slot.x)
