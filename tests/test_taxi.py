"""Production checks for Taxi Szczecin decal output and plotter outlines."""
import io
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from PIL import Image
from taxi_generator import (parse_numbers, font_path, OutlinedText,
                            make_archive, side_tiff, rear_eps, rear_svg, DPI)


def test_number_parser_accepts_batches_and_deduplicates():
    assert parse_numbers('1740, 1713\n034;1740') == ['1740','1713','034']


@pytest.mark.parametrize('bad', ['', '1740,foo', '1740/../../', '1740 zł', '1234567'])
def test_number_parser_rejects_unsafe_input(bad):
    with pytest.raises(ValueError):
        parse_numbers(bad)


def test_source_tiff_200dpi_and_native_size():
    from taxi_generator import template_path
    for side in ('lewy','prawy'):
        with Image.open(template_path(side)) as im:
            assert im.size == (2283,1102)
            assert im.info['dpi'] == (200,200)


def test_number_change_does_not_touch_crest_or_city():
    from taxi_generator import template_path
    font=OutlinedText(font_path())
    try:
        for side in ('lewy','prawy'):
            generated=Image.open(io.BytesIO(side_tiff('1713',side,font))).convert('RGB')
            source=Image.open(template_path(side)).convert('RGB')
            # Artwork outside numeric ROI is identical, including the city word.
            assert generated.crop((0,780,2283,1102)).tobytes() == source.crop((0,780,2283,1102)).tobytes()
            crest=(1650,150) if side=='lewy' else (250,150)
            assert generated.getpixel(crest) == source.getpixel(crest)
            assert generated.size == source.size
            assert Image.open(io.BytesIO(side_tiff('1713',side,font))).info['dpi'] == (200,200)
    finally:
        font.close()


def test_reference_number_has_identical_original_pixels():
    from taxi_generator import template_path
    font=OutlinedText(font_path())
    try:
        for side in ('lewy','prawy'):
            original=Image.open(template_path(side)).convert('RGB')
            out=Image.open(io.BytesIO(side_tiff('1740',side,font))).convert('RGB')
            assert original.tobytes() == out.tobytes()
    finally:
        font.close()


def test_rear_vector_has_four_objects_and_mirror_transform():
    font=OutlinedText(font_path())
    try:
        xml=rear_svg('1713',font)
        doc=ET.fromstring(xml)
        assert doc.attrib['viewBox'] == '0 0 210 297'
        groups=[node for node in doc if node.tag.endswith('g')]
        assert len(groups)==4
        matrix_values=[g.attrib['transform'].replace('matrix(','').replace(')','').split() for g in groups]
        assert float(matrix_values[0][4]) != float(matrix_values[3][4]) or float(matrix_values[0][5]) != float(matrix_values[3][5])
        # first and last groups must have opposite vertical transform signs
        def vertical(g): return float(g.attrib['transform'].replace('matrix(','').replace(')','').split()[3])
        assert vertical(groups[0]) < 0
        assert vertical(groups[3]) > 0
        eps=rear_eps('1713',font)
        assert eps.startswith(b'%!PS-Adobe-3.0 EPSF-3.0')
        assert eps.count(b'closepath')>=10
        assert b'curveto' in eps
        assert b'showpage' in eps
        assert b'/Impact' not in eps and b'show ' not in eps
    finally:
        font.close()


def test_build_zip_has_one_complete_set_per_number(tmp_path):
    path=tmp_path/'taxi_set.zip'
    result=make_archive('1740,1713',path)
    assert result.numbers==('1740','1713')
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for n in ('1740','1713'):
            root=f'TAXI_{n}/{n}_'
            for ext in ('lewy.tif','prawy.tif','TYL.ai','TYL.eps','TYL.svg','TYL_PODGLAD.png'):
                assert root+ext in z.namelist()
            assert z.read(root+'TYL.ai') == z.read(root+'TYL.eps')
            assert b'%%BoundingBox' in z.read(root+'TYL.eps')
            assert Image.open(io.BytesIO(z.read(root+'lewy.tif'))).info['dpi']==(DPI,DPI)
        assert 'CZYTAJ_PRZED_CIECIEM.txt' in z.namelist()


def test_import_application_no_legacy_mail_dependency():
    import app
    assert hasattr(app,'TaxiGeneratorFrame')
    assert 'labels_ui' not in Path(app.__file__).read_text(encoding='utf-8')
