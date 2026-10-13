"""Gang-run: exact copies, capacity, vector PDF, reporting and regression."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import random

import pymupdf as fitz
import pytest

from economic_csv import write_economic_csv
from engine import (Job, Project, Settings, SourcePage, economic_demands, economic_report,
                    export_pdf, geometry, open_sources, plan_sides, project_sides,
                    assign_slot, save_project, load_project, ROLE_SHARED)
from preflight import inspect_project


def source(path: Path, labels: tuple[str, ...] = ('A',), w: float = 93, h: float = 53) -> str:
    doc = fitz.open()
    for label in labels:
        page = doc.new_page(width=w * 72 / 25.4, height=h * 72 / 25.4)
        page.insert_text((25, 40), f'PRINT-{label}', fontsize=15)
        page.draw_rect((20, 55, 70, 90), color=(0, 0, 0))
    doc.save(str(path))
    doc.close()
    return str(path)


def settings() -> Settings:
    return Settings(sheet_w=450,sheet_h=320,trim_w=93,trim_h=53,bleed=0,
        margin_x=7,margin_y=7,gap_x=4,gap_y=4,scale_mode='Bez skalowania',
        mode='Ekonomiczny',crop_marks=False)


def inspect(project: Project):
    docs = open_sources(project.jobs)
    try:
        return economic_report(project, docs)
    finally:
        for doc in docs.values(): doc.close()


def test_packs_mixed_quantities_exactly_and_minimum_paper(tmp_path):
    a = source(tmp_path/'a.pdf', ('A',))
    b = source(tmp_path/'b.pdf', ('B',))
    s = settings()
    project = Project(s, [Job(a,700),Job(b,300)])
    report = inspect(project)
    assert report.capacity > 1
    assert report.physical_sheets == (1000+report.capacity-1)//report.capacity
    assert report.filled_slots == 1000
    assert report.empty_slots == report.physical_sheets*report.capacity-1000
    assert report.overproduction == report.shortage == 0
    assert tuple((x.requested,x.planned) for x in report.lines)==((700,700),(300,300))
    assert any(len(set(p.signature)-{None}) > 1 for p in report.patterns)
    assert sum(p.sheet_count for p in report.patterns)==report.physical_sheets


def test_multi_page_pdf_copies_each_artwork(tmp_path):
    a = source(tmp_path/'three.pdf', ('A','B','C'))
    project = Project(settings(), [Job(a,9,page_roles={'2':'Pomiń'})])
    report=inspect(project)
    assert len(report.lines)==2
    assert [line.source.index for line in report.lines]==[0,2]
    assert [line.planned for line in report.lines]==[9,9]


def test_referenced_same_page_jobs_are_combined(tmp_path):
    a = source(tmp_path/'same.pdf')
    project=Project(settings(),[Job(a,3),Job(a,5)])
    result=inspect(project)
    assert len(result.lines)==1 and result.lines[0].requested==8


def test_duplex_roles_rejected_in_gang_run(tmp_path):
    a=source(tmp_path/'front.pdf')
    project=Project(settings(),[Job(a,5,role=ROLE_SHARED)])
    with pytest.raises(ValueError,match='jednostronny'):
        inspect(project)
    report=inspect_project(project)
    assert report.errors>0


def test_manual_change_counts_are_guarded_by_preflight_and_export(tmp_path):
    a=source(tmp_path/'a.pdf')
    b=source(tmp_path/'b.pdf',('B',))
    project=Project(settings(),[Job(a,4),Job(b,2)])
    docs=open_sources(project.jobs)
    try:
        side=next(project_sides(project, docs))
        slot_idx=next(i for i,p in enumerate(side.placements) if p.source==SourcePage(a,0))
        assign_slot(project,side,slot_idx,SourcePage(b,0))
    finally:
        for d in docs.values(): d.close()
    report=inspect(project)
    assert report.shortage==1 and report.overproduction==1
    findings=inspect_project(project)
    assert any(f.code=='EKON_NAKLAD' and f.level=='BŁĄD' for f in findings.findings)
    target=tmp_path/'not_exported.pdf'
    with pytest.raises(ValueError,match='naruszają nakłady'):
        export_pdf(project,str(target))
    assert not target.exists()


def test_vector_pdf_and_csv_production_report(tmp_path):
    a=source(tmp_path/'a.pdf')
    b=source(tmp_path/'b.pdf',('B',))
    project=Project(settings(),[Job(a,17),Job(b,11)])
    report=inspect(project)
    output=tmp_path/'gang.pdf'
    sheets=export_pdf(project,str(output))
    assert sheets==report.physical_sheets
    with fitz.open(output) as doc:
        assert len(doc)==sheets
        all_text=' '.join(page.get_text() for page in doc)
        assert all_text.count('PRINT-A')==17
        assert all_text.count('PRINT-B')==11
        assert all(not page.get_images(full=True) for page in doc)
    csv_path=tmp_path/'plan.csv'
    write_economic_csv(report,csv_path)
    contents=csv_path.read_text(encoding='utf-8-sig')
    assert 'Arkusze fizyczne' in contents and 'Nadprodukcja;0' in contents
    assert 'a.pdf' in contents and 'b.pdf' in contents


def test_gang_settings_roundtrip_and_legacy_unchanged(tmp_path):
    a=source(tmp_path/'a.pdf')
    p=Project(settings(),[Job(a,2)])
    path=tmp_path/'new.psimp'
    save_project(p,str(path))
    loaded=load_project(str(path))
    assert loaded.settings.mode=='Ekonomiczny'
    assert inspect(loaded).filled_slots==2
    assert Settings().mode=='Jednostronnie'


@pytest.mark.parametrize('seed',range(25))
def test_randomized_exact_quantities(seed,tmp_path):
    rng=random.Random(seed)
    paths=[source(tmp_path/f'{i}.pdf',(str(i),)) for i in range(1+rng.randrange(7))]
    quantities=[1+rng.randrange(130) for _ in paths]
    p=Project(settings(),[Job(path,qty) for path,qty in zip(paths,quantities)])
    result=inspect(p)
    assert result.overproduction==result.shortage==0
    assert result.filled_slots==sum(quantities)
    assert result.physical_sheets==(sum(quantities)+result.capacity-1)//result.capacity
    assert sum(e.sheet_count for e in result.patterns)==result.physical_sheets
