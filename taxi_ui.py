"""Tkinter tab for producing ready-to-cut TAXI number sets."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import sys
import os
from PIL import Image, ImageTk

from taxi_generator import make_archive, parse_numbers, font_path, font_label

BG = '#141923'
PANEL = '#1d2531'
ACCENT = '#3ed6d0'
MUTED = '#a7b4c8'


class TaxiGeneratorFrame(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent,padding=20)
        self.columnconfigure(0,weight=1)
        self.rowconfigure(2,weight=1)
        header=ttk.Frame(self)
        header.grid(row=0,column=0,sticky='ew',pady=(0,14))
        ttk.Label(header,text='GENERATOR NAKLEJEK TAXI',font=('Segoe UI',18,'bold'),
                  foreground=ACCENT).pack(anchor='w')
        ttk.Label(header,text='Wpisz numery → otrzymasz ZIP z bokami TIFF i wektorowym tyłem do plotera.',
                  foreground=MUTED).pack(anchor='w',pady=3)

        main=ttk.Frame(self)
        main.grid(row=1,column=0,sticky='ew')
        main.columnconfigure(1,weight=1)
        ttk.Label(main,text='Numery TAXI (oddziel przecinkami, spacją lub Enterem):').grid(
            row=0,column=0,columnspan=2,sticky='w',pady=(0,5))
        self.numbers=tk.Text(main,height=5,width=46,font=('Consolas',14),bg=PANEL,fg='#f4f7fb',
                             insertbackground='white',relief='solid',borderwidth=1)
        self.numbers.grid(row=1,column=0,columnspan=2,sticky='ew')
        self.numbers.insert('1.0','1740')
        row=ttk.Frame(main)
        row.grid(row=2,column=0,columnspan=2,sticky='ew',pady=8)
        ttk.Label(row,text='Szablon: Szczecin · lewy/prawy bok 200 DPI · tył A4').pack(side='left')
        self.font_note=tk.StringVar()
        try:
            f=font_path(); self.font_note.set(f'Font: {font_label(f)}' +
                ('' if f.name.lower()=='impact.ttf' else ' (zamiennik — na Windows użyj Impact)'))
        except Exception:
            self.font_note.set('Brak fontu — wskaż Impact.ttf')
        ttk.Label(main,textvariable=self.font_note,foreground=MUTED).grid(row=3,column=0,columnspan=2,sticky='w')
        self.custom_font=tk.StringVar()
        ttk.Label(main,text='Własny font Impact.ttf (opcjonalnie):').grid(row=4,column=0,sticky='w',pady=(10,3))
        ft=ttk.Frame(main)
        ft.grid(row=5,column=0,columnspan=2,sticky='ew');ft.columnconfigure(0,weight=1)
        ttk.Entry(ft,textvariable=self.custom_font).grid(row=0,column=0,sticky='ew')
        ttk.Button(ft,text='Wybierz font',command=self.pick_font).grid(row=0,column=1,padx=(8,0))
        ttk.Label(main,text='Paczka zawiera: 2 × TIFF · AI (EPS) · EPS · SVG · podgląd PNG dla każdego numeru.',
                  foreground=MUTED).grid(row=6,column=0,columnspan=2,sticky='w',pady=(9,6))
        ttk.Button(main,text='GENERUJ KOMPLET NAKLEJEK TAXI  →  ZIP',
                   command=self.generate,style='Accent.TButton').grid(row=7,column=0,columnspan=2,sticky='ew',pady=7)
        self.status=tk.StringVar(value='Gotowe do generowania.')
        ttk.Label(main,textvariable=self.status,wraplength=850).grid(row=8,column=0,columnspan=2,sticky='w',pady=5)

        section=ttk.Frame(self)
        section.grid(row=2,column=0,sticky='nsew',pady=(16,0))
        section.columnconfigure(0,weight=1)
        ttk.Label(section,text='WZORY BOCZNE — PODGLĄD',foreground=ACCENT,font=('Segoe UI',11,'bold')).grid(
            row=0,column=0,sticky='w',pady=(0,8))
        self.preview_images=[]
        preview_row=ttk.Frame(section)
        preview_row.grid(row=1,column=0,sticky='ew')
        for i,side in enumerate(('lewy','prawy')):
            card=ttk.Frame(preview_row)
            card.grid(row=0,column=i,sticky='n',padx=(0 if i==0 else 16,12))
            ttk.Label(card,text=side.upper(),foreground=MUTED).pack(anchor='w')
            try:
                from taxi_generator import template_path
                with Image.open(template_path(side)) as im:
                    thumbnail=im.convert('RGB')
                thumbnail.thumbnail((440,218))
                photo=ImageTk.PhotoImage(thumbnail)
                self.preview_images.append(photo)
                ttk.Label(card,image=photo).pack()
            except Exception as exc:
                ttk.Label(card,text=f'Nie można wyświetlić: {exc}').pack()
        ttk.Label(section,text=(
            'Uwaga: pliki tylne są konturami do wycinania, nie oryginalnym CDR. '
            'Przed pierwszą produkcją sprawdź import EPS/AI w CorelDRAW X4 '
            'oraz rzeczywisty wymiar A4 i linię cięcia.'),
            foreground=MUTED,wraplength=900,justify='left').grid(row=2,column=0,sticky='w',pady=12)

    def pick_font(self):
        path=filedialog.askopenfilename(parent=self,title='Wybierz systemowy Impact.ttf',
            filetypes=[('Pliki TrueType/OpenType','*.ttf *.otf'),('Wszystkie','*.*')])
        if path:self.custom_font.set(path)

    def generate(self):
        try:
            numbers=parse_numbers(self.numbers.get('1.0','end'))
        except Exception as exc:
            messagebox.showerror('Nieprawidłowe numery',str(exc),parent=self)
            return
        suggested=f'TAXI_{numbers[0]}.zip' if len(numbers)==1 else f'TAXI_{len(numbers)}_NUMEROW.zip'
        dest=filedialog.asksaveasfilename(parent=self,title='Zapisz komplet naklejek TAXI',
            defaultextension='.zip',filetypes=[('Archiwum ZIP','*.zip')],initialfile=suggested)
        if not dest:return
        self.status.set(f'Generuję {len(numbers)} kompletów…')
        self.update_idletasks()
        try:
            result=make_archive(numbers,dest,font=self.custom_font.get().strip() or None)
            self.status.set(f'Zapisano {len(numbers)} kompletów: {result.archive}. Font: {result.font_name}.')
            note='' if result.impact_matched else '\nUWAGA: użyto zamiennika fontu. Dla pełnego wzoru użyj Windows Impact.'
            messagebox.showinfo('Gotowe naklejki TAXI',f'Zapisano:\n{result.archive}\n\n'
                f'Numerów: {len(numbers)}\nPlików: {len(result.files)}\n'
                'W każdym komplecie: lewy/prawy TIFF, tył AI/EPS/SVG oraz podgląd.'+note,
                parent=self)
        except Exception as exc:
            self.status.set('Błąd generowania: '+str(exc))
            messagebox.showerror('Błąd generatora TAXI',str(exc),parent=self)
