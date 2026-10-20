from types import SimpleNamespace

import pytest

from preview_labels import file_color, symbolic_preview, _head_edge
from ui_icons import draw


def _side():
    return SimpleNamespace(placements=[
        SimpleNamespace(source=SimpleNamespace(index=0, path='C:/a.pdf'),
                        slot=SimpleNamespace(x=10, y=10, w=90, h=50, rotation=0)),
        SimpleNamespace(source=SimpleNamespace(index=3, path='C:/b.pdf'),
                        slot=SimpleNamespace(x=110, y=10, w=50, h=90, rotation=90)),
        SimpleNamespace(source=None, slot=SimpleNamespace(x=10, y=120, w=90, h=50, rotation=0))])


def test_symbolic_preview_keeps_sheet_proportions_and_colours_uses():
    settings = SimpleNamespace(sheet_w=450, sheet_h=320)
    colors = {'C:/a.pdf': file_color(0), 'C:/b.pdf': file_color(1)}
    image = symbolic_preview(_side(), settings, colors.__getitem__, pixels=900, bleed=2)
    assert image.size == (900, 640)
    zoom = 2
    def rgb(c): return tuple(int(c[i:i+2], 16) for i in (1, 3, 5))
    # Inside each use (away from text) the file colour is used.
    assert image.getpixel((int(15*zoom), int(55*zoom))) == rgb(file_color(0))
    assert image.getpixel((int(115*zoom), int(90*zoom))) == rgb(file_color(1))
    # Empty slot stays light grey, outside of uses the sheet stays white.
    assert image.getpixel((int(15*zoom), int(165*zoom))) == (244, 245, 247)
    assert image.getpixel((int(300*zoom), int(300*zoom))) == (255, 255, 255)


def test_symbolic_preview_without_side_is_blank_sheet():
    image = symbolic_preview(None, SimpleNamespace(sheet_w=320, sheet_h=450), lambda p: '#000000', pixels=450)
    assert image.size == (320, 450)
    assert image.getbbox() == (0, 0, 320, 450) and image.getextrema() == ((255, 255),) * 3


@pytest.mark.parametrize('rotation,edge', [(0, (0, 0, 10, 0)), (90, (10, 0, 10, 5)),
                                           (180, (0, 5, 10, 5)), (270, (0, 0, 0, 5))])
def test_page_head_edge_follows_pdf_view_rotation(rotation, edge):
    assert _head_edge(0, 0, 10, 5, rotation) == edge


@pytest.mark.parametrize('name', ['single', 'duplex_long', 'duplex_short', 'economic', 'booklet',
                                  'symbols', 'edit', 'register', 'refresh', 'preflight', 'marks', 'numbers'])
def test_toolbar_icons_render(name):
    icon = draw(name, 30)
    assert icon.size == (30, 30)
    assert icon.getbbox() is not None
