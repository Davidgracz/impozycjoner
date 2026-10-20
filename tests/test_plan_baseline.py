"""Testy charakteryzujące dotychczasowe zachowanie warstwy planowania (bez PyMuPDF).

Cel: mieć uruchamialne wszędzie (też bez PyMuPDF i Tk) dowody, że istniejące funkcje
silnika — siatka, kolejność stron, dupleks, role, broszura — nie zmieniają się przy
rozbudowie. Oczekiwania pochodzą z istniejących testów repozytorium (tests/test_engine.py)
albo z ręcznego rachunku geometrii; NIE są obserwacjami oryginalnego programu (to E4).
"""
import unittest
from pathlib import Path
from unittest import mock

import engine
from engine import (Job, Settings, ROLE_AUTO, ROLE_BACK, ROLE_FRONT, ROLE_SHARED, ROLE_SKIP,
                    Slot, _draw_marks, _duplex_pairs, geometry, plan_sides, pt, scaling_layout, validate)

TWO_UP = dict(sheet_w=190, sheet_h=60, trim_w=90, trim_h=50, bleed=0,
              margin_x=4, margin_y=4, gap_x=0, gap_y=0, crop_marks=False)


def docs(**pages):
    return {name: [None] * count for name, count in pages.items()}


def pairs(jobs, **pages):
    return [(None if f is None else (Path(f.path).name, f.index + 1),
             None if b is None else (Path(b.path).name, b.index + 1))
            for f, b in _duplex_pairs(jobs, docs(**pages))]


