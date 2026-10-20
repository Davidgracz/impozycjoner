"""Szablony prac: zgodność z silnikiem, zapis lokalny i walidacja."""
from __future__ import annotations

from dataclasses import fields, replace
import json

import pytest

import job_templates as jt
from engine import Settings, geometry, validate


def test_every_template_field_exists_in_settings():
    names = {f.name for f in fields(Settings)}
    assert set(jt.FIELDS) <= names


def test_templates_do_not_carry_machine_or_file_data():
    # Kalibracja maszyny i dane z plików zostają poza szablonem.
    for key in ('verso_shift_x', 'verso_shift_y', 'flip', 'source_w', 'source_h', 'auto_source'):
        assert key not in jt.FIELDS


def test_allowed_choices_match_engine_validation():
    for value in jt.MODES:
        validate(replace(Settings(), mode=value))
    for value in jt.ROTATIONS:
        validate(replace(Settings(), rotation=value))
    for value in jt.SCALE_MODES:
        validate(replace(Settings(), scale_mode=value))


@pytest.mark.parametrize('name', list(jt.BUILTIN))
def test_builtin_templates_are_valid_and_fit_on_sheet(name):
    template = jt.read_template(name)
    settings = jt.apply_template(Settings(), template)
    validate(settings)
    assert geometry(settings).capacity >= 1


def test_builtin_card_from_original_matches_known_sra3_layout():
    # README 0.4.0/0.4.1: brutto 96 × 56 mm na SRA3 daje 21 użytków (7 × 3, obrót 90).
    name = 'Wizytówka 93×53 z oryginału (kadr 1:1) — SRA3'
    settings = jt.apply_template(Settings(), jt.read_template(name))
    assert (settings.trim_w, settings.trim_h, settings.bleed) == (93.0, 53.0, 1.5)
    assert (settings.gross_w, settings.gross_h) == (96.0, 56.0)
    g = geometry(settings)
    assert (g.cols, g.rows, g.capacity, g.rotation) == (7, 3, 21, 90)


def test_builtin_90x50_matches_engine_default_layout():
    settings = jt.apply_template(Settings(), jt.read_template('Wizytówka 90×50 — SRA3 — jednostronnie'))
    g = geometry(settings)
    assert (g.cols, g.rows, g.capacity, g.rotation) == (7, 3, 21, 90)


def test_apply_changes_only_template_fields():
    base = replace(Settings(), verso_shift_x=0.7, verso_shift_y=-0.4, flip='Krótka krawędź',
                   source_w=110, source_h=70, auto_source=True)
    result = jt.apply_template(base, jt.read_template('Ulotka A5 — SRA3 — dwustronnie'))
    assert (result.trim_w, result.trim_h, result.mode) == (148.0, 210.0, 'Dwustronnie')
    for key in ('verso_shift_x', 'verso_shift_y', 'flip', 'source_w', 'source_h', 'auto_source'):
        assert getattr(result, key) == getattr(base, key)


def test_builtin_templates_cannot_be_changed_through_a_copy():
    template = jt.read_template('Ulotka A5 — SRA3 — dwustronnie')
    template['settings']['trim_w'] = 1.0
    assert jt.read_template('Ulotka A5 — SRA3 — dwustronnie')['settings']['trim_w'] == 148.0


def test_list_has_builtins_first_then_own_sorted(tmp_path):
    path = tmp_path / 'templates.json'
    assert jt.list_templates(path=path) == list(jt.BUILTIN)
    jt.store_template('zeta', Settings(), path=path)
    jt.store_template('Alfa', Settings(), path=path)
    assert jt.list_templates(path=path) == list(jt.BUILTIN) + ['Alfa', 'zeta']


def test_store_read_roundtrip_with_machine(tmp_path):
    path = tmp_path / 'sub' / 'templates.json'
    settings = replace(Settings(), trim_w=85, trim_h=55, mode='Dwustronnie', columns=3, rows=2,
                       crop_marks=False)
    jt.store_template('  Moja wizytówka  ', settings, machine='Konica', path=path)
    loaded = jt.read_template('Moja wizytówka', path=path)
    assert loaded['machine'] == 'Konica'
    assert loaded['settings'] == jt.template_from_settings(settings)
    again = jt.apply_template(Settings(), loaded)
    assert (again.trim_w, again.trim_h, again.columns, again.rows, again.crop_marks) == (85.0, 55.0, 3, 2, False)
    assert not list(path.parent.glob('*.tmp'))


def test_store_without_machine_keeps_none(tmp_path):
    path = tmp_path / 't.json'
    jt.store_template('x', Settings(), path=path)
    assert jt.read_template('x', path=path)['machine'] is None


def test_store_accepts_plain_dict(tmp_path):
    path = tmp_path / 't.json'
    jt.store_template('x', jt.template_from_settings(Settings()), path=path)
    assert jt.read_template('x', path=path)['settings']['trim_w'] == 90.0


