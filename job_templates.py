"""Szablony prac: gotowe zestawy ustawień montażu (arkusz, netto, spad, odstępy, tryb...).

Szablon zawiera wyłącznie ustawienia *pracy*. Celowo NIE zawiera:
  * danych zależnych od plików (wymiar oryginału PDF, przesunięcia kadru),
  * kalibracji maszyny (przesunięcie verso X/Y, krawędź odwracania).
Kalibracja pozostaje w profilach maszyn (duplex_calibration.py). Szablon może
tylko wskazać NAZWĘ profilu maszyny, który program wczyta razem z szablonem.

Szablony użytkownika leżą poza plikami projektów, w APPDATA (Windows):
%APPDATA%\\Impozycjoner Studio\\job_templates.json. Szablony wbudowane są
tylko do odczytu i służą jako punkty startowe.
Moduł nie importuje silnika PDF, więc da się go używać bez PyMuPDF.
"""
from __future__ import annotations

import json
import os
from dataclasses import fields, is_dataclass, replace
from math import isfinite
from pathlib import Path

MODES = ('Jednostronnie', 'Dwustronnie', 'Broszura', 'Ekonomiczny')
ROTATIONS = ('Auto', '0', '90', '180', '270')
SCALE_MODES = ('Bez skalowania', 'Kadruj 1:1', 'Dopasuj', 'Wypełnij', 'Wypełnij ze spadem')

# pole -> (minimum, maksimum) w mm
_MM_RANGES = {
    'sheet_w': (10.0, 3000.0), 'sheet_h': (10.0, 3000.0),
    'trim_w': (1.0, 3000.0), 'trim_h': (1.0, 3000.0),
    'bleed': (0.0, 50.0),
    'gross_w': (0.0, 3000.0), 'gross_h': (0.0, 3000.0),  # 0 = liczone automatycznie
    'margin_x': (0.0, 500.0), 'margin_y': (0.0, 500.0),
    'gap_x': (0.0, 500.0), 'gap_y': (0.0, 500.0),
}
_INT_RANGES = {'columns': (0, 500), 'rows': (0, 500)}
_CHOICES = {'mode': MODES, 'rotation': ROTATIONS, 'scale_mode': SCALE_MODES}
_BOOLS = ('auto_gross', 'crop_marks', 'show_page_labels')
# Pola dodane później: opcjonalne, żeby starsze szablony użytkownika nadal się wczytywały.
_OPTIONAL_BOOLS = {'white_trim': False}

FIELDS = tuple(_MM_RANGES) + tuple(_INT_RANGES) + tuple(_CHOICES) + _BOOLS + tuple(_OPTIONAL_BOOLS)


def template_path() -> Path:
    if os.name == 'nt' and os.environ.get('APPDATA'):
        base = Path(os.environ['APPDATA'])
    else:
        base = Path.home() / '.config'
    return base / 'Impozycjoner Studio' / 'job_templates.json'


def _name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError('Nazwa szablonu musi być tekstem.')
    name = name.strip()
    if not 1 <= len(name) <= 64 or any(ord(c) < 32 for c in name):
        raise ValueError('Nazwa szablonu musi mieć 1–64 znaki bez znaków sterujących.')
    return name


def _clean(values) -> dict:
    """Sprawdza komplet pól szablonu i zwraca ich czystą kopię."""
    if not isinstance(values, dict):
        raise ValueError('Ustawienia szablonu muszą być słownikiem.')
    unknown = sorted(set(values) - set(FIELDS))
    if unknown:
        raise ValueError(f'Nieznane pola szablonu: {", ".join(unknown)}')
    missing = [key for key in FIELDS if key not in values and key not in _OPTIONAL_BOOLS]
    if missing:
        raise ValueError(f'Brakujące pola szablonu: {", ".join(missing)}')
    clean = {}
    for key, (low, high) in _MM_RANGES.items():
        value = values[key]
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError(f'{key}: wartość musi być skończoną liczbą.')
        if not low <= value <= high:
            raise ValueError(f'{key}: wartość spoza zakresu {low:g}…{high:g} mm.')
        clean[key] = round(float(value), 3)
    for key, (low, high) in _INT_RANGES.items():
        value = values[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key}: liczba całkowita z zakresu {low}…{high}.')
        clean[key] = value
    for key, allowed in _CHOICES.items():
        if values[key] not in allowed:
            raise ValueError(f'{key}: niedozwolona wartość „{values[key]}”.')
        clean[key] = values[key]
    for key in _BOOLS:
        if type(values[key]) is not bool:
            raise ValueError(f'{key}: wartość musi być prawda/fałsz.')
        clean[key] = values[key]
    for key, default in _OPTIONAL_BOOLS.items():
        value = values.get(key, default)
        if type(value) is not bool:
            raise ValueError(f'{key}: wartość musi być prawda/fałsz.')
        clean[key] = value
    return clean


def _machine(value) -> str | None:
    return None if value is None else _name(value)


