"""Local production generator of Szczecin TAXI number decals.

Source side TIFF artwork is retained at native resolution. Rear cutter artwork
is written as a single SVG outline decal: one number over the word SZCZECIN,
without mirror copies. The SVG remains font-free and uses genuine vector curves.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import io
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.basePen import BasePen

VERSION = '0.2.8'
REFERENCE_NUMBER = '1740'
DPI = 200
IMAGE_SIZE = (2283, 1102)
# Bboxes measured from source photos, keeping the Szczecin logo/text untouched.
NUMBER_BBOX = {
    'lewy': (85, 43, 1405, 704),
    'prawy': (894, 43, 2214, 704),
}
# The actual font in the CorelDRAW X4 reference was Impact.
SYSTEM_FONT_CANDIDATES = [
    Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'impact.ttf',
    Path('/usr/share/fonts/truetype/msttcorefonts/Impact.ttf'),
    Path('/usr/share/fonts/truetype/liberation2/LiberationSansNarrow-Bold.ttf'),
    Path('/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'),
]


@dataclass(frozen=True)
class GenerationResult:
    archive: Path
    numbers: tuple[str, ...]
    font_name: str
    impact_matched: bool
    files: tuple[str, ...]


def parse_numbers(value: str, *, max_count=100) -> list[str]:
    """Accept newline/comma/semicolon/whitespace separated numeric taxi IDs."""
    tokens = [t for t in re.split(r'[\s,;]+', value.strip()) if t]
    if not tokens:
        raise ValueError('Wpisz co najmniej jeden numer TAXI, np. 1740, 1713.')
    if len(tokens) > max_count:
        raise ValueError(f'Maksymalnie {max_count} numerów jednocześnie.')
    if any(not re.fullmatch('[0-9]{1,6}', t) for t in tokens):
        raise ValueError('Numery TAXI muszą zawierać wyłącznie od 1 do 6 cyfr.')
    return list(dict.fromkeys(tokens))


def template_path(side: str, base_dir: Path | None = None) -> Path:
    root = base_dir or Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return root / 'assets' / 'taxi' / f'1740_{side}.tif'


def font_path(override: str | Path | None = None) -> Path:
    if override:
        p = Path(override)
        if not p.is_file():
            raise FileNotFoundError(f'Nie odnaleziono fontu: {p}')
        return p
    for p in SYSTEM_FONT_CANDIDATES:
        if p.is_file():
            return p
    raise FileNotFoundError('Brak fontu Impact lub zgodnego zamiennika. Wskaż plik Impact.ttf z Windows.')


def font_label(path: Path) -> str:
    return 'Impact' if path.name.lower() == 'impact.ttf' else path.stem


class OutlinedText:
    """Simple closed SVG path glyph outlines from an installed OpenType font."""
    def __init__(self, source: Path):
        self.source = Path(source)
        self.font = TTFont(str(source), lazy=True)
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        self.hmtx = self.font['hmtx'].metrics

    def close(self):
        self.font.close()

    def _shapes(self, text: str):
        advances = 0
        output = []
        box = [float('inf'), float('inf'), float('-inf'), float('-inf')]
        for char in text:
            name = self.cmap.get(ord(char))
            if name is None:
                raise ValueError(f'Font nie zawiera znaku {char!r}.')
            svg_pen = SVGPathPen(self.glyphs)
            self.glyphs[name].draw(svg_pen)
            bpen = BoundsPen(self.glyphs)
            self.glyphs[name].draw(bpen)
            if bpen.bounds:
                x0,y0,x1,y1=bpen.bounds
                box[0]=min(box[0],x0+advances)
                box[1]=min(box[1],y0)
                box[2]=max(box[2],x1+advances)
                box[3]=max(box[3],y1)
            output.append((advances,svg_pen.getCommands()))
            advances += self.hmtx[name][0]
        if box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError('Brak widocznych konturów tekstu.')
        return output, box

    def paths(self, text: str, bounds: tuple[float, float, float, float], *,
              inverted: bool = False, color: str = '#111111',
              fill: bool = True, preview: bool = False) -> str:
        shapes, (bx0,by0,bx1,by1) = self._shapes(text)
        x0,y0,x1,y1=bounds
        if x1<=x0 or y1<=y0:
            raise ValueError('Niepoprawny obszar tekstu.')
        sx=(x1-x0)/(bx1-bx0)
        sy=(y1-y0)/(by1-by0)
        a=sx
        d=sy if inverted else -sy
        tx=x0-bx0*sx
        ty=(y0-by0*sy) if inverted else (y1+by0*sy)
        svg=[f'<g transform="matrix({a:.8f} 0 0 {d:.8f} {tx:.8f} {ty:.8f})">']
        for advance,path in shapes:
            if path:
                style = f'fill="{color}" stroke="none"' if fill else f'fill="none" stroke="{color}" stroke-width="{12 if preview else 1.4}"'
                svg.append(f'<path d="{escape(path)}" transform="translate({advance} 0)" {style}/>')
        svg.append('</g>')
        return ''.join(svg)


def _wrap_svg(width: float, height: float, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" '
            f'viewBox="0 0 {width} {height}">{body}</svg>')


def _text_bounds(outlined: OutlinedText, text: str) -> tuple[float, float, float, float]:
    _, (bx0, by0, bx1, by1) = outlined._shapes(text)
    return bx0, by0, bx1, by1


def _fit_box_for_height(outlined: OutlinedText, text: str, *, target_height: float) -> tuple[float, float]:
    bx0, by0, bx1, by1 = _text_bounds(outlined, text)
    height = by1 - by0
    width = bx1 - bx0
    scale = target_height / height
    return width * scale, target_height


def _fit_box_for_width(outlined: OutlinedText, text: str, *, target_width: float) -> tuple[float, float]:
    bx0, by0, bx1, by1 = _text_bounds(outlined, text)
    height = by1 - by0
    width = bx1 - bx0
    scale = target_width / width
    return target_width, height * scale


def rear_svg(number: str, outlined: OutlinedText, *, preview: bool = False) -> str:
    """Single rear decal: number over SZCZECIN, no mirror copy.

    Production geometry requested by the operator:
    - number: always 55 mm high
    - SZCZECIN: always 120 mm wide
    """
    fg = '#101010' if preview else '#000000'
    margin = 6.0
    gap = 4.0
    number_w, number_h = _fit_box_for_height(outlined, number, target_height=55.0)
    city_w, city_h = _fit_box_for_width(outlined, 'SZCZECIN', target_width=120.0)
    canvas_w = max(number_w, city_w) + 2 * margin
    canvas_h = number_h + gap + city_h + 2 * margin
    number_x = (canvas_w - number_w) / 2
    city_x = (canvas_w - city_w) / 2
    number_y = margin
    city_y = number_y + number_h + gap
    pieces = [
        outlined.paths(number, (number_x, number_y, number_x + number_w, number_y + number_h),
                       color=fg, fill=False, preview=preview),
        outlined.paths('SZCZECIN', (city_x, city_y, city_x + city_w, city_y + city_h),
                       color=fg, fill=False, preview=preview),
    ]
    return _wrap_svg(canvas_w, canvas_h, ''.join(pieces))


def _raw_text_mask(text: str, font: Path) -> Image.Image:
    """Render text once at high resolution and return its tight mask."""
    fontobj=ImageFont.truetype(str(font),950)
    probe=Image.new('L',(max(12000,len(text)*1700),1800),0)
    ImageDraw.Draw(probe).text((30,10),text,font=fontobj,fill=255)
    bbox=probe.getbbox()
    if not bbox:
        raise ValueError(f'Brak widocznego napisu: {text}')
    return probe.crop(bbox)


def _fitted_text_mask(text: str, font: Path, size: tuple[int,int]) -> Image.Image:
    """Fit text proportionally inside a target ROI, preserving original glyph proportions."""
    raw=_raw_text_mask(text,font)
    target_w,target_h=size
    if target_w<=0 or target_h<=0:
        raise ValueError('Niepoprawny docelowy obszar napisu.')
    scale=min(target_w/raw.width,target_h/raw.height)
    out_w=max(1,round(raw.width*scale))
    out_h=max(1,round(raw.height*scale))
    return raw.resize((out_w,out_h),Image.Resampling.LANCZOS)


def _svg_number_pixels(number: str, outline: OutlinedText, bbox) -> Image.Image:
    x0,y0,x1,y1=bbox
    box_w=x1-x0+1
    box_h=y1-y0+1
    mask=_fitted_text_mask(number,outline.source,(box_w,box_h))
    result=Image.new('RGBA',IMAGE_SIZE,(0,0,0,0))
    colored=Image.new('RGBA',mask.size,(0,0,0,255))
    px=x0+max(0,(box_w-mask.size[0])//2)
    py=y0+max(0,(box_h-mask.size[1])//2)
    result.paste(colored,(px,py),mask)
    return result


def _rear_preview(number: str, outlined: OutlinedText) -> bytes:
    svg = rear_svg(number, outlined, preview=True)
    # Raster preview only for UI/debug, not written into the production archive.
    try:
        import cairosvg  # type: ignore
        png = cairosvg.svg2png(bytestring=svg.encode('utf-8'), dpi=144)
        return png
    except Exception:
        width, height = 800, 420
        image = Image.new('RGB', (width, height), 'white')
        number_size = (round(width * 0.78), round(height * 0.52))
        city_size = (round(width * 0.62), round(height * 0.20))
        num_mask = _fitted_text_mask(number, outlined.source, number_size)
        city_mask = _fitted_text_mask('SZCZECIN', outlined.source, city_size)
        for mask, pos in ((num_mask, ((width - num_mask.size[0]) // 2, 26)),
                          (city_mask, ((width - city_mask.size[0]) // 2, 26 + num_mask.size[1] + 16))):
            outer = mask.filter(ImageFilter.MaxFilter(5))
            inner = mask.filter(ImageFilter.MinFilter(5))
            stroke = ImageChops.subtract(outer, inner)
            colored = Image.new('RGB', mask.size, 'black')
            image.paste(colored, pos, stroke)
        output = io.BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()

def side_tiff(number: str, side: str, outlined: OutlinedText, base_dir: Path | None = None) -> bytes:
    with Image.open(template_path(side,base_dir)) as original:
        if original.size != IMAGE_SIZE:
            raise ValueError(f'Nieprawidłowy rozmiar wzoru {side}: {original.size}')
        # Matching reference number: preserve original raster, absolutely no redesign.
        if number == REFERENCE_NUMBER:
            stream = io.BytesIO()
            original.save(stream,format='TIFF',compression='tiff_lzw',dpi=(DPI,DPI))
            return stream.getvalue()
        image=original.convert('RGB')
    bbox=NUMBER_BBOX[side]
    draw=ImageDraw.Draw(image)
    draw.rectangle((bbox[0]-20,bbox[1]-20,bbox[2]+20,bbox[3]+20),fill='white')
    layer=_svg_number_pixels(number,outlined,bbox)
    image.paste(layer,(0,0),layer)
    out=io.BytesIO()
    image.save(out,format='TIFF',compression='tiff_lzw',dpi=(DPI,DPI))
    return out.getvalue()


def make_archive(numbers: list[str] | str, output: str | Path,
                 *, font: str | Path | None = None,
                 base_dir: Path | None = None) -> GenerationResult:
    parsed = parse_numbers(numbers) if isinstance(numbers,str) else parse_numbers(','.join(numbers))
    source_font=font_path(font)
    outlined=OutlinedText(source_font)
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.suffix.lower()!='.zip':
        raise ValueError('Wynikowy plik musi mieć rozszerzenie .zip')
    names=[]
    try:
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for number in parsed:
                for side in ('lewy','prawy'):
                    filename=f'{number}_{side}.tif'
                    z.writestr(filename, side_tiff(number, side, outlined, base_dir))
                    names.append(filename)
                svg = rear_svg(number, outlined).encode('utf-8')
                filename = f'{number}_tyl.svg'
                z.writestr(filename, svg)
                names.append(filename)
            z.writestr('CZYTAJ_PRZED_CIECIEM.txt', (
                'IMPOZYCJONER TAXI - PAKIET PRODUKCYJNY\n'
                'Wszystkie pliki znajduja sie luzem w jednym folderze ZIP.\n'
                'BOKI: TIFF 2283x1102 px, 200 DPI, z zachowanym herbem i napisem SZCZECIN.\n'
                'TYL: jeden plik SVG na numer, bez lustrzanego odbicia.\n'
                'GEOMETRIA TYLU: numer zawsze 55 mm wysokosci, napis SZCZECIN zawsze 120 mm szerokosci.\n'
                'W plikach tylu sa wyłącznie wektorowe krzywe, bez live text.\n'
                f'FONT UZYTY DO KONTUROW: {font_label(source_font)}\n'
                'CorelDRAW X4: importuj SVG i sprawdz linie ciecia oraz rzeczywisty wymiar.\n'
                'Przed produkcja zrob test na ploterze.\n'
            ).encode('utf-8'))
    finally:
        outlined.close()
    return GenerationResult(output,tuple(parsed),font_label(source_font),source_font.name.lower()=='impact.ttf',tuple(names))


if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser(description='TAXI Szczecin side TIFF and rear SVG cut generator')
    ap.add_argument('numbers',nargs='+',help='Numery np. 1740 1713')
    ap.add_argument('-o','--output',default='TAXI_NAKLEJKI.zip')
    ap.add_argument('--font',default=None)
    args=ap.parse_args()
    print(make_archive(args.numbers,args.output,font=args.font))