class GridGeometry(unittest.TestCase):
    def test_default_sra3_grid(self):
        g = geometry(Settings())
        self.assertEqual((g.cols, g.rows, g.capacity, g.rotation), (7, 3, 21, 90))

    def test_rotation_180_and_270_are_accepted(self):
        self.assertEqual(geometry(Settings(rotation='180')).rotation, 180)
        self.assertEqual(geometry(Settings(rotation='270')).rotation, 270)

    def test_auto_rotation_finds_more_items(self):
        s = Settings(sheet_w=210, sheet_h=297, trim_w=90, trim_h=50, margin_x=5, margin_y=5,
                     gap_x=2, gap_y=2, bleed=0, rotation='Auto')
        self.assertGreaterEqual(geometry(s).capacity, 8)

    def test_impossible_grid_is_an_error(self):
        with self.assertRaises(ValueError):
            geometry(Settings(sheet_w=30, sheet_h=30, trim_w=90, trim_h=50))

    def test_two_up_slots_are_centred_with_known_coordinates(self):
        g = geometry(Settings(**TWO_UP))
        self.assertEqual((g.cols, g.rows, g.capacity, g.rotation), (2, 1, 2, 0))
        self.assertEqual([(s.x, s.y, s.w, s.h) for s in g.slots],
                         [(5.0, 5.0, 90, 50), (95.0, 5.0, 90, 50)])

    def test_validation_rejects_nonsense(self):
        for kwargs in (dict(trim_w=0), dict(sheet_h=-1), dict(bleed=-0.1), dict(columns=-1),
                       dict(rotation='45'), dict(mode='Trójstronnie'), dict(flip='Przekątna'),
                       dict(scale_mode='Rozciągnij'), dict(trim_w=float('nan'))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                validate(Settings(**kwargs))


class SingleSidedOrder(unittest.TestCase):
    def test_pages_fill_slots_row_major_and_sheets_in_order(self):
        sides = list(plan_sides([Job('/k/a.pdf')], docs(**{'/k/a.pdf': 3}), Settings(**TWO_UP)))
        self.assertEqual([[p.source.index + 1 for p in s.placements] for s in sides], [[1, 2], [3]])
        self.assertEqual([(s.sheet_number, s.side) for s in sides], [(1, 0), (2, 0)])

    def test_copies_repeat_the_whole_file(self):
        sides = list(plan_sides([Job('/k/a.pdf', 2)], docs(**{'/k/a.pdf': 3}), Settings(**TWO_UP)))
        self.assertEqual([p.source.index + 1 for s in sides for p in s.placements], [1, 2, 3, 1, 2, 3])

    def test_no_jobs_means_no_sheets(self):
        self.assertEqual(list(plan_sides([], {}, Settings(**TWO_UP))), [])


class DuplexRolesCharacterisation(unittest.TestCase):
    def test_legacy_pairs_with_odd_last_page(self):
        self.assertEqual(pairs([Job('/k/automatic.pdf')], **{'/k/automatic.pdf': 5}),
                         [(('automatic.pdf', 1), ('automatic.pdf', 2)),
                          (('automatic.pdf', 3), ('automatic.pdf', 4)),
                          (('automatic.pdf', 5), None)])

    def test_two_files_front_and_repeated_shared_back(self):
        result = pairs([Job('/k/fronts.pdf', role=ROLE_FRONT), Job('/k/backs.pdf', role=ROLE_SHARED)],
                       **{'/k/fronts.pdf': 7, '/k/backs.pdf': 1})
        self.assertEqual([f[1] for f, _ in result], list(range(1, 8)))
        self.assertEqual([b for _, b in result], [('backs.pdf', 1)] * 7)

    def test_one_shared_page_inside_a_file_the_rest_are_fronts(self):
        result = pairs([Job('/k/mix.pdf', page_roles={'13': ROLE_SHARED})], **{'/k/mix.pdf': 22})
        self.assertEqual([f[1] for f, _ in result], list(range(1, 13)) + list(range(14, 23)))
        self.assertTrue(all(b == ('mix.pdf', 13) for _, b in result))

    def test_separate_front_and_back_files_pair_by_position(self):
        result = pairs([Job('/k/f.pdf', role=ROLE_FRONT), Job('/k/b.pdf', role=ROLE_BACK)],
                       **{'/k/f.pdf': 3, '/k/b.pdf': 3})
        self.assertEqual(result, [(('f.pdf', i), ('b.pdf', i)) for i in (1, 2, 3)])

    def test_mixed_roles_do_not_cross_legacy_job_boundaries(self):
        jobs = [Job('/k/normal.pdf'), Job('/k/front.pdf', role=ROLE_FRONT), Job('/k/back.pdf', role=ROLE_BACK)]
        self.assertEqual(pairs(jobs, **{'/k/normal.pdf': 3, '/k/front.pdf': 2, '/k/back.pdf': 2}),
                         [(('normal.pdf', 1), ('normal.pdf', 2)), (('normal.pdf', 3), None),
                          (('front.pdf', 1), ('back.pdf', 1)), (('front.pdf', 2), ('back.pdf', 2))])

    def test_skip_removes_a_page_from_both_sides(self):
        jobs = [Job('/k/a.pdf', role=ROLE_FRONT, page_roles={'2': ROLE_SKIP}), Job('/k/b.pdf', role=ROLE_BACK)]
        self.assertEqual(pairs(jobs, **{'/k/a.pdf': 3, '/k/b.pdf': 2}),
                         [(('a.pdf', 1), ('b.pdf', 1)), (('a.pdf', 3), ('b.pdf', 2))])

    def test_inconsistent_assignments_are_rejected(self):
        cases = {
            'dwa różne tyły wspólne': ([Job('/k/a.pdf', page_roles={'1': ROLE_SHARED, '2': ROLE_SHARED})],
                                       {'/k/a.pdf': 3}),
            'tyły bez przodów': ([Job('/k/b.pdf', role=ROLE_BACK)], {'/k/b.pdf': 2}),
            'za dużo tyłów': ([Job('/k/f.pdf', role=ROLE_FRONT), Job('/k/b.pdf', role=ROLE_BACK)],
                              {'/k/f.pdf': 1, '/k/b.pdf': 2}),
            'za mało tyłów': ([Job('/k/f.pdf', role=ROLE_FRONT), Job('/k/b.pdf', role=ROLE_BACK)],
                              {'/k/f.pdf': 3, '/k/b.pdf': 1}),
            'wspólny tył bez przodów': ([Job('/k/s.pdf', role=ROLE_SHARED)], {'/k/s.pdf': 1}),
            'strona poza zakresem': ([Job('/k/a.pdf', page_roles={'9': ROLE_FRONT})], {'/k/a.pdf': 2}),
            'nieznana rola': ([Job('/k/a.pdf', role='Dziwna')], {'/k/a.pdf': 2}),
        }
        for name, (jobs, pages) in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                pairs(jobs, **pages)


class DuplexFlipCharacterisation(unittest.TestCase):
    def test_verso_slots_are_mirrored_by_selected_edge(self):
        for edge in ('Długa krawędź', 'Krótka krawędź'):
            with self.subTest(edge=edge):
                s = Settings(mode='Dwustronnie', bleed=0, flip=edge)
                jobs = [Job('/k/a.pdf', role=ROLE_FRONT), Job('/k/b.pdf', role=ROLE_SHARED)]
                front, back = list(plan_sides(jobs, docs(**{'/k/a.pdf': 5, '/k/b.pdf': 1}), s))
                self.assertEqual(len(front.placements), len(back.placements))
                for f, v in zip(front.placements, back.placements):
                    if edge == 'Długa krawędź':
                        self.assertAlmostEqual(f.slot.x, v.slot.x, places=2)
                        self.assertAlmostEqual(s.sheet_h - f.slot.y - f.slot.h, v.slot.y, places=2)
                    else:
                        self.assertAlmostEqual(f.slot.y, v.slot.y, places=2)
                        self.assertAlmostEqual(s.sheet_w - f.slot.x - f.slot.w, v.slot.x, places=2)

    def test_recto_and_verso_share_sheet_numbers(self):
        s = Settings(mode='Dwustronnie', sheet_w=100, sheet_h=75, trim_w=90, trim_h=50, bleed=0,
                     gap_x=0, gap_y=0, margin_x=4, margin_y=4, crop_marks=False)
        sides = list(plan_sides([Job('/k/d.pdf')], docs(**{'/k/d.pdf': 4}), s))
        self.assertEqual([(x.sheet_number, x.side) for x in sides], [(1, 0), (1, 1), (2, 0), (2, 1)])
        self.assertEqual([x.placements[0].source.index + 1 for x in sides], [1, 2, 3, 4])


class BookletCharacterisation(unittest.TestCase):
    S = Settings(sheet_w=200, sheet_h=70, trim_w=90, trim_h=50, bleed=0,
                 margin_x=4, margin_y=4, gap_x=4, mode='Broszura', crop_marks=False)

    def plan(self, jobs, **pages):
        sides = list(plan_sides(jobs, docs(**pages), self.S))
        return [[None if p.source is None else p.source.index + 1 for p in s.placements] for s in sides]

    def test_eight_pages_saddle_stitch_order(self):
        self.assertEqual(self.plan([Job('/k/b.pdf')], **{'/k/b.pdf': 8}),
                         [[8, 1], [2, 7], [6, 3], [4, 5]])

    def test_incomplete_signature_is_padded_with_blank_pages_to_multiple_of_four(self):
        self.assertEqual(self.plan([Job('/k/b.pdf')], **{'/k/b.pdf': 6}),
                         [[None, 1], [2, None], [6, 3], [4, 5]])

    def test_skipped_pages_are_removed_before_imposition(self):
        job = Job('/k/b.pdf', page_roles={'5': ROLE_SKIP, '6': ROLE_SKIP})
        self.assertEqual(self.plan([job], **{'/k/b.pdf': 6}), [[4, 1], [2, 3]])

    def test_only_one_file_at_a_time(self):
        with self.assertRaises(ValueError):
            self.plan([Job('/k/a.pdf'), Job('/k/b.pdf')], **{'/k/a.pdf': 4, '/k/b.pdf': 4})

    def test_spread_must_fit_on_the_sheet(self):
        small = Settings(sheet_w=150, sheet_h=70, trim_w=90, trim_h=50, bleed=0, margin_x=4,
                         margin_y=4, gap_x=4, mode='Broszura')
        with self.assertRaises(ValueError):
            list(plan_sides([Job('/k/b.pdf')], docs(**{'/k/b.pdf': 4}), small))

    def test_all_pages_skipped_is_an_error(self):
        with self.assertRaises(ValueError):
            self.plan([Job('/k/b.pdf', role=ROLE_SKIP)], **{'/k/b.pdf': 4})


class RecordingPage:
    """Atrapa strony PDF zapisująca wywołania draw_line (tylko do testu geometrii znaczników)."""

    def __init__(self):
        self.lines = []

    def draw_line(self, a, b, color=None, width=None):
        self.lines.append((a, b, color, width))


class MarksCharacterisation(unittest.TestCase):
    S = Settings(**TWO_UP)

    def test_full_set_of_eight_hairline_marks_per_item(self):
        page = RecordingPage()
        _draw_marks(page, Slot(5, 5, 90, 50, 0, 0, 0), self.S)
        self.assertEqual(len(page.lines), 8)
        self.assertTrue(all(w == 0.25 and c == (0, 0, 0) for _, _, c, w in page.lines))
        # lewa dolna: pozioma kreska 3 mm kończąca się 0,8 mm od krawędzi użytku (spad = 0)
        rounded = [tuple(round(v, 6) for v in (*a, *b)) for a, b, _, _ in page.lines]
        self.assertIn(tuple(round(v, 6) for v in (pt(4.2), pt(55), pt(1.2), pt(55))), rounded)

    def test_marks_that_would_leave_the_sheet_are_not_drawn(self):
        page = RecordingPage()
        _draw_marks(page, Slot(1, 5, 90, 50, 0, 0, 0), self.S)  # lewe znaczniki wyszłyby poza arkusz
        self.assertEqual(len(page.lines), 6)

    def test_marks_start_after_the_bleed(self):
        page = RecordingPage()
        s = Settings(**{**TWO_UP, 'bleed': 2})
        _draw_marks(page, Slot(10, 10, 90, 50, 0, 0, 0), s)
        starts = sorted(round(a[0] / pt(1), 3) for a, _, _, _ in page.lines if a[1] == pt(10))
        self.assertEqual(starts, [7.2, 102.8])  # 10 − (2 + 0,8) oraz 100 + (2 + 0,8)


class ScalingLayoutCharacterisation(unittest.TestCase):
    def test_fit_fill_and_none(self):
        self.assertEqual(scaling_layout(210, 297, 105, 148.5, 'Dopasuj'), (0.5, 0.0, 0.0))
        scale, dx, dy = scaling_layout(100, 100, 50, 100, 'Dopasuj')
        self.assertEqual((scale, dx, dy), (0.5, 0.0, 25.0))     # letterbox w pionie
        scale, dx, dy = scaling_layout(100, 100, 50, 100, 'Wypełnij')
        self.assertEqual((scale, dx, dy), (1.0, -25.0, 0.0))    # kadrowanie w poziomie
        self.assertEqual(scaling_layout(100, 100, 50, 100, 'Bez skalowania'), (1.0, -25.0, 0.0))

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            scaling_layout(0, 10, 10, 10, 'Dopasuj')
        with self.assertRaises(ValueError):
            scaling_layout(10, 10, 10, 10, 'Rozciągnij')


class MissingPyMuPDF(unittest.TestCase):
    def test_clear_error_instead_of_attribute_error(self):
        with mock.patch.object(engine, 'fitz', None):
            for call in (lambda: engine.open_sources([Job('/k/a.pdf')]),
                         lambda: engine.source_summary('/k/a.pdf')):
                with self.assertRaises(RuntimeError) as ctx:
                    call()
                self.assertIn('PyMuPDF', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
