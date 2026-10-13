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
