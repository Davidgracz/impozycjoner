"""Warstwa komend: jedyne miejsce, w którym UI zmienia model projektu.

Zasady (docs/architecture.md):
  * komenda jest niezależna od Tk i PyMuPDF — da się ją testować bez okna i bez PDF;
  * komenda waliduje dane w `apply`, a przy błędzie NIE zmienia projektu;
  * każda komenda jest odwracalna (`undo`), a `CommandStack` pamięta historię.

Na razie jest jedna funkcja pionowa: liczba powtórzeń każdej strony (F-AKC-REP),
ręcznie lub odczytana z nazwy pliku (reguła w naming.py). Interfejs UI dla cofania
nie jest jeszcze podłączony — patrz F-SYS-UNDO w docs/feature-parity.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from engine import Job, Project
from naming import MAX_REPEATS, RepeatParse, parse_repeats


class CommandError(ValueError):
    """Komenda odrzucona; projekt pozostaje bez zmian. Komunikat jest po polsku, dla operatora."""


class Command(Protocol):
    label: str

    def apply(self, project: Project) -> None: ...

    def undo(self, project: Project) -> None: ...


def _job(project: Project, index: int) -> Job:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(project.jobs):
        raise CommandError('Wybierz plik z listy po lewej stronie.')
    return project.jobs[index]


@dataclass
class SetPageRepeat:
    """Ustaw liczbę powtórzeń każdej strony pliku (p1,p1,…,p2,p2,…)."""

    job_index: int
    value: int
    source: RepeatParse | None = None  # niepuste, gdy wartość pochodzi z nazwy pliku
    label: str = 'Powtórzenia każdej strony'
    _previous: int | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_filename(cls, project: Project, job_index: int) -> 'SetPageRepeat':
        job = _job(project, job_index)
        parsed = parse_repeats(job.path)
        return cls(job_index, parsed.count, source=parsed,
                   label='Powtórzenia każdej strony z nazwy pliku')

    @property
    def message(self) -> str:
        """Jedno zdanie dla operatora: skąd wzięła się liczba."""
        if self.source is None:
            return f'Powtórzenia każdej strony: {self.value}.'
        p = self.source
        if not p.found_digits:
            return f'W nazwie „{p.stem}” nie ma cyfr — powtórzenia: 1.'
        where = 'po ostatnim „_”' if p.used_separator else 'w całej nazwie'
        return f'Z nazwy „{p.stem}” ({where}: „{p.fragment}”) odczytano {p.count}.'

    def apply(self, project: Project) -> None:
        job = _job(project, self.job_index)
        value = self.value
        if isinstance(value, bool) or not isinstance(value, int):
            raise CommandError('Liczba powtórzeń musi być liczbą całkowitą.')
        if value < 1:
            raise CommandError(f'Liczba powtórzeń musi być co najmniej 1 (odczytano {value}). '
                               'Plik pozostaje bez zmian.')
        if value > MAX_REPEATS:
            limit = f'{MAX_REPEATS:,}'.replace(',', ' ')
            raise CommandError(f'Liczba powtórzeń nie może przekraczać {limit}. '
                               'Plik pozostaje bez zmian.')
        self._previous = job.page_repeat
        job.page_repeat = value

    def undo(self, project: Project) -> None:
        if self._previous is None:
            return
        _job(project, self.job_index).page_repeat = self._previous
        self._previous = None


@dataclass(frozen=True)
class Outcome:
    """Wynik wykonania komendy w formie wygodnej dla UI (bez wyjątków)."""

    ok: bool
    message: str


def parse_int_field(text: str, what: str = 'Liczba powtórzeń') -> int:
    """Zamień tekst z pola wpisywania na liczbę całkowitą albo zgłoś CommandError."""
    try:
        return int(str(text).strip())
    except ValueError:
        raise CommandError(f'{what} musi być liczbą całkowitą.') from None


def execute(stack: 'CommandStack', factory) -> Outcome:
    """Zbuduj i wykonaj komendę; błędy walidacji zamień na komunikat dla operatora.

    `factory` jest wywoływana tutaj, bo budowa komendy też może się nie udać
    (np. zły numer pliku albo tekst, który nie jest liczbą).
    """
    try:
        command = factory()
        stack.run(command)
    except CommandError as error:
        return Outcome(False, str(error))
    return Outcome(True, getattr(command, 'message', command.label))


class CommandStack:
    """Historia wykonanych komend (cofnij / ponów). Nie zna UI ani plików."""

    def __init__(self, project: Project):
        self.project = project
        self._done: list[Command] = []
        self._undone: list[Command] = []

    def run(self, command: Command) -> None:
        command.apply(self.project)  # wyjątek => nic nie trafia do historii
        self._done.append(command)
        self._undone.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self._done)

    @property
    def can_redo(self) -> bool:
        return bool(self._undone)

    def undo(self) -> Command | None:
        if not self._done:
            return None
        command = self._done.pop()
        command.undo(self.project)
        self._undone.append(command)
        return command

    def redo(self) -> Command | None:
        if not self._undone:
            return None
        command = self._undone.pop()
        command.apply(self.project)
        self._done.append(command)
        return command
