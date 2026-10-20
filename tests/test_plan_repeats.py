"""F-AKC-REP, krok 3: silnik planuje powtórzenia stron (bez PyMuPDF).

`plan_sides` używa dokumentów wyłącznie przez `len(documents[path])`, więc
zamiast prawdziwych PDF-ów wystarczą listy o odpowiedniej długości. Dzięki temu
kolejność stron na arkuszach można sprawdzić bez renderowania.
"""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine import (Job, Project, Settings, ROLE_BACK, ROLE_FRONT, ROLE_SHARED, ROLE_SKIP,
                    load_project, plan_sides, save_project, validate_job_roles)

# Arkusz 190×60: dokładnie dwa użytki 90×50 obok siebie (pojemność 2).
TWO_UP = dict(sheet_w=190, sheet_h=60, trim_w=90, trim_h=50, bleed=0,
              margin_x=4, margin_y=4, gap_x=0, gap_y=0, crop_marks=False)
# Arkusz 100×75: jeden użytek na stronę arkusza (jak test_duplex_pairing).
ONE_UP = dict(sheet_w=100, sheet_h=75, trim_w=90, trim_h=50, bleed=0,
              margin_x=4, margin_y=4, gap_x=0, gap_y=0, crop_marks=False)


def docs(**pages):
    return {name: [None] * count for name, count in pages.items()}


def sources(sides):
    """[(strona arkusza)] -> lista krotek (nazwa, numer strony od 1) lub None dla pustego."""
    return [[(Path(p.source.path).name, p.source.index + 1) if p.source else None
             for p in side.placements] for side in sides]


def flat(sides):
    return [item for side in sources(sides) for item in side]


class SingleSidedRepeats(unittest.TestCase):
    def setUp(self):
        self.s = Settings(**TWO_UP)

    def plan(self, jobs, **pages):
        return list(plan_sides(jobs, docs(**pages), self.s))

    def test_default_keeps_previous_behaviour_whole_file_copies(self):
        # regresja: copies=2 powtarza cały plik (1,2,3,1,2,3), page_repeat=1 niczego nie zmienia
        sides = self.plan([Job('/k/a.pdf', 2)], **{'/k/a.pdf': 3})
        self.assertEqual(flat(sides), [('a.pdf', n) for n in (1, 2, 3, 1, 2, 3)])
        self.assertEqual(len(sides), 3)

    def test_each_page_is_repeated_consecutively(self):
        sides = self.plan([Job('/k/a.pdf', page_repeat=3)], **{'/k/a.pdf': 2})
        self.assertEqual(sources(sides), [[('a.pdf', 1), ('a.pdf', 1)],
                                          [('a.pdf', 1), ('a.pdf', 2)],
                                          [('a.pdf', 2), ('a.pdf', 2)]])

    def test_copies_cycle_over_repeated_pages(self):
        sides = self.plan([Job('/k/a.pdf', copies=2, page_repeat=2)], **{'/k/a.pdf': 2})
        self.assertEqual(flat(sides), [('a.pdf', n) for n in (1, 1, 2, 2, 1, 1, 2, 2)])

    def test_skipped_pages_are_not_repeated(self):
        job = Job('/k/a.pdf', page_repeat=2, page_roles={'2': ROLE_SKIP})
        sides = self.plan([job], **{'/k/a.pdf': 3})
        self.assertEqual(flat(sides), [('a.pdf', n) for n in (1, 1, 3, 3)])

    def test_each_job_has_its_own_repeat_in_file_order(self):
        jobs = [Job('/k/a.pdf', page_repeat=2), Job('/k/b.pdf', page_repeat=1)]
        sides = self.plan(jobs, **{'/k/a.pdf': 1, '/k/b.pdf': 2})
        self.assertEqual(flat(sides), [('a.pdf', 1), ('a.pdf', 1), ('b.pdf', 1), ('b.pdf', 2)])

    def test_sheet_count_follows_total_impressions(self):
        # 3 strony × 7 powtórzeń = 21 odbitek, 2 na arkusz ⇒ 11 arkuszy
        sides = self.plan([Job('/k/a.pdf', page_repeat=7)], **{'/k/a.pdf': 3})
        self.assertEqual(len(sides), 11)
        self.assertEqual(len(flat(sides)), 21)

    def test_invalid_repeat_is_rejected_by_the_engine_too(self):
        for bad in (0, -1):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    validate_job_roles([Job('/k/a.pdf', page_repeat=bad)], docs(**{'/k/a.pdf': 1}))
                with self.assertRaises(ValueError):
                    self.plan([Job('/k/a.pdf', page_repeat=bad)], **{'/k/a.pdf': 1})


