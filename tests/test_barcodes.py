"""F-NAR-EAN13: kody EAN-13 / EAN-8. Wartości oczekiwane z publicznej normy GS1 (nie z oryginału).

Część czysta działa bez PyMuPDF; test PDF jest pomijany, gdy biblioteki brak.
"""
import unittest

import barcodes


class CheckDigitFromStandard(unittest.TestCase):
    def test_known_codes(self):
        # Przykłady powszechnie używane w dokumentacji normy: 400638133393(1), 9638507(4), 590123412345(7)
        self.assertEqual(barcodes.check_digit('400638133393'), 1)
        self.assertEqual(barcodes.check_digit('9638507'), 4)
        self.assertEqual(barcodes.check_digit('590123412345'), 7)

    def test_e1_lengths(self):
        # E1 (P-44): EAN-13 ma 12 albo 13 cyfr, EAN-8 — 7 albo 8
        self.assertEqual(barcodes.normalize('400638133393'), '4006381333931')
        self.assertEqual(barcodes.normalize('4006381333931'), '4006381333931')
        self.assertEqual(barcodes.normalize('9638507', 'EAN8'), '96385074')
        for value, kind in (('40063813339', 'EAN13'), ('40063813339312', 'EAN13'),
                            ('963850', 'EAN8'), ('963850741', 'EAN8')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                barcodes.normalize(value, kind)

    def test_wrong_check_digit_and_non_digits(self):
        for value in ('4006381333932', '40063813339a', '４００６３８１３３３９３'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                barcodes.normalize(value)


class ModulePattern(unittest.TestCase):
    def test_ean13_structure(self):
        p = barcodes.modules('4006381333931')
        self.assertEqual(len(p), 95)
        self.assertEqual((p[:3], p[45:50], p[-3:]), ('101', '01010', '101'))
        # pierwsza cyfra 4 → parzystość LGLLGG; druga cyfra 0 kodowana L = 0001101
        self.assertEqual(p[3:10], '0001101')
        # trzecia cyfra 0 w zestawie G = 0100111
        self.assertEqual(p[10:17], '0100111')
        # prawa połowa: ostatnia cyfra 1 w zestawie R = 1100110
        self.assertEqual(p[85:92], '1100110')

    def test_ean8_structure(self):
        p = barcodes.modules('96385074')
        self.assertEqual(len(p), 67)
        self.assertEqual((p[:3], p[31:36], p[-3:]), ('101', '01010', '101'))
        self.assertEqual(p[3:10], '0001011')  # 9 w zestawie L

    def test_every_digit_is_two_bars_and_two_spaces(self):
        p = barcodes.modules('5901234123457')
        for start in list(range(3, 45, 7)) + list(range(50, 92, 7)):
            digit = p[start:start + 7]
            runs = len([i for i in range(7) if i == 0 or digit[i] != digit[i - 1]])
            self.assertEqual(runs, 4, digit)

    def test_bars_runs(self):
        self.assertEqual(barcodes.bars('0110100111'), [(1, 2), (4, 1), (7, 3)])


class ReadCodes(unittest.TestCase):
    def test_bad_lines_reported_and_skipped(self):
        good, bad = barcodes.read_codes('400638133393\n\nabc\n5901234123457\n')
        self.assertEqual(good, ['4006381333931', '5901234123457'])
        self.assertEqual([n for n, _ in bad], [3])

    def test_no_valid_line_is_an_error(self):
        with self.assertRaises(ValueError):
            barcodes.read_codes('abc\n\n12')


class PdfOutput(unittest.TestCase):
    def test_vector_bars_on_own_page(self):
        try:
            import pymupdf as fitz
        except ImportError:
            self.skipTest('brak PyMuPDF')
        import tempfile, os
        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, 'kody.pdf')
            self.assertEqual(barcodes.export_pdf(['4006381333931', '96385074'], out), 2)
            with fitz.open(out) as doc:
                drawings = doc[0].get_drawings()
                rects = [item for d in drawings for item in d['items'] if item[0] == 're']
                self.assertEqual(len(rects), 30)  # EAN-13 ma zawsze 30 kresek
                self.assertEqual(doc[0].get_images(), [])
                # cyfry czytelne dla człowieka w trzech grupach: 4 | 006381 | 333931
                self.assertEqual(doc[0].get_text().split(), ['4', '006381', '333931'])
                w_mm = doc[0].rect.width * 25.4 / 72
                self.assertAlmostEqual(w_mm, 113 * 0.33, places=2)
                rects8 = [item for d in doc[1].get_drawings() for item in d['items'] if item[0] == 're']
                self.assertEqual(len(rects8), 22)  # EAN-8: 22 kreski


if __name__ == '__main__':
    unittest.main()
