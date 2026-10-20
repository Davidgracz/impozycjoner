"""Kontrola spójności docs/feature-parity.md (bez zależności zewnętrznych).

Użycie:
    python scripts/parity.py            # sprawdź tabelę, wypisz podsumowanie, kod wyjścia 1 przy błędach
    python scripts/parity.py --write    # dodatkowo przepisz blok „Podsumowanie” w dokumencie

Skrypt nie uruchamia testów i nie potrafi stwierdzić, że test przeszedł. Pilnuje tylko,
żeby dokument nie obiecywał więcej, niż da się sprawdzić mechanicznie:
  * statusy należą do słownika, identyfikatory są unikalne, zależności istnieją i nie tworzą cykli,
  * każdy wskazany test (`tests/plik.py::Nazwa`) naprawdę istnieje,
  * `working` i `verified` wymagają testu oraz wpisu „Przebieg: RRRR-MM-DD”,
  * `verified` wymaga dowodu E1 lub E3 (oczekiwane wartości nie mogą pochodzić tylko z naszego kodu),
  * brakujące i częściowe funkcje mają opisany plan testu akceptacyjnego („PLAN: …”),
  * liczby w podsumowaniu zgadzają się z tabelą.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs' / 'feature-parity.md'

STATUSES = ('missing', 'partial', 'working', 'working†', 'verified')
ID_RE = re.compile(r'^F-[A-Z]{3}-[A-Z0-9]{2,12}$')
ROW_RE = re.compile(r'^\|\s*(F-[A-Z]+-[A-Z0-9]+)\s*\|')
TEST_RE = re.compile(r'`(tests/[\w./-]+\.py)::(\w+)`')
RUN_RE = re.compile(r'Przebieg:\s*\d{4}-\d{2}-\d{2}')
SUMMARY_START = '<!-- PODSUMOWANIE:START -->'
SUMMARY_END = '<!-- PODSUMOWANIE:END -->'


def parse_rows(text: str) -> list[dict]:
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not ROW_RE.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append({'line': number, 'cells': cells,
                     **(dict(zip(('id', 'name', 'deps', 'status', 'evidence', 'test'), cells))
                        if len(cells) == 6 else {})})
    return rows


def _test_exists(root: Path, file: str, name: str) -> bool:
    path = root / file
    if not path.is_file():
        return False
    source = path.read_text(encoding='utf-8')
    return re.search(rf'^\s*(?:def|class)\s+{re.escape(name)}\b', source, re.MULTILINE) is not None


def summary_table(rows: list[dict]) -> str:
    counts = Counter(r['status'] for r in rows if 'status' in r)
    lines = ['| Status | Liczba |', '|---|---|']
    lines += [f'| {status} | {counts.get(status, 0)} |' for status in STATUSES]
    lines.append(f'| razem | {sum(counts.values())} |')
    return '\n'.join(lines)


def check(text: str, root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    rows = parse_rows(text)
    if not rows:
        return ['Brak wierszy funkcji w tabeli (oczekiwano linii zaczynających się od „| F-…”).']
    ids: dict[str, dict] = {}
    for r in rows:
        where = f'linia {r["line"]}'
        if 'id' not in r:
            problems.append(f'{where}: wiersz ma {len(r["cells"])} kolumn zamiast 6')
            continue
        fid = r['id']
        if not ID_RE.match(fid):
            problems.append(f'{where}: zły format identyfikatora {fid!r}')
        if fid in ids:
            problems.append(f'{where}: powtórzony identyfikator {fid}')
        ids[fid] = r
        if r['status'] not in STATUSES:
            problems.append(f'{where} {fid}: nieznany status {r["status"]!r} (dozwolone: {", ".join(STATUSES)})')
    for fid, r in ids.items():
        where = f'linia {r["line"]} {fid}'
        status, test, evidence = r['status'], r['test'], r['evidence']
        refs = TEST_RE.findall(test)
        for file, name in refs:
            if not _test_exists(root, file, name):
                problems.append(f'{where}: test `{file}::{name}` nie istnieje')
        if not re.search(r'\bE[1-4]\b', evidence):
            problems.append(f'{where}: brak oznaczenia poziomu dowodu (E1–E4)')
        if status in ('working', 'working†', 'verified') and not refs:
            problems.append(f'{where}: status {status} wymaga co najmniej jednego istniejącego testu')
        if status in ('working', 'verified') and not RUN_RE.search(test):
            problems.append(f'{where}: status {status} wymaga wpisu „Przebieg: RRRR-MM-DD” z uruchomienia testów')
        if status == 'working†' and RUN_RE.search(test) and 'Nieuruchomione' not in test:
            problems.append(f'{where}: working† z wpisem Przebieg — opisz też „Nieuruchomione:” albo zmień status')
        if status == 'verified' and not re.search(r'\bE[13]\b', evidence):
            problems.append(f'{where}: verified wymaga dowodu E1 lub E3, a nie tylko E2/E4')
        if status in ('missing', 'partial') and not test.startswith('PLAN:'):
            problems.append(f'{where}: status {status} wymaga opisu planu testu akceptacyjnego („PLAN: …”)')
        deps = [] if r['deps'] in ('', '—', '-') else [d.strip() for d in r['deps'].split(',')]
        for d in deps:
            if d == fid:
                problems.append(f'{where}: funkcja zależy od samej siebie')
            elif d not in ids:
                problems.append(f'{where}: nieznana zależność {d}')
        r['_deps'] = deps
    # cykle zależności
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]):
        if state.get(node) == 1:
            problems.append('cykl zależności: ' + ' → '.join(path + [node]))
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for dep in ids[node].get('_deps', []):
            if dep in ids:
                visit(dep, path + [node])
        state[node] = 2

    for fid in ids:
        visit(fid, [])
    # podsumowanie
    if SUMMARY_START in text and SUMMARY_END in text:
        block = text.split(SUMMARY_START, 1)[1].split(SUMMARY_END, 1)[0].strip()
        if block != summary_table([r for r in rows if 'status' in r]):
            problems.append('blok „Podsumowanie” nie zgadza się z tabelą (uruchom: python scripts/parity.py --write)')
    else:
        problems.append('brak bloku „Podsumowanie” (znaczniki PODSUMOWANIE:START/END)')
    return problems


def write_summary(text: str) -> str:
    rows = [r for r in parse_rows(text) if 'status' in r]
    block = f'{SUMMARY_START}\n{summary_table(rows)}\n{SUMMARY_END}'
    if SUMMARY_START in text and SUMMARY_END in text:
        head, rest = text.split(SUMMARY_START, 1)
        tail = rest.split(SUMMARY_END, 1)[1]
        return head + block + tail
    return text + '\n' + block + '\n'


def main(argv: list[str]) -> int:
    text = DOC.read_text(encoding='utf-8')
    if '--write' in argv:
        updated = write_summary(text)
        if updated != text:
            DOC.write_text(updated, encoding='utf-8')
            text = updated
    problems = check(text)
    print(summary_table([r for r in parse_rows(text) if 'status' in r]))
    for p in problems:
        print('BŁĄD:', p)
    print('OK' if not problems else f'{len(problems)} problem(ów)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
