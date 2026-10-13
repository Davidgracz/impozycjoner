"""Impozycjoner Studio - desktop operator UI (Tkinter, Windows friendly)."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk

from engine import Job, Project, Settings, SourcePage, open_sources, project_sides, assign_slot, swap_slots, export_pdf, export_pages, geometry, load_project, preview, save_project, source_summary, PAGE_ROLES, ROLE_AUTO, ROLE_SKIP
from preflight import inspect_project
from taxi_ui import TaxiGeneratorFrame
from preview_labels import overlay_preview, OVERLAY_OPTIONS
from duplex_calibration import list_profiles, read_profile, store_profile, remove_profile
from duplex_test_sheet import create_duplex_test_pdf, correction_from_front_error

BG = '#141923'
PANEL = '#1d2531'
PANEL_LIGHT = '#273242'
BORDER = '#3c4859'
TEXT = '#edf2f7'
MUTED = '#a7b4c8'
ACCENT = '#3ed6d0'

TRIM_PRESETS = {
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
        self.title('Impozycjoner Studio 0.3.7')
        self.geometry('1500x850')
        self.minsize(1000, 700)
        self.configure(background=BG)
        self.project = Project()
        # New production workflow; existing .psimp files restore their own settings.
        self.project.settings.trim_w = 93
        self.project.settings.trim_h = 53
        self.project.settings.bleed = 1.5
        self.project.settings.gross_w = 96
        self.project.settings.gross_h = 56
        self.project.settings.scale_mode = 'Kadruj 1:1'
        self.project_filename = None
        self.side_index = 0
        self.register_overlay = False
        self.preview_label_mode = tk.StringVar(value="Numer strony")
        self.render_job = None
        self.preview_photo = None
        self.pending_display_error = None
        self._suspend_events = False
        self._configure_style()
        self._create_layout()
        self._fill_fields()
        self.after(200, self.refresh)

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', background=BG, foreground=TEXT, fieldbackground=PANEL_LIGHT,
                        bordercolor=BORDER, font=('Segoe UI', 10))
        style.configure('TFrame', background=BG)
        style.configure('Panel.TFrame', background=PANEL)
        style.configure('TLabel', background=BG, foreground=TEXT)
        style.configure('Panel.TLabel', background=PANEL, foreground=TEXT)
        style.configure('Muted.TLabel', background=PANEL, foreground=MUTED)
        style.configure('Header.TLabel', background=PANEL, foreground=ACCENT, font=('Segoe UI', 11, 'bold'))
        style.configure('TButton', background=PANEL_LIGHT, foreground=TEXT, padding=(11, 8))
        style.map('TButton', background=[('active', '#36495d')])
        style.configure('Accent.TButton', background='#168d92', foreground='white', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active','#1db3b8')])
        style.configure('TEntry', padding=(6, 5), insertcolor=TEXT)
        style.configure('TCombobox', padding=(7,5), fieldbackground=PANEL_LIGHT,
                        selectbackground=PANEL_LIGHT, selectforeground=TEXT)
        style.map('TCombobox', fieldbackground=[('readonly', PANEL_LIGHT)], foreground=[('readonly', TEXT)])
        style.configure('Treeview', background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=30, borderwidth=0)
        style.map('Treeview', background=[('selected', '#166b77')])
        style.configure('Treeview.Heading', background=PANEL_LIGHT, foreground=TEXT, padding=(8,7))
        style.configure('TCheckbutton', background=PANEL, foreground=TEXT)
        style.map('TCheckbutton', background=[('active', PANEL)])
        style.configure('TLabelframe', background=PANEL, bordercolor=BORDER)
        style.configure('TLabelframe.Label', background=PANEL, foreground=ACCENT)

    def _button(self, parent, text, command, accent=False, **kw):
        return ttk.Button(parent, text=text, command=command,
                          style='Accent.TButton' if accent else 'TButton', **kw)

    def _create_layout(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill='both', expand=True)
        self.imposition_tab = ttk.Frame(self.tabs)
        self.taxi_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.imposition_tab, text='  Impozycja PDF  ')
        self.tabs.add(self.taxi_tab, text='  Generator naklejek TAXI  ')
        self.taxi_ui = TaxiGeneratorFrame(self.taxi_tab)
        self.taxi_ui.pack(fill='both', expand=True)
        top = ttk.Frame(self.imposition_tab, padding=(14, 11))
        top.pack(fill='x')
        ttk.Label(top, text='IMPOZYCJONER', font=('Segoe UI', 19, 'bold'), foreground=ACCENT).pack(side='left', padx=(0, 4))
        ttk.Label(top, text='STUDIO 0.3.7', foreground=MUTED, font=('Segoe UI', 10)).pack(side='left', padx=(5, 16))
        self._button(top, 'Otwórz projekt', self.load_project).pack(side='left', padx=3)
        self._button(top, 'Zapisz projekt', self.save_project).pack(side='left', padx=3)
        self._button(top, 'Eksportuj PDF', self.export, True).pack(side='right', padx=5)
        self._button(top, 'Eksportuj pojedyncze strony', self.export_single_pages).pack(side='right', padx=5)
        self._button(top, 'Preflight PDF', self.show_preflight).pack(side='right', padx=5)
        self._button(top, 'Odśwież podgląd', self.refresh).pack(side='right', padx=5)

        body = ttk.Frame(self.imposition_tab)
        body.pack(fill='both', expand=True, padx=12, pady=(0,10))
        body.columnconfigure(0, weight=0, minsize=320)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=0, minsize=310)
        body.rowconfigure(0, weight=1)

        jobs = ttk.Frame(body, style='Panel.TFrame', padding=12, width=335)
        jobs.grid(row=0,column=0,sticky='nsew',padx=(0,7))
        jobs.grid_propagate(False)
        ttk.Label(jobs, text='PLIKI WEJŚCIOWE', style='Header.TLabel').pack(anchor='w',pady=(3,10))
        btns = ttk.Frame(jobs, style='Panel.TFrame')
        btns.pack(fill='x', pady=(0,8))
        self._button(btns, '+ Dodaj PDF',self.add_files).pack(side='left', fill='x',expand=True)
        self._button(btns, 'Usuń',self.remove_file).pack(side='left',padx=(5,0))
        tree_frame = ttk.Frame(jobs, style='Panel.TFrame')
        tree_frame.pack(fill='both',expand=True)
        self.files = ttk.Treeview(tree_frame, columns=('p','copies','role'),show='tree headings',selectmode='browse')
        self.files.heading('#0',text='Plik')
        self.files.heading('p',text='Str.')
        self.files.heading('copies',text='Nakład')
        self.files.heading('role',text='Rola')
        self.files.column('#0',width=110,stretch=True)
        self.files.column('p',width=38,stretch=False,anchor='center')
        self.files.column('copies',width=51,stretch=False,anchor='center')
        self.files.column('role',width=80,stretch=False,anchor='center')
        self.files.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(tree_frame,orient='vertical',command=self.files.yview)
        bar.pack(side='right',fill='y')
        self.files.configure(yscrollcommand=bar.set)
        self.files.bind('<<TreeviewSelect>>',self._tree_selection)
        self.files.bind('<Double-1>',lambda event:self.edit_page_roles())
        self.selected_info=tk.StringVar(value='Wczytaj pliki PDF, aby rozpocząć montaż.')
        ttk.Label(jobs,textvariable=self.selected_info,style='Muted.TLabel',wraplength=235,justify='left').pack(anchor='w',pady=(10,7))
        copies_frame = ttk.Frame(jobs, style='Panel.TFrame')
        copies_frame.pack(fill='x',pady=(0,6))
        ttk.Label(copies_frame,text='Nakład pliku:',style='Panel.TLabel').pack(side='left')
        self.copies_var=tk.StringVar(value='1')
        self.copies_entry=ttk.Entry(copies_frame,textvariable=self.copies_var,width=7)
        self.copies_entry.pack(side='left',padx=6)
        self.copies_entry.bind('<Return>',lambda e:self.change_copies())
        self._button(copies_frame,'Zmień',self.change_copies).pack(side='left')
        self._button(jobs, 'Przód / tył — role pliku i stron…', self.edit_page_roles,
                     accent=True).pack(fill='x', pady=(3, 7))
        ttk.Label(jobs,text='Role stosuje się w trybie Dwustronnie. Strony można oznaczać pojedynczo lub zakresami.',
                  style='Muted.TLabel',wraplength=300).pack(anchor='w',pady=3)
        reorder = ttk.Frame(jobs, style='Panel.TFrame')
        reorder.pack(fill='x')
        self._button(reorder,'↑ W górę',lambda:self.move_job(-1)).pack(side='left',expand=True,fill='x',padx=(0,3))
        self._button(reorder,'↓ W dół',lambda:self.move_job(1)).pack(side='left',expand=True,fill='x')

        central=ttk.Frame(body)
        central.grid(row=0,column=1,sticky='nsew',padx=7)
        central.rowconfigure(1,weight=1)
        central.columnconfigure(0,weight=1)
        toolbar=ttk.Frame(central,padding=(4,6))
        toolbar.grid(row=0,column=0,sticky='ew')
        ttk.Label(toolbar,text='PODGLĄD ARKUSZA', font=('Segoe UI', 11, 'bold')).pack(side='left')
        self._button(toolbar,'Edytuj użytki (przeciągnij)',self.edit_sheet).pack(side='left',padx=5)
        self._button(toolbar,'Rejestracja ON/OFF',self.toggle_overlay).pack(side='left',padx=4)
        ttk.Label(toolbar, text='Nakładki:').pack(side='left',padx=(10,3))
        self.preview_label_choice=ttk.Combobox(toolbar, textvariable=self.preview_label_mode,
                                               values=OVERLAY_OPTIONS, state='readonly', width=15)
        self.preview_label_choice.pack(side='left',padx=3)
        self.preview_label_choice.bind('<<ComboboxSelected>>', lambda event:self.refresh())
        self._button(toolbar,'▶',lambda:self.change_side(1)).pack(side='right',padx=2)
        self._button(toolbar,'◀',lambda:self.change_side(-1)).pack(side='right',padx=2)
        self.side_text=tk.StringVar(value='Arkusz 1 • Recto')
        ttk.Label(toolbar,textvariable=self.side_text,foreground=MUTED).pack(side='right',padx=12)
        self.canvas = tk.Canvas(central,background='#394455',highlightthickness=0)
        self.canvas.grid(row=1,column=0,sticky='nsew')
        self.canvas.bind('<Configure>',lambda e:self._display_image())
        self.canvas.create_text(280,180,text='Dodaj pliki PDF',fill='white',font=('Segoe UI',16),tags='placeholder')
        self.stats_text=tk.StringVar(value='Oczekiwanie na pliki PDF')
        ttk.Label(central,textvariable=self.stats_text,foreground=MUTED).grid(row=2,column=0,sticky='ew',pady=(8,0))

        controls=ttk.Frame(body,style='Panel.TFrame',padding=12,width=310)
        controls.grid(row=0,column=2,sticky='nsew',padx=(7,0))
        controls.grid_propagate(False)
        ttk.Label(controls,text='USTAWIENIA MONTAŻU',style='Header.TLabel').pack(anchor='w',pady=(2,12))
        viewport=tk.Canvas(controls,background=PANEL,highlightthickness=0)
        viewport.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(controls,orient='vertical',command=viewport.yview)
        scroll.pack(side='right',fill='y')
        viewport.configure(yscrollcommand=scroll.set)
        form=ttk.Frame(viewport,style='Panel.TFrame')
        window=viewport.create_window((0,0),window=form,anchor='nw')
        form.bind('<Configure>',lambda e:viewport.configure(scrollregion=viewport.bbox('all')))
        viewport.bind('<Configure>',lambda e:viewport.itemconfigure(window,width=e.width))
        viewport.bind('<MouseWheel>',lambda e:viewport.yview_scroll(int(-1*e.delta/120),'units'))
        form.bind('<MouseWheel>',lambda e:viewport.yview_scroll(int(-1*e.delta/120),'units'))

        self.variables={}
        self.mode_var=tk.StringVar(value='Jednostronnie')
        self._row(form,'Tryb',self.mode_var,'combo',('Jednostronnie','Dwustronnie','Broszura'))
        self._separator(form)
        ttk.Label(form,text='ARKUSZ',style='Header.TLabel').pack(anchor='w',pady=(8,6))
        self.preset_var=tk.StringVar(value=next(iter(PRESETS)))
        ttk.Combobox(form,textvariable=self.preset_var,values=list(PRESETS),state='readonly').pack(fill='x',pady=3)
        self.preset_var.trace_add('write',lambda *_:self.apply_preset())
        self._paired(form,'Szer. arkusza (mm)','sheet_w','Wys. arkusza (mm)','sheet_h')
        self._separator(form)
        ttk.Label(form,text='KADROWANIE / WYMIARY',style='Header.TLabel').pack(anchor='w',pady=(8,7))
        ttk.Label(form,text='1. ORYGINAŁ PLIKU PDF (mm)',style='Panel.TLabel').pack(anchor='w',pady=(3,2))
        self._paired(form,'Szer. oryginału','source_w','Wys. oryginału','source_h')
        ttk.Label(form,text='Pobierane automatycznie z PDF. Możesz poprawić ręcznie;\nnie zmienia to fizycznych wymiarów źródła.',
                  style='Muted.TLabel',wraplength=255,justify='left').pack(anchor='w',pady=(0,8))
        ttk.Label(form,text='2. UŻYTEK ZE SPADAMI (BRUTTO)',style='Panel.TLabel').pack(anchor='w',pady=(5,2))
        self._paired(form,'Szer. brutto (mm)','gross_w','Wys. brutto (mm)','gross_h')
        ttk.Label(form,text='3. WYMIAR NETTO PO DOCIĘCIU',style='Panel.TLabel').pack(anchor='w',pady=(10,2))
        self.trim_preset_var=tk.StringVar(value='Niestandardowy')
        ttk.Combobox(form,textvariable=self.trim_preset_var,
                     values=list(TRIM_PRESETS),state='readonly').pack(fill='x',pady=(0,5))
        self.trim_preset_var.trace_add('write',lambda *_:self.apply_trim_preset())
        self._paired(form,'Szer. netto (mm)','trim_w','Wys. netto (mm)','trim_h')
        self.derived_bleed_var = tk.StringVar(value='Spad wynikowy: 1,5 mm na każdą stronę')
        ttk.Label(form,textvariable=self.derived_bleed_var,foreground=ACCENT,
                  wraplength=255,justify='left').pack(anchor='w',pady=(3,7))
        self.scale_var=tk.StringVar(value='Kadruj 1:1')
        self._row(form,'Sposób dopasowania PDF',self.scale_var,'combo',
                  ('Kadruj 1:1','Bez skalowania','Dopasuj','Wypełnij'))
        self.scale_var.trace_add('write',lambda *_:self.schedule_refresh())
        ttk.Label(form,text='Kadruj 1:1 = wytnij środek oryginału bez zmiany wielkości.\nSpad wynika z różnicy brutto i netto.\nInne tryby zachowują dawne skalowanie.',
                  style='Muted.TLabel',wraplength=255,justify='left').pack(anchor='w',pady=(3,6))
        self._paired(form,'Spad dla innych trybów (mm)','bleed','Odstęp X (mm)','gap_x')
        self._paired(form,'Odstęp Y (mm)','gap_y','Margines X (mm)','margin_x')
        self.variables['margin_y']=tk.StringVar()
        self._row(form,'Margines Y (mm)',self.variables['margin_y'])
        self.rot_var=tk.StringVar(value='Auto')
        self._row(form,'Obrót użytków',self.rot_var,'combo',('Auto','0','90','180','270'))
        self._paired(form,'Kolumny (0=auto)','columns','Wiersze (0=auto)','rows')
        self._separator(form)
        ttk.Label(form,text='DUPLEX I ZNACZNIKI',style='Header.TLabel').pack(anchor='w',pady=(8,6))
        self.flip_var=tk.StringVar(value='Długa krawędź')
        self._row(form,'Odwracanie arkusza',self.flip_var,'combo',('Długa krawędź','Krótka krawędź'))
        ttk.Label(form,text='KALIBRACJA RECTO / VERSO',style='Header.TLabel').pack(anchor='w',pady=(12,4))
        self._paired(form,'Przesunięcie verso X (mm)','verso_shift_x',
                     'Przesunięcie verso Y (mm)','verso_shift_y')
        ttk.Label(form,text='Krok 0,1 mm. Współrzędne wynikowego verso: +X w prawo, +Y w dół. '
                  'Offset przesuwa grafikę i linie cięcia, nie arkusz. Recto bez zmian.',
                  style='Muted.TLabel',wraplength=255,justify='left').pack(anchor='w',pady=(3,8))
        self.profile_name=tk.StringVar()
        self.profile_choices=ttk.Combobox(form,textvariable=self.profile_name,
                          values=list_profiles(),state='readonly')
        self.profile_choices.pack(fill='x',pady=(2,5))
        profile_buttons=ttk.Frame(form,style='Panel.TFrame')
        profile_buttons.pack(fill='x',pady=(0,8))
        self._button(profile_buttons,'Wczytaj',self.apply_duplex_profile).pack(side='left',expand=True,fill='x')
        self._button(profile_buttons,'Zapisz',self.save_duplex_profile).pack(side='left',expand=True,fill='x',padx=3)
        self._button(profile_buttons,'Usuń',self.delete_duplex_profile).pack(side='left',expand=True,fill='x')
        calibration_actions=ttk.Frame(form,style='Panel.TFrame')
        calibration_actions.pack(fill='x',pady=(5,4))
        self._button(calibration_actions,'1. Arkusz testowy PDF',self.export_duplex_test_sheet).pack(
            side='left',expand=True,fill='x',padx=(0,3))
        self._button(calibration_actions,'2. Wpisz pomiar',self.open_duplex_measurement).pack(
            side='left',expand=True,fill='x')
        ttk.Label(form,text='Wydrukuj dwustronnie w skali 100%, przyłóż do światła i zmierz położenie znaczników tyłu względem krzyży przodu.',
            style='Muted.TLabel',wraplength=255,justify='left').pack(anchor='w',pady=(0,9))
        self.marks_var=tk.BooleanVar(value=True)
        self.labels_var=tk.BooleanVar(value=False)
        for text, var in [('Znaczniki cięcia',self.marks_var),('Numery stron (oznaczenia pomocnicze)',self.labels_var)]:
            ttk.Checkbutton(form,text=text,variable=var,command=self.schedule_refresh).pack(anchor='w',pady=(8,2))
        ttk.Label(form,text='Preflight sprawdza format i ostrzega o brakach spadów.\nEksport pozostaje wektorowy; sprawdź wydruk próbny.',
                  style='Muted.TLabel',wraplength=255,justify='left').pack(anchor='w',pady=(15,25))
        self.mode_var.trace_add('write',lambda *_:self.schedule_refresh())
        self.rot_var.trace_add('write',lambda *_:self.schedule_refresh())
        self.flip_var.trace_add('write',lambda *_:self.schedule_refresh())
        bottom=ttk.Frame(self.imposition_tab,padding=(13,5))
        bottom.pack(fill='x')
        ttk.Label(bottom,text='Impozycjoner Studio • darmowa, niezależna implementacja • Windows',foreground=MUTED).pack(side='left')
        ttk.Label(bottom,text='Ctrl+O – Dodaj PDF   Ctrl+R – Przód/tył   Ctrl+P – Preflight   Ctrl+E – Eksport',foreground=MUTED).pack(side='right')
        self.bind('<Control-o>',lambda e:self.add_files())
        self.bind('<Control-s>',lambda e:self.save_project())
        self.bind('<Control-e>',lambda e:self.export())
        self.bind('<Control-p>',lambda e:self.show_preflight())
        self.bind('<Control-r>',lambda e:self.edit_page_roles())

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

    def _separator(self,frm):
        ttk.Separator(frm,orient='horizontal').pack(fill='x',pady=(10,3))

    def _row(self,frm,label,var,kind='entry',options=()):
        r=ttk.Frame(frm,style='Panel.TFrame')
        r.pack(fill='x',pady=3)
        ttk.Label(r,text=label,style='Panel.TLabel').pack(side='left')
        if kind=='combo':
            w=ttk.Combobox(r,textvariable=var,values=options,state='readonly',width=16)
        else:
            w=ttk.Entry(r,textvariable=var,width=9)
        w.pack(side='right',fill='x')
        if kind != 'combo':
            w.bind('<KeyRelease>',lambda e:self.schedule_refresh())
            w.bind('<FocusOut>',lambda e:self.schedule_refresh())
        return w

    def _paired(self,frm,label_a,key_a,label_b,key_b):
        line=ttk.Frame(frm,style='Panel.TFrame')
        line.pack(fill='x',pady=4)
        for label,key in ((label_a,key_a),(label_b,key_b)):
            box=ttk.Frame(line,style='Panel.TFrame')
            box.pack(side='left',expand=True,fill='x',padx=(0,6))
            ttk.Label(box,text=label,style='Muted.TLabel',font=('Segoe UI',8)).pack(anchor='w')
            v=tk.StringVar()
            self.variables[key]=v
            field=ttk.Entry(box,textvariable=v,width=12)
            field.pack(fill='x',pady=(2,0))
            field.bind('<KeyRelease>',lambda e:self.schedule_refresh())
            field.bind('<FocusOut>',lambda e:self.schedule_refresh())

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

    def _update_derived_bleed(self):
        try:
            w = float(self.variables['gross_w'].get().replace(',', '.'))
            h = float(self.variables['gross_h'].get().replace(',', '.'))
            nw = float(self.variables['trim_w'].get().replace(',', '.'))
            nh = float(self.variables['trim_h'].get().replace(',', '.'))
            bx, by = (w-nw)/2, (h-nh)/2
            if bx < 0 or by < 0 or abs(bx-by) > .02:
                self.derived_bleed_var.set('BŁĄD: brutto − netto musi dawać identyczny spad z każdej strony.')
            else:
                self.derived_bleed_var.set(f'Spad wynikowy: {bx:.2f} mm z każdej strony')
        except (ValueError, KeyError):
            self.derived_bleed_var.set('Wprowadź prawidłowe wymiary brutto i netto.')

    def _read_fields(self) -> Settings:
        data={}
        for key,var in self.variables.items():
            value = var.get().strip()
            if not value and key in ('source_w','source_h','gross_w','gross_h'):
                value = '0'
            data[key]=int(value) if key in ('columns','rows') else float(value.replace(',','.'))
        if self.scale_var.get() == 'Kadruj 1:1' and data['gross_w'] > 0:
            data['bleed'] = (data['gross_w'] - data['trim_w'])/2
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
            self.variables['gross_w'].set(str(round(dims[0] + 2*gap,3)))
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
            self._render_jobs()
            self.refresh()

    def _render_jobs(self,selected=None):
        self.files.delete(*self.files.get_children())
        for i,j in enumerate(self.project.jobs):
            try:
                pages,w,h=source_summary(j.path)
                name=Path(j.path).name
            except Exception:
                pages='!'
                name=Path(j.path).name+' [BRAK]'
            self.files.insert('', 'end', iid=str(i), text=name,
                              values=(pages,j.copies, j.role if not j.page_roles else 'Mieszane'))
        if selected is not None and str(selected) in self.files.get_children():
            self.files.selection_set(str(selected))

    def _tree_selection(self,*args):
        selection=self.files.selection()
        if not selection:return
        j=self.project.jobs[int(selection[0])]
        self.copies_var.set(str(j.copies))
        try:
            count,w,h=source_summary(j.path)
            self.selected_info.set(f'{Path(j.path).name}\n{count} str. · TrimBox: {w} × {h} mm\nRola: {j.role}'
                                       + (f' (wyjątki: {len(j.page_roles)})' if j.page_roles else ''))
        except Exception as e:
            self.selected_info.set(str(e))

    def edit_page_roles(self):
        """Assign one file role or page overrides by multi-select/range."""
        selection = self.files.selection()
        if not selection:
            messagebox.showinfo('Wybierz plik', 'Zaznacz plik PDF po lewej stronie.')
            return
        idx = int(selection[0])
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
        sel=self.files.selection()
        if not sel:return
        self.project.jobs.pop(int(sel[0]))
        self.side_index=0
        self._render_jobs()
        self.refresh()

    def change_copies(self):
        sel=self.files.selection()
        if not sel:return
        try:
            copies=int(self.copies_var.get())
            if copies<1 or copies>1000000:raise ValueError()
            self.project.jobs[int(sel[0])].copies=copies
            self._render_jobs(int(sel[0]))
            self.side_index=0
            self.refresh()
        except ValueError:
            messagebox.showerror('Błąd','Nakład musi być liczbą całkowitą 1–1 000 000')

    def move_job(self,direction):
        sel=self.files.selection()
        if not sel:return
        idx=int(sel[0]);new_idx=idx+direction
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

    def refresh(self):
        self.render_job=None
        try:
            self.project.settings=self._read_fields()
            s=self.project.settings
            if not self.project.jobs:
                self.stats_text.set('Dodaj pliki PDF, aby zobaczyć prawdziwy podgląd montażu')
                self.side_text.set('Arkusz 1 • Recto')
                self.preview_photo=None
                self.preview_pil=None
                self.canvas.delete('all')
                self.canvas.create_text(200,120,text='DODAJ PLIKI PDF',fill=TEXT,font=('Segoe UI',18,'bold'),anchor='nw')
                self.canvas.create_text(200,165,text='Obsługiwane: PDF, również wielostronicowe',fill=MUTED,font=('Segoe UI',11),anchor='nw')
                self._display_image()
                return
            if s.mode != 'Broszura':
                g=geometry(s)
                details=f'{g.cols} × {g.rows} = {g.capacity} użytków / strona  •  obrót {g.rotation}°'
            else:
                details='Broszura zeszytowa 2-up (4 strony na arkusz)'
            image, side=preview(self.project,pixels=1300,index=self.side_index)
            if side is None and self.side_index>0:
                self.side_index=0
                image,side=preview(self.project,pixels=1300,index=0)
            if self.register_overlay and s.mode == 'Dwustronnie' and side is not None:
                from PIL import Image
                matching = self.side_index + 1 if side.side == 0 else self.side_index - 1
                opposite, other = preview(self.project, pixels=1300, index=matching)
                if other is not None and other.sheet_number == side.sheet_number and other.side != side.side:
                    landscape = s.sheet_w >= s.sheet_h
                    flip_horizontal = (s.flip == 'Długa krawędź') != landscape
                    inverse = opposite.transpose(Image.Transpose.FLIP_LEFT_RIGHT if flip_horizontal else Image.Transpose.FLIP_TOP_BOTTOM)
                    if inverse.size != image.size:
                        inverse = inverse.resize(image.size)
                    image = Image.blend(image.convert('RGB'), inverse.convert('RGB'), 0.5)
            image=overlay_preview(image, side, s, self.preview_label_mode.get())
            self.preview_pil=image
            self.preview_photo=ImageTk.PhotoImage(image)
            self.image_size=image.size
            self.canvas.delete('all')
            self._display_image()
            self.side_text.set(f'Arkusz {side.sheet_number} • {"Recto" if side.side == 0 else "Verso"}' if side else 'Brak stron')
            self.stats_text.set(f'{details}   •   format: {s.sheet_w:g} × {s.sheet_h:g} mm  •   plików: {len(self.project.jobs)}')
        except Exception as e:
            self.stats_text.set(f'Błąd konfiguracji / PDF: {e}')
            self.side_text.set('Nie można wyświetlić')

    def _display_image(self):
        if self.preview_photo is None:return
        self.canvas.delete('preview')
        ww,hh=self.canvas.winfo_width(),self.canvas.winfo_height()
        iw,ih=self.image_size
        if ww<5 or hh<5:return
        # Image is deliberately rendered once at high resolution; canvas zoom
        # is configured by using a thumbnail for each preview window size.
        from PIL import Image
        original=self.preview_photo
        # Resize pre-rendered raster to fit the canvas without re-rendering PDF.
        if not hasattr(self,'preview_pil') or self.preview_pil is None:
            # initial path: original already a PhotoImage, draw centered
            self.canvas.create_image(ww//2,hh//2,image=original,anchor='center',tags='preview')
            return
        available=max(0.02,min((ww-35)/iw,(hh-35)/ih))
        thumb=self.preview_pil.resize((max(1,int(iw*available)),max(1,int(ih*available))),Image.Resampling.LANCZOS)
        self.scaled_photo=ImageTk.PhotoImage(thumb)
        self.canvas.create_image(ww//2,hh//2,image=self.scaled_photo,anchor='center',tags='preview')

    def toggle_overlay(self):
        self.register_overlay = not self.register_overlay
        self.refresh()

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
        next_idx=max(0,self.side_index+delta)
        if next_idx!=self.side_index:
            self.side_index=next_idx
            self.refresh()

    def save_project(self):
        path=self.project_filename or filedialog.asksaveasfilename(defaultextension='.psimp',
                      filetypes=[('Projekt Impozycjonera','*.psimp')])
        if not path:return
        try:
            self.project.settings=self._read_fields()
            save_project(self.project,path)
            self.project_filename=path
            messagebox.showinfo('Projekt zapisany',f'Zapisano:\n{path}')
        except Exception as e:
            messagebox.showerror('Błąd zapisu',str(e))

    def load_project(self):
        path=filedialog.askopenfilename(filetypes=[('Projekt Impozycjonera','*.psimp')])
        if not path:return
        try:
            self.project=load_project(path)
            self.project_filename=path
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
            count=(export_pages(self.project,path) if standalone
                   else export_pdf(self.project,path))
            self.stats_text.set(f'Wyeksportowano {count} stron PDF: {path}')
            messagebox.showinfo('Eksport zakończony',f'Zapisano {count} stron PDF.\n{path}\n\nSprawdź podgląd i wydruk próbny przed nakładem.')
        except Exception as e:
            messagebox.showerror('Błąd eksportu',str(e))
            self.refresh()


if __name__=='__main__':
    App().mainloop()
