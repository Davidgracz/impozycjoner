"""Small local, user-owned collection of per-printer duplex calibration profiles.

Profiles live outside project files in APPDATA on Windows. The selected offsets
and flip convention are also saved in the current .psimp project settings.
No printer data, tokens or passwords are stored.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from math import isfinite

FLIPS = ('Długa krawędź', 'Krótka krawędź')


def profile_path() -> Path:
    if os.name == 'nt' and os.environ.get('APPDATA'):
        base = Path(os.environ['APPDATA'])
    else:
        base = Path.home() / '.config'
    return base / 'Impozycjoner Studio' / 'duplex_profiles.json'


def _name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError('Nazwa profilu musi być tekstem.')
    name = name.strip()
    if not 1 <= len(name) <= 64 or any(ord(c) < 32 for c in name):
        raise ValueError('Nazwa profilu musi mieć 1–64 znaki bez znaków sterujących.')
    return name


def _offset(value: float) -> float:
    if type(value) not in (int, float) or not isfinite(value) or abs(value) > 20.0:
        raise ValueError('Przesunięcie musi być liczbą z zakresu −20…20 mm.')
    if abs(value * 10 - round(value * 10)) > 1e-6:
        raise ValueError('Kalibrację ustawiaj co 0,1 mm.')
    return round(float(value), 1)


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Uszkodzony plik profili kalibracji: {path}') from exc
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('profiles'), dict):
        raise ValueError('Nieobsługiwany format profili kalibracji.')
    profiles=data['profiles']
    for name, profile in profiles.items():
        _name(name)
        if not isinstance(profile, dict) or profile.get('flip') not in FLIPS:
            raise ValueError(f'Błędny profil: {name}')
        _offset(profile.get('x'))
        _offset(profile.get('y'))
    return profiles


def list_profiles(*, path: Path | None = None) -> list[str]:
    return sorted(_load(Path(path) if path is not None else profile_path()), key=str.casefold)


def read_profile(name: str, *, path: Path | None = None) -> dict:
    name = _name(name)
    profiles = _load(Path(path) if path is not None else profile_path())
    if name not in profiles:
        raise ValueError(f'Nie znaleziono profilu: {name}')
    return dict(profiles[name])


def _save(path: Path, profiles: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    try:
        tmp.write_text(json.dumps({'version':1, 'profiles':profiles}, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def store_profile(name: str, *, x: float, y: float, flip: str, path: Path | None = None):
    name = _name(name)
    x, y = _offset(x), _offset(y)
    if flip not in FLIPS:
        raise ValueError('Nieznany sposób odwracania arkusza.')
    destination = Path(path) if path is not None else profile_path()
    profiles = _load(destination)
    profiles[name] = {'x':x, 'y':y, 'flip':flip}
    _save(destination, profiles)


def remove_profile(name: str, *, path: Path | None = None):
    name = _name(name)
    destination = Path(path) if path is not None else profile_path()
    profiles = _load(destination)
    if name not in profiles:
        raise ValueError(f'Nie znaleziono profilu: {name}')
    del profiles[name]
    _save(destination, profiles)
