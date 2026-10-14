"""Visual PDF crop-centre editor. UI rectangles are guides, never printed."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from PIL import Image, ImageTk
import pymupdf as fitz

from engine import source_summary, gross_dimensions, pt, mm


class CropEditor(tk.Toplevel):
    """Drag the gross/net outline over actual source PDF pixels, at 1:1 geometry."""

    def __init__(self, parent, path: str, settings, x: float, y: float, on_apply):
        super().__init__(parent)
        self.title('Kadrowanie na PDF — '+Path(path).name)
        self.geometry('900x710')
        self.minsize(680, 580)
        self.transient(parent)
        self.path = path
        self.on_apply = on_apply
        self.settings = settings
        _, self.orig_w, self.orig_h = source_summary(path)
        self.gross_w, self.gross_h = gross_dimensions(settings)
        if self.gross_w > self.orig_w+.02 or self.gross_h > self.orig_h+.02:
            raise ValueError('Użytek brutto jest większy niż oryginał. Zmień format lub sposób kadrowania.')
        self.x = self._clamp(x, (self.orig_w-self.gross_w)/2)
        self.y = self._clamp(y, (self.orig_h-self.gross_h)/2)
        self.original = self._load_pdf_preview()
        self.preview_photo = None
        self.drag_start = None
        self.anchor_x = self.x
        self.anchor_y = self.y
        self._layout()
        self.after(100, self._draw)

    @staticmethod
    def _clamp(value, limit):
        return round(max(-max(0.0, limit), min(max(0.0, limit), float(value))), 1)

    def _load_pdf_preview(self):
        with fitz.open(self.path) as doc:
            page = doc[0]
            # Respect page trim when possible, not extra PDF marks on MediaBox.
            bbox = fitz.Rect(page.trimbox)
            if page.rotation in (90, 270):
                bbox = fitz.Rect(page.rect)
            if not page.rotation:
                bbox = bbox & page.rect
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), clip=bbox if not bbox.is_empty else None,
                                  alpha=False)
            return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)

    def _layout(self):
        ttk.Label(self,text='PRZESUŃ RAMKĘ BRUTTO NA PROJEKCIE PDF',
                  font=('Segoe UI',14,'bold')).pack(anchor='w',padx=16,pady=(14,5))
        ttk.Label(self,text=f'Źródło: {self.orig_w:g} × {self.orig_h:g} mm   |   '
                  f'Brutto: {self.gross_w:g} × {self.gross_h:g} mm   |   '
                  f'Netto: {self.settings.trim_w:g} × {self.settings.trim_h:g} mm   |   '
                  f'Spad: {(self.gross_w-self.settings.trim_w)/2:g} mm',
                  wraplength=850).pack(anchor='w',padx=16,pady=(0,8))
        self.canvas=tk.Canvas(self,bg='#131921',highlightthickness=0,cursor='fleur')
        self.canvas.pack(expand=True,fill='both',padx=16,pady=6)
        self.canvas.bind('<Configure>',lambda e:self._draw())
        self.canvas.bind('<ButtonPress-1>',self._start_drag)
        self.canvas.bind('<B1-Motion>',self._drag)
        self.canvas.bind('<ButtonRelease-1>',lambda e:self._stop_drag())
        bar=ttk.Frame(self);bar.pack(fill='x',padx=16,pady=6)
        ttk.Label(bar,text='Kadr X (mm):').pack(side='left')
        self.xvar=tk.StringVar(value=f'{self.x:.1f}')
        ttk.Entry(bar,textvariable=self.xvar,width=8).pack(side='left',padx=(5,14))
        ttk.Label(bar,text='Kadr Y (mm):').pack(side='left')
        self.yvar=tk.StringVar(value=f'{self.y:.1f}')
        ttk.Entry(bar,textvariable=self.yvar,width=8).pack(side='left',padx=(5,14))
        ttk.Button(bar,text='Zastosuj X/Y',command=self._from_entries).pack(side='left')
        ttk.Button(bar,text='Wyśrodkuj',command=self._reset).pack(side='left',padx=7)
        buttons=ttk.Frame(self);buttons.pack(fill='x',padx=16,pady=(4,15))
        ttk.Label(buttons,text='Turkus = brutto / pomarańczowy = netto. Ruch co 0,1 mm; export PDF pozostaje wektorowy.').pack(side='left')
        ttk.Button(buttons,text='ZAPISZ KADR',command=self._apply).pack(side='right')
        ttk.Button(buttons,text='Anuluj',command=self.destroy).pack(side='right',padx=6)

    def _layout_image(self):
        cw=max(300,self.canvas.winfo_width()-26)
        ch=max(180,self.canvas.winfo_height()-26)
        # Place preview using same metric aspect as dimensions in PDF.
        scale=min(cw/self.orig_w,ch/self.orig_h)
        width=max(1,round(self.orig_w*scale))
        height=max(1,round(self.orig_h*scale))
        x0=(self.canvas.winfo_width()-width)/2
        y0=(self.canvas.winfo_height()-height)/2
        return x0,y0,width,height,scale

    def _draw(self):
        if not self.winfo_exists():return
        c=self.canvas;c.delete('all')
        x0,y0,w,h,scale=self._layout_image()
        image=self.original.resize((w,h),Image.Resampling.LANCZOS)
        self.preview_photo=ImageTk.PhotoImage(image)
        c.create_image(x0,y0,image=self.preview_photo,anchor='nw')
        for width,height,color,weight in ((self.gross_w,self.gross_h,'#00ccc1',3),
                                           (self.settings.trim_w,self.settings.trim_h,'#ef942c',2)):
            left=x0+(self.orig_w/2+self.x-width/2)*scale
            top=y0+(self.orig_h/2+self.y-height/2)*scale
            c.create_rectangle(left,top,left+width*scale,top+height*scale,
                               outline=color,width=weight,tags='crop-box')
        c.create_text(x0+7,y0+7,text=f'KADR X={self.x:+.1f}  Y={self.y:+.1f} mm',
                      anchor='nw',fill='#fff',font=('Segoe UI',12,'bold'))

    def _start_drag(self,e):
        x0,y0,w,h,scale=self._layout_image()
        self.drag_start=(e.x,e.y,scale)
        self.anchor_x,self.anchor_y=self.x,self.y

    def _drag(self,e):
        if not self.drag_start:return
        start_x,start_y,scale=self.drag_start
        self.x=self._clamp(self.anchor_x+(e.x-start_x)/scale,(self.orig_w-self.gross_w)/2)
        self.y=self._clamp(self.anchor_y+(e.y-start_y)/scale,(self.orig_h-self.gross_h)/2)
        self.xvar.set(f'{self.x:.1f}');self.yvar.set(f'{self.y:.1f}')
        self._draw()

    def _stop_drag(self):
        self.drag_start=None

    def _from_entries(self):
        try:
            x=float(self.xvar.get().replace(',','.'))
            y=float(self.yvar.get().replace(',','.'))
        except ValueError:
            messagebox.showerror('Kadr', 'Wprowadź liczby X i Y.',parent=self)
            return False
        if abs(x) > (self.orig_w-self.gross_w)/2+.001 or abs(y) > (self.orig_h-self.gross_h)/2+.001:
            messagebox.showerror('Kadr','Kadr ze spadami wychodzi poza oryginalny PDF.',parent=self)
            return False
        self.x=round(x,1);self.y=round(y,1)
        self._draw()
        return True

    def _reset(self):
        self.x=self.y=0.0
        self.xvar.set('0.0');self.yvar.set('0.0')
        self._draw()

    def _apply(self):
        if not self._from_entries():
            return
        try:
            self.on_apply(self.x,self.y)
        except ValueError as exc:
            messagebox.showerror('Kadr',str(exc),parent=self)
            return
        self.destroy()
