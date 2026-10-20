"""Preview-only semi-transparent sheet cell identifiers. Not used in PDF export."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OVERLAY_OPTIONS = ('Brak', 'Numer strony', 'Plik + numer')


def _font(size):
    for name in ('C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def page_identifier(source, mode):
    if source is None:
        return 'PUSTE' if mode != 'Brak' else ''
    number = str(source.index + 1)
    if mode == 'Plik + numer':
        return f'{Path(source.path).name} • {number}'
    return number


def overlay_preview(image, side, settings, mode='Numer strony', *, show_empty=True):
    """Draw labels only into raster preview after PDF rendering; preserve source image."""
    if mode == 'Brak' or side is None:
        return image
    if mode not in OVERLAY_OPTIONS:
        raise ValueError(f'Nieznany tryb numerowania: {mode}')
    canvas = image.convert('RGBA')
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    sx = canvas.width / settings.sheet_w
    sy = canvas.height / settings.sheet_h
    for placement in side.placements:
        if placement.source is None and not show_empty:
            continue
        slot = placement.slot
        x0, y0 = slot.x*sx, slot.y*sy
        w, h = slot.w*sx, slot.h*sy
        if w < 6 or h < 6:
            continue
        label = page_identifier(placement.source, mode)
        # Large digits; long filenames shrink to fit, keeping text legible.
        size = max(10, int(min(h*0.55, w*(0.55 if mode == 'Numer strony' else 0.22), 165)))
        font = _font(size)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if tw <= 0 or th <= 0:
            continue
        shrink = min(1, (w*0.9)/tw, (h*0.7)/th)
        if shrink < 1:
            font = _font(max(8,int(size*shrink)))
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        cx = x0 + w/2
        cy = y0 + h/2
        # Soft translucent plaque improves readability on dark or busy PDF designs.
        pad_x, pad_y = max(5, w*0.045), max(3, h*0.05)
        bx0 = max(x0+1, cx-tw/2-pad_x)
        bx1 = min(x0+w-1, cx+tw/2+pad_x)
        by0 = max(y0+1, cy-th/2-pad_y)
        by1 = min(y0+h-1, cy+th/2+pad_y)
        draw.rounded_rectangle((bx0,by0,bx1,by1), radius=min(10,int(h/12)), fill=(18,31,42,105))
        draw.text((cx-(bbox[0]+bbox[2])/2, cy-(bbox[1]+bbox[3])/2), label, font=font, fill=(235,255,250,205))
    return Image.alpha_composite(canvas, layer).convert('RGB')


# Paleta symbolicznych użytków (jak kolorowe pola w Impozycjonerze 4).
SYMBOL_COLORS = ('#f2c94c', '#c9a882', '#8fc1e3', '#9bc25b', '#b8b26d', '#4f6fd8',
                 '#c0612b', '#a9b8d9', '#d98cb3', '#5fb8a5', '#e0904a', '#8a7fc9')


def file_color(index):
    return SYMBOL_COLORS[index % len(SYMBOL_COLORS)]


def _rgb(color):
    color = color.lstrip('#')
    return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))


def _head_edge(x0, y0, x1, y1, rotation):
    """Edge holding the top of the page: 0° top, 90° right (PDF view rotation), 180° bottom, 270° left."""
    return {0: (x0, y0, x1, y0), 90: (x1, y0, x1, y1),
            180: (x0, y1, x1, y1), 270: (x0, y0, x0, y1)}[rotation % 360]


def symbolic_preview(side, settings, color_for_path, *, pixels=1300, bleed=0.0,
                     marks=True, mode='Numer strony'):
    """Draws a schematic sheet without rendering PDF content: coloured uses with
    page number, rotation and a thick bar on the edge holding the page head."""
    zoom = pixels / max(settings.sheet_w, settings.sheet_h)
    width, height = max(1, round(settings.sheet_w*zoom)), max(1, round(settings.sheet_h*zoom))
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    if side is None:
        return image
    for placement in side.placements:
        slot = placement.slot
        x0, y0 = slot.x*zoom, slot.y*zoom
        x1, y1 = (slot.x+slot.w)*zoom, (slot.y+slot.h)*zoom
        b = bleed*zoom
        if placement.source is None:
            draw.rectangle((x0, y0, x1, y1), fill=(244, 245, 247), outline=(190, 196, 205), width=1)
            label, sub = 'PUSTE', ''
            fg = (150, 158, 170)
        else:
            base = _rgb(color_for_path(placement.source.path))
            dark = tuple(int(c*.78) for c in base)
            draw.rectangle((x0-b, y0-b, x1+b, y1+b), fill=dark)
            draw.rectangle((x0, y0, x1, y1), fill=base, outline=(255, 255, 255), width=max(1, int(zoom*.6)))
            hx0, hy0, hx1, hy1 = _head_edge(x0, y0, x1, y1, slot.rotation)
            draw.line((hx0, hy0, hx1, hy1), fill=(255, 255, 255), width=max(3, int(min(x1-x0, y1-y0)*.07)))
            label = f'{placement.source.index+1}:{slot.rotation % 360}°'
            sub = Path(placement.source.path).stem if mode == 'Plik + numer' else ''
            fg = (30, 30, 30) if sum(base) > 380 else (255, 255, 255)
        w, h = x1-x0, y1-y0
        if w < 8 or h < 8:
            continue
        size = max(9, int(min(h*.28, w*.22, 72)))
        font = _font(size)
        tb = draw.textbbox((0, 0), label, font=font)
        cx, cy = (x0+x1)/2, (y0+y1)/2 - (size*.35 if sub else 0)
        draw.text((cx-(tb[0]+tb[2])/2, cy-(tb[1]+tb[3])/2), label, font=font, fill=fg)
        if sub:
            small = _font(max(8, size//2))
            while len(sub) > 3 and draw.textlength(sub, font=small) > w*.9:
                sub = sub[:-2] + '…'
            sb = draw.textbbox((0, 0), sub, font=small)
            draw.text((cx-(sb[0]+sb[2])/2, cy+size*.75), sub, font=small, fill=fg)
        if marks and placement.source is not None:
            m = 3*zoom
            for (px, py, dx, dy) in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x0, y1, -1, 1), (x1, y1, 1, 1)):
                draw.line((px+dx*(b+1), py, px+dx*(b+1+m), py), fill=(0, 0, 0), width=1)
                draw.line((px, py+dy*(b+1), px, py+dy*(b+1+m)), fill=(0, 0, 0), width=1)
    return image
