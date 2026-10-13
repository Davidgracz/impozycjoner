"""Production checks for Taxi Szczecin decal output and SVG cutter outlines."""
import io
import zipfile
import xml.etree.ElementTree as ET

import pytest
from PIL import Image
from taxi_generator import (
    parse_numbers,
    font_path,
    OutlinedText,
    make_archive,
    side_tiff,
    rear_svg,
    DPI,
)


def test_number_parser_accepts_batches_and_deduplicates():
    assert parse_numbers('1740, 1713\n034;1740') == ['1740', '1713', '034']


@pytest.mark.parametrize('bad', ['', '1740,foo', '1740/../../', '1740 zł', '1234567'])
def test_number_parser_rejects_unsafe_input(bad):
    with pytest.raises(ValueError):
        parse_numbers(bad)


def test_source_tiff_200dpi_and_native_size():
    from taxi_generator import template_path
    for side in ('lewy', 'prawy'):
        with Image.open(template_path(side)) as im:
            assert im.size == (2283, 1102)
            assert im.info['dpi'] == (200, 200)


def test_number_change_does_not_touch_crest_or_city():
    from taxi_generator import template_path
    font = OutlinedText(font_path())
    try:
        for side in ('lewy', 'prawy'):
            generated = Image.open(io.BytesIO(side_tiff('1713', side, font))).convert('RGB')
            source = Image.open(template_path(side)).convert('RGB')
            assert generated.crop((0, 780, 2283, 1102)).tobytes() == source.crop((0, 780, 2283, 1102)).tobytes()
            crest = (1650, 150) if side == 'lewy' else (250, 150)
            assert generated.getpixel(crest) == source.getpixel(crest)
            assert generated.size == source.size
            assert Image.open(io.BytesIO(side_tiff('1713', side, font))).info['dpi'] == (DPI, DPI)
    finally:
        font.close()


def test_reference_number_has_identical_original_pixels():
    from taxi_generator import template_path
    font = OutlinedText(font_path())
    try:
        for side in ('lewy', 'prawy'):
            original = Image.open(template_path(side)).convert('RGB')
            out = Image.open(io.BytesIO(side_tiff('1740', side, font))).convert('RGB')
            assert original.tobytes() == out.tobytes()
    finally:
        font.close()


def test_rear_vector_has_two_objects_and_requested_geometry():
    font = OutlinedText(font_path())
    try:
        xml = rear_svg('1713', font)
        doc = ET.fromstring(xml)
        assert doc.tag.endswith('svg')
        width = float(doc.attrib['width'].replace('mm', ''))
        height = float(doc.attrib['height'].replace('mm', ''))
        vb = [float(v) for v in doc.attrib['viewBox'].split()]
        assert vb[2] == pytest.approx(width)
        assert vb[3] == pytest.approx(height)
        groups = [node for node in doc if node.tag.endswith('g')]
        assert len(groups) == 2
        # Both groups should share normal top-down orientation (negative svg Y scale from font coordinates).
        def vertical(g):
            return float(g.attrib['transform'].replace('matrix(', '').replace(')', '').split()[3])
        assert vertical(groups[0]) < 0
        assert vertical(groups[1]) < 0
        # Number height fixed at 55 mm, city width fixed at 120 mm.
        nvals = [float(v) for v in groups[0].attrib['transform'].replace('matrix(', '').replace(')', '').split()]
        cvals = [float(v) for v in groups[1].attrib['transform'].replace('matrix(', '').replace(')', '').split()]
        _, nbox = font._shapes('1713')
        _, cbox = font._shapes('SZCZECIN')
        nheight = (nbox[3] - nbox[1]) * abs(nvals[3])
        cwidth = (cbox[2] - cbox[0]) * abs(cvals[0])
        assert nheight == pytest.approx(55.0, abs=0.2)
        assert cwidth == pytest.approx(120.0, abs=0.2)
    finally:
        font.close()


def test_build_zip_has_flat_files_only(tmp_path):
    path = tmp_path / 'taxi_set.zip'
    result = make_archive('1740,1713', path)
    assert result.numbers == ('1740', '1713')
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        names = set(z.namelist())
        for n in ('1740', '1713'):
            for filename in (f'{n}_lewy.tif', f'{n}_prawy.tif', f'{n}_tyl.svg'):
                assert filename in names
        assert not any('/' in name for name in names if name != 'CZYTAJ_PRZED_CIECIEM.txt')
        assert Image.open(io.BytesIO(z.read('1713_lewy.tif'))).info['dpi'] == (DPI, DPI)
        assert 'CZYTAJ_PRZED_CIECIEM.txt' in names
        txt = z.read('CZYTAJ_PRZED_CIECIEM.txt').decode('utf-8')
        assert '55 mm' in txt and '120 mm' in txt and 'SVG' in txt


def test_import_application_no_legacy_mail_dependency():
    import app
    assert hasattr(app, 'TaxiGeneratorFrame')
    assert 'labels_ui' not in app.__dict__