class DuplexRepeats(unittest.TestCase):
    def setUp(self):
        self.s = Settings(mode='Dwustronnie', **ONE_UP)

    def plan(self, jobs, **pages):
        return list(plan_sides(jobs, docs(**pages), self.s))

    def test_default_legacy_pairs_unchanged(self):
        sides = self.plan([Job('/k/a.pdf')], **{'/k/a.pdf': 4})
        self.assertEqual(flat(sides), [('a.pdf', n) for n in (1, 2, 3, 4)])

    def test_legacy_pairs_repeat_together_recto_and_verso(self):
        sides = self.plan([Job('/k/a.pdf', page_repeat=2)], **{'/k/a.pdf': 4})
        self.assertEqual(flat(sides), [('a.pdf', n) for n in (1, 2, 1, 2, 3, 4, 3, 4)])
        self.assertEqual([(x.sheet_number, x.side) for x in sides],
                         [(1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1), (4, 0), (4, 1)])

    def test_explicit_fronts_and_backs_stay_paired_when_both_repeat(self):
        jobs = [Job('/k/f.pdf', role=ROLE_FRONT, page_repeat=2),
                Job('/k/b.pdf', role=ROLE_BACK, page_repeat=2)]
        sides = self.plan(jobs, **{'/k/f.pdf': 2, '/k/b.pdf': 2})
        self.assertEqual(flat(sides), [('f.pdf', 1), ('b.pdf', 1), ('f.pdf', 1), ('b.pdf', 1),
                                       ('f.pdf', 2), ('b.pdf', 2), ('f.pdf', 2), ('b.pdf', 2)])

    def test_unequal_repeats_of_fronts_and_backs_are_reported(self):
        jobs = [Job('/k/f.pdf', role=ROLE_FRONT, page_repeat=2), Job('/k/b.pdf', role=ROLE_BACK)]
        with self.assertRaises(ValueError) as ctx:
            self.plan(jobs, **{'/k/f.pdf': 2, '/k/b.pdf': 2})
        self.assertIn('Tyłów jest 2, przodów 4', str(ctx.exception))

    def test_shared_back_is_under_every_repeated_front(self):
        job = Job('/k/c.pdf', page_repeat=2, page_roles={'3': ROLE_SHARED})
        sides = self.plan([job], **{'/k/c.pdf': 3})
        self.assertEqual(flat(sides), [('c.pdf', 1), ('c.pdf', 3), ('c.pdf', 1), ('c.pdf', 3),
                                       ('c.pdf', 2), ('c.pdf', 3), ('c.pdf', 2), ('c.pdf', 3)])


class BookletRepeats(unittest.TestCase):
    S = Settings(sheet_w=200, sheet_h=70, trim_w=90, trim_h=50, bleed=0,
                 margin_x=4, margin_y=4, gap_x=4, mode='Broszura', crop_marks=False)

    def test_booklet_without_repeat_is_unchanged(self):
        sides = list(plan_sides([Job('/k/book.pdf')], docs(**{'/k/book.pdf': 8}), self.S))
        self.assertEqual(len(sides), 4)
        self.assertEqual(sources(sides)[0], [('book.pdf', 8), ('book.pdf', 1)])

    def test_booklet_refuses_page_repeat_instead_of_guessing(self):
        with self.assertRaises(ValueError) as ctx:
            list(plan_sides([Job('/k/book.pdf', page_repeat=2)], docs(**{'/k/book.pdf': 8}), self.S))
        self.assertIn('Broszura', str(ctx.exception))


class ProjectFile(unittest.TestCase):
    def roundtrip(self, project):
        with tempfile.TemporaryDirectory() as d:
            name = Path(d) / 'p.psimp'
            save_project(project, str(name))
            with zipfile.ZipFile(name) as z:
                raw = json.loads(z.read('project.json'))
            return raw, load_project(str(name))

    def test_default_repeat_is_not_written_so_old_files_stay_identical(self):
        raw, loaded = self.roundtrip(Project(jobs=[Job('/tmp/x.pdf', 3)]))
        self.assertNotIn('page_repeat', raw['jobs'][0])
        self.assertEqual(raw['version'], 1)
        self.assertEqual(loaded.jobs[0].page_repeat, 1)
        self.assertEqual(loaded.jobs[0].copies, 3)

    def test_repeat_is_persisted(self):
        raw, loaded = self.roundtrip(Project(jobs=[Job('/tmp/x.pdf', 2, page_repeat=300)]))
        self.assertEqual(raw['jobs'][0]['page_repeat'], 300)
        self.assertEqual((loaded.jobs[0].copies, loaded.jobs[0].page_repeat), (2, 300))

    def test_files_saved_by_older_versions_load_with_repeat_one(self):
        with tempfile.TemporaryDirectory() as d:
            name = Path(d) / 'old.psimp'
            with zipfile.ZipFile(name, 'w') as z:
                z.writestr('project.json', json.dumps({
                    'format': 'psimp', 'version': 1, 'settings': vars(Settings()),
                    'jobs': [{'path': 'card.pdf', 'copies': 4}]}))
            job = load_project(str(name)).jobs[0]
        self.assertEqual((job.copies, job.page_repeat, job.role), (4, 1, 'Normalnie'))

    def test_positional_job_constructor_is_backward_compatible(self):
        job = Job('/k/a.pdf', 2, ROLE_FRONT, {'1': ROLE_SKIP})
        self.assertEqual((job.copies, job.role, job.page_roles, job.page_repeat),
                         (2, ROLE_FRONT, {'1': ROLE_SKIP}, 1))


if __name__ == '__main__':
    unittest.main()
