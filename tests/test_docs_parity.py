"""Spójność dokumentacji zgodności (docs/feature-parity.md, docs/behavior-spec.md).

Te testy nie dowodzą, że funkcje działają. Pilnują, żeby dokument nie twierdził więcej,
niż da się sprawdzić mechanicznie: statusy, istnienie wskazanych testów, wpis o przebiegu
dla `working`/`verified`, definicje hipotez i pytań otwartych używanych w kodzie.
"""
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('parity_tool', ROOT / 'scripts' / 'parity.py')
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


def row(fid='F-TST-ONE', deps='—', status='missing', evidence='E1', test='PLAN: coś'):
    return f'| {fid} | Funkcja | {deps} | {status} | {evidence} | {test} |'


def doc(*rows):
    table = '\n'.join(rows)
    return f'{table}\n\n{parity.write_summary(table)[len(table):]}'


class RealDocument(unittest.TestCase):
    def test_feature_parity_table_is_consistent(self):
        text = (ROOT / 'docs' / 'feature-parity.md').read_text(encoding='utf-8')
        self.assertEqual(parity.check(text, ROOT), [])

    def test_every_hypothesis_and_open_question_used_in_the_repo_is_defined(self):
        spec_text = (ROOT / 'docs' / 'behavior-spec.md').read_text(encoding='utf-8')
        # definicja = nagłówek („### H-01 — …”) albo pierwsza komórka wiersza tabeli („| OQ-05 | …”)
        defined = set(re.findall(r'^#{2,4}\s+((?:H|OQ)-\d{2})\b', spec_text, re.MULTILINE))
        defined |= set(re.findall(r'^\|\s*((?:H|OQ)-\d{2})\s*\|', spec_text, re.MULTILINE))
        used = set()
        sources = [*ROOT.glob('*.py'), *(ROOT / 'tests').glob('*.py'), *(ROOT / 'docs').glob('*.md'),
                   ROOT / 'AGENTS.md']
        for path in sources:
            if path.name == 'test_docs_parity.py':
                continue
            used |= set(re.findall(r'\b((?:H|OQ)-\d{2})\b', path.read_text(encoding='utf-8')))
        self.assertEqual(sorted(used - defined), [], 'użyte, ale niezdefiniowane w docs/behavior-spec.md')

    def test_required_documents_exist(self):
        for name in ('AGENTS.md', 'docs/feature-parity.md', 'docs/behavior-spec.md',
                     'docs/architecture.md', 'docs/roadmap.md'):
            self.assertTrue((ROOT / name).is_file(), name)


class LintCatchesMistakes(unittest.TestCase):
    """Lint musi umieć się pogniewać; inaczej „zielony” dokument nic nie znaczy."""

    def problems(self, *rows):
        return parity.check(doc(*rows), ROOT)

    def test_clean_minimal_table_passes(self):
        self.assertEqual(self.problems(row()), [])

    def test_unknown_status_is_reported(self):
        self.assertTrue(any('nieznany status' in p for p in self.problems(row(status='done'))))

    def test_duplicate_ids_and_unknown_dependencies(self):
        p = self.problems(row(), row(), row('F-TST-TWO', deps='F-TST-NOPE'))
        self.assertTrue(any('powtórzony' in x for x in p))
        self.assertTrue(any('nieznana zależność' in x for x in p))

    def test_dependency_cycle(self):
        p = self.problems(row('F-TST-A', deps='F-TST-B'), row('F-TST-B', deps='F-TST-A'))
        self.assertTrue(any('cykl' in x for x in p))

    def test_nonexistent_test_is_reported(self):
        t = '`tests/test_naming.py::NoSuchTest` Przebieg: 2026-10-20'
        self.assertTrue(any('nie istnieje' in p for p in self.problems(row(status='working', test=t))))

    def test_working_requires_test_and_run_entry(self):
        no_test = self.problems(row(status='working', test='coś bez testu Przebieg: 2026-10-20'))
        no_run = self.problems(row(status='working', test='`tests/test_naming.py::OriginalHelpExamples`'))
        self.assertTrue(any('wymaga co najmniej jednego' in p for p in no_test))
        self.assertTrue(any('Przebieg' in p for p in no_run))

    def test_dagger_status_needs_no_run_entry_but_needs_a_test(self):
        ok = self.problems(row(status='working†', test='`tests/test_naming.py::OriginalHelpExamples`'))
        self.assertEqual(ok, [])
        bad = self.problems(row(status='working†', test='brak'))
        self.assertTrue(any('wymaga co najmniej jednego' in p for p in bad))

    def test_verified_needs_original_evidence(self):
        t = '`tests/test_naming.py::OriginalHelpExamples` Przebieg: 2026-10-20'
        own_only = self.problems(row(status='verified', evidence='E4', test=t))
        self.assertTrue(any('verified wymaga dowodu E1 lub E3' in p for p in own_only))
        self.assertEqual(self.problems(row(status='verified', evidence='E1', test=t)), [])

    def test_missing_and_partial_need_a_plan(self):
        for status in ('missing', 'partial'):
            p = self.problems(row(status=status, test='tests/test_naming.py'))
            self.assertTrue(any('PLAN' in x for x in p), status)

    def test_evidence_level_is_mandatory(self):
        self.assertTrue(any('poziomu dowodu' in p for p in self.problems(row(evidence='z głowy'))))

    def test_stale_summary_is_reported(self):
        text = doc(row()).replace('| missing | 1 |', '| missing | 7 |')
        self.assertTrue(any('Podsumowanie' in p for p in parity.check(text, ROOT)))


if __name__ == '__main__':
    unittest.main()