def test_overwrite_and_case_insensitive_same_name(tmp_path):
    path = tmp_path / 't.json'
    jt.store_template('Karta', replace(Settings(), trim_w=80), path=path)
    jt.store_template('KARTA', replace(Settings(), trim_w=81), path=path)
    own = [n for n in jt.list_templates(path=path) if n not in jt.BUILTIN]
    assert own == ['KARTA']
    assert jt.read_template('KARTA', path=path)['settings']['trim_w'] == 81.0


def test_builtin_names_are_reserved(tmp_path):
    path = tmp_path / 't.json'
    name = 'Ulotka A5 — SRA3 — dwustronnie'
    with pytest.raises(ValueError, match='zarezerwowana'):
        jt.store_template(name, Settings(), path=path)
    with pytest.raises(ValueError, match='zarezerwowana'):
        jt.store_template(name.upper(), Settings(), path=path)
    with pytest.raises(ValueError, match='wbudowanych'):
        jt.remove_template(name, path=path)
    assert not path.exists()


def test_remove_and_missing(tmp_path):
    path = tmp_path / 't.json'
    jt.store_template('x', Settings(), path=path)
    jt.remove_template('x', path=path)
    assert 'x' not in jt.list_templates(path=path)
    with pytest.raises(ValueError, match='Nie znaleziono'):
        jt.remove_template('x', path=path)
    with pytest.raises(ValueError, match='Nie znaleziono'):
        jt.read_template('x', path=path)


@pytest.mark.parametrize('bad', ['', '   ', 'a' * 65, 'ab\x00c', 'line\nbreak', None, 5])
def test_invalid_names_rejected(tmp_path, bad):
    with pytest.raises(ValueError):
        jt.store_template(bad, Settings(), path=tmp_path / 't.json')


@pytest.mark.parametrize('change', [
    {'trim_w': float('nan')}, {'trim_w': float('inf')}, {'trim_w': 0}, {'trim_w': -5},
    {'sheet_w': 5}, {'bleed': -1}, {'bleed': 51}, {'gap_x': -0.1}, {'margin_y': 501},
    {'gross_w': -1}, {'columns': -1}, {'columns': 1.5}, {'rows': True},
    {'mode': 'Inny'}, {'rotation': '45'}, {'scale_mode': 'Rozciągnij'},
    {'crop_marks': 1}, {'auto_gross': 'tak'}, {'trim_w': True}, {'trim_h': '50'},
])
def test_invalid_values_rejected(tmp_path, change):
    values = jt.template_from_settings(Settings()) | change
    with pytest.raises(ValueError):
        jt.store_template('x', values, path=tmp_path / 't.json')


def test_unknown_and_missing_fields_rejected(tmp_path):
    values = jt.template_from_settings(Settings())
    with pytest.raises(ValueError, match='Nieznane'):
        jt.store_template('x', values | {'flip': 'Długa krawędź'}, path=tmp_path / 't.json')
    values.pop('bleed')
    with pytest.raises(ValueError, match='Brakujące'):
        jt.store_template('x', values, path=tmp_path / 't.json')


def test_invalid_machine_name_rejected(tmp_path):
    with pytest.raises(ValueError):
        jt.store_template('x', Settings(), machine='a' * 65, path=tmp_path / 't.json')


def test_corrupt_and_foreign_files_are_reported(tmp_path):
    path = tmp_path / 't.json'
    path.write_text('{ nie json', encoding='utf-8')
    with pytest.raises(ValueError, match='Uszkodzony'):
        jt.list_templates(path=path)
    path.write_text(json.dumps({'version': 2, 'templates': {}}), encoding='utf-8')
    with pytest.raises(ValueError, match='Nieobsługiwany'):
        jt.list_templates(path=path)
    bad = {'version': 1, 'templates': {'x': {'settings': {'trim_w': 90}, 'machine': None}}}
    path.write_text(json.dumps(bad), encoding='utf-8')
    with pytest.raises(ValueError, match='Błędny szablon'):
        jt.list_templates(path=path)


def test_failed_store_does_not_damage_existing_file(tmp_path):
    path = tmp_path / 't.json'
    jt.store_template('good', Settings(), path=path)
    before = path.read_text(encoding='utf-8')
    with pytest.raises(ValueError):
        jt.store_template('bad', jt.template_from_settings(Settings()) | {'mode': 'X'}, path=path)
    assert path.read_text(encoding='utf-8') == before


def test_apply_rejects_non_template_input():
    with pytest.raises(ValueError):
        jt.apply_template(Settings(), None)
    with pytest.raises(ValueError):
        jt.apply_template(Settings(), {'settings': {'trim_w': 90}, 'machine': None})
