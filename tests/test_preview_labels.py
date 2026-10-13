from types import SimpleNamespace
from PIL import Image, ImageChops
from preview_labels import page_identifier, overlay_preview


def _side():
    return SimpleNamespace(placements=[
        SimpleNamespace(source=SimpleNamespace(index=11,path='C:/test/zamowienie.pdf'),
                        slot=SimpleNamespace(x=10,y=10,w=80,h=50)),
        SimpleNamespace(source=None, slot=SimpleNamespace(x=110,y=10,w=80,h=50))])


def test_page_identifier_is_one_based():
    assert page_identifier(_side().placements[0].source,'Numer strony')=='12'
    assert page_identifier(_side().placements[0].source,'Plik + numer')=='zamowienie.pdf • 12'
    assert page_identifier(None,'Numer strony')=='PUSTE'


def test_no_overlay_does_not_change_preview_pixels():
    image=Image.new('RGB',(840,594),'white')
    settings=SimpleNamespace(sheet_w=210,sheet_h=148.5)
    assert overlay_preview(image,_side(),settings,'Brak') is image
    out=overlay_preview(image,_side(),settings,'Numer strony')
    assert ImageChops.difference(image,out).getbbox() is not None
    assert image.getpixel((200,150))==(255,255,255)  # input untouched
    assert out.getpixel((5,5))==(255,255,255)  # margins untouched


def test_modes_produce_distinct_overlays():
    image=Image.new('RGB',(840,594),'white')
    settings=SimpleNamespace(sheet_w=210,sheet_h=148.5)
    a=overlay_preview(image,_side(),settings,'Numer strony')
    b=overlay_preview(image,_side(),settings,'Plik + numer')
    assert ImageChops.difference(a,b).getbbox() is not None
