from pathlib import Path
import fitz
from engine import (Job, Project, Settings, SourcePage, open_sources, project_sides,
                    assign_slot, swap_slots, save_project, load_project, export_pdf, preview)

def make_file(path):
    d=fitz.open()
    for n in range(1,5):
        p=d.new_page(width=255.118,height=141.732)
        p.insert_text((35,55),f'LABEL{n}',fontsize=18)
    d.save(path);d.close()

def test_manual_roundtrip_and_export(tmp_path):
    inp=tmp_path/'source.pdf';make_file(inp)
    s=Settings(sheet_w=205,sheet_h=64,trim_w=90,trim_h=50,bleed=0,margin_x=4,margin_y=4,gap_x=3,gap_y=0,mode='Dwustronnie',crop_marks=False)
    p=Project(s,[Job(str(inp))])
    docs=open_sources(p.jobs)
    try:
        sides=list(project_sides(p,docs))
        front=sides[0];back=sides[1]
        assert len(front.placements)==2
        swap_slots(p,front,0,1)
        assign_slot(p,back,0,None)
        assign_slot(p,back,1,SourcePage(str(inp),3))
    finally:
        for d in docs.values():d.close()
    proj=tmp_path/'saved.psimp';save_project(p,str(proj))
    restored=load_project(str(proj))
    assert restored.overrides==p.overrides
    pdf=tmp_path/'out.pdf';export_pdf(restored,str(pdf))
    with fitz.open(pdf) as d:
        fronttext=d[0].get_text();backtext=d[1].get_text()
        assert fronttext.index('LABEL3') < fronttext.index('LABEL1') or ('LABEL3' in fronttext and 'LABEL1' in fronttext)
        assert 'LABEL4' in backtext
        assert 'LABEL2' not in backtext
    im, side=preview(restored,index=1)
    assert side.side==1 and im.width>10

def test_bad_manual_source_rejected(tmp_path):
    inp=tmp_path/'source.pdf';make_file(inp)
    p=Project(Settings(),[Job(str(inp))]);p.overrides['1:0:0']={'path':str(inp),'page':99}
    try:
        preview(p,index=0)
    except ValueError as e:
        assert 'nie istnieje' in str(e)
    else:raise AssertionError('invalid manual ref accepted')
