import fitz
import pytest
from engine import Project, Job, Settings, export_pages, export_pdf, preview, pt


def sample(tmp_path):
    path=tmp_path/'source110x70.pdf'
    d=fitz.open();p=d.new_page(width=pt(110),height=pt(70))
    p.draw_rect(fitz.Rect(0,0,pt(110),pt(70)),color=(1,0,0),width=1)
    p.insert_text((pt(12),pt(20)),'inside',fontsize=10)
    p.insert_text((pt(2),pt(2)),'outside',fontsize=6)
    d.save(path);d.close()
    return path


def test_crop_exact_net_and_bleed(tmp_path):
    source=sample(tmp_path)
    settings=Settings(trim_w=93,trim_h=53,bleed=2,scale_mode='Kadruj 1:1')
    project=Project(settings=settings,jobs=[Job(str(source))])
    output=tmp_path/'cropped.pdf'
    assert export_pages(project,str(output)) == 1
    with fitz.open(output) as doc:
        page=doc[0]
        assert page.rect.width/pt(1)==pytest.approx(97,abs=.01)
        assert page.rect.height/pt(1)==pytest.approx(57,abs=.01)
        assert page.trimbox.width/pt(1)==pytest.approx(93,abs=.01)
        assert page.trimbox.height/pt(1)==pytest.approx(53,abs=.01)
        assert 'inside' in page.get_text()
        assert 'outside' not in page.get_text()


def test_crop_rejects_too_small_source(tmp_path):
    source=sample(tmp_path)
    project=Project(settings=Settings(trim_w=120,trim_h=53,scale_mode='Kadruj 1:1'), jobs=[Job(str(source))])
    with pytest.raises(ValueError, match='za mały'):
        export_pages(project,str(tmp_path/'out.pdf'))


def test_crop_montage_and_preview(tmp_path):
    source=sample(tmp_path)
    settings=Settings(sheet_w=320,sheet_h=220,trim_w=93,trim_h=53,bleed=2,scale_mode='Kadruj 1:1',crop_marks=False)
    project=Project(settings=settings,jobs=[Job(str(source))])
    output=tmp_path/'montage.pdf'
    assert export_pdf(project,str(output)) >= 1
    im, n = preview(project)
    assert im.width > 0 and n.sheet_number >= 1
