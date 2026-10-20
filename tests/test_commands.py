"""F-AKC-REP, krok 2: warstwa komend (bez UI, bez PyMuPDF)."""
import unittest

from commands import CommandError, CommandStack, SetPageRepeat, execute, parse_int_field
from engine import Job, Project
from naming import MAX_REPEATS


def project_with(*names):
    return Project(jobs=[Job(f'/prace/{n}') for n in names])


class SetPageRepeatTests(unittest.TestCase):
    def test_manual_value_is_applied_to_the_selected_job_only(self):
        p = project_with('a.pdf', 'b.pdf')
        SetPageRepeat(1, 12).apply(p)
        self.assertEqual([j.page_repeat for j in p.jobs], [1, 12])

    def test_from_filename_reads_the_name_rule(self):
        p = project_with('Arkusz_300s.pdf', 'Instrukcja.pdf')
        SetPageRepeat.from_filename(p, 0).apply(p)
        SetPageRepeat.from_filename(p, 1).apply(p)
        self.assertEqual([j.page_repeat for j in p.jobs], [300, 1])

    def test_message_explains_where_the_number_came_from(self):
        p = project_with('Arkusz_300s.pdf', 'Instrukcja.pdf', 'Dyplom200.pdf')
        m = [SetPageRepeat.from_filename(p, i).message for i in range(3)]
        self.assertIn('300', m[0])
        self.assertIn('po ostatnim „_”', m[0])
        self.assertIn('nie ma cyfr', m[1])
        self.assertIn('w całej nazwie', m[2])

    def test_invalid_values_are_rejected_and_do_not_change_the_job(self):
        p = project_with('a.pdf')
        p.jobs[0].page_repeat = 4
        for bad in (0, -3, MAX_REPEATS + 1, 2.5, '7', True, None):
            with self.subTest(value=bad):
                with self.assertRaises(CommandError):
                    SetPageRepeat(0, bad).apply(p)  # type: ignore[arg-type]
                self.assertEqual(p.jobs[0].page_repeat, 4)

    def test_zero_in_the_name_is_reported_not_silently_replaced(self):
        p = project_with('praca_000.pdf')
        with self.assertRaises(CommandError) as ctx:
            SetPageRepeat.from_filename(p, 0).apply(p)
        self.assertIn('0', str(ctx.exception))
        self.assertEqual(p.jobs[0].page_repeat, 1)

    def test_no_selection_or_stale_index_is_a_clear_error(self):
        p = project_with('a.pdf')
        for index in (-1, 1, None, True):
            with self.subTest(index=index):
                with self.assertRaises(CommandError):
                    SetPageRepeat(index, 2).apply(p)  # type: ignore[arg-type]
        with self.assertRaises(CommandError):
            SetPageRepeat.from_filename(Project(), 0)

    def test_undo_restores_previous_value(self):
        p = project_with('a_5.pdf')
        c = SetPageRepeat.from_filename(p, 0)
        c.apply(p)
        self.assertEqual(p.jobs[0].page_repeat, 5)
        c.undo(p)
        self.assertEqual(p.jobs[0].page_repeat, 1)


class CommandStackTests(unittest.TestCase):
    def test_run_undo_redo(self):
        p = project_with('a.pdf')
        stack = CommandStack(p)
        stack.run(SetPageRepeat(0, 3))
        stack.run(SetPageRepeat(0, 9))
        self.assertEqual(p.jobs[0].page_repeat, 9)
        stack.undo()
        self.assertEqual(p.jobs[0].page_repeat, 3)
        stack.undo()
        self.assertEqual(p.jobs[0].page_repeat, 1)
        self.assertFalse(stack.can_undo)
        self.assertIsNone(stack.undo())
        stack.redo()
        stack.redo()
        self.assertEqual(p.jobs[0].page_repeat, 9)
        self.assertFalse(stack.can_redo)

    def test_failed_command_is_not_recorded(self):
        p = project_with('a.pdf')
        stack = CommandStack(p)
        with self.assertRaises(CommandError):
            stack.run(SetPageRepeat(0, 0))
        self.assertFalse(stack.can_undo)

    def test_new_command_clears_redo_history(self):
        p = project_with('a.pdf')
        stack = CommandStack(p)
        stack.run(SetPageRepeat(0, 2))
        stack.undo()
        self.assertTrue(stack.can_redo)
        stack.run(SetPageRepeat(0, 4))
        self.assertFalse(stack.can_redo)


class UiBoundaryTests(unittest.TestCase):
    """Funkcje, na których opierają się procedury obsługi przycisków w app.py."""

    def test_parse_int_field(self):
        self.assertEqual(parse_int_field(' 12 '), 12)
        for bad in ('', 'abc', '1,5', '2.0', None):
            with self.subTest(text=bad):
                with self.assertRaises(CommandError):
                    parse_int_field(bad)  # type: ignore[arg-type]

    def test_execute_reports_success_with_explanation(self):
        p = project_with('Dyplom200.pdf')
        stack = CommandStack(p)
        outcome = execute(stack, lambda: SetPageRepeat.from_filename(p, 0))
        self.assertTrue(outcome.ok)
        self.assertIn('200', outcome.message)
        self.assertEqual(p.jobs[0].page_repeat, 200)
        self.assertTrue(stack.can_undo)

    def test_execute_turns_every_validation_failure_into_a_message(self):
        p = project_with('a.pdf')
        stack = CommandStack(p)
        for factory in (lambda: SetPageRepeat(0, parse_int_field('x')),
                        lambda: SetPageRepeat(0, 0),
                        lambda: SetPageRepeat(5, 2),
                        lambda: SetPageRepeat.from_filename(p, 3)):
            outcome = execute(stack, factory)
            self.assertFalse(outcome.ok)
            self.assertTrue(outcome.message)
        self.assertEqual(p.jobs[0].page_repeat, 1)
        self.assertFalse(stack.can_undo)


if __name__ == '__main__':
    unittest.main()