def _sheet_job(name: str, trim_w: float, trim_h: float, mode: str, *,
               bleed: float = 2.0, scale_mode: str = 'Bez skalowania',
               white_trim: bool = False) -> tuple[str, dict]:
    """Punkt startowy: SRA3 450 × 320 mm, marginesy 6 mm, odstępy 5 mm, znaczniki cięcia."""
    return name, {
        'settings': {
            'sheet_w': 450.0, 'sheet_h': 320.0,
            'trim_w': float(trim_w), 'trim_h': float(trim_h), 'bleed': float(bleed),
            'gross_w': round(trim_w + 2 * bleed, 3), 'gross_h': round(trim_h + 2 * bleed, 3),
            'auto_gross': True,
            'margin_x': 6.0, 'margin_y': 6.0, 'gap_x': 5.0, 'gap_y': 5.0,
            'rotation': 'Auto', 'columns': 0, 'rows': 0,
            'mode': mode, 'scale_mode': scale_mode,
            'crop_marks': True, 'show_page_labels': False, 'white_trim': white_trim,
        },
        'machine': None,
    }


BUILTIN: dict[str, dict] = dict([
    _sheet_job('Wizytówka 93×53 z oryginału (kadr 1:1) — SRA3', 93, 53, 'Jednostronnie',
               bleed=1.5, scale_mode='Kadruj 1:1'),
    _sheet_job('Wizytówka 90×50 — SRA3 — jednostronnie', 90, 50, 'Jednostronnie'),
    _sheet_job('Wizytówka 90×50 — SRA3 — dwustronnie', 90, 50, 'Dwustronnie'),
    _sheet_job('Wizytówka 85×55 — SRA3 — dwustronnie', 85, 55, 'Dwustronnie'),
    _sheet_job('Ulotka A6 — SRA3 — dwustronnie', 105, 148, 'Dwustronnie'),
    _sheet_job('Ulotka A6 + 1,5 mm z A4 (bez białych marginesów) — SRA3',
               105, 148, 'Jednostronnie', bleed=1.5, scale_mode='Wypełnij ze spadem', white_trim=True),
    _sheet_job('Ulotka DL — SRA3 — dwustronnie', 99, 210, 'Dwustronnie'),
    _sheet_job('Ulotka A5 — SRA3 — dwustronnie', 148, 210, 'Dwustronnie'),
])


def _copy(entry: dict) -> dict:
    return {'settings': dict(entry['settings']), 'machine': entry['machine']}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Uszkodzony plik szablonów prac: {path}') from exc
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('templates'), dict):
        raise ValueError('Nieobsługiwany format szablonów prac.')
    result = {}
    for name, entry in data['templates'].items():
        _name(name)
        if not isinstance(entry, dict):
            raise ValueError(f'Błędny szablon: {name}')
        try:
            result[name] = {'settings': _clean(entry.get('settings')),
                            'machine': _machine(entry.get('machine'))}
        except ValueError as exc:
            raise ValueError(f'Błędny szablon „{name}”: {exc}') from exc
    return result


def _save(path: Path, templates: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    try:
        tmp.write_text(json.dumps({'version': 1, 'templates': templates},
                                  ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _resolve(path) -> Path:
    return Path(path) if path is not None else template_path()


def is_builtin(name: str) -> bool:
    key = _name(name).casefold()
    return any(key == builtin.casefold() for builtin in BUILTIN)


def list_templates(*, path: Path | None = None) -> list[str]:
    """Najpierw szablony wbudowane (kolejność z kodu), potem własne alfabetycznie."""
    own = sorted(_load(_resolve(path)), key=str.casefold)
    return list(BUILTIN) + own


def read_template(name: str, *, path: Path | None = None) -> dict:
    name = _name(name)
    if name in BUILTIN:
        return _copy(BUILTIN[name])
    own = _load(_resolve(path))
    if name not in own:
        raise ValueError(f'Nie znaleziono szablonu: {name}')
    return _copy(own[name])


def template_from_settings(settings) -> dict:
    """Wybiera z ustawień montażu tylko pola, które należą do szablonu."""
    return {key: getattr(settings, key) for key in FIELDS}


def store_template(name: str, settings, *, machine: str | None = None,
                   path: Path | None = None):
    """Zapisuje szablon użytkownika. `settings` to Settings albo słownik pól."""
    name = _name(name)
    if is_builtin(name):
        raise ValueError('Ta nazwa jest zarezerwowana dla szablonu wbudowanego. Wybierz inną.')
    values = template_from_settings(settings) if is_dataclass(settings) else settings
    entry = {'settings': _clean(values), 'machine': _machine(machine)}
    destination = _resolve(path)
    templates = _load(destination)
    for existing in [key for key in templates if key.casefold() == name.casefold()]:
        del templates[existing]   # ta sama nazwa z inną wielkością liter to ten sam szablon
    templates[name] = entry
    _save(destination, templates)


def remove_template(name: str, *, path: Path | None = None):
    name = _name(name)
    if is_builtin(name):
        raise ValueError('Szablonów wbudowanych nie można usunąć.')
    destination = _resolve(path)
    templates = _load(destination)
    if name not in templates:
        raise ValueError(f'Nie znaleziono szablonu: {name}')
    del templates[name]
    _save(destination, templates)


def apply_template(base, template: dict):
    """Zwraca kopię `base` z polami szablonu. Pozostałe ustawienia zostają bez zmian."""
    if not isinstance(template, dict):
        raise ValueError('Szablon musi być słownikiem.')
    settings = _clean(template.get('settings'))
    known = {f.name for f in fields(base)}
    if not set(settings) <= known:
        raise ValueError('Szablon zawiera pola nieobecne w ustawieniach programu.')
    return replace(base, **settings)
