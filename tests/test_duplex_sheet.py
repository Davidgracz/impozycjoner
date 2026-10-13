"""v0.3.7: printable test marks, correct front-view signs and iterative profiles."""
from pathlib import Path
import math

import pytest
import pymupdf as fitz

from duplex_test_sheet import (create_duplex_test_pdf, correction_from_front_error,
                               horizontal_flip, measurement_points, on_back, PT_PER_MM)
from duplex_calibration import read_profile, store_profile
from engine import Settings, geometry, _flip_slot


@pytest.mark.parametrize('w,h,flip,expected_horizontal', [
    (320,450,'Długa krawędź',True),
    (450,320,'Długa krawędź',False),
    (320,450,'Krótka krawędź',False),
    (450,320,'Krótka krawędź',True),
])
def test_flip_matches_engine(w,h,flip,expected_horizontal):
    assert horizontal_flip(flip,w,h)==expected_horizontal
    s=Settings(sheet_w=w,sheet_h=h,trim_w=93,trim_h=53,rotation='0',flip=flip)
    slot=geometry(s).slots[0]
    back=_flip_slot(slot,s)
    x,y=slot.x+slot.w/2,slot.y+slot.h/2
    bx,by=on_back(x,y,w,h,flip)
    assert (back.x+back.w/2,back.y+back.h/2)==pytest.approx((bx,by))
    # Mapped back centres coincide with front centres.
    assert on_back(bx,by,w,h,flip)==pytest.approx((x,y))


@pytest.mark.parametrize('w,h,flip,expected', [
    (320,450,'Długa krawędź',(.7,.4)),
    (450,320,'Długa krawędź',(-.7,-.4)),
    (320,450,'Krótka krawędź',(-.7,-.4)),
    (450,320,'Krótka krawędź',(.7,.4)),
])
def test_calculator_front_view_correction(w,h,flip,expected):
    assert correction_from_front_error(.7,-.4,flip=flip,sheet_w=w,sheet_h=h)==expected
    # Opposite error on the next test returns to zero (supports iterative measurements).
    x,y=expected
    result=correction_from_front_error(-.7,.4,flip=flip,sheet_w=w,sheet_h=h,
                                       current_x=x,current_y=y)
    assert result==pytest.approx((0,0))


def test_calculator_adds_to_existing_profile(tmp_path):
    profile=tmp_path/'profiles.json'
    store_profile('Cyfra SRA3',x=.3,y=-.2,flip='Długa krawędź',path=profile)
    d=read_profile('Cyfra SRA3',path=profile)
    new=correction_from_front_error(.7,-.4,flip=d['flip'],sheet_w=320,sheet_h=450,
                                    current_x=d['x'],current_y=d['y'])
    assert new==(1.0,.2)
    store_profile('Cyfra SRA3',x=new[0],y=new[1],flip=d['flip'],path=profile)
    assert read_profile('Cyfra SRA3',path=profile)['x']==1.0


def test_vector_pdf_is_two_pages_actual_size_and_printable(tmp_path):
    target=tmp_path/'TEST_320x450.pdf'
    create_duplex_test_pdf(target,sheet_w=320,sheet_h=450,flip='Długa krawędź',
                           verso_shift_x=.7,verso_shift_y=-.4)
    with fitz.open(target) as pdf:
        assert len(pdf)==2
        for page in pdf:
            assert page.rect.width==pytest.approx(320*PT_PER_MM,abs=.1)
            assert page.rect.height==pytest.approx(450*PT_PER_MM,abs=.1)
            assert page.get_images(full=True)==[]  # vector only
            assert len(page.get_drawings())>20
            assert page.get_text().strip()
        assert 'FRONT' in pdf[0].get_text()
        assert 'BACK' in pdf[1].get_text()
        assert 'X=+0.7' in pdf[1].get_text()
        assert 'Y=-0.4' in pdf[1].get_text()
        assert '100%' in pdf[0].get_text()


def test_pdf_back_targets_follow_flip_and_shift(tmp_path):
    p0=tmp_path/'base.pdf'
    p1=tmp_path/'shifted.pdf'
    create_duplex_test_pdf(p0,sheet_w=320,sheet_h=450,flip='Długa krawędź')
    create_duplex_test_pdf(p1,sheet_w=320,sheet_h=450,flip='Długa krawędź',
                           verso_shift_x=.8,verso_shift_y=-.3)
    with fitz.open(p0) as a,fitz.open(p1) as b:
        assert a[0].get_pixmap().samples==b[0].get_pixmap().samples
        # Compare ring centres, reading first circle's rect.
        def centres(page):
            return [d['rect'] for d in page.get_drawings() if d['type']=='s' and d.get('closePath')]
        # Recto unchanged, verso changed vector artwork, no rasterisation.
        assert a[1].get_pixmap().samples!=b[1].get_pixmap().samples
        assert a[1].get_images()==b[1].get_images()==[]


@pytest.mark.parametrize('bad', [0.15,21,float('nan'),float('inf')])
def test_invalid_measurements_do_not_get_silently_rounded(bad):
    with pytest.raises(ValueError):
        correction_from_front_error(bad,0,flip='Długa krawędź',sheet_w=320,sheet_h=450)


def test_reject_invalid_sheet_no_partial_file(tmp_path):
    path=tmp_path/'should_not_exist.pdf'
    with pytest.raises(ValueError):
        create_duplex_test_pdf(path,sheet_w=50,sheet_h=450,flip='Długa krawędź')
    assert not path.exists()
    with pytest.raises(ValueError):
        create_duplex_test_pdf(path,sheet_w=320,sheet_h=450,flip='Długa krawędź',verso_shift_x=20.1)
    assert not path.exists()
