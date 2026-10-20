"""F-NAR-*: czysta logika narzędzi stron (zakresy, tasowanie, powielanie, nazwy). Bez PyMuPDF.

Przypadki E1 pochodzą z tekstów okien oryginału (przykład zakresu, przykłady tasowania);
H — nasze decyzje z docs/imp4-wersja-finalna.md (H-13…H-18).
"""
import unittest

import pageops


class PageRangesFromOriginalHelp(unittest.TestCase):
    """E1 (P-40): przykład „-3, 6, 9-11, 15-”, dozwolone tylko cyfry, przecinek i minus."""

    def test_original_example(self):
        self.assertEqual(pageops.parse_page_ranges('-3, 6, 9-11, 15-', 17),
                         [1, 2, 3, 6, 9, 10, 11, 15, 16, 17])

    def test_other_characters_are_rejected(self):
        for text in ('1;3', '1..3', 'a', '2+3', '1–3'):  # ostatni: półpauza, nie minus
            with self.subTest(text=text), self.assertRaises(ValueError):
                pageops.parse_page_ranges(text, 10)


class PageRangesHypotheses(unittest.TestCase):
    """H-13: wynik rosnąco i bez powtórzeń, spacje dozwolone, strony spoza dokumentu to błąd."""

    def test_sorted_unique(self):
        self.assertEqual(pageops.parse_page_ranges('5, 1-3, 2', 9), [1, 2, 3, 5])

    def test_whole_document_with_open_ranges(self):
        self.assertEqual(pageops.parse_page_ranges('1-', 3), [1, 2, 3])
        self.assertEqual(pageops.parse_page_ranges('-2', 3), [1, 2])

    def test_errors(self):
        for text in ('', '   ', '-', '0', '5-3', '1,,2', '3,', '1-2-3', '12', '3-12', '1 2'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                pageops.parse_page_ranges(text, 10)


class ShuffleFromOriginalHelp(unittest.TestCase):
    """E1 (P-41): „1, 2, 3, 4 > 4, 3, 2, 1” dla stron i „1, 2, 3, 4 > 3, 4, 1, 2” dla kartek."""

    def test_pages(self):
        self.assertEqual(pageops.shuffle_order(4), [4, 3, 2, 1])

    def test_leaves(self):
        self.assertEqual(pageops.shuffle_order(4, leaves=True), [3, 4, 1, 2])
        self.assertEqual(pageops.shuffle_order(6, leaves=True), [5, 6, 3, 4, 1, 2])

    def test_single_page_and_odd_leaves_refused(self):
        with self.assertRaises(ValueError):
            pageops.shuffle_order(1)
        with self.assertRaises(ValueError):
            pageops.shuffle_order(5, leaves=True)
        self.assertEqual(pageops.shuffle_order(5), [5, 4, 3, 2, 1])


class DuplicateAndSplit(unittest.TestCase):
    def test_h14_selected_pages_repeat_in_place(self):
        self.assertEqual(pageops.duplicate_order(4, [2, 4], 3), [1, 2, 2, 2, 3, 4, 4, 4])

    def test_duplicate_errors(self):
        for args in ((4, [2], 1), (4, [], 2), (4, [5], 2), (4, [1], 1001)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                pageops.duplicate_order(*args)

    def test_h15_suffix_two_digits_at_least(self):
        self.assertEqual(pageops.page_suffix(3, 12), '--03')
        self.assertEqual(pageops.page_suffix(12, 12), '--12')
        self.assertEqual(pageops.page_suffix(7, 150), '--007')
        with self.assertRaises(ValueError):
            pageops.page_suffix(13, 12)

    def test_h16_chunks(self):
        self.assertEqual(pageops.chunks(7, 3), [[1, 2, 3], [4, 5, 6], [7]])
        for per_file in (0, 7, 8):
            with self.subTest(per_file=per_file), self.assertRaises(ValueError):
                pageops.chunks(7, per_file)

    def test_p43_cover_needs_five_pages(self):
        self.assertEqual(pageops.cover_and_body(8), ([1, 2, 7, 8], [3, 4, 5, 6]))
        with self.assertRaises(ValueError):
            pageops.cover_and_body(4)

    def test_even_odd(self):
        self.assertEqual(pageops.even_odd(5), ([1, 3, 5], [2, 4]))
        with self.assertRaises(ValueError):
            pageops.even_odd(1)

    def test_h18_rotation_adds_to_current(self):
        self.assertEqual(pageops.rotation_for(1, 90, 270), 0)
        self.assertEqual(pageops.rotation_for(2, 0, 90, even_extra_180=True), 270)
        self.assertEqual(pageops.rotation_for(3, 0, 90, even_extra_180=True), 90)
        with self.assertRaises(ValueError):
            pageops.rotation_for(1, 0, 45)


if __name__ == '__main__':
    unittest.main()
