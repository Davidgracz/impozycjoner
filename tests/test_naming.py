"""F-AKC-REP, krok 1: odczyt liczby powtórzeń z nazwy pliku (czysta logika).

Uruchomienie: `python -m pytest -q tests/test_naming.py` albo
`python -m unittest tests.test_naming` (nie wymaga PyMuPDF ani Tk).

Przypadki oznaczone E1 pochodzą z tekstu pomocy oryginału (przykłady tam podane),
oznaczone H to nasze hipotezy — opisane w docs/behavior-spec.md i NIE są
potwierdzone obserwacją oryginału. Zmiana hipotezy wymaga zmiany obu miejsc.
"""
import unittest

from naming import MAX_REPEATS, parse_repeats, repeats_from_filename


class OriginalHelpExamples(unittest.TestCase):
    """E1: cztery przykłady z pomocy oryginału (Impozycjoner 4.0.4.0)."""

    def test_digits_after_last_underscore_with_trailing_letter(self):
        self.assertEqual(repeats_from_filename('Arkusz_300s.pdf'), 300)

    def test_only_last_underscore_segment_counts(self):
        self.assertEqual(repeats_from_filename('Ulotka_dla_sklepu_500stron.pdf'), 500)

    def test_no_underscore_uses_whole_name(self):
        self.assertEqual(repeats_from_filename('Dyplom200.pdf'), 200)

    def test_no_digits_means_one(self):
        self.assertEqual(repeats_from_filename('Instrukcja.pdf'), 1)

    def test_run_example_from_calculator_help(self):
        # E1 (kalkulator nakładów): „test_2000.pdf” → 2000
        self.assertEqual(repeats_from_filename('test_2000.pdf'), 2000)


class LiteralReadingOfTheRule(unittest.TestCase):
    """E1, dosłowne brzmienie reguły: po ostatnim „_”, tylko cyfry, brak cyfr = 1."""

    def test_digits_before_underscore_are_ignored(self):
        self.assertEqual(repeats_from_filename('500_Ulotka.pdf'), 1)

    def test_digits_in_earlier_segments_do_not_leak(self):
        self.assertEqual(repeats_from_filename('A4_2024_wizytowka.pdf'), 1)
        self.assertEqual(repeats_from_filename('A4_2024_wizytowka_50.pdf'), 50)

    def test_non_digits_are_removed_not_split(self):
        # „usunięcie znaków innych niż cyfry” ⇒ 5x10 staje się 510 (nie 5 ani 10)
        self.assertEqual(repeats_from_filename('plik_5x10.pdf'), 510)

    def test_parse_reports_how_the_value_was_found(self):
        p = parse_repeats('Arkusz_300s.pdf')
        self.assertEqual((p.stem, p.fragment, p.digits, p.used_separator, p.found_digits),
                         ('Arkusz_300s', '300s', '300', True, True))
        q = parse_repeats('Instrukcja.pdf')
        self.assertEqual((q.count, q.digits, q.found_digits, q.used_separator), (1, '', False, False))


class HypothesesNotConfirmedByTheOriginal(unittest.TestCase):
    """H-01…H-04 z docs/behavior-spec.md. Zmiana tych zachowań wymaga aktualizacji specyfikacji."""

    def test_h01_pdf_extension_is_not_part_of_the_name(self):
        self.assertEqual(repeats_from_filename('Dyplom200.PDF'), 200)
        self.assertEqual(parse_repeats('Dyplom200.pdf').stem, 'Dyplom200')

    def test_h02_ascii_digits_only(self):
        # indeks górny „²” i cyfry arabsko-indyjskie nie są traktowane jako cyfry
        self.assertEqual(repeats_from_filename('plik_²5.pdf'), 5)
        self.assertEqual(repeats_from_filename('plik_٣.pdf'), 1)

    def test_h03_empty_fragment_after_underscore_is_one(self):
        self.assertEqual(repeats_from_filename('Arkusz_.pdf'), 1)
        self.assertEqual(repeats_from_filename('_.pdf'), 1)

    def test_h04_directories_are_ignored_for_both_separators(self):
        self.assertEqual(repeats_from_filename('C:\\prace_100\\Ulotka.pdf'), 1)
        self.assertEqual(repeats_from_filename('/prace_100/Ulotka_7.pdf'), 7)

    def test_leading_zeros_and_zero_are_returned_as_read(self):
        # walidacja zakresu należy do warstwy komend, nie parsera
        self.assertEqual(repeats_from_filename('x_007.pdf'), 7)
        self.assertEqual(repeats_from_filename('x_000.pdf'), 0)

    def test_huge_numbers_do_not_overflow_the_parser(self):
        self.assertGreater(repeats_from_filename('x_' + '9' * 30 + '.pdf'), MAX_REPEATS)

    def test_non_text_input_is_rejected(self):
        with self.assertRaises(TypeError):
            repeats_from_filename(None)  # type: ignore[arg-type]


if __name__ == '__main__':
    unittest.main()
