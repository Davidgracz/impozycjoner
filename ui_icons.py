"""Small vector-style toolbar icons drawn with Pillow (no image files to ship)."""
from PIL import Image, ImageDraw

from preview_labels import _font

INK = (47, 111, 194)
DARK = (55, 65, 81)
PAPER = (255, 255, 255)
BACK = (200, 210, 224)
SCALE = 4  # draw large and downsample for smooth edges


def _canvas(size):
    big = size * SCALE
    return Image.new('RGBA', (big, big), (0, 0, 0, 0)), big


def _page(d, box, fill=PAPER, fold=True):
    x0, y0, x1, y1 = box
    f = (x1 - x0) * .3 if fold else 0
    d.polygon([(x0, y0), (x1 - f, y0), (x1, y0 + f), (x1, y1), (x0, y1)], fill=fill, outline=DARK, width=SCALE*2)
    if fold:
        d.line([(x1 - f, y0), (x1 - f, y0 + f), (x1, y0 + f)], fill=DARK, width=SCALE*2)


def _arrow(d, a, b, width):
    (x0, y0), (x1, y1) = a, b
    d.line([a, b], fill=INK, width=width)
    head = width * 2.2
    if y0 == y1:
        for x, s in ((x0, 1), (x1, -1)):
            d.polygon([(x, y0), (x + s*head, y0 - head*.8), (x + s*head, y0 + head*.8)], fill=INK)
    else:
        for y, s in ((y0, 1), (y1, -1)):
            d.polygon([(x0, y), (x0 - head*.8, y + s*head), (x0 + head*.8, y + s*head)], fill=INK)


def draw(name, size=30):
    img, n = _canvas(size)
    d = ImageDraw.Draw(img)
    u = n / 30
    if name == 'single':
        _page(d, (8*u, 3*u, 22*u, 27*u))
    elif name in ('duplex_long', 'duplex_short'):
        _page(d, (9*u, 2*u, 21*u, 17*u), fill=BACK)
        _page(d, (4*u, 7*u, 16*u, 22*u))
        if name == 'duplex_long':
            _arrow(d, (8*u, 26.5*u), (28*u, 26.5*u), int(2*u))
        else:
            _arrow(d, (25.5*u, 6*u), (25.5*u, 28*u), int(2*u))
    elif name == 'economic':
        colors = [(242, 201, 76), (201, 168, 130), (143, 193, 227), (155, 194, 91), (242, 201, 76), (143, 193, 227)]
        for i, c in enumerate(colors):
            x, y = 3*u + (i % 3)*8.3*u, 6*u + (i // 3)*10*u
            d.rectangle((x, y, x + 7*u, y + 8.5*u), fill=c, outline=DARK, width=SCALE)
    elif name == 'booklet':
        d.polygon([(15*u, 8*u), (3*u, 5*u), (3*u, 24*u), (15*u, 27*u)], fill=PAPER, outline=DARK, width=SCALE*2)
        d.polygon([(15*u, 8*u), (27*u, 5*u), (27*u, 24*u), (15*u, 27*u)], fill=BACK, outline=DARK, width=SCALE*2)
        for k in (12, 16, 20):
            d.line([(6*u, k*u), (12*u, (k+1.5)*u)], fill=INK, width=SCALE*2)
    elif name == 'symbols':
        for i, c in enumerate([(242, 201, 76), (143, 193, 227), (155, 194, 91), (79, 111, 216)]):
            x, y = 3*u + (i % 2)*12.5*u, 3*u + (i // 2)*12.5*u
            d.rectangle((x, y, x + 11*u, y + 11*u), fill=c, outline=PAPER, width=SCALE)
    elif name == 'edit':
        d.rectangle((3*u, 6*u, 21*u, 27*u), fill=PAPER, outline=DARK, width=SCALE*2)
        d.polygon([(25*u, 3*u), (28*u, 6*u), (14*u, 20*u), (10*u, 21*u), (11*u, 17*u)], fill=INK)
    elif name == 'register':
        d.ellipse((3*u, 5*u, 20*u, 22*u), outline=DARK, width=SCALE*2)
        d.ellipse((10*u, 8*u, 27*u, 25*u), outline=INK, width=SCALE*2)
        d.line([(15*u, 2*u), (15*u, 28*u)], fill=DARK, width=SCALE)
        d.line([(2*u, 15*u), (28*u, 15*u)], fill=DARK, width=SCALE)
    elif name == 'refresh':
        d.arc((5*u, 5*u, 25*u, 25*u), 40, 330, fill=INK, width=int(3*u))
        d.polygon([(25*u, 3*u), (26*u, 13*u), (17*u, 10*u)], fill=INK)
    elif name == 'preflight':
        _page(d, (5*u, 3*u, 22*u, 27*u))
        d.line([(10*u, 17*u), (15*u, 23*u), (28*u, 8*u)], fill=(46, 160, 67), width=int(3.4*u))
    elif name == 'marks':
        d.rectangle((9*u, 9*u, 21*u, 21*u), outline=BACK, width=SCALE*2)
        for x in (9, 21):
            d.line([(x*u, 1*u), (x*u, 6*u)], fill=DARK, width=SCALE*2)
            d.line([(x*u, 24*u), (x*u, 29*u)], fill=DARK, width=SCALE*2)
        for y in (9, 21):
            d.line([(1*u, y*u), (6*u, y*u)], fill=DARK, width=SCALE*2)
            d.line([(24*u, y*u), (29*u, y*u)], fill=DARK, width=SCALE*2)
    elif name == 'numbers':
        _page(d, (6*u, 3*u, 24*u, 27*u))
        d.text((14*u, 17*u), '12', fill=INK, anchor='mm', font=_font(int(10*u)))
    else:
        raise ValueError(f'Nieznana ikona: {name}')
    return img.resize((size, size), Image.Resampling.LANCZOS)
