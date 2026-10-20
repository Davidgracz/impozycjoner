"""Zakładka „Programy dodatkowe” — cienki interfejs do pdftools.py i barcodes.py (Tkinter).

Cała logika (zakresy, kolejność, nazwy, walidacja) jest poza UI; tu tylko zbieramy pola,
wywołujemy narzędzie i pokazujemy wynik albo komunikat błędu po polsku.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import barcodes
import pdftools

PANEL = '#ffffff'
ACCENT = '#2f6fc2'
MUTED = '#66768a'
TEXT = '#1f2933'

RANGE_HELP = 'Zakres, np. -3, 6, 9-11, 15- (tylko cyfry, przecinek i minus). Puste = wszystkie strony.'


@dataclass(frozen=True)
class Tool:
    name: str
    hint: str
    output: str            # 'folder' | 'file'
    suffix: str = ''       # domyślny dopisek nazwy dla 'file'
    range_field: str = ''  # '' | 'optional' | 'required'
    number: str = ''       # etykieta pola liczbowego ('' = brak)
    options: tuple[str, ...] = ()
    many_inputs: bool = False
    text_input: bool = False


TOOLS = (
    Tool('Rozdziel na pojedyncze strony', 'Każda strona w osobnym pliku: nazwa--01.pdf, nazwa--02.pdf…',
         'folder', range_field='optional'),
    Tool('Połącz pliki PDF', 'Łączy pliki w kolejności listy (co najmniej 2).', 'file', '--polaczone',
         many_inputs=True),
    Tool('Wydziel strony z zakresu', 'Zapisuje wskazane strony do nowego pliku.', 'folder',
         range_field='required', options=('Każda strona w osobnym pliku', 'Utwórz też plik bez stron wydzielonych')),
    Tool('Wydziel parzyste i nieparzyste', 'Dwa pliki: nazwa--nieparzyste.pdf i nazwa--parzyste.pdf.', 'folder'),
    Tool('Wydziel okładkę i wkład', 'Okładka = strony 1, 2, przedostatnia i ostatnia (min. 5 stron).', 'folder'),
    Tool('Wydziel zakresy po N stron', 'Kolejne pliki po N stron; ostatni może być krótszy.', 'folder',
         number='Stron w każdym pliku:'),
    Tool('Obróć strony', 'Kąt dodaje się do bieżącego obrotu strony.', 'file', '--obrot',
         range_field='optional', number='Kąt (0, 90, 180, 270):', options=('Dla stron parzystych dodaj +180°',)),
    Tool('Powiel strony', 'Każda wskazana strona N razy pod rząd.', 'file', '--powielone',
         range_field='optional', number='Powiel × (2–1000):'),
    Tool('Tasuj strony / kartki', 'Strony: 1,2,3,4 → 4,3,2,1. Kartki: 1,2,3,4 → 3,4,1,2.', 'file', '--tasowane',
         options=('Tasuj kartki (pary stron)',)),
    Tool('Kody EAN-13 / EAN-8 z pliku tekstowego',
         'Jeden kod w wierszu (EAN-13: 12/13 cyfr, EAN-8: 7/8). Każdy kod na osobnej stronie, wektorowo.',
         'file', '--EAN', options=('EAN-8 zamiast EAN-13',), text_input=True),
)


class PdfToolsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=20)
        self.inputs: list[str] = []
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text='PROGRAMY DODATKOWE', font=('Segoe UI', 18, 'bold'), foreground=ACCENT).grid(
            row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(self, text='Operacje na stronach bez rasteryzacji. Plik wejściowy nigdy nie jest nadpisywany.',
                  foreground=MUTED).grid(row=1, column=0, columnspan=2, sticky='w', pady=(2, 14))

        self.tool_var = tk.StringVar(value=TOOLS[0].name)
        tools = ttk.Frame(self)
        tools.grid(row=2, column=0, sticky='nw', padx=(0, 20))
        for tool in TOOLS:
            ttk.Radiobutton(tools, text=tool.name, value=tool.name, variable=self.tool_var,
                            command=self._update).pack(anchor='w', pady=2)

        form = ttk.Frame(self)
        form.grid(row=2, column=1, sticky='nsew')
        form.columnconfigure(0, weight=1)
        self.hint = tk.StringVar()
        ttk.Label(form, textvariable=self.hint, foreground=MUTED, wraplength=620).grid(row=0, column=0, sticky='w')
        files = ttk.Frame(form)
        files.grid(row=1, column=0, sticky='ew', pady=8)
        files.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(files, height=6, bg=PANEL, fg=TEXT, selectbackground='#cfe0f7', selectforeground=TEXT,
                                  relief='solid', borderwidth=1, highlightthickness=0)
        self.listbox.grid(row=0, column=0, rowspan=4, sticky='nsew')
        ttk.Button(files, text='Wybierz plik…', command=self.choose).grid(row=0, column=1, sticky='ew', padx=(8, 0))
        ttk.Button(files, text='↑', command=lambda: self.move(-1)).grid(row=1, column=1, sticky='ew', padx=(8, 0))
        ttk.Button(files, text='↓', command=lambda: self.move(1)).grid(row=2, column=1, sticky='ew', padx=(8, 0))
        ttk.Button(files, text='Usuń z listy', command=self.remove).grid(row=3, column=1, sticky='ew', padx=(8, 0))

        self.range_frame = ttk.Frame(form)
        self.range_var = tk.StringVar()
        ttk.Label(self.range_frame, text='Zakres stron:').pack(side='left')
        ttk.Entry(self.range_frame, textvariable=self.range_var, width=30).pack(side='left', padx=6)
        self.range_hint = ttk.Label(self.range_frame, foreground=MUTED)
        self.range_hint.pack(side='left')
        self.number_frame = ttk.Frame(form)
        self.number_label = ttk.Label(self.number_frame)
        self.number_label.pack(side='left')
        self.number_var = tk.StringVar(value='2')
        ttk.Entry(self.number_frame, textvariable=self.number_var, width=8).pack(side='left', padx=6)
        self.option_vars = [tk.BooleanVar(), tk.BooleanVar()]
        self.option_buttons = [ttk.Checkbutton(form, variable=v) for v in self.option_vars]
        self.form = form
        ttk.Button(form, text='Start', style='Accent.TButton', command=self.run).grid(row=7, column=0, sticky='w', pady=12)
        self.log = tk.Text(form, height=9, bg=PANEL, fg=TEXT, relief='solid', borderwidth=1, font=('Consolas', 10), wrap='word')
        self.log.grid(row=8, column=0, sticky='nsew')
        form.rowconfigure(8, weight=1)
        self.rowconfigure(2, weight=1)
        self._update()

    @property
    def tool(self) -> Tool:
        return next(t for t in TOOLS if t.name == self.tool_var.get())

    def _update(self):
        tool = self.tool
        self.hint.set(tool.hint)
        self.range_frame.grid_forget()
        self.number_frame.grid_forget()
        for button in self.option_buttons:
            button.grid_forget()
        if tool.range_field:
            self.range_hint.configure(text=RANGE_HELP if tool.range_field == 'optional'
                                      else 'Wymagany, np. -3, 6, 9-11, 15-')
            self.range_frame.grid(row=2, column=0, sticky='w', pady=3)
        if tool.number:
            self.number_label.configure(text=tool.number)
            self.number_var.set('90' if 'Kąt' in tool.number else '2')
            self.number_frame.grid(row=3, column=0, sticky='w', pady=3)
        for i, text in enumerate(tool.options):
            self.option_buttons[i].configure(text=text)
            self.option_vars[i].set(False)
            self.option_buttons[i].grid(row=4 + i, column=0, sticky='w', pady=2)
        if not tool.many_inputs and len(self.inputs) > 1:
            self.inputs = self.inputs[:1]
        self._render()

    def _render(self):
        self.listbox.delete(0, 'end')
        for path in self.inputs:
            self.listbox.insert('end', path)

    def choose(self):
        tool = self.tool
        types = [('Plik tekstowy', '*.txt')] if tool.text_input else [('PDF', '*.pdf')]
        if tool.many_inputs:
            self.inputs += list(filedialog.askopenfilenames(filetypes=types))
        else:
            path = filedialog.askopenfilename(filetypes=types)
            if path:
                self.inputs = [path]
        self._render()

    def move(self, delta):
        sel = self.listbox.curselection()
        if not sel:
            return
        i, j = sel[0], sel[0] + delta
        if 0 <= j < len(self.inputs):
            self.inputs[i], self.inputs[j] = self.inputs[j], self.inputs[i]
            self._render()
            self.listbox.selection_set(j)

    def remove(self):
        for i in reversed(self.listbox.curselection()):
            self.inputs.pop(i)
        self._render()

    def _number(self, low, high) -> int:
        try:
            value = int(self.number_var.get().strip())
        except ValueError:
            raise ValueError(f'{self.tool.number.rstrip(":")} — wpisz liczbę całkowitą') from None
        if not low <= value <= high:
            raise ValueError(f'{self.tool.number.rstrip(":")} — dozwolone {low}–{high}')
        return value

    def run(self):
        tool = self.tool
        try:
            if not self.inputs:
                raise ValueError('Wybierz plik wejściowy.')
            first = self.inputs[0]
            pages = self.range_var.get().strip() or None
            if tool.range_field == 'required' and not pages:
                raise ValueError('Podaj zakres stron, np. -3, 6, 9-11, 15-')
            opt = [v.get() for v in self.option_vars]
            if tool.output == 'folder':
                target = filedialog.askdirectory(initialdir=str(Path(first).parent),
                                                 title='Folder na pliki wynikowe')
            else:
                ext = '.pdf'
                target = filedialog.asksaveasfilename(
                    initialdir=str(Path(first).parent), initialfile=Path(first).stem + tool.suffix + ext,
                    defaultextension=ext, filetypes=[('PDF', '*.pdf')])
            if not target:
                return
            name = tool.name
            if name == 'Rozdziel na pojedyncze strony':
                written = pdftools.split_pages(first, target, pages)
            elif name == 'Połącz pliki PDF':
                written = pdftools.merge(self.inputs, target)
            elif name == 'Wydziel strony z zakresu':
                written = pdftools.extract(first, target, pages, each_separately=opt[0], remainder=opt[1])
            elif name == 'Wydziel parzyste i nieparzyste':
                written = pdftools.extract_even_odd(first, target)
            elif name == 'Wydziel okładkę i wkład':
                written = pdftools.extract_cover(first, target)
            elif name == 'Wydziel zakresy po N stron':
                written = pdftools.extract_chunks(first, target, self._number(1, 100000))
            elif name == 'Obróć strony':
                angle = self._number(0, 270)
                written = pdftools.rotate(first, target, angle, pages, even_extra_180=opt[0])
            elif name == 'Powiel strony':
                written = pdftools.duplicate(first, target, self._number(2, 1000), pages)
            elif name == 'Tasuj strony / kartki':
                written = pdftools.shuffle(first, target, leaves=opt[0])
            else:
                kind = 'EAN8' if opt[0] else 'EAN13'
                codes, bad = barcodes.read_codes(Path(first).read_text(encoding='utf-8-sig'), kind)
                barcodes.export_pdf(codes, target)
                written = [target]
                for line, message in bad:
                    self._log(f'Pominięto wiersz {line}: {message}')
        except (ValueError, FileNotFoundError, RuntimeError, OSError) as exc:
            messagebox.showerror(tool.name, str(exc))
            return
        self._log(f'{tool.name}: zapisano {len(written)} plik(ów)')
        for path in written:
            self._log('  ' + path)

    def _log(self, line):
        self.log.insert('end', line + '\n')
        self.log.see('end')
