"""Test różnicowy planowania: engine.py z wybranej rewizji gita vs katalog roboczy.

Cel: udowodnić, że zmiana silnika nie zmienia dotychczasowych planów arkuszy
(kolejność stron, sloty, recto/verso) dla projektów, które nie używają nowych pól.

    python scripts/diff_planning.py                 # porównaj z HEAD, 3000 losowych konfiguracji
    python scripts/diff_planning.py --rev main~3 --runs 10000

Porównywana jest wyłącznie czysta logika planowania; PyMuPDF nie jest potrzebny
(dla starej wersji modułu podstawiany jest pusty zamiennik). Konfiguracje są losowe,
ale deterministyczne (ziarno stałe), a błędy walidacji też muszą być identyczne.
Skrypt zakłada, że `Job(path, copies, role, page_roles)` i `Settings(**kwargs)` są
zgodne wstecz — to jest właśnie to, co sprawdza.
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_old_engine(rev: str):
    source = subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{rev}:engine.py'], text=True)
    stub = types.ModuleType('pymupdf')
    for name in ('Page', 'Rect', 'Document', 'Matrix'):
        setattr(stub, name, type(name, (), {}))
    saved = sys.modules.get('pymupdf')
    sys.modules['pymupdf'] = stub
    module = types.ModuleType('engine_old')
    sys.modules['engine_old'] = module   # wymagane przez dataclasses
    try:
        exec(compile(source, f'engine@{rev}', 'exec'), module.__dict__)
    finally:
        if saved is None:
            sys.modules.pop('pymupdf', None)
        else:
            sys.modules['pymupdf'] = saved
    return module


def signature(module, jobs_spec, documents, settings):
    jobs = [module.Job(path, copies, role, dict(page_roles)) for path, copies, role, page_roles in jobs_spec]
    try:
        return [(side.sheet_number, side.side,
                 [(p.source.path, p.source.index) if p.source else None for p in side.placements],
                 [(round(p.slot.x, 6), round(p.slot.y, 6), p.slot.col, p.slot.row, p.slot.rotation)
                  for p in side.placements])
                for side in module.plan_sides(jobs, documents, module.Settings(**settings))]
    except ValueError as error:
        return ('ValueError', str(error))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--rev', default='HEAD', help='rewizja gita ze starym engine.py (domyślnie HEAD)')
    parser.add_argument('--runs', type=int, default=3000)
    parser.add_argument('--seed', type=int, default=20261020)
    args = parser.parse_args()

    old = load_old_engine(args.rev)
    sys.path.insert(0, str(ROOT))
    import engine as new

    rnd = random.Random(args.seed)
    all_roles = [new.ROLE_AUTO, new.ROLE_FRONT, new.ROLE_BACK, new.ROLE_SHARED, new.ROLE_SKIP]
    mostly_valid = [new.ROLE_AUTO] * 8 + [new.ROLE_FRONT, new.ROLE_SKIP]
    valid_plans = identical_errors = 0
    for n in range(args.runs):
        roles = all_roles if n % 2 else mostly_valid
        files = {f'/k/f{i}.pdf': rnd.randint(1, 9) for i in range(rnd.randint(1, 3))}
        documents = {path: [None] * pages for path, pages in files.items()}
        spec = [(path, rnd.randint(1, 3), rnd.choice(roles),
                 {str(rnd.randint(1, pages)): rnd.choice(roles) for _ in range(rnd.randint(0, 2))})
                for path, pages in files.items()]
        settings = dict(mode=rnd.choice(['Jednostronnie', 'Dwustronnie', 'Broszura']),
                        sheet_w=rnd.choice([100, 190, 450]), sheet_h=rnd.choice([60, 75, 320]),
                        trim_w=90, trim_h=50, bleed=rnd.choice([0, 2]), margin_x=4, margin_y=4,
                        gap_x=rnd.choice([0, 4]), gap_y=0, rotation=rnd.choice(['Auto', '0', '90']),
                        flip=rnd.choice(['Długa krawędź', 'Krótka krawędź']))
        before = signature(old, spec, documents, settings)
        after = signature(new, spec, documents, settings)
        if before != after:
            print('RÓŻNICA', spec, settings, before, after, sep='\n')
            return 1
        if isinstance(before, tuple) and before[:1] == ('ValueError',):
            identical_errors += 1
        else:
            valid_plans += 1
    print(f'identyczne plany względem {args.rev}: {valid_plans} poprawnych + {identical_errors} identycznych błędów walidacji '
          f'(razem {args.runs})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
