"""Local production generator of Szczecin TAXI number decals.

Source side TIFF artwork is retained at native resolution. Rear cutter artwork
is written as genuine closed vector glyph outlines (EPS-based Illustrator .ai,
EPS and SVG), independent of fonts on the cutting workstation.

X4 import of the generated .ai needs a real on-machine validation; an EPS file
is also provided as a compatibility fallback. Not a native Corel CDR writer.
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

VERSION = '0.2.6'
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


def rear_svg(number: str, outlined: OutlinedText, *, preview=False) -> str:
    """A4, two mirrored pairs as in the supplied X4 CDR reference thumbnail.

    Placement is based on the preview of the original CDR, which was made from
    four artistic text objects. Paths remain separate, closed curves.
    """
    fg = '#101010' if preview else '#000000'
    # Reference art is notably right-offset on the A4 sheet.
    left,right = 63.0, 186.0
    pieces = [
        outlined.paths(number,(left,36,right,93),color=fg,fill=False,preview=preview),
        outlined.paths('SZCZECIN',(left,94,right,116),color=fg,fill=False,preview=preview),
        outlined.paths('SZCZECIN',(left,117,right,139),inverted=True,color=fg,fill=False,preview=preview),
        outlined.paths(number,(left,140,right,214),inverted=True,color=fg,fill=False,preview=preview),
    ]
    # For production the paths are black closed silhouettes. A plotter can cut
    # both the inner and outer contours of letters without needing a font.
    return _wrap_svg(210,297,''.join(pieces))


class _PostScriptPen(BasePen):
    """Convert quadratic/cubic TrueType outlines to standard cubic PostScript."""
    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.commands=[]

    def _moveTo(self, xy):
        self.commands.append(f'{xy[0]:.5f} {xy[1]:.5f} moveto')

    def _lineTo(self, xy):
        self.commands.append(f'{xy[0]:.5f} {xy[1]:.5f} lineto')

    def _curveToOne(self, a,b,c):
        self.commands.append(f'{a[0]:.5f} {a[1]:.5f} '
                             f'{b[0]:.5f} {b[1]:.5f} '
                             f'{c[0]:.5f} {c[1]:.5f} curveto')

    def _closePath(self):
        self.commands.append('closepath')


def rear_eps(number: str, outlined: OutlinedText) -> bytes:
    """A4 legacy PostScript EPS, font-free hairline vector strokes."""
    commands=[
        '%!PS-Adobe-3.0 EPSF-3.0',
        '%%Creator: Impozycjoner Studio TAXI cut generator',
        '%%Title: Taxi rear vinyl cutting artwork',
        '%%BoundingBox: 0 0 596 842',
        '%%HiResBoundingBox: 0 0 595.276 841.890',
        '%%Pages: 1',
        '%%LanguageLevel: 2',
        '%%EndComments',
        '0 setgray',
    ]
    ptmm=72/25.4
    items=[
        (number, (63.0,36,186.0,93),False),
        ('SZCZECIN', (63.0,94,186.0,116),False),
        ('SZCZECIN', (63.0,117,186.0,139),True),
        (number, (63.0,140,186.0,214),True),
    ]
    for text,bounds,inverted in items:
        glyphs,(bx0,by0,bx1,by1)=outlined._shapes(text)
        x0,y0,x1,y1=bounds
        sx=(x1-x0)/(bx1-bx0)
        sy=(y1-y0)/(by1-by0)
        d=sy if inverted else -sy
        tx=x0-bx0*sx
        ty=y0-by0*sy if inverted else y1+by0*sy
        commands.extend(['gsave',f'{tx*ptmm:.8f} {(297-ty)*ptmm:.8f} translate',
                         f'{sx*ptmm:.8f} {-d*ptmm:.8f} scale',
                         '1.4 setlinewidth 1 setlinejoin 1 setlinecap'])
        advance=0
        for char in text:
            name=outlined.cmap[ord(char)]
            pen=_PostScriptPen(outlined.glyphs)
            outlined.glyphs[name].draw(pen)
            commands.extend(['gsave',f'{advance:.6f} 0 translate','newpath',
                             *pen.commands,'stroke','grestore'])
            advance+=outlined.hmtx[name][0]
        commands.append('grestore')
    commands.extend(['showpage','%%EOF'])
    return ('\n'.join(commands)+'\n').encode('ascii')


def _fitted_text_mask(text: str, font: Path, size: tuple[int,int]) -> Image.Image:
    """Render glyphs from the installed typeface, fitting them to a target ROI."""
    fontobj=ImageFont.truetype(str(font),950)
    probe=Image.new('L',(max(12000,len(text)*1700),1800),0)
    ImageDraw.Draw(probe).text((30,10),text,font=fontobj,fill=255)
    bbox=probe.getbbox()
    if not bbox:
        raise ValueError(f'Brak widocznego napisu: {text}')
    return probe.crop(bbox).resize(size,Image.Resampling.LANCZOS)


def _svg_number_pixels(number: str, outline: OutlinedText, bbox) -> Image.Image:
    x0,y0,x1,y1=bbox
    mask=_fitted_text_mask(number,outline.source,(x1-x0+1,y1-y0+1))
    result=Image.new('RGBA',IMAGE_SIZE,(0,0,0,0))
    colored=Image.new('RGBA',mask.size,(0,0,0,255))
    result.paste(colored,(x0,y0),mask)
    return result


def _rear_preview(number: str, outlined: OutlinedText) -> bytes:
    w,h=707,1000
    image=Image.new('RGB',(w,h),'white')
    factor_x=w/210
    factor_y=h/297
    texts=[(number,(63,36,186,93),False),
           ('SZCZECIN',(63,94,186,116),False),
           ('SZCZECIN',(63,117,186,139),True),
           (number,(63,140,186,214),True)]
    for text,(x0,y0,x1,y1),invert in texts:
        width=max(1,round((x1-x0)*factor_x))
        height=max(1,round((y1-y0)*factor_y))
        mask=_fitted_text_mask(text,outlined.source,(width,height))
        if invert:
            mask=mask.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        outer=mask.filter(ImageFilter.MaxFilter(5))
        inner=mask.filter(ImageFilter.MinFilter(5))
        stroke=ImageChops.subtract(outer,inner)
        # Outline remains a preview; production data is vector EPS/SVG.
        colored=Image.new('RGB',(width,height),'black')
        image.paste(colored,(round(x0*factor_x),round(y0*factor_y)),stroke)
    output=io.BytesIO()
    image.save(output,format='PNG')
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
                prefix=f'TAXI_{number}/'
                for side in ('lewy','prawy'):
                    filename=prefix+f'{number}_{side}.tif'
                    z.writestr(filename,side_tiff(number,side,outlined,base_dir))
                    names.append(filename)
                svg=rear_svg(number,outlined)
                eps=rear_eps(number,outlined)
                outputs=((f'{number}_TYL.ai',eps),(f'{number}_TYL.eps',eps),
                         (f'{number}_TYL.svg',svg.encode('utf-8')))
                for filename,payload in outputs:
                    z.writestr(prefix+filename,payload)
                    names.append(prefix+filename)
                # Light background with bold contour preview; EPS remains hairline.
                pic=_rear_preview(number,outlined)
                z.writestr(prefix+f'{number}_TYL_PODGLAD.png',pic)
                names.append(prefix+f'{number}_TYL_PODGLAD.png')
            z.writestr('CZYTAJ_PRZED_CIECIEM.txt',(
                'IMPOZYCJONER TAXI - PAKIET PRODUKCYJNY\n'
                'BOKI: dwa TIFF-y 2283x1102 px, 200 DPI, z zachowanym herbem i napisem SZCZECIN.\n'
                'TYL: AI w starszym formacie PostScript/EPS + EPS i SVG jako alternatywy.\n'
                'W plikach do cięcia są wyłącznie wektorowe krzywe, bez live text.\n'
                f'FONT UZYTY DO KONTUROW: {font_label(source_font)}\n'
                'CorelDRAW X4: sproboj importu EPS lub otwarcia AI; po imporcie sprawdz linie cięcia.\n'
                'UWAGA: To nie jest natywny plik CDR; nie potwierdzono jeszcze importu w X4.\n'
                'Przed cięciem sprawdź rozmiar 210 x 297 mm oraz test na ploterze.\n'
                'Załączony wzór CDR zawierał 1713; przykładowe boki zawierały 1740.\n'
            ).encode('utf-8'))
    finally:
        outlined.close()
    return GenerationResult(output,tuple(parsed),font_label(source_font),source_font.name.lower()=='impact.ttf',tuple(names))


if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser(description='TAXI Szczecin side TIFF and rear vector-cut generator')
    ap.add_argument('numbers',nargs='+',help='Numery np. 1740 1713')
    ap.add_argument('-o','--output',default='TAXI_NAKLEJKI.zip')
    ap.add_argument('--font',default=None)
    args=ap.parse_args()
    print(make_archive(args.numbers,args.output,font=args.font))
