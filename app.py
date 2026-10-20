"""Impozycjoner Studio - desktop operator UI (Tkinter, Windows friendly)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk
import pymupdf as fitz

from engine import Job, Project, Settings, SourcePage, open_sources, economic_report, project_sides, assign_slot, swap_slots, export_pdf, export_pages, geometry, load_project, preview, save_project, source_summary, validate, bleed_for, gross_dimensions, mm, PAGE_ROLES, ROLE_AUTO, ROLE_SKIP
from job_templates import (BUILTIN, apply_template, is_builtin, list_templates, read_template,
                           remove_template, store_template)
from preflight import inspect_project
from taxi_ui import TaxiGeneratorFrame
from preview_labels import overlay_preview, symbolic_preview, file_color, OVERLAY_OPTIONS
from duplex_calibration import list_profiles, read_profile, store_profile, remove_profile
from duplex_test_sheet import create_duplex_test_pdf, correction_from_front_error
from economic_csv import write_economic_csv
from crop_editor import CropEditor
from ui_icons import draw as draw_icon
from engine import RUN_MODES, RUN_ALL
from naming import add_imposition_phrase, output_name_problem
import table_actions
from tools_ui import PdfToolsFrame

# Jasny motyw zbliżony do Impozycjonera 4 (Windows, niebieski akcent).
BG = '#eef1f5'
PANEL = '#ffffff'
PANEL_LIGHT = '#f6f8fb'
RIBBON = '#fbfcfd'
FIELD = '#ffffff'
READONLY = '#eef1f5'
BUTTON = '#e9edf2'
HOVER = '#dbe6f5'
SELECT = '#cfe0f7'
CANVAS = '#dde2e8'
BORDER = '#c3ccd8'
TEXT = '#1f2933'
MUTED = '#66768a'
ACCENT = '#2f6fc2'
ACCENT_DARK = '#245aa0'

# Rodzaj arkuszy: wartość = tryb[|krawędź odwracania], jak przyciski wstęgi Imp4.
SHEET_KINDS = (
    ('Jednostronnie', 'single', 'Jednostronnie'),
    ('Dwustronnie|Długa krawędź', 'duplex_long', 'Dwustronnie\ndługa krawędź'),
    ('Dwustronnie|Krótka krawędź', 'duplex_short', 'Dwustronnie\nkrótka krawędź'),
    ('Ekonomiczny', 'economic', 'Ekonomiczny\nmix nakładów'),
)

TRIM_PRESETS = {
    'Wizytówka 93 × 53 mm': (93,53),
    'Wizytówka 90 × 50 mm': (90,50),
    'DL 99 × 210 mm': (99,210),
    'A7 74 × 105 mm': (74,105),
    'Z PDF (oryginał)': None,
    'A6 105 × 148 mm': (105, 148),
    'A6 poziomo 148 × 105 mm': (148, 105),
    'A5 148 × 210 mm': (148, 210),
    'A5 poziomo 210 × 148 mm': (210, 148),
    'A4 210 × 297 mm': (210, 297),
    'A4 poziomo 297 × 210 mm': (297, 210),
    'Niestandardowy': None,
}

PRESETS = {
    'SRA3 450 × 320 mm': (450, 320),
    'SRA3 320 × 450 mm': (320, 450),
    'SRA4 320 × 225 mm': (320, 225),
    'SRA4 225 × 320 mm': (225, 320),
    'A3 420 × 297 mm': (420, 297),
    'A4 297 × 210 mm': (297, 210),
    'A4 210 × 297 mm': (210, 297),
    'B2 700 × 500 mm': (700, 500),
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Impozycjoner Studio 0.4.1')
        self.geometry('1600x900')
        self.minsize(1220, 720)
        self.configure(background=BG)
        self.project = Project()
        # New production workflow; existing .psimp files restore their own settings.
        self.project.settings.trim_w = 93
        self.project.settings.trim_h = 53
        self.project.settings.bleed = 1.5
        self.project.settings.gross_w = 96
        self.project.settings.gross_h = 56
        self.project.settings.scale_mode = 'Kadruj 1:1'
        self.project.settings.auto_gross = True
        self.project.settings.auto_source = True
        self.project_filename = None
        self.side_index = 0
        self.register_overlay = False
        self.preview_label_mode = tk.StringVar(value="Numer strony")
        self.render_job = None
        self.preview_photo = None
        self.pending_display_error = None
        self._suspend_events = False
        self._page_size_cache = {}
        self.current_sides = []
        self.current_side = None
        self._view = None
        self._configure_style()
        self._create_layout()
        self._fill_fields()
        self.after(200, self.refresh)

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=TEXT, fieldbackground=FIELD,
                        bordercolor=BORDER, lightcolor=BG, darkcolor=BORDER, font=('Segoe UI', 9))
        style.configure('TFrame', background=BG)
        style.configure('Panel.TFrame', background=PANEL)
        style.configure('Ribbon.TFrame', background=RIBBON)
        style.configure('TLabel', background=BG, foreground=TEXT)
        style.configure('Panel.TLabel', background=PANEL, foreground=TEXT)
        style.configure('Ribbon.TLabel', background=RIBBON, foreground=TEXT)
        style.configure('Caption.TLabel', background=RIBBON, foreground=MUTED, font=('Segoe UI', 8))
        style.configure('Muted.TLabel', background=PANEL, foreground=MUTED)
        style.configure('Header.TLabel', background=PANEL, foreground=ACCENT, font=('Segoe UI', 10, 'bold'))
        style.configure('Title.TLabel', background=BG, foreground=MUTED, font=('Segoe UI', 9))
        style.configure('Summary.TLabel', background=PANEL, foreground=TEXT, font=('Segoe UI', 9, 'bold'))
        style.configure('TButton', background=BUTTON, foreground=TEXT, padding=(8, 4), relief='flat')
        style.map('TButton', background=[('active', HOVER)])
        style.configure('Quick.TButton', background=BG, foreground=TEXT, padding=(6, 2), relief='flat',
                        borderwidth=0)
        style.map('Quick.TButton', background=[('active', HOVER)])
        style.configure('Accent.TButton', background=ACCENT, foreground='white', font=('Segoe UI', 9, 'bold'))
        style.map('Accent.TButton', background=[('active', ACCENT_DARK)])
        style.configure('Run.TButton', background=PANEL, foreground=ACCENT, bordercolor=ACCENT,
                        lightcolor=ACCENT, darkcolor=ACCENT, borderwidth=2, relief='solid',
                        font=('Segoe UI', 12, 'bold'), padding=(10, 14))
        style.map('Run.TButton', background=[('active', SELECT)])
        style.configure('Kind.Toolbutton', background=RIBBON, foreground=TEXT, padding=(6, 4),
                        font=('Segoe UI', 8), anchor='center', justify='center', width=13)
        style.map('Kind.Toolbutton', background=[('selected', SELECT), ('active', HOVER)],
                  bordercolor=[('selected', ACCENT)])
        style.configure('Tool.Toolbutton', background=PANEL, foreground=TEXT, padding=(4, 5),
                        font=('Segoe UI', 8), anchor='center', justify='center', width=9)
        style.map('Tool.Toolbutton', background=[('selected', SELECT), ('active', HOVER)],
                  bordercolor=[('selected', ACCENT)])
        style.configure('Sheet.Toolbutton', background=PANEL, foreground=TEXT, padding=(10, 2),
                        font=('Segoe UI', 8, 'bold'))
        style.map('Sheet.Toolbutton', background=[('selected', ACCENT), ('active', HOVER)],
                  foreground=[('selected', 'white')])
        style.configure('TEntry', padding=(4, 2))
        style.configure('TSpinbox', padding=(4, 1), arrowsize=10)
        style.map('TSpinbox', fieldbackground=[('readonly', READONLY)])
        style.map('TEntry', fieldbackground=[('readonly', READONLY)])
        style.configure('TCombobox', padding=(4, 1))
        style.map('TCombobox', fieldbackground=[('readonly', FIELD)], foreground=[('readonly', TEXT)])
        style.configure('Treeview', background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=20, borderwidth=1)
        style.map('Treeview', background=[('selected', '#1b1b1b')], foreground=[('selected', 'white')])
        style.configure('Treeview.Heading', background=BUTTON, foreground=TEXT, padding=(4, 2),
                        font=('Segoe UI', 8, 'bold'))
        style.configure('TCheckbutton', background=RIBBON, foreground=TEXT)
        style.map('TCheckbutton', background=[('active', RIBBON)])
        style.configure('TLabelframe', background=PANEL, bordercolor=BORDER)
        style.configure('TLabelframe.Label', background=PANEL, foreground=MUTED, font=('Segoe UI', 8))
        style.configure('Ribbon.TNotebook', background=BG, borderwidth=0, tabmargins=(6, 2, 0, 0))
        style.configure('Ribbon.TNotebook.Tab', background=BG, foreground=TEXT, padding=(12, 4),
                        font=('Segoe UI', 9))
        style.map('Ribbon.TNotebook.Tab', background=[('selected', RIBBON)],
                  foreground=[('selected', ACCENT)])
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=BG, padding=(12, 4))
        style.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', ACCENT)])

    def _icon(self, name, size=30):
        icons = self.__dict__.setdefault('_icons', {})
        if (name, size) not in icons:
            icons[name, size] = ImageTk.PhotoImage(draw_icon(name, size), master=self)
        return icons[name, size]

    def _button(self, parent, text, command, accent=False, **kw):
        return ttk.Button(parent, text=text, command=command,
                          style='Accent.TButton' if accent else 'TButton', **kw)

    # --- Wstęga (ribbon) w stylu Impozycjonera 4 -------------------------------------------------

    def _group(self, parent, caption):
        """Ribbon group: controls on top, caption underneath, vertical divider on the right."""
        outer = ttk.Frame(parent, style='Ribbon.TFrame', padding=(8, 4, 8, 1))
        outer.pack(side='left', fill='y')
        ttk.Label(outer, text=caption, style='Caption.TLabel').pack(side='bottom', pady=(2, 0))
        inner = ttk.Frame(outer, style='Ribbon.TFrame')
        inner.pack(side='top', fill='both', expand=True)
        ttk.Separator(parent, orient='vertical').pack(side='left', fill='y', pady=6)
        return inner

    def _spin(self, parent, key, row, col, label=None, step=0.5, low=0, high=5000, width=7):
        """Labelled ttk.Spinbox bound to self.variables[key], like Imp4's ▲▼ fields."""
        if label:
            ttk.Label(parent, text=label, style='Ribbon.TLabel').grid(row=row, column=col, sticky='e', padx=(0, 3), pady=1)
        var = self.variables.setdefault(key, tk.StringVar())
        spin = ttk.Spinbox(parent, textvariable=var, from_=low, to=high, increment=step, width=width,
                           command=self.schedule_refresh)
        spin.grid(row=row, column=col+1 if label else col, sticky='w', pady=1)
        spin.bind('<KeyRelease>', lambda e: self.schedule_refresh())
        spin.bind('<FocusOut>', lambda e: self.schedule_refresh())
        self.entries[key] = spin
        return spin

    def _create_layout(self):
        self.variables = {}
        self.entries = {}
        self.mode_var = tk.StringVar(value='Jednostronnie')
        self.flip_var = tk.StringVar(value='Długa krawędź')
        self.sheet_kind = tk.StringVar(value='Jednostronnie')
        self.symbolic_var = tk.BooleanVar(value=False)
        self.marks_var = tk.BooleanVar(value=True)
        self.labels_var = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value='')
        self.stats_text = tk.StringVar(value='Oczekiwanie na pliki PDF')

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True)
        self.imposition_tab = ttk.Frame(self.tabs)
        self.taxi_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.imposition_tab, text='  Impozycja PDF  ')
        self.tools_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.tools_tab, text='  Programy dodatkowe  ')
        self.tabs.add(self.taxi_tab, text='  Generator naklejek TAXI  ')
        self.tools_ui = PdfToolsFrame(self.tools_tab)
        self.tools_ui.pack(fill='both', expand=True)
        self.taxi_ui = TaxiGeneratorFrame(self.taxi_tab)
        self.taxi_ui.pack(fill='both', expand=True)
        # Ustawienia pliku wynikowego (w Imp4: okno Ustawienia) — lokalne, nie trafiają do .psimp.
        self.phrase_var = tk.BooleanVar(value=False)
        self.meta_vars = {key: tk.StringVar() for key in ('author', 'title', 'subject', 'keywords')}
        self.run_mode_var = tk.StringVar(value=RUN_ALL)

        # Pasek szybkiego dostępu (jak w tytule okna Imp4).
        quick = ttk.Frame(self.imposition_tab, padding=(6, 3))
        quick.pack(fill='x')
        ttk.Button(quick, text='📂 Otwórz plik pdf do impozycji', style='Quick.TButton',
                   command=self.add_files).pack(side='left')
        ttk.Label(quick, text='›', style='Title.TLabel').pack(side='left')
        ttk.Button(quick, text='Wczytaj projekt', style='Quick.TButton',
                   command=self.load_project).pack(side='left')
        ttk.Button(quick, text='💾 Zapisz projekt', style='Quick.TButton',
                   command=self.save_project).pack(side='left', padx=(4, 0))
        ttk.Button(quick, text='Nowa impozycja', style='Quick.TButton',
                   command=self.new_project).pack(side='left', padx=(4, 0))
        ttk.Button(quick, text='Ustawienia…', style='Quick.TButton',
                   command=self.open_output_settings).pack(side='left', padx=(4, 0))
        self.print_area = tk.StringVar(value='')
        self.print_area_label = ttk.Label(quick, textvariable=self.print_area, style='Title.TLabel')
        self.print_area_label.pack(side='left', expand=True)
        ttk.Button(quick, text='Usuń', style='Quick.TButton', command=self.delete_job_template).pack(side='right')
        ttk.Button(quick, text='Zapisz jako…', style='Quick.TButton', command=self.save_job_template).pack(side='right')
        ttk.Button(quick, text='Wczytaj', style='Quick.TButton', command=self.apply_job_template).pack(side='right')
        self.template_name = tk.StringVar()
        self.template_choices = ttk.Combobox(quick, textvariable=self.template_name,
                                             values=self._template_names(), state='readonly', width=34)
        self.template_choices.pack(side='right', padx=4)
        ttk.Label(quick, text='Szablon pracy:', style='Title.TLabel').pack(side='right')

        ribbon = ttk.Notebook(self.imposition_tab, style='Ribbon.TNotebook', height=104)
        ribbon.pack(fill='x', padx=4)
        self._ribbon_jobwork(ribbon)
        self._ribbon_crop(ribbon)
        self._ribbon_duplex(ribbon)

        body = ttk.Frame(self.imposition_tab, padding=(6, 6, 6, 0))
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)
        self._create_preview(body)
        self._create_pages_panel(body)
        self._create_marks_strip(body)

        bottom = ttk.Frame(self.imposition_tab, padding=(8, 3))
        bottom.pack(fill='x')
        ttk.Label(bottom, text='Impozycjoner Studio 0.4.1', foreground=MUTED).pack(side='left')
        ttk.Label(bottom, textvariable=self.stats_text, foreground=MUTED).pack(side='left', padx=18)
        ttk.Label(bottom, textvariable=self.status_text, foreground=MUTED).pack(side='right')

        self.mode_var.trace_add('write', lambda *_: (self._sync_sheet_kind(), self.schedule_refresh()))
        self.flip_var.trace_add('write', lambda *_: (self._sync_sheet_kind(), self.schedule_refresh()))
        self.rot_var.trace_add('write', lambda *_: self.schedule_refresh())
        self.bind('<Control-o>', lambda e: self.add_files())
        self.bind('<Control-s>', lambda e: self.save_project())
        # Skróty jak w Impozycjonerze 4: Ctrl+N nowa impozycja, Ctrl+W wczytaj projekt, Shift+Ctrl+S zapisz jako.
        self.bind('<Control-n>', lambda e: self.new_project())
        self.bind('<Control-w>', lambda e: self.load_project())
        self.bind('<Control-S>', lambda e: self.save_project(ask=True))
        self.bind('<Control-e>', lambda e: self.export())
        self.bind('<Control-p>', lambda e: self.show_preflight())
        self.bind('<Control-r>', lambda e: self.edit_page_roles())
        self.bind('<Prior>', lambda e: self.change_side(-1))
        self.bind('<Next>', lambda e: self.change_side(1))

    def _ribbon_jobwork(self, ribbon):
        tab = ttk.Frame(ribbon, style='Ribbon.TFrame')
        ribbon.add(tab, text='Montaż akcydensów')

        g = self._group(tab, 'Użytek netto [mm] i obrót')
        self._spin(g, 'trim_w', 0, 0, 'Poziomo:')
        self._spin(g, 'trim_h', 1, 0, 'Pionowo:')
        self.rot_var = tk.StringVar(value='Auto')
        ttk.Combobox(g, textvariable=self.rot_var, values=('Auto', '0', '90', '180', '270'),
                     state='readonly', width=6).grid(row=0, column=2, padx=(8, 0), sticky='w')
        ttk.Label(g, text='obrót', style='Ribbon.TLabel').grid(row=0, column=3, padx=3, sticky='w')
        self.trim_preset_var = tk.StringVar(value='Niestandardowy')
        ttk.Combobox(g, textvariable=self.trim_preset_var, values=list(TRIM_PRESETS),
                     state='readonly', width=22).grid(row=2, column=0, columnspan=4, sticky='ew', pady=(2, 0))
        self.trim_preset_var.trace_add('write', lambda *_: self.apply_trim_preset())
        ttk.Label(g, text='format', style='Ribbon.TLabel').grid(row=1, column=2, columnspan=2, padx=(8, 0), sticky='w')

        g = self._group(tab, 'Tabela (0 = auto)')
        self._spin(g, 'columns', 0, 0, 'K:', step=1, high=200, width=4)
        self._spin(g, 'rows', 1, 0, 'W:', step=1, high=200, width=4)

        g = self._group(tab, 'Spady (na stronę) [mm]')
        self.variables['bleed'] = tk.StringVar(value='1.5')
        self._spin(g, 'bleed', 0, 0, 'Spad:', step=0.5, high=50, width=5)
        self.auto_gross_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text='brutto = netto + 2 × spad', variable=self.auto_gross_var,
                        command=self.toggle_auto_gross).grid(row=1, column=0, columnspan=2, sticky='w')
        self.derived_bleed_var = tk.StringVar(value='Spad: 1,5 mm z każdej strony')
        ttk.Label(g, textvariable=self.derived_bleed_var, style='Caption.TLabel',
                  foreground=ACCENT, wraplength=230, justify='left').grid(row=2, column=0, columnspan=2, sticky='w')

        g = self._group(tab, 'Odstępy i marginesy [mm]')
        self._spin(g, 'gap_x', 0, 0, 'Odstęp X:', width=5)
        self._spin(g, 'gap_y', 1, 0, 'Odstęp Y:', width=5)
        self._spin(g, 'margin_x', 0, 2, '  Margines X:', width=5)
        self._spin(g, 'margin_y', 1, 2, '  Margines Y:', width=5)

        g = self._group(tab, 'Arkusz [mm]')
        self.preset_var = tk.StringVar(value=next(iter(PRESETS)))
        ttk.Combobox(g, textvariable=self.preset_var, values=list(PRESETS), state='readonly',
                     width=19).grid(row=0, column=0, columnspan=4, sticky='ew', pady=(0, 2))
        self.preset_var.trace_add('write', lambda *_: self.apply_preset())
        self._spin(g, 'sheet_w', 1, 0, 'Szer.:', step=1, width=5)
        self._spin(g, 'sheet_h', 2, 0, 'Wys.:', step=1, width=5)

        g = self._group(tab, 'Rodzaj arkuszy')
        for value, icon, text in SHEET_KINDS:
            ttk.Radiobutton(g, text=text, image=self._icon(icon), compound='top', value=value,
                            variable=self.sheet_kind, style='Kind.Toolbutton',
                            command=self._apply_sheet_kind).pack(side='left', fill='y', padx=1)

    def _ribbon_crop(self, ribbon):
        tab = ttk.Frame(ribbon, style='Ribbon.TFrame')
        ribbon.add(tab, text='Kadrowanie PDF')
        g = self._group(tab, '1. Oryginał PDF [mm]')
        self.auto_source_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(g, text='rozmiar z każdego pliku PDF', variable=self.auto_source_var,
                        command=self.toggle_auto_source).grid(row=0, column=0, columnspan=2, sticky='w')
        self._spin(g, 'source_w', 1, 0, 'Szer.:', step=1, width=7)
        self._spin(g, 'source_h', 2, 0, 'Wys.:', step=1, width=7)
        g = self._group(tab, '3. Brutto = netto + spady [mm]')
        ttk.Checkbutton(g, text='obliczaj automatycznie', variable=self.auto_gross_var,
                        command=self.toggle_auto_gross).grid(row=0, column=0, columnspan=2, sticky='w')
        self._spin(g, 'gross_w', 1, 0, 'Szer.:', width=7)
        self._spin(g, 'gross_h', 2, 0, 'Wys.:', width=7)
        g = self._group(tab, 'Sposób dopasowania PDF')
        self.scale_var = tk.StringVar(value='Kadruj 1:1')
        ttk.Combobox(g, textvariable=self.scale_var, values=('Kadruj 1:1', 'Bez skalowania', 'Dopasuj', 'Wypełnij'),
                     state='readonly', width=16).pack(anchor='w')
        self.scale_var.trace_add('write', lambda *_: self.schedule_refresh())
        ttk.Label(g, text='Kadruj 1:1 = wytnij środek oryginału bez skalowania.\n'
                  'Netto ustawiasz w „Montaż akcydensów”.', style='Caption.TLabel',
                  justify='left').pack(anchor='w', pady=(3, 0))
        g = self._group(tab, 'Kadr wybranego PDF')
        ttk.Button(g, text='✂  Kadruj wybrany PDF\n(podgląd, przesunięcie X/Y)',
                   command=self.open_crop_editor).pack(fill='both', expand=True)
        g = self._group(tab, 'Kontrola')
        ttk.Label(g, textvariable=self.derived_bleed_var, style='Ribbon.TLabel', foreground=ACCENT,
                  wraplength=260, justify='left').pack(anchor='w')

    def _ribbon_duplex(self, ribbon):
        tab = ttk.Frame(ribbon, style='Ribbon.TFrame')
        ribbon.add(tab, text='Druk cyfrowy — recto/verso')
        g = self._group(tab, 'Przesunięcie verso [mm]  (+X prawo, +Y dół)')
        self._spin(g, 'verso_shift_x', 0, 0, 'X:', step=0.1, low=-20, high=20, width=6)
        self._spin(g, 'verso_shift_y', 1, 0, 'Y:', step=0.1, low=-20, high=20, width=6)
        g = self._group(tab, 'Profil maszyny')
        self.profile_name = tk.StringVar()
        self.profile_choices = ttk.Combobox(g, textvariable=self.profile_name, values=list_profiles(),
                                            state='readonly', width=24)
        self.profile_choices.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0, 3))
        for col, (text, cmd) in enumerate((('Wczytaj', self.apply_duplex_profile),
                                           ('Zapisz', self.save_duplex_profile),
                                           ('Usuń', self.delete_duplex_profile))):
            ttk.Button(g, text=text, command=cmd).grid(row=1, column=col, sticky='ew', padx=1)
        g = self._group(tab, 'Kalibracja spasowania')
        ttk.Button(g, text='1. Arkusz testowy PDF', command=self.export_duplex_test_sheet).pack(fill='x', pady=1)
        ttk.Button(g, text='2. Wpisz pomiar', command=self.open_duplex_measurement).pack(fill='x', pady=1)
        g = self._group(tab, 'Podgląd')
        ttk.Button(g, text='Rejestracja\nprzód + tył', image=self._icon('register'), compound='left',
                   command=self.toggle_overlay).pack(fill='both', expand=True)
        g = self._group(tab, 'Wskazówka')
        ttk.Label(g, text='Rodzaj arkusza „Dwustronnie” wybierz w zakładce Montaż akcydensów.\n'
                  'Drukuj 100% skali; offset przesuwa grafikę i linie cięcia verso, nie arkusz.',
                  style='Ribbon.TLabel', justify='left').pack(anchor='w')

    # --- Podgląd arkusza ---------------------------------------------------------------------------

    def _create_preview(self, body):
        area = ttk.Frame(body, style='Panel.TFrame', padding=(6, 4))
        area.grid(row=0, column=0, sticky='nsew', padx=(0, 6))
        area.columnconfigure(0, weight=1)
        area.rowconfigure(1, weight=1)
        head = ttk.Frame(area, style='Panel.TFrame')
        head.grid(row=0, column=0, columnspan=2, sticky='ew')
        self.slots_title = tk.StringVar(value='Tabela użytków')
        ttk.Label(head, textvariable=self.slots_title, style='Muted.TLabel').pack(side='left', expand=True)
        self.side_text = tk.StringVar(value='Arkusz 1 • Recto')
        ttk.Label(head, textvariable=self.side_text, style='Summary.TLabel').pack(side='right')
        self.canvas = tk.Canvas(area, background=CANVAS, highlightthickness=1, highlightbackground=BORDER)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda e: self._display_image())
        self.canvas.bind('<Button-1>', self._canvas_click)
        self.canvas.bind('<Double-1>', lambda e: self.edit_sheet())

        tools = ttk.Frame(area, style='Panel.TFrame', padding=(5, 0, 0, 0))
        tools.grid(row=1, column=1, sticky='ns')
        ttk.Checkbutton(tools, text='Symbole', image=self._icon('symbols'), compound='top',
                        variable=self.symbolic_var, style='Tool.Toolbutton',
                        command=self.refresh).pack(fill='x', pady=1)
        for icon, text, cmd in (('edit', 'Edytuj użytki', self.edit_sheet),
                                ('register', 'Rejestracja', self.toggle_overlay),
                                ('refresh', 'Odśwież', self.refresh),
                                ('preflight', 'Preflight', self.show_preflight)):
            ttk.Button(tools, text=text, image=self._icon(icon), compound='top', command=cmd,
                       style='Tool.Toolbutton').pack(fill='x', pady=1)
        ttk.Label(tools, text='Nakładki', style='Muted.TLabel').pack(pady=(8, 0))
        self.preview_label_choice = ttk.Combobox(tools, textvariable=self.preview_label_mode,
                                                 values=OVERLAY_OPTIONS, state='readonly', width=11)
        self.preview_label_choice.pack()
        self.preview_label_choice.bind('<<ComboboxSelected>>', lambda event: self.refresh())

        sheets = ttk.Frame(area, style='Panel.TFrame', padding=(0, 6, 0, 0))
        sheets.grid(row=2, column=0, columnspan=2, sticky='ew')
        self.sheets_title = tk.StringVar(value='Arkusze')
        ttk.Label(sheets, textvariable=self.sheets_title, style='Muted.TLabel').pack(anchor='center')
        strip = ttk.Frame(sheets, style='Panel.TFrame')
        strip.pack(fill='x')
        ttk.Button(strip, text='▶', width=3, command=lambda: self.change_side(1)).pack(side='right')
        ttk.Button(strip, text='◀', width=3, command=lambda: self.change_side(-1)).pack(side='right', padx=(4, 2))
        holder = ttk.Frame(strip, style='Panel.TFrame')
        holder.pack(side='left', fill='x', expand=True)
        self.sheet_canvas = tk.Canvas(holder, height=26, background=PANEL, highlightthickness=0)
        self.sheet_canvas.pack(fill='x')
        self.sheet_scroll = ttk.Scrollbar(holder, orient='horizontal', command=self.sheet_canvas.xview)
        self.sheet_canvas.configure(xscrollcommand=self.sheet_scroll.set)
        self.sheet_buttons = ttk.Frame(self.sheet_canvas, style='Panel.TFrame')
        self.sheet_canvas.create_window((0, 0), window=self.sheet_buttons, anchor='nw')
        self.sheet_buttons.bind('<Configure>', lambda e: self._sheet_strip_scroll())
        self.sheet_choice = tk.IntVar(value=0)
        self._sheet_signature = None

    # --- Tabela stron, podsumowanie, WYKONAJ IMPOZYCJĘ --------------------------------------------

    def _create_pages_panel(self, body):
        panel = ttk.Frame(body, style='Panel.TFrame', padding=(8, 4), width=470)
        panel.grid(row=0, column=1, sticky='nsew')
        panel.grid_propagate(False)
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)
        self.pages_title = tk.StringVar(value='Stron: 0 • Plików: 0')
        ttk.Label(panel, textvariable=self.pages_title, style='Muted.TLabel').grid(row=0, column=0, pady=(0, 3))
        tree_frame = ttk.Frame(panel, style='Panel.TFrame')
        tree_frame.grid(row=1, column=0, sticky='nsew')
        columns = ('s', 'spdf', 'name', 'w', 'h', 'copies', 'role')
        self.files = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='extended')
        for key, label, width, anchor, stretch in (('s', 'S', 34, 'center', False),
                                                   ('spdf', 'SPDF', 40, 'center', False),
                                                   ('name', 'Nazwa pliku', 150, 'w', True),
                                                   ('w', 'Szer.', 48, 'center', False),
                                                   ('h', 'Wys.', 48, 'center', False),
                                                   ('copies', 'Nakład', 52, 'center', False),
                                                   ('role', 'Rola', 82, 'center', False)):
            self.files.heading(key, text=label)
            self.files.column(key, width=width, anchor=anchor, stretch=stretch)
        self.files.pack(side='left', fill='both', expand=True)
        bar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.files.yview)
        bar.pack(side='right', fill='y')
        self.files.configure(yscrollcommand=bar.set)
        self.files.bind('<<TreeviewSelect>>', self._tree_selection)
        self.files.bind('<Double-1>', lambda event: self.edit_page_roles())
        self.files.bind('<Delete>', lambda event: self.remove_file())
        self.files.bind('<Button-3>', self._table_menu)

        actions = ttk.Frame(panel, style='Panel.TFrame')
        actions.grid(row=2, column=0, sticky='ew', pady=(5, 0))
        self._button(actions, '+ Dodaj PDF', self.add_files, True).pack(side='left', padx=1)
        self._button(actions, 'Usuń plik', self.remove_file).pack(side='left', padx=1)
        self._button(actions, '↑', lambda: self.move_job(-1), width=3).pack(side='left', padx=1)
        self._button(actions, '↓', lambda: self.move_job(1), width=3).pack(side='left', padx=1)
        ttk.Label(actions, text='Nakład:', style='Panel.TLabel').pack(side='left', padx=(10, 3))
        self.copies_var = tk.StringVar(value='1')
        self.copies_entry = ttk.Spinbox(actions, textvariable=self.copies_var, from_=1, to=1000000,
                                        width=7, command=self.change_copies)
        self.copies_entry.pack(side='left')
        self.copies_entry.bind('<Return>', lambda e: self.change_copies())
        self._button(actions, 'Zmień', self.change_copies).pack(side='left', padx=(2, 0))

        actions2 = ttk.Frame(panel, style='Panel.TFrame')
        actions2.grid(row=3, column=0, sticky='ew', pady=(3, 0))
        self._button(actions2, 'Przód / tył — role…', self.edit_page_roles).pack(side='left', expand=True, fill='x', padx=1)
        self._button(actions2, '✂ Kadruj PDF…', self.open_crop_editor).pack(side='left', expand=True, fill='x', padx=1)
        self._button(actions2, '📊 Plan ekonomiczny', self.show_economic_plan).pack(side='left', expand=True, fill='x', padx=1)
        self.selected_info = tk.StringVar(value='Wczytaj pliki PDF, aby rozpocząć montaż.')
        ttk.Label(panel, textvariable=self.selected_info, style='Muted.TLabel', wraplength=430,
                  justify='left').grid(row=4, column=0, sticky='w', pady=(5, 3))

        summary = ttk.LabelFrame(panel, text='Podsumowanie', padding=(10, 4))
        summary.grid(row=5, column=0, sticky='ew', pady=(2, 6))
        summary.columnconfigure(1, weight=1)
        self.summary_vars = {}
        for row, (key, label) in enumerate((('pages', 'Stron do impozycji:'),
                                            ('sheets', 'Ilość arkuszy:'),
                                            ('capacity', 'Użytków na stronie arkusza:'),
                                            ('empty', 'Ilość pól nieużytych:'),
                                            ('use', 'Użytek brutto / netto:'))):
            ttk.Label(summary, text=label, style='Panel.TLabel').grid(row=row, column=0, sticky='e')
            var = tk.StringVar(value='—')
            self.summary_vars[key] = var
            ttk.Label(summary, textvariable=var, style='Summary.TLabel').grid(row=row, column=1, sticky='w', padx=6)

        ttk.Button(panel, text='WYKONAJ IMPOZYCJĘ', style='Run.TButton',
                   command=self.export).grid(row=6, column=0, sticky='ew')
        run_row = ttk.Frame(panel, style='Panel.TFrame')
        run_row.grid(row=7, column=0, sticky='ew', pady=(3, 0))
        ttk.Label(run_row, text='Wykonaj:', style='Panel.TLabel').pack(side='left', padx=(2, 4))
        ttk.Combobox(run_row, textvariable=self.run_mode_var, values=RUN_MODES, state='readonly',
                     width=28).pack(side='left')
        extra = ttk.Frame(panel, style='Panel.TFrame')
        extra.grid(row=8, column=0, sticky='ew', pady=(4, 2))
        self._button(extra, 'Preflight PDF', self.show_preflight).pack(side='left', expand=True, fill='x', padx=1)
        self._button(extra, 'Eksportuj pojedyncze strony', self.export_single_pages).pack(side='left', expand=True, fill='x', padx=1)

    def _create_marks_strip(self, body):
        """Narrow vertical panel like Imp4's 'DRUK OFFSETOWY' marks bar."""
        strip = ttk.Frame(body, style='Panel.TFrame', padding=(4, 4))
        strip.grid(row=0, column=2, sticky='ns', padx=(6, 0))
        title = tk.Canvas(strip, width=22, height=150, background=ACCENT, highlightthickness=0)
        title.create_text(11, 75, text='ZNACZNIKI', angle=90, fill='white', font=('Segoe UI', 9, 'bold'))
        title.pack(side='left', fill='y', padx=(0, 4))
        marks = ttk.Frame(strip, style='Panel.TFrame')
        marks.pack(side='left', fill='y')
        for icon, text, var in (('marks', 'Linie\ncięcia', self.marks_var),
                                ('numbers', 'Numery\nstron', self.labels_var)):
            ttk.Checkbutton(marks, text=text, image=self._icon(icon), compound='top', variable=var,
                            style='Tool.Toolbutton', width=7,
                            command=self.schedule_refresh).pack(fill='x', pady=1)
        ttk.Label(marks, text='w PDF', style='Muted.TLabel').pack(pady=(4, 0))

    # --- Synchronizacja „Rodzaj arkuszy” ↔ tryb/odwracanie -----------------------------------------

    def _apply_sheet_kind(self):
        kind = self.sheet_kind.get()
        mode, _, flip = kind.partition('|')
        self._syncing_kind = True
        try:
            if flip:
                self.flip_var.set(flip)
            self.mode_var.set(mode)
        finally:
            self._syncing_kind = False

    def _sync_sheet_kind(self):
        if getattr(self, '_syncing_kind', False):
            return
        mode = self.mode_var.get()
        self.sheet_kind.set(f'{mode}|{self.flip_var.get()}' if mode == 'Dwustronnie' else mode)

    def _reload_profile_choices(self):
        self.profile_choices.configure(values=list_profiles())

    def apply_duplex_profile(self):
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showwarning('Kalibracja', 'Wybierz profil drukarki.', parent=self)
            return
        try:
            profile=read_profile(name)
            self.variables['verso_shift_x'].set(f"{profile['x']:.1f}")
            self.variables['verso_shift_y'].set(f"{profile['y']:.1f}")
            self.flip_var.set(profile['flip'])
            self.schedule_refresh()
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror('Kalibracja', str(exc), parent=self)

    def save_duplex_profile(self):
        name = simpledialog.askstring('Profil maszyny', 'Nazwa profilu drukarki / maszyny:',
                                      initialvalue=self.profile_name.get(), parent=self)
        if name is None: return
        try:
            s = self._read_fields()
            store_profile(name, x=s.verso_shift_x, y=s.verso_shift_y, flip=s.flip)
            self._reload_profile_choices()
            self.profile_name.set(name.strip())
        except (OSError, ValueError) as exc:
            messagebox.showerror('Kalibracja', str(exc), parent=self)

    def delete_duplex_profile(self):
        name=self.profile_name.get().strip()
        if not name:return
        if not messagebox.askyesno('Usuń profil', f'Usunąć profil „{name}”?', parent=self):return
        try:
            remove_profile(name)
            self.profile_name.set('')
            self._reload_profile_choices()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Kalibracja', str(exc), parent=self)

    def _template_names(self):
        try:
            return list_templates()
        except (OSError, ValueError) as exc:
            # Uszkodzony plik własnych szablonów nie może zablokować programu.
            self.after(400, lambda: messagebox.showerror('Szablony prac', str(exc), parent=self))
            return list(BUILTIN)

    def _reload_template_choices(self):
        self.template_choices.configure(values=self._template_names())

    def apply_job_template(self):
        name = self.template_name.get().strip()
        if not name:
            messagebox.showwarning('Szablony prac', 'Wybierz szablon z listy.', parent=self)
            return
        missing_machine = None
        machine = None
        try:
            template = read_template(name)
            settings = apply_template(self._read_fields(), template)
            machine = template.get('machine')
            if machine:
                try:
                    profile = read_profile(machine)
                except (OSError, ValueError):
                    missing_machine = machine
                else:
                    settings = replace(settings, verso_shift_x=profile['x'],
                                       verso_shift_y=profile['y'], flip=profile['flip'])
            validate(settings)
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror('Szablony prac', str(exc), parent=self)
            return
        self.project.settings = settings
        self._fill_fields()
        if machine and missing_machine is None:
            self.profile_name.set(machine)
        self.refresh()
        if missing_machine:
            messagebox.showwarning('Szablony prac',
                f'Szablon wskazuje profil maszyny „{missing_machine}”, którego nie ma na tym komputerze. '
                'Kalibracja recto/verso i odwracanie zostały bez zmian — sprawdź je przed drukiem.',
                parent=self)

    def save_job_template(self):
        current = self.template_name.get().strip()
        initial = current if current and not is_builtin(current) else ''
        name = simpledialog.askstring('Szablon pracy', 'Nazwa nowego szablonu:',
                                      initialvalue=initial, parent=self)
        if name is None: return
        try:
            existing = next((n for n in self._template_names() if n.casefold() == name.strip().casefold()), None)
            if existing and not is_builtin(existing):
                if not messagebox.askyesno('Szablon pracy', f'Szablon „{existing}” już istnieje. Nadpisać go?', parent=self):
                    return
            settings = self._read_fields()
            machine = None
            profile = self.profile_name.get().strip()
            if profile and messagebox.askyesno('Szablon pracy',
                    f'Powiązać szablon z profilem maszyny „{profile}”?\n\n'
                    'Przy wczytaniu szablonu program ustawi też kalibrację recto/verso '
                    'i krawędź odwracania z tego profilu.', parent=self):
                machine = profile
            store_template(name, settings, machine=machine)
            self._reload_template_choices()
            self.template_name.set(name.strip())
        except (OSError, ValueError) as exc:
            messagebox.showerror('Szablony prac', str(exc), parent=self)

    def delete_job_template(self):
        name = self.template_name.get().strip()
        if not name: return
        if is_builtin(name):
            messagebox.showinfo('Szablony prac', 'Szablonów wbudowanych nie można usunąć.', parent=self)
            return
        if not messagebox.askyesno('Usuń szablon', f'Usunąć szablon „{name}”?', parent=self): return
        try:
            remove_template(name)
            self.template_name.set('')
            self._reload_template_choices()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Szablony prac', str(exc), parent=self)

    def export_duplex_test_sheet(self):
        """Two-page vector PDF using the current sheet format/flip/offset."""
        try:
            settings = self._read_fields()
            if settings.mode != 'Dwustronnie':
                raise ValueError('Wybierz tryb Dwustronnie przed generowaniem arkusza testowego.')
        except (ValueError, KeyError) as exc:
            messagebox.showerror('Arkusz kalibracyjny',str(exc),parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self,
            title='Zapisz dwustronny arkusz do kalibracji',
            defaultextension='.pdf',filetypes=[('Dokument PDF','*.pdf')],
            initialfile='KALIBRACJA_RECTO_VERSO.pdf')
        if not path:return
        try:
            create_duplex_test_pdf(path,sheet_w=settings.sheet_w,sheet_h=settings.sheet_h,
                flip=settings.flip,verso_shift_x=settings.verso_shift_x,
                verso_shift_y=settings.verso_shift_y)
            messagebox.showinfo('Arkusz kalibracyjny',
                'Zapisano PDF z dwiema stronami.\n\n'
                '1. Drukuj dwustronnie, 100% skali, bez dopasowania do strony.\n'
                '2. W drukarce wybierz tę samą krawędź odwracania co w programie.\n'
                '3. Przyłóż wydruk do światła i oglądaj od PRZODU.\n'
                '4. Zmierz, o ile pierścienie z tyłu są przesunięte względem krzyży z przodu.\n'
                '5. Wpisz różnicę do kalkulatora pomiaru.\n\n'
                'Uwaga: do poprawnej kalibracji drukarka nie może skalować PDF-a.',
                parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Arkusz kalibracyjny',str(exc),parent=self)

    def open_duplex_measurement(self):
        """Convert measured front-view back misregistration into backside offsets."""
        try:
            s=self._read_fields()
            if s.mode!='Dwustronnie':
                raise ValueError('Wybierz tryb Dwustronnie przed kalibracją.')
        except (ValueError, KeyError) as exc:
            messagebox.showerror('Kalkulator kalibracji',str(exc),parent=self)
            return
        dlg=tk.Toplevel(self)
        dlg.title('Kalkulator kalibracji recto / verso')
        dlg.transient(self)
        dlg.resizable(False,False)
        body=ttk.Frame(dlg,padding=22)
        body.pack(fill='both',expand=True)
        ttk.Label(body,text='Pomiar z arkusza testowego',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=(0,9))
        ttk.Label(body,text='Oglądaj kartkę OD PRZODU, pod światło.\n'
            'Zmierz, gdzie znajduje się środek pierścienia TYŁU względem krzyża PRZODU.\n'
            'W prawo = dodatni X, w dół = dodatni Y.\n'
            'Podaj średnią z kilku znaczników. Wartości z dokładnością 0,1 mm.',
            wraplength=450,justify='left').pack(anchor='w',pady=(0,11))
        mx=tk.StringVar(value='0,0')
        my=tk.StringVar(value='0,0')
        for title,var in [('Błąd tyłu w osi X (mm)',mx),('Błąd tyłu w osi Y (mm)',my)]:
            row=ttk.Frame(body)
            row.pack(fill='x',pady=3)
            ttk.Label(row,text=title).pack(side='left')
            entry=ttk.Entry(row,textvariable=var,width=12)
            entry.pack(side='right',padx=(12,0))
        note=tk.StringVar()
        ttk.Label(body,textvariable=note,wraplength=450,justify='left',
                  font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(12,7))
        ttk.Label(body,text=f'Obecna korekta: X={s.verso_shift_x:+.1f} mm, Y={s.verso_shift_y:+.1f} mm.\n'
              f'Krawędź: {s.flip}; arkusz {s.sheet_w:g} × {s.sheet_h:g} mm.',
              wraplength=450,justify='left').pack(anchor='w',pady=(0,12))
        result=[None]
        def recompute(*_):
            try:
                x=float(mx.get().replace(',','.'))
                y=float(my.get().replace(',','.'))
                result[0]=correction_from_front_error(x,y,flip=s.flip,
                   sheet_w=s.sheet_w,sheet_h=s.sheet_h,
                   current_x=s.verso_shift_x,current_y=s.verso_shift_y)
                note.set(f'Nowy offset verso: X={result[0][0]:+.1f} mm, Y={result[0][1]:+.1f} mm')
                apply_btn.configure(state='normal')
            except ValueError as exc:
                result[0]=None
                note.set('Sprawdź pomiar: '+str(exc))
                apply_btn.configure(state='disabled')
        def apply():
            if result[0] is None:return
            self.variables['verso_shift_x'].set(f'{result[0][0]:.1f}')
            self.variables['verso_shift_y'].set(f'{result[0][1]:.1f}')
            self.schedule_refresh()
            dlg.destroy()
            messagebox.showinfo('Kalibracja',
                'Nowa korekta została zastosowana do projektu.\n'
                'Zrób kolejny arkusz testowy, aby zweryfikować spasowanie.\n'
                'Jeśli jest poprawne, zapisz profil maszyny przyciskiem Zapisz.',
                parent=self)
        actions=ttk.Frame(body)
        actions.pack(fill='x',pady=(5,0))
        apply_btn=ttk.Button(actions,text='Zastosuj korektę',command=apply)
        apply_btn.pack(side='right')
        ttk.Button(actions,text='Anuluj',command=dlg.destroy).pack(side='right',padx=(0,8))
        mx.trace_add('write',recompute)
        my.trace_add('write',recompute)
        recompute()
        dlg.wait_visibility()
        dlg.grab_set()
        dlg.focus_set()

    def _fill_fields(self):
        s=self.project.settings
        self._suspend_events=True
        for field in ('sheet_w','sheet_h','source_w','source_h','gross_w','gross_h','trim_w','trim_h','bleed','margin_x','margin_y','gap_x','gap_y','verso_shift_x','verso_shift_y','columns','rows'):
            if field not in self.variables:
                # single control (margin_y)
                self.variables[field]=tk.StringVar()
            value = getattr(s,field)
            if field in ('gross_w','gross_h') and value == 0:
                value = (s.trim_w if field=='gross_w' else s.trim_h) + 2*s.bleed
            if field in ('source_w','source_h') and value == 0 and self.project.jobs:
                try:
                    _, source_w, source_h = source_summary(self.project.jobs[0].path)
                    value = source_w if field=='source_w' else source_h
                except Exception:
                    pass
            self.variables[field].set(str(value) if value else '' if field in ('source_w','source_h') else '0')
        self.auto_source_var.set(s.auto_source)
        self.auto_gross_var.set(s.auto_gross)
        self._auto_field_states()
        self._update_derived_bleed()
        self.mode_var.set(s.mode)
        self.scale_var.set(s.scale_mode)
        preset=next((name for name, size in TRIM_PRESETS.items()
                     if size and abs(size[0]-s.trim_w)<.05 and abs(size[1]-s.trim_h)<.05),
                    'Niestandardowy')
        self.trim_preset_var.set(preset)
        self.rot_var.set(s.rotation)
        self.flip_var.set(s.flip)
        self.marks_var.set(s.crop_marks)
        self.labels_var.set(s.show_page_labels)
        self._suspend_events=False
        self._render_jobs()

    def _auto_field_states(self):
        auto_source=self.auto_source_var.get()
        auto_gross=self.auto_gross_var.get()
        for key in ('source_w','source_h'):
            self.entries[key].configure(state='readonly' if auto_source else 'normal')
        for key in ('gross_w','gross_h'):
            self.entries[key].configure(state='readonly' if auto_gross else 'normal')

    def toggle_auto_source(self):
        self._auto_field_states()
        if self.auto_source_var.get() and self.project.jobs:
            idx=self._selected_job() or 0
            _,w,h=source_summary(self.project.jobs[idx].path)
            self.variables['source_w'].set(f'{w:g}')
            self.variables['source_h'].set(f'{h:g}')
        self.schedule_refresh()

    def toggle_auto_gross(self):
        self._auto_field_states()
        self.schedule_refresh()

    def _update_derived_bleed(self):
        try:
            nw=float(self.variables['trim_w'].get().replace(',','.'))
            nh=float(self.variables['trim_h'].get().replace(',','.'))
            bleed=float(self.variables['bleed'].get().replace(',','.'))
            if self.auto_gross_var.get():
                gw=round(nw+2*bleed,3)
                gh=round(nh+2*bleed,3)
                if self.variables['gross_w'].get()!=str(gw):self.variables['gross_w'].set(str(gw))
                if self.variables['gross_h'].get()!=str(gh):self.variables['gross_h'].set(str(gh))
                self.derived_bleed_var.set(f'Automatycznie: {gw:g} × {gh:g} mm; spad {bleed:g} mm')
            else:
                w=float(self.variables['gross_w'].get().replace(',','.'))
                h=float(self.variables['gross_h'].get().replace(',','.'))
                bx,by=(w-nw)/2,(h-nh)/2
                if bx<0 or by<0 or abs(bx-by)>.02:
                    self.derived_bleed_var.set('BŁĄD: brutto − netto musi dawać identyczny spad z każdej strony.')
                else:
                    self.derived_bleed_var.set(f'Ręczne brutto; spad wynikowy: {bx:.2f} mm na stronę')
        except (ValueError, KeyError):
            self.derived_bleed_var.set('Wprowadź prawidłowe wymiary netto i spad.')

    def _read_fields(self) -> Settings:
        data={}
        for key,var in self.variables.items():
            value = var.get().strip()
            if not value and key in ('source_w','source_h','gross_w','gross_h'):
                value = '0'
            data[key]=int(value) if key in ('columns','rows') else float(value.replace(',','.'))
        if self.auto_source_var.get():
            data['source_w']=data['source_h']=0
        if self.auto_gross_var.get():
            data['gross_w']=round(data['trim_w']+2*data['bleed'],3)
            data['gross_h']=round(data['trim_h']+2*data['bleed'],3)
        elif self.scale_var.get() == 'Kadruj 1:1' and data['gross_w'] > 0:
            data['bleed']=(data['gross_w']-data['trim_w'])/2
        data['auto_source']=self.auto_source_var.get()
        data['auto_gross']=self.auto_gross_var.get()
        return Settings(**data,mode=self.mode_var.get(), rotation=self.rot_var.get(),
                        scale_mode=self.scale_var.get(),
                        flip=self.flip_var.get(),crop_marks=self.marks_var.get(),
                        show_page_labels=self.labels_var.get())

    def apply_preset(self):
        if self._suspend_events:return
        size=PRESETS.get(self.preset_var.get())
        if size:
            self.variables['sheet_w'].set(str(size[0]))
            self.variables['sheet_h'].set(str(size[1]))
            self.schedule_refresh()

    def apply_trim_preset(self):
        if self._suspend_events:
            return
        item=self.trim_preset_var.get()
        dims=TRIM_PRESETS.get(item)
        if item == 'Z PDF (oryginał)' and self.project.jobs:
            try:
                _,w,h=source_summary(self.project.jobs[0].path)
                dims=(w,h)
            except Exception:
                return
        if dims:
            try:
                gap = max(0, (float(self.variables['gross_w'].get().replace(',','.')) -
                              float(self.variables['trim_w'].get().replace(',','.')))/2)
            except (ValueError, KeyError):
                gap = 1.5
            self.variables['trim_w'].set(str(dims[0]))
            self.variables['trim_h'].set(str(dims[1]))
            self.variables['gross_w'].set(str(round(dims[0]+2*gap,3)))
            self.variables['gross_h'].set(str(round(dims[1] + 2*gap,3)))
            self.schedule_refresh()

    def add_files(self):
        paths=filedialog.askopenfilenames(title='Dodaj pliki PDF',filetypes=[('Pliki PDF','*.pdf')])
        for path in paths:
            try:
                count,w,h=source_summary(path)
                if not self.project.jobs:
                    # Step 1: actual input PDF dimensions, visible and editable.
                    self.variables['source_w'].set(str(w))
                    self.variables['source_h'].set(str(h))
                    if self.trim_preset_var.get() == 'Z PDF (oryginał)':
                        self.variables['trim_w'].set(str(w))
                        self.variables['trim_h'].set(str(h))
                        bleed = float(self.variables['bleed'].get().replace(',','.'))
                        self.variables['gross_w'].set(str(round(w+2*bleed,3)))
                        self.variables['gross_h'].set(str(round(h+2*bleed,3)))
                self.project.jobs.append(Job(path,1))
            except Exception as e:
                messagebox.showerror('Błąd PDF',str(e))
        if paths:
            self.side_index=0
            self._render_jobs(len(self.project.jobs)-1)
            self.refresh()

    def _selected_job(self):
        """Index of the job owning the selected page row (rows are 'job:page')."""
        selection = self.files.selection()
        if not selection:
            return None
        return int(selection[0].split(':')[0])

    def _page_sizes(self, path):
        """Apparent TrimBox size of every page in mm, cached per file modification time."""
        try:
            stamp = Path(path).stat().st_mtime
        except OSError:
            return None
        cached = self._page_size_cache.get(path)
        if cached and cached[0] == stamp:
            return cached[1]
        sizes = []
        with fitz.open(path) as doc:
            for page in doc:
                b = page.trimbox
                w, h = mm(b.width), mm(b.height)
                sizes.append((h, w) if page.rotation in (90, 270) else (w, h))
        self._page_size_cache[path] = (stamp, sizes)
        return sizes

    def _job_color(self, path):
        for i, job in enumerate(self.project.jobs):
            if job.path == path:
                return file_color(i)
        return '#bbbbbb'

    def _render_jobs(self,selected=None):
        self.files.delete(*self.files.get_children())
        total = 0
        for i,j in enumerate(self.project.jobs):
            name = Path(j.path).name
            try:
                sizes = self._page_sizes(j.path)
            except Exception:
                sizes = None
            color = file_color(i)
            tint = '#' + ''.join(f'{int(int(color[k:k+2],16)*.45 + 255*.55):02x}' for k in (1,3,5))
            self.files.tag_configure(f'job{i}', background=tint)
            self.files.tag_configure('skip', foreground='#8a94a3')
            if sizes is None:
                self.files.insert('', 'end', iid=f'{i}:0', values=('!', '—', name+' [BRAK]', '', '', j.copies, ''),
                                  tags=(f'job{i}',))
                continue
            for page,(w,h) in enumerate(sizes):
                role = j.role_for(page)
                if role != ROLE_SKIP:
                    total += 1
                tags = (f'job{i}', 'skip') if role == ROLE_SKIP else (f'job{i}',)
                self.files.insert('', 'end', iid=f'{i}:{page}',
                                  values=(total if role != ROLE_SKIP else '–', page+1, name,
                                          f'{w:.1f}'.rstrip('0').rstrip('.'), f'{h:.1f}'.rstrip('0').rstrip('.'),
                                          j.copies, role), tags=tags)
        self.pages_title.set(f'Stron: {total} • Plików: {len(self.project.jobs)}')
        if selected is not None and f'{selected}:0' in self.files.get_children():
            self.files.selection_set(f'{selected}:0')
            self.files.see(f'{selected}:0')

    def _tree_selection(self,*args):
        idx=self._selected_job()
        if idx is None:return
        j=self.project.jobs[idx]
        self.copies_var.set(str(j.copies))
        try:
            count,w,h=source_summary(j.path)
            if self.auto_source_var.get():
                self.variables['source_w'].set(f'{w:g}')
                self.variables['source_h'].set(f'{h:g}')
            self.selected_info.set(f'{Path(j.path).name}  •  {count} str.  •  oryginał {w:g} × {h:g} mm  •  '
                                   f'kadr X={j.crop_x:+.1f}, Y={j.crop_y:+.1f} mm  •  rola: {j.role}'
                                   + (f' (wyjątki: {len(j.page_roles)})' if j.page_roles else ''))
        except Exception as e:
            self.selected_info.set(str(e))

    def open_crop_editor(self):
        if not self.project.jobs:
            messagebox.showinfo('Kadr','Dodaj plik PDF.',parent=self)
            return
        idx=self._selected_job() or 0
        job=self.project.jobs[idx]
        try:
            self.project.settings=self._read_fields()
            if self.project.settings.scale_mode!='Kadruj 1:1':
                raise ValueError('Wybierz Kadruj 1:1, aby przesuwać kadr na oryginale.')
            CropEditor(self,job.path,self.project.settings,job.crop_x,job.crop_y,
                       lambda x,y:self._apply_file_crop(idx,x,y))
        except (OSError,ValueError,RuntimeError) as exc:
            messagebox.showerror('Kadr',str(exc),parent=self)

    def _apply_file_crop(self,idx,x,y):
        self.project.jobs[idx].crop_x=round(x,1)
        self.project.jobs[idx].crop_y=round(y,1)
        self._tree_selection()
        self.refresh()

    def edit_page_roles(self):
        """Assign one file role or page overrides by multi-select/range."""
        idx = self._selected_job()
        if idx is None:
            messagebox.showinfo('Wybierz plik', 'Zaznacz stronę pliku PDF w tabeli stron.')
            return
        job = self.project.jobs[idx]
        try:
            count, _, _ = source_summary(job.path)
        except Exception as exc:
            messagebox.showerror('Błąd PDF', str(exc))
            return

        dlg = tk.Toplevel(self)
        dlg.title('Przód / tył — '+Path(job.path).name)
        dlg.geometry('760x690')
        dlg.minsize(630,520)
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.grab_set()
        role = tk.StringVar(value=job.role)
        default = tk.StringVar(value=job.role)
        edits = dict(job.page_roles)

        top = ttk.Frame(dlg, padding=14)
        top.pack(fill='x')
        ttk.Label(top,text=f'{Path(job.path).name}  •  {count} stron',
                  font=('Segoe UI',12,'bold')).pack(anchor='w')
        ttk.Label(top,text='Normalnie = pary 1/2, 3/4…; Przód = czeka na rewers; '
                       'Tył sparowany = kolejny rewers; Tył wspólny = rewers wszystkich przodów.',
                  wraplength=680).pack(anchor='w',pady=(6,5))
        r = ttk.Frame(top)
        r.pack(fill='x',pady=6)
        ttk.Label(r,text='Wybierz rolę:').pack(side='left')
        choice = ttk.Combobox(r,textvariable=role,values=PAGE_ROLES, state='readonly',width=23)
        choice.pack(side='left',padx=9)
        ttk.Label(r,text='Domyślnie dla pliku:').pack(side='left',padx=(12,4))
        ttk.Label(r,textvariable=default,foreground=ACCENT).pack(side='left')

        table_frame=ttk.Frame(dlg,padding=(14,0,14,4))
        table_frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(table_frame,columns=('role',),show='tree headings',selectmode='extended')
        tree.heading('#0',text='Strona')
        tree.heading('role',text='Przypisana rola')
        tree.column('#0',width=100,stretch=False)
        tree.column('role',width=380)
        tree.pack(side='left',fill='both',expand=True)
        sb=ttk.Scrollbar(table_frame,orient='vertical',command=tree.yview)
        sb.pack(side='right',fill='y')
        tree.configure(yscrollcommand=sb.set)
        for page in range(1,count+1):
            tree.insert('', 'end', iid=str(page),text=str(page),values=(edits.get(str(page),job.role),))

        def update_rows():
            for page in range(1,count+1):
                tree.set(str(page),'role',edits.get(str(page),default.get()))
        def set_all():
            default.set(role.get())
            edits.clear()
            update_rows()
        def apply_list(pages):
            if not pages:
                messagebox.showinfo('Zaznacz strony', 'Wybierz strony w tabeli albo wpisz zakres.',parent=dlg)
                return
            for page in pages:
                if role.get() == default.get():
                    edits.pop(str(page), None)
                else:
                    edits[str(page)] = role.get()
            update_rows()
        def parse_range(value):
            result = set()
            for token in value.replace(';',',').split(','):
                token = token.strip()
                if not token: continue
                if '-' in token:
                    parts = token.split('-')
                    if len(parts)!=2 or not all(t.strip().isdigit() for t in parts):
                        raise ValueError('Nieprawidłowy zakres: '+token)
                    lo,hi=map(int,parts)
                    if lo>hi: raise ValueError('Zakres musi rosnąć: '+token)
                    result.update(range(lo,hi+1))
                elif token.isdigit():
                    result.add(int(token))
                else:
                    raise ValueError('Nieprawidłowy numer strony: '+token)
            if any(i<1 or i>count for i in result):
                raise ValueError(f'Numery muszą być w zakresie 1–{count}')
            return sorted(result)
        def apply_range():
            try:
                pages=parse_range(ranges.get())
                apply_list(pages)
                if pages:
                    tree.selection_set(tuple(str(n) for n in pages))
                    tree.see(str(pages[0]))
            except ValueError as exc:
                messagebox.showerror('Nieprawidłowy zakres',str(exc),parent=dlg)

        row=ttk.Frame(dlg,padding=(14,5))
        row.pack(fill='x')
        self._button(row,'Ustaw rolę CAŁEGO PLIKU',set_all).pack(side='left',padx=(0,7))
        self._button(row,'Zastosuj do zaznaczonych stron',
                     lambda:apply_list([int(v) for v in tree.selection()])).pack(side='left')
        range_row=ttk.Frame(dlg,padding=(14,3))
        range_row.pack(fill='x')
        ttk.Label(range_row,text='Zakres (np. 1,3-8,22):').pack(side='left')
        ranges=tk.StringVar()
        entry=ttk.Entry(range_row,textvariable=ranges,width=23)
        entry.pack(side='left',padx=(6,8))
        entry.bind('<Return>',lambda _e:apply_range())
        self._button(range_row,'Zastosuj do zakresu',apply_range).pack(side='left')
        ttk.Label(dlg,text='Ważne: wybierz tryb Dwustronnie. Jeden „Tył wspólny” powtarza się na verso '
                       'każdego przodu; gdy go ustawisz, nieoznaczone strony są przodami.',
                  wraplength=690,foreground=MUTED).pack(anchor='w',padx=15,pady=(6,5))
        bottom=ttk.Frame(dlg,padding=12)
        bottom.pack(fill='x')
        def save():
            # Validation will also run before generating the PDF.
            job.role = default.get()
            job.page_roles = {k:v for k,v in edits.items() if v!=job.role}
            self._render_jobs(idx)
            self.side_index=0
            dlg.destroy()
            self.refresh()
        self._button(bottom,'Anuluj',dlg.destroy).pack(side='right')
        self._button(bottom,'Zapisz przypisanie',save,True).pack(side='right',padx=8)

    def remove_file(self):
        idx=self._selected_job()
        if idx is None:return
        self.project.jobs.pop(idx)
        self.side_index=0
        self._render_jobs()
        self.refresh()

    def change_copies(self):
        idx=self._selected_job()
        if idx is None:return
        try:
            copies=int(self.copies_var.get())
            if copies<1 or copies>1000000:raise ValueError()
            self.project.jobs[idx].copies=copies
            self._render_jobs(idx)
            self.side_index=0
            self.refresh()
        except ValueError:
            messagebox.showerror('Błąd','Nakład musi być liczbą całkowitą 1–1 000 000')

    def move_job(self,direction):
        idx=self._selected_job()
        if idx is None:return
        new_idx=idx+direction
        if 0<=new_idx<len(self.project.jobs):
            self.project.jobs[idx],self.project.jobs[new_idx]=self.project.jobs[new_idx],self.project.jobs[idx]
            self._render_jobs(new_idx)
            self.side_index=0
            self.refresh()

    def schedule_refresh(self):
        if hasattr(self, 'derived_bleed_var'):
            self._update_derived_bleed()
        if self._suspend_events:return
        if self.render_job is not None:
            self.after_cancel(self.render_job)
        self.render_job=self.after(450,self.refresh)

    MAX_LISTED_SIDES = 20000

    def _collect_sides(self):
        """All sheet sides exactly as export will place them (no PDF rendering)."""
        sources = open_sources(self.project.jobs)
        try:
            sides = []
            for side in project_sides(self.project, sources):
                sides.append(side)
                if len(sides) >= self.MAX_LISTED_SIDES:
                    break
            return sides
        finally:
            for doc in sources.values():
                doc.close()

    def _update_summary(self, s, sides, capacity):
        filled = sum(1 for side in sides for p in side.placements if p.source is not None)
        empty = sum(1 for side in sides for p in side.placements if p.source is None)
        if capacity:
            empty += sum(max(0, capacity-len(side.placements)) for side in sides)
        sheets = len({side.sheet_number for side in sides})
        more = '+' if len(sides) >= self.MAX_LISTED_SIDES else ''
        gw, gh = gross_dimensions(s)
        self.summary_vars['pages'].set(f'{filled}{more}')
        self.summary_vars['sheets'].set(f'{sheets}{more}' + ('  (dwustronnie)' if s.mode == 'Dwustronnie' else ''))
        self.summary_vars['capacity'].set(str(capacity) if capacity else '4 strony (2-up)')
        self.summary_vars['empty'].set(f'{empty}{more}')
        self.summary_vars['use'].set(f'{gw:g} × {gh:g} / {s.trim_w:g} × {s.trim_h:g} mm  (spad {bleed_for(s):g})')

    def _sheet_label(self, side, duplex):
        return f'{side.sheet_number}{"R" if side.side == 0 else "V"}' if duplex else str(side.sheet_number)

    def _rebuild_sheet_strip(self, sides, duplex):
        signature = (len(sides), duplex, tuple((x.sheet_number, x.side) for x in sides[:400]))
        if signature != self._sheet_signature:
            self._sheet_signature = signature
            for child in self.sheet_buttons.winfo_children():
                child.destroy()
            for i, side in enumerate(sides[:400]):
                ttk.Radiobutton(self.sheet_buttons, text=self._sheet_label(side, duplex), value=i,
                                variable=self.sheet_choice, style='Sheet.Toolbutton',
                                command=lambda i=i: self.go_to_side(i)).pack(side='left', padx=1)
        self.sheet_choice.set(self.side_index)
        active = sum(1 for x in sides if any(p.source is not None for p in x.placements))
        self.sheets_title.set(f'Arkusze (stron arkuszy: {len(sides)}, aktywnych: {active})'
                              + ('  — pokazano pierwsze 400' if len(sides) > 400 else ''))

    def _sheet_strip_scroll(self):
        self.sheet_canvas.configure(scrollregion=self.sheet_canvas.bbox('all'))
        wide = self.sheet_buttons.winfo_reqwidth() > self.sheet_canvas.winfo_width()
        if wide and not self.sheet_scroll.winfo_ismapped():
            self.sheet_scroll.pack(fill='x')
        elif not wide and self.sheet_scroll.winfo_ismapped():
            self.sheet_scroll.pack_forget()

    def go_to_side(self, index):
        if index != self.side_index:
            self.side_index = index
            self.refresh()

    def refresh(self):
        self.render_job=None
        try:
            self.project.settings=self._read_fields()
            s=self.project.settings
            self.print_area.set(f'Rozmiar pola zadruku: {s.sheet_w-2*s.margin_x:g} × {s.sheet_h-2*s.margin_y:g} mm')
            if not self.project.jobs:
                self.stats_text.set('Dodaj pliki PDF, aby zobaczyć prawdziwy podgląd montażu')
                self.side_text.set('Arkusz 1 • Recto')
                self.slots_title.set('Tabela użytków')
                self.preview_photo=None
                self.preview_pil=None
                self.current_side=None
                self.current_sides=[]
                self._rebuild_sheet_strip([], False)
                for var in self.summary_vars.values():
                    var.set('—')
                self.canvas.delete('all')
                self.canvas.create_text(40,40,text='OTWÓRZ PLIK PDF DO IMPOZYCJI',fill=TEXT,font=('Segoe UI',16,'bold'),anchor='nw')
                self.canvas.create_text(40,78,text='Ctrl+O lub „+ Dodaj PDF”. Obsługiwane są również PDF-y wielostronicowe.',fill=MUTED,font=('Segoe UI',10),anchor='nw')
                return
            capacity = 0
            if s.mode != 'Broszura':
                g=geometry(s)
                capacity = g.capacity
                details=f'{g.cols} × {g.rows} = {g.capacity} użytków / strona  •  obrót {g.rotation}°'
            else:
                details='Broszura zeszytowa 2-up (4 strony na arkusz)'
            sides = self._collect_sides()
            self.current_sides = sides
            if self.side_index >= len(sides):
                self.side_index = 0
            duplex = s.mode in ('Dwustronnie', 'Broszura')
            self._rebuild_sheet_strip(sides, duplex)
            self._update_summary(s, sides, capacity)
            side = sides[self.side_index] if sides else None
            if self.symbolic_var.get():
                image = symbolic_preview(side, s, self._job_color, pixels=1300, bleed=bleed_for(s),
                                         marks=s.crop_marks, mode=self.preview_label_mode.get())
            else:
                image, side = preview(self.project,pixels=1300,index=self.side_index)
            if self.register_overlay and s.mode == 'Dwustronnie' and side is not None:
                from PIL import Image
                matching = self.side_index + 1 if side.side == 0 else self.side_index - 1
                if self.symbolic_var.get():
                    other = sides[matching] if 0 <= matching < len(sides) else None
                    opposite = symbolic_preview(other, s, self._job_color, pixels=1300, bleed=bleed_for(s))
                else:
                    opposite, other = preview(self.project, pixels=1300, index=matching)
                if other is not None and other.sheet_number == side.sheet_number and other.side != side.side:
                    landscape = s.sheet_w >= s.sheet_h
                    flip_horizontal = (s.flip == 'Długa krawędź') != landscape
                    inverse = opposite.transpose(Image.Transpose.FLIP_LEFT_RIGHT if flip_horizontal else Image.Transpose.FLIP_TOP_BOTTOM)
                    if inverse.size != image.size:
                        inverse = inverse.resize(image.size)
                    image = Image.blend(image.convert('RGB'), inverse.convert('RGB'), 0.5)
            if not self.symbolic_var.get():
                image=overlay_preview(image, side, s, self.preview_label_mode.get())
            self.current_side=side
            self.preview_pil=image
            self.preview_photo=ImageTk.PhotoImage(image)
            self.image_size=image.size
            self.canvas.delete('all')
            self._display_image()
            used = sum(1 for p in side.placements if p.source is not None) if side else 0
            self.slots_title.set(f'Tabela użytków ({used})' + ('  •  REJESTRACJA przód + tył' if self.register_overlay and s.mode == 'Dwustronnie' else ''))
            self.side_text.set(f'Arkusz {side.sheet_number} • {"Recto" if side.side == 0 else "Verso"}' if side else 'Brak stron')
            self.stats_text.set(f'{details}   •   arkusz {s.sheet_w:g} × {s.sheet_h:g} mm' + ('  •  MIX NAKŁADÓW' if s.mode == 'Ekonomiczny' else ''))
        except Exception as e:
            self.stats_text.set(f'Błąd konfiguracji / PDF: {e}')
            self.side_text.set('Nie można wyświetlić')

    def _display_image(self):
        if self.preview_photo is None or getattr(self, 'preview_pil', None) is None:return
        self.canvas.delete('preview')
        ww,hh=self.canvas.winfo_width(),self.canvas.winfo_height()
        iw,ih=self.image_size
        if ww<5 or hh<5:return
        # The sheet is rendered once at high resolution and only scaled to the canvas here.
        from PIL import Image
        available=max(0.02,min((ww-30)/iw,(hh-30)/ih))
        tw,th=max(1,int(iw*available)),max(1,int(ih*available))
        thumb=self.preview_pil.resize((tw,th),Image.Resampling.LANCZOS)
        self.scaled_photo=ImageTk.PhotoImage(thumb)
        x0,y0=(ww-tw)//2,(hh-th)//2
        self.canvas.create_rectangle(x0+4,y0+4,x0+tw+4,y0+th+4,fill='#b9c1cc',outline='',tags='preview')
        self.canvas.create_image(x0,y0,image=self.scaled_photo,anchor='nw',tags='preview')
        self._view=(x0,y0,tw/self.project.settings.sheet_w)

    def _canvas_click(self, event):
        """Click a use on the sheet -> select its page in the page table (like Imp4)."""
        if not self._view or self.current_side is None:
            return
        x0, y0, scale = self._view
        x, y = (event.x-x0)/scale, (event.y-y0)/scale
        for placement in self.current_side.placements:
            slot = placement.slot
            if placement.source and slot.x <= x <= slot.x+slot.w and slot.y <= y <= slot.y+slot.h:
                job = next((i for i, j in enumerate(self.project.jobs) if j.path == placement.source.path), None)
                iid = f'{job}:{placement.source.index}'
                if job is not None and self.files.exists(iid):
                    self.files.selection_set(iid)
                    self.files.see(iid)
                return

    def toggle_overlay(self):
        self.register_overlay = not self.register_overlay
        self.refresh()

    def show_economic_plan(self):
        """Show quantities from the exact placements that will be exported."""
        if not self.project.jobs:
            messagebox.showwarning('Brak plików', 'Dodaj pliki PDF.', parent=self)
            return
        try:
            self.project.settings = self._read_fields()
            if self.project.settings.mode != 'Ekonomiczny':
                messagebox.showinfo('Tryb montażu',
                    'W USTAWIENIACH MONTAŻU wybierz Tryb → Ekonomiczny.', parent=self)
                return
            docs = open_sources(self.project.jobs)
            try:
                audit = economic_report(self.project, docs)
            finally:
                for doc in docs.values():
                    doc.close()
            if audit.shortage or audit.overproduction:
                messagebox.showerror('Niezgodny nakład',
                    f'Brakuje {audit.shortage} szt., nadprodukcja {audit.overproduction}. '
                    'Przywróć ręczne przypisania lub zamień użytki.', parent=self)
            window = tk.Toplevel(self)
            window.title('PLAN EKONOMICZNY — użytki i nakłady')
            window.geometry('925x640')
            window.transient(self)
            header = (f'Arkusze do druku: {audit.physical_sheets}    •    '
                      f'Użytki/arkusz: {audit.capacity}    •    '
                      f'Zajęte: {audit.filled_slots}    •    Puste: {audit.empty_slots}    •    '
                      f'Nadprodukcja: {audit.overproduction}')
            ttk.Label(window, text=header, font=('Segoe UI', 11, 'bold'),
                      foreground=ACCENT, wraplength=870).pack(anchor='w', padx=14, pady=12)
            ttk.Label(window, text='NAKŁADY WEDŁUG STRON PDF', foreground=MUTED).pack(anchor='w',padx=14)
            columns=('file', 'page', 'needed', 'actual', 'extra', 'missing')
            table=ttk.Treeview(window,columns=columns,show='headings',height=9)
            for key,label,width in (('file','Plik',230),('page','Str.',60),
                                    ('needed','Zamówiono',120),('actual','W PDF',100),
                                    ('extra','Nadprodukcja',135),('missing','Brakuje',90)):
                table.heading(key,text=label)
                table.column(key,width=width,anchor='w' if key=='file' else 'center')
            for line in audit.lines:
                table.insert('', 'end', values=(Path(line.source.path).name,line.source.index+1,
                              line.requested,line.planned,line.surplus,line.shortage))
            table.pack(fill='both', expand=True, padx=14, pady=7)
            ttk.Label(window, text=f'Wzory arkuszy: {len(audit.patterns)}. '
                'W eksportowanym PDF każdy arkusz występuje już tyle razy, ile należy go wydrukować. '
                'Nie ustawiaj dodatkowych kopii w drukarce.', foreground=MUTED,
                wraplength=870).pack(anchor='w',padx=14,pady=(4,7))
            actions=ttk.Frame(window,padding=12)
            actions.pack(fill='x')
            def save_plan():
                dest=filedialog.asksaveasfilename(parent=window,defaultextension='.csv',
                      initialfile='plan_ekonomiczny.csv',filetypes=[('CSV — Excel','*.csv')])
                if dest:
                    try:
                        write_economic_csv(audit,dest)
                        messagebox.showinfo('Zapisano',f'Raport CSV: {dest}',parent=window)
                    except Exception as exc:
                        messagebox.showerror('Błąd zapisu',str(exc),parent=window)
            self._button(actions, 'Zapisz plan CSV',save_plan,accent=True).pack(side='left')
            self._button(actions, 'Zamknij',window.destroy).pack(side='right')
        except Exception as exc:
            messagebox.showerror('Plan ekonomiczny',str(exc),parent=self)

    def edit_sheet(self):
        """Open visual drag/drop sheet editor, with per-use rigid transforms."""
        if not self.project.jobs:
            messagebox.showwarning('Brak plików', 'Dodaj pliki PDF przed edycją arkusza.')
            return
        try:
            self.project.settings = self._read_fields()
            from sheet_editor import SheetEditor
            window = SheetEditor(self)
            self.sheet_editor_window = window
        except Exception as exc:
            messagebox.showerror('Edytor arkusza', str(exc), parent=self)

    def change_side(self,delta):
        last=max(0,len(self.current_sides)-1) if self.current_sides else 0
        next_idx=min(last,max(0,self.side_index+delta))
        if next_idx!=self.side_index:
            self.side_index=next_idx
            self.refresh()

    # --- Funkcje wzorowane na oknie głównym Impozycjonera 4 -------------------------------------------

    def new_project(self):
        """Nowa impozycja (Ctrl+N): czyści listę plików, zostawia bieżące ustawienia montażu."""
        if self.project.jobs and not messagebox.askyesno(
                'Nowa impozycja', 'Usunąć wszystkie pliki z tabeli stron i zacząć nową impozycję?\n'
                'Ustawienia montażu zostaną zachowane.', parent=self):
            return
        try:
            settings = self._read_fields()
        except (ValueError, KeyError):
            settings = self.project.settings
        self.project = Project(settings=settings)
        self.project_filename = None
        self.status_text.set('')
        self.side_index = 0
        self._render_jobs()
        self.refresh()

    def open_output_settings(self):
        """Ustawienia pliku wynikowego: dopisek --IMPOZYCJONER i metadane PDF (puste = nazwa pliku)."""
        dlg = tk.Toplevel(self)
        dlg.title('Ustawienia — plik wynikowy')
        dlg.configure(background=BG)
        dlg.transient(self)
        body = ttk.Frame(dlg, padding=16)
        body.pack(fill='both', expand=True)
        ttk.Checkbutton(body, text='Dodaj frazę --IMPOZYCJONER do nazwy pliku z impozycją',
                        variable=self.phrase_var).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        for row, (key, label) in enumerate((('title', 'Tytuł'), ('author', 'Autor'),
                                            ('subject', 'Temat'), ('keywords', 'Słowa kluczowe')), start=1):
            ttk.Label(body, text=f'{label} (puste = nazwa pliku):').grid(row=row, column=0, sticky='w', pady=2)
            ttk.Entry(body, textvariable=self.meta_vars[key], width=36).grid(row=row, column=1, sticky='ew', pady=2)
        ttk.Label(body, text='Nazwa pliku nie może zawierać znaków # % & * : < > ? / \\ { } | '
                             'ani być nazwą pliku przetwarzanego.', style='Muted.TLabel',
                  wraplength=440).grid(row=5, column=0, columnspan=2, sticky='w', pady=(10, 0))
        ttk.Button(body, text='Zamknij', command=dlg.destroy).grid(row=6, column=1, sticky='e', pady=(12, 0))

    def _table_menu(self, event):
        row = self.files.identify_row(event.y)
        if row and row not in self.files.selection():
            self.files.selection_set(row)
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='Zaznacz wszystkie wiersze', command=lambda: self._select_rows(table_actions.SELECT_ALL))
        menu.add_command(label='Zaznacz wiersze parzyste', command=lambda: self._select_rows(table_actions.SELECT_EVEN))
        menu.add_command(label='Zaznacz wiersze nieparzyste', command=lambda: self._select_rows(table_actions.SELECT_ODD))
        menu.add_command(label='Odwróć zaznaczenie', command=lambda: self._select_rows(table_actions.SELECT_INVERT))
        menu.add_separator()
        menu.add_command(label='Znajdź pierwszy arkusz z tą stroną', command=self.find_first_sheet)
        menu.add_command(label='Ustaw rozmiar użytka równy rozmiarom zaznaczonej strony', command=self.use_page_size)
        menu.add_separator()
        menu.add_command(label='Pomiń zaznaczone strony w impozycji', command=lambda: self._skip_selected(True))
        menu.add_command(label='Przywróć zaznaczone strony do impozycji', command=lambda: self._skip_selected(False))
        menu.add_command(label='Usuń wszystkie wiersze z pliku', command=self.remove_file)
        menu.add_separator()
        menu.add_command(label='Otwórz plik w czytniku PDF', command=self.open_in_reader)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _select_rows(self, which):
        rows = table_actions.select_rows(list(self.files.get_children()), which, list(self.files.selection()))
        self.files.selection_set(rows)
        if rows:
            self.files.see(rows[0])

    def find_first_sheet(self):
        selection = self.files.selection()
        if not selection:
            return
        job, page = table_actions.parse_row(selection[0])
        index = table_actions.first_side_with(self.current_sides, self.project.jobs[job].path, page)
        if index is None:
            messagebox.showinfo('Znajdź arkusz', 'Ta strona nie występuje na żadnym arkuszu.', parent=self)
            return
        self.go_to_side(index)

    def use_page_size(self):
        selection = self.files.selection()
        if not selection:
            return
        job, page = table_actions.parse_row(selection[0])
        sizes = self._page_sizes(self.project.jobs[job].path)
        if not sizes or page >= len(sizes):
            messagebox.showerror('Rozmiar użytka', 'Nie można odczytać rozmiaru strony.', parent=self)
            return
        w, h = (round(v, 2) for v in sizes[page])
        try:  # spad zostaje taki sam, brutto idzie za netto (jak przy presetach formatu)
            gap = max(0, (float(self.variables['gross_w'].get().replace(',', '.')) -
                          float(self.variables['trim_w'].get().replace(',', '.'))) / 2)
        except (ValueError, KeyError):
            gap = 0
        self._suspend_events = True
        self.trim_preset_var.set('Niestandardowy')
        self._suspend_events = False
        self.variables['trim_w'].set(f'{w:g}')
        self.variables['trim_h'].set(f'{h:g}')
        self.variables['gross_w'].set(f'{round(w + 2 * gap, 3):g}')
        self.variables['gross_h'].set(f'{round(h + 2 * gap, 3):g}')
        self.schedule_refresh()

    def _skip_selected(self, skip):
        groups = table_actions.pages_by_job(list(self.files.selection()))
        if not groups:
            return
        for job, pages in groups.items():
            j = self.project.jobs[job]
            j.page_roles = table_actions.set_skip(j.page_roles, pages, skip, ROLE_SKIP, j.role, ROLE_AUTO)
        self.side_index = 0
        self._render_jobs(next(iter(groups)))
        self.refresh()

    def open_in_reader(self):
        idx = self._selected_job()
        if idx is None:
            return
        import os
        try:
            os.startfile(self.project.jobs[idx].path)  # Windows: domyślny czytnik PDF
        except (AttributeError, OSError) as exc:
            messagebox.showerror('Czytnik PDF', str(exc), parent=self)

    def save_project(self, ask=False):
        path=(None if ask else self.project_filename) or filedialog.asksaveasfilename(defaultextension='.psimp',
                      filetypes=[('Projekt Impozycjonera','*.psimp')])
        if not path:return
        try:
            self.project.settings=self._read_fields()
            save_project(self.project,path)
            self.project_filename=path
            self.status_text.set(path)
            messagebox.showinfo('Projekt zapisany',f'Zapisano:\n{path}')
        except Exception as e:
            messagebox.showerror('Błąd zapisu',str(e))

    def load_project(self):
        path=filedialog.askopenfilename(filetypes=[('Projekt Impozycjonera','*.psimp')])
        if not path:return
        try:
            self.project=load_project(path)
            self.project_filename=path
            self.status_text.set(path)
            self.side_index=0
            self._fill_fields()
            self.refresh()
        except Exception as e:
            messagebox.showerror('Błąd projektu',str(e))

    def show_preflight(self, report=None):
        if not self.project.jobs:
            messagebox.showwarning('Brak plików', 'Najpierw dodaj PDF.')
            return
        try:
            self.project.settings = self._read_fields()
            report = report or inspect_project(self.project)
        except Exception as exc:
            messagebox.showerror('Błąd preflight', str(exc))
            return
        window = tk.Toplevel(self)
        window.title('Preflight PDF — Impozycjoner Studio')
        window.geometry('850x540')
        window.configure(bg=BG)
        window.transient(self)
        ttk.Label(window, text=f'PREFLIGHT  •  {report.errors} błędów  •  {report.warnings} uwag  •  {report.checked_pages}/{report.total_pages} stron',
                  font=('Segoe UI',12,'bold')).pack(anchor='w',padx=15,pady=10)
        frame=ttk.Frame(window)
        frame.pack(fill='both',expand=True,padx=15)
        field=tk.Text(frame,background=PANEL,foreground=TEXT,insertbackground=TEXT,
                      wrap='word',font=('Consolas',10),relief='flat')
        field.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(frame,orient='vertical',command=field.yview)
        bar.pack(side='right',fill='y')
        field.configure(yscrollcommand=bar.set)
        field.insert('1.0',report.to_text())
        field.configure(state='disabled')
        actions=ttk.Frame(window,padding=12)
        actions.pack(fill='x')
        def save_report():
            path=filedialog.asksaveasfilename(parent=window,defaultextension='.txt',
                  filetypes=[('Raport tekstowy','*.txt'),('Raport JSON','*.json')])
            if path:
                try:
                    Path(path).write_text(report.to_json() if path.lower().endswith('.json') else report.to_text(),encoding='utf-8')
                    messagebox.showinfo('Zapisano raport',path,parent=window)
                except Exception as exc:
                    messagebox.showerror('Błąd zapisu',str(exc),parent=window)
        self._button(actions,'Zapisz raport TXT / JSON',save_report).pack(side='left')
        self._button(actions,'Zamknij',window.destroy).pack(side='right')

    def export(self):
        self._export(standalone=False)

    def export_single_pages(self):
        self._export(standalone=True)

    def _export(self, standalone=False):
        if not self.project.jobs:
            messagebox.showwarning('Brak plików','Najpierw dodaj PDF.')
            return
        path=filedialog.asksaveasfilename(defaultextension='.pdf',
              initialfile='strony_docelowe.pdf' if standalone else 'montaz.pdf',
              filetypes=[('PDF do druku','*.pdf')])
        if not path:return
        if self.phrase_var.get():
            path=str(Path(path).with_name(add_imposition_phrase(Path(path).name)))
        problem=output_name_problem(Path(path).name,[j.path for j in self.project.jobs])
        if problem:
            messagebox.showerror('Nazwa pliku wynikowego',problem)
            return
        metadata={key:var.get() for key,var in self.meta_vars.items()}
        run_mode=RUN_ALL if standalone else self.run_mode_var.get()
        active=self.current_side.sheet_number if self.current_side is not None else None
        try:
            self.project.settings=self._read_fields()
            report=inspect_project(self.project)
            if report.errors:
                self.show_preflight(report)
                messagebox.showerror('Eksport wstrzymany',
                    f'Preflight wykrył {report.errors} błędów geometrii PDF.\n'
                    'Popraw pliki przed eksportem.')
                return
            if report.warnings and not messagebox.askyesno('Uwagi preflight',
                    f'Preflight wykrył {report.warnings} uwag.\n'
                    'Zalecamy sprawdzić raport i wykonać wydruk próbny.\n\nKontynuować eksport?'):
                self.show_preflight(report)
                return
            self.update_idletasks()
            self.stats_text.set('Eksport w toku…')
            count=(export_pages(self.project,path,metadata) if standalone
                   else export_pdf(self.project,path,metadata,run_mode,active))
            extra_note = '' if run_mode == RUN_ALL else f'\n\nTryb: {run_mode} (aktywny arkusz {active}).'
            if not standalone and run_mode == RUN_ALL and self.project.settings.mode == 'Ekonomiczny':
                docs = open_sources(self.project.jobs)
                try:
                    audit = economic_report(self.project, docs)
                finally:
                    for doc in docs.values():
                        doc.close()
                csv_dest = str(Path(path).with_name(Path(path).stem + '_plan_ekonomiczny.csv'))
                write_economic_csv(audit,csv_dest)
                extra_note = f'\n\nPlan nakładów CSV: {csv_dest}\nNadprodukcja: {audit.overproduction} szt.'
            self.stats_text.set(f'Wyeksportowano {count} stron PDF: {path}')
            messagebox.showinfo('Eksport zakończony',f'Zapisano {count} stron PDF.\n{path}' + extra_note + '\n\nSprawdź podgląd i wydruk próbny przed nakładem.')
        except Exception as e:
            messagebox.showerror('Błąd eksportu',str(e))
            self.refresh()


if __name__=='__main__':
    App().mainloop()
