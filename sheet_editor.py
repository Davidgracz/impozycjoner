"""Interactive, vector-safe sheet editor for Impozycjoner Studio.

Source pages can be dropped onto exact sheet slots. Existing uses can be
swapped with drag/drop or moved with free 0.1-mm snapped displacement.
Rendered previews are read-only; production placement lives in engine.py.
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from engine import (SourcePage, assign_slot, open_sources, preview, editor_preview, overlapping_uses, reset_slot,
                    set_slot_transform, swap_slots)


class SheetEditor(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.project = app.project
        self.index = app.side_index
        self.selected = None
        self.side = None
        self.photo = None
        self.pil = None
        self.photo_fit = None
        self._origin = (0, 0)
        self._drag = None
        self._layout = (0, 0, 1)
        self._form_sync = False
        self.title('Impozycjoner 0.3.5 — ręczny montaż arkusza')
        self.geometry('1250x810')
        self.minsize(930, 630)
        self.transient(app)
        self.configure(background='#eef1f5')

        top = ttk.Frame(self, padding=10)
        top.pack(fill='x')
        ttk.Label(top, text='EDYTOR MONTAŻU — PRZECIĄGNIJ STRONĘ PDF NA UŻYTEK',
                  font=('Segoe UI', 13, 'bold')).pack(side='left', padx=(0, 15))
        ttk.Button(top, text='◀ poprzednia strona', command=lambda: self.change_side(-1)).pack(side='left')
        ttk.Button(top, text='następna strona ▶', command=lambda: self.change_side(1)).pack(side='left', padx=5)
        self.info = tk.StringVar()
        ttk.Label(top, textvariable=self.info, foreground='#2f6fc2').pack(side='right')

        content = ttk.PanedWindow(self, orient='horizontal')
        content.pack(fill='both', expand=True, padx=10, pady=6)
        left = ttk.Frame(content, padding=(0, 5))
        content.add(left, weight=4)
        right = ttk.Frame(content, padding=(12, 5))
        content.add(right, weight=2)
        ttk.Label(left, text='Arkusz — kliknij, przeciągnij lub użyj strzałek',
                  font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 7))
        self.canvas = tk.Canvas(left, bg='#dde2e8', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda event: self.draw())
        self.canvas.bind('<ButtonPress-1>', self.on_canvas_down)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_canvas_up)
        self.canvas.bind('<KeyPress-Up>', lambda event: self.nudge(0, -0.1))
        self.canvas.bind('<KeyPress-Down>', lambda event: self.nudge(0, 0.1))
        self.canvas.bind('<KeyPress-Left>', lambda event: self.nudge(-0.1, 0))
        self.canvas.bind('<KeyPress-Right>', lambda event: self.nudge(0.1, 0))
        self.canvas.bind('<Delete>', lambda event: self.apply('clear'))
        self.canvas.bind('<KeyPress-r>', lambda event: self.rotate(90))
        self.canvas.bind('<Escape>', lambda event: self.cancel_drag())
        ttk.Label(left, text=('Przeciągnij stronę z listy na arkusz: PRZYPISZ. '
                   'Przeciągnij użytek na inny: ZAMIEŃ. '
                   'Przeciągnij w wolne miejsce lub z Shift: PRZESUŃ (0,1 mm).'),
                  foreground='#66768a', wraplength=780).pack(anchor='w', pady=(5, 0))

        ttk.Label(right, text='STRONY ŹRÓDŁOWE', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        treebar = ttk.Frame(right); treebar.pack(fill='both', expand=True, pady=(6, 11))
        self.pages = ttk.Treeview(treebar, show='tree', selectmode='browse', height=11)
        self.pages.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(treebar, orient='vertical', command=self.pages.yview)
        scroll.pack(side='right', fill='y'); self.pages.configure(yscrollcommand=scroll.set)
        self.page_refs = {}
        docs = open_sources(self.project.jobs)
        try:
            for k, job in enumerate(self.project.jobs):
                count = len(docs[job.path])
                node = self.pages.insert('', 'end', iid=f'job{k}', text=f'{Path(job.path).name} ({count} str.)', open=True)
                for i in range(count):
                    iid = f'p{k}_{i}'
                    self.page_refs[iid] = SourcePage(job.path, i)
                    self.pages.insert(node, 'end', iid=iid, text=f'Strona {i+1}')
        finally:
            for doc in docs.values(): doc.close()
        self.pages.bind('<ButtonPress-1>', self.on_source_down)
        self.pages.bind('<ButtonRelease-1>', self.on_source_up)
        self.pages.bind('<Double-1>', lambda event: self.apply('assign'))
        self.source_start = None
        ttk.Button(right, text='Wstaw wybraną stronę w pole', command=lambda: self.apply('assign')).pack(fill='x', pady=(0, 12))

        ttk.Label(right, text='WYBRANY UŻYTEK', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        self.selection_info = tk.StringVar(value='Kliknij na arkuszu')
        ttk.Label(right, textvariable=self.selection_info, wraplength=285).pack(anchor='w', pady=(5, 8))
        coords = ttk.Frame(right); coords.pack(fill='x', pady=4)
        self.dx_var = tk.StringVar(value='0.0')
        self.dy_var = tk.StringVar(value='0.0')
        self.rotate_var = tk.StringVar(value='0°')
        for col, label, var in [(0, 'X [mm]', self.dx_var), (1, 'Y [mm]', self.dy_var)]:
            coords.columnconfigure(col, weight=1)
            frame = ttk.Frame(coords); frame.grid(row=0, column=col, sticky='ew', padx=(0, 6))
            ttk.Label(frame, text=label).pack(anchor='w')
            tk.Spinbox(frame, textvariable=var, from_=-1000, to=1000,
                       increment=0.1, format='%.1f', width=9).pack(fill='x')
        ttk.Button(right, text='Zastosuj przesunięcie X / Y', command=self.apply_coords).pack(fill='x', pady=(7, 5))
        actions = ttk.Frame(right); actions.pack(fill='x', pady=5)
        ttk.Button(actions, text='⟲ −90°', command=lambda: self.rotate(-90)).pack(side='left', expand=True, fill='x')
        ttk.Button(actions, text='⟳ +90°', command=lambda: self.rotate(90)).pack(side='left', expand=True, fill='x', padx=5)
        ttk.Label(actions, textvariable=self.rotate_var).pack(side='left', padx=7)
        actions2 = ttk.Frame(right); actions2.pack(fill='x', pady=6)
        ttk.Button(actions2, text='Wyczyść', command=lambda: self.apply('clear')).pack(side='left', expand=True, fill='x')
        ttk.Button(actions2, text='Przywróć automat', command=lambda: self.apply('reset')).pack(side='left', expand=True, fill='x', padx=6)
        self.swap_with = tk.StringVar(value='1')
        swaprow = ttk.Frame(right); swaprow.pack(fill='x', pady=5)
        ttk.Label(swaprow, text='Zamień z polem:').pack(side='left')
        ttk.Entry(swaprow, textvariable=self.swap_with, width=5).pack(side='left', padx=7)
        ttk.Button(swaprow, text='Zamień', command=lambda: self.apply('swap')).pack(side='left')
        self.status = tk.StringVar(value='Przeciągaj lub użyj strzałek dla przesunięcia co 0,1 mm.')
        ttk.Label(right, textvariable=self.status, foreground='#66768a',
                  wraplength=285).pack(anchor='w', pady=(14, 5))
        ttk.Button(right, text='Zamknij — zapisz projekt .psimp', command=self.destroy).pack(side='bottom', fill='x', pady=6)
        self.refresh_side()

    def _side_preview(self):
        img, side = editor_preview(self.project, pixels=1200, index=self.index)
        if side is None: raise ValueError('Brak takiej strony arkusza.')
        return img, side

    def refresh_side(self, *, keep_selection=True):
        try:
            self.pil, self.side = self._side_preview()
            from preview_labels import overlay_preview
            self.pil = overlay_preview(self.pil, self.side, self.project.settings,
                                       self.app.preview_label_mode.get(), show_empty=False)
            self.info.set(f'Arkusz {self.side.sheet_number} • {"RECTO" if self.side.side == 0 else "VERSO"}')
            self.app.side_index = self.index
            self.app.refresh()
            if not keep_selection or self.selected is None or self.selected >= len(self.side.placements):
                self.selected = 0 if self.side.placements else None
            self._sync_props()
            self.draw()
        except Exception as exc:
            self.status.set(f'Błąd: {exc}')
            messagebox.showerror('Edytor arkusza', str(exc), parent=self)

    def change_side(self, shift):
        idx = self.index + shift
        if idx < 0: return
        try:
            image, side = editor_preview(self.project, pixels=500, index=idx)
            if side is None: return
        except Exception as exc:
            messagebox.showerror('Zmiana strony', str(exc), parent=self)
            return
        self.index = idx
        self.refresh_side(keep_selection=False)

    def _bounds(self, slot):
        left, top, scale = self._layout
        return (left+slot.x*scale, top+slot.y*scale,
                left+(slot.x+slot.w)*scale, top+(slot.y+slot.h)*scale)

    def draw(self):
        if self.pil is None or self.side is None or not self.winfo_exists(): return
        self.canvas.delete('all')
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 50 or ch < 50: return
        s = self.project.settings
        scale = min((cw-30)/s.sheet_w, (ch-30)/s.sheet_h)
        pxw = max(1, round(s.sheet_w*scale)); pxh = max(1, round(s.sheet_h*scale))
        left = (cw-pxw)/2; top = (ch-pxh)/2
        self._layout = (left, top, scale)
        img = self.pil.resize((pxw, pxh), Image.Resampling.LANCZOS)
        self.photo_fit = ImageTk.PhotoImage(img)
        self.canvas.create_image(left, top, image=self.photo_fit, anchor='nw', tags=('art',))
        conflicts = {cell for pair in overlapping_uses(self.side, s) for cell in pair}
        for i, placement in enumerate(self.side.placements):
            x0,y0,x1,y1 = self._bounds(placement.slot)
            active = i == self.selected
            self.canvas.create_rectangle(x0,y0,x1,y1,outline='#ff7c7c' if i in conflicts else '#00f9eb' if active else '#368f9c',
                                         width=3 if active else 1, dash=() if active else (5, 4), tags=(f'slot_{i}',))
            if active:
                self.canvas.create_rectangle(x0+2,y0+2,min(x0+28,x1),min(y0+22,y1),fill='#005d66',outline='')
                self.canvas.create_text(x0+14,y0+12,text=str(i+1),fill='white',font=('Segoe UI',10,'bold'))
            if placement.source is None:
                self.canvas.create_text((x0+x1)/2,(y0+y1)/2,text='PUSTE',fill='#e9acac',font=('Segoe UI',11,'bold'))

    def _hit(self, x, y):
        if self.side is None: return None
        # If cells overlap prefer selected one, for precise movement.
        order = [i for i in range(len(self.side.placements)) if i != self.selected]
        if self.selected is not None: order.append(self.selected)
        for i in reversed(order):
            x0,y0,x1,y1 = self._bounds(self.side.placements[i].slot)
            if x0 <= x <= x1 and y0 <= y <= y1: return i
        return None

    def _current_entry(self):
        if self.selected is None: return {}
        return self.project.overrides.get(f'{self.side.sheet_number}:{self.side.side}:{self.selected}', {})

    def _sync_props(self):
        if self.side is None or self.selected is None: return
        placement = self.side.placements[self.selected]
        ref = placement.source
        self.selection_info.set(f'Użytek {self.selected+1} • '
            + (f'{Path(ref.path).name} • strona {ref.index+1}' if ref else 'PUSTE'))
        entry = self._current_entry()
        self.dx_var.set(f'{float(entry.get("dx",0)):.1f}')
        self.dy_var.set(f'{float(entry.get("dy",0)):.1f}')
        self.rotate_var.set(f'{entry.get("rotate",0)}°')
        self.swap_with.set(str(min(self.selected+2, len(self.side.placements))))

    def select(self, i):
        if i is None or self.side is None: return
        self.selected = i
        self._sync_props()
        self.draw()
        self.canvas.focus_set()

    def _operation(self, callback):
        if self.selected is None: return
        try:
            callback()
            self.status.set('Zapisano zmianę użytku — podgląd i eksport są zgodne.')
            self.refresh_side()
            if overlaps := overlapping_uses(self.side, self.project.settings):
                self.status.set(f'UWAGA: nachodzą na siebie użytki: '+', '.join(f'{a+1} i {b+1}' for a,b in overlaps[:5]))
        except Exception as exc:
            messagebox.showerror('Edycja użytku', str(exc), parent=self)
            self.status.set(str(exc))

    def _selected_source(self):
        choice = self.pages.selection()
        if not choice or choice[0] not in self.page_refs:
            raise ValueError('Wybierz konkretną stronę PDF z listy.')
        return self.page_refs[choice[0]]

    def apply(self, kind):
        if self.selected is None: return
        def change():
            if kind == 'assign':
                assign_slot(self.project, self.side, self.selected, self._selected_source())
            elif kind == 'clear':
                assign_slot(self.project, self.side, self.selected, None)
            elif kind == 'reset':
                reset_slot(self.project, self.side, self.selected)
            elif kind == 'swap':
                swap_slots(self.project, self.side, self.selected, int(self.swap_with.get())-1)
        self._operation(change)

    def apply_coords(self):
        if self.selected is None: return
        def update():
            dx = round(float(self.dx_var.get().replace(',', '.')), 1)
            dy = round(float(self.dy_var.get().replace(',', '.')), 1)
            set_slot_transform(self.project, self.side, self.selected, dx=dx, dy=dy)
        self._operation(update)

    def rotate(self, deg):
        if self.selected is None: return
        angle = (int(self._current_entry().get('rotate', 0))+deg)%360
        self._operation(lambda: set_slot_transform(self.project, self.side, self.selected, rotate=angle))

    def nudge(self, dx, dy):
        if self.selected is None: return
        entry = self._current_entry()
        x = round(float(entry.get('dx',0))+dx, 1)
        y = round(float(entry.get('dy',0))+dy, 1)
        self._operation(lambda: set_slot_transform(self.project, self.side, self.selected, dx=x, dy=y))

    def cancel_drag(self):
        self._drag = None
        self.draw()

    def on_canvas_down(self, event):
        i = self._hit(event.x, event.y)
        if i is None: return
        self.select(i)
        self._drag = (i, event.x, event.y, dict(self._current_entry()))

    def on_canvas_drag(self, event):
        if self._drag is None: return
        i, sx, sy, entry = self._drag
        if abs(event.x-sx)+abs(event.y-sy) < 3: return
        self.draw()
        x0,y0,x1,y1 = self._bounds(self.side.placements[i].slot)
        dx=event.x-sx;dy=event.y-sy
        self.canvas.create_rectangle(x0+dx,y0+dy,x1+dx,y1+dy,
                                     outline='#fff394',width=3,dash=(5,3),tags=('drag_ghost',))

    def on_canvas_up(self, event):
        if self._drag is None: return
        i, sx, sy, entry = self._drag
        self._drag = None
        if abs(event.x-sx)+abs(event.y-sy) < 4:
            self.draw(); return
        dest = self._hit(event.x, event.y)
        if dest is not None and dest != i and not (event.state & 0x0001):
            self._operation(lambda: swap_slots(self.project, self.side, i, dest))
            return
        scale = self._layout[2]
        dx = round(float(entry.get('dx',0))+(event.x-sx)/scale,1)
        dy = round(float(entry.get('dy',0))+(event.y-sy)/scale,1)
        self._operation(lambda: set_slot_transform(self.project, self.side, i, dx=dx, dy=dy))

    def on_source_down(self, event):
        iid = self.pages.identify_row(event.y)
        if iid in self.page_refs:
            self.pages.selection_set(iid)
            self.source_start = (iid, event.x_root, event.y_root)
        else:
            self.source_start = None

    def on_source_up(self, event):
        if self.source_start is None: return
        iid, x, y = self.source_start
        self.source_start = None
        if abs(event.x_root-x)+abs(event.y_root-y) < 5: return
        cx = event.x_root-self.canvas.winfo_rootx()
        cy = event.y_root-self.canvas.winfo_rooty()
        if not (0 <= cx < self.canvas.winfo_width() and 0 <= cy < self.canvas.winfo_height()):
            return
        target = self._hit(cx, cy)
        if target is None:
            self.status.set('Upuść stronę na zaznaczonym polu arkusza.')
            return
        self.selected = target
        self._operation(lambda: assign_slot(self.project,self.side,target,self.page_refs[iid]))

