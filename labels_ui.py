"""Desktop UI for parsing actual email messages and producing print-ready labels."""
from __future__ import annotations

import threading
import json
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from labels import (LabelItem, MailHeader, TEMPLATES, infer_template, mail_list,
                    mail_read, make_labels_pdf, normalize_price, parse_mail)


class LabelGeneratorFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=12)
        self.items: list[LabelItem] = []
        self.template_choices: dict[str, str] = {}
        self.mail_headers: list[MailHeader] = []
        self._busy = False
        self._load_mail_settings()
        self._layout()

    def _layout(self):
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 8))
        ttk.Label(header, text='GENERATOR ETYKIET', font=('Segoe UI', 16, 'bold')).pack(side='left')
        ttk.Label(header, text='Wypieki 11×5 cm z ceną  •  Lody 9×5 cm bez ceny  •  PDF A4',
                  foreground='#a7b4c8').pack(side='right')

        left = ttk.Frame(self, padding=12, style='Panel.TFrame')
        left.grid(row=1, column=0, sticky='nsew', padx=(0, 7))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(5, weight=1)
        ttk.Label(left, text='1. WCZYTAJ TREŚĆ WIADOMOŚCI', style='Header.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(left, text='Poczta IMAP przez SSL lub zwykłe wklejenie tekstu. Hasło nie jest zapisywane.',
                  style='Muted.TLabel', wraplength=460).grid(row=1, column=0, sticky='w', pady=(4, 8))
        self.host = tk.StringVar(value='')
        self.port = tk.StringVar(value='993')
        self.login = tk.StringVar(value='')
        self.password = tk.StringVar(value='')
        self.search = tk.StringVar(value='')
        self.mail_group = ttk.LabelFrame(left, text='Połączenie z pocztą (IMAP SSL)', padding=8)
        self.mail_group.grid(row=2, column=0, sticky='ew')
        self.mail_group.columnconfigure(1, weight=1)
        rows = [('Serwer IMAP', self.host, False), ('Port', self.port, False),
                ('Pełny adres e-mail / login', self.login, False), ('Hasło / hasło aplikacji', self.password, True)]
        for ri,(label,var,secret) in enumerate(rows):
            ttk.Label(self.mail_group, text=label, style='Panel.TLabel').grid(row=ri,column=0,sticky='w',pady=2)
            ttk.Entry(self.mail_group, textvariable=var, show='•' if secret else '', width=20).grid(
                row=ri,column=1,sticky='ew',padx=(7,0),pady=2)
        row = ttk.Frame(self.mail_group, style='Panel.TFrame')
        row.grid(row=4,column=0,columnspan=2,sticky='ew',pady=(6,0))
        ttk.Label(row,text='Filtr tematu/nadawcy:', style='Panel.TLabel').pack(side='left')
        ttk.Entry(row,textvariable=self.search, width=18).pack(side='left',padx=6,fill='x',expand=True)
        ttk.Button(row,text='Pobierz listę maili',command=self.fetch_list).pack(side='right')
        self.mailbox = ttk.Treeview(self.mail_group, columns=('sender','subject'), show='headings', height=4, selectmode='browse')
        self.mailbox.heading('sender',text='Od')
        self.mailbox.heading('subject',text='Temat')
        self.mailbox.column('sender',width=160)
        self.mailbox.column('subject',width=250)
        self.mailbox.grid(row=5,column=0,columnspan=2,sticky='ew',pady=6)
        self.mailbox.bind('<Double-1>',lambda _:self.fetch_mail())
        ttk.Button(self.mail_group,text='Wczytaj zaznaczony mail',command=self.fetch_mail).grid(
            row=6,column=0,columnspan=2,sticky='ew')
        ttk.Button(self.mail_group,text='Zapamiętaj serwer/adres (BEZ hasła)',command=self._save_mail_settings).grid(
            row=7,column=0,columnspan=2,sticky='ew',pady=(3,0))
        ttk.Label(left,text='Lub wklej treść maila:',style='Panel.TLabel').grid(row=3,column=0,sticky='w',pady=(10,3))
        bar = ttk.Frame(left, style='Panel.TFrame')
        bar.grid(row=4,column=0,sticky='ew')
        ttk.Button(bar,text='Wklej ze schowka',command=self.paste).pack(side='left')
        ttk.Button(bar,text='Otwórz TXT / EML',command=self.open_file).pack(side='left',padx=5)
        ttk.Button(bar,text='Rozpoznaj pozycje',command=self.parse,style='Accent.TButton').pack(side='right')
        self.body = tk.Text(left,wrap='word',undo=True,background='#111927',foreground='#edf2f7',
                            insertbackground='#edf2f7',relief='flat',font=('Segoe UI',10),height=12)
        self.body.grid(row=5,column=0,sticky='nsew',pady=(6,0))

        right = ttk.Frame(self, padding=12, style='Panel.TFrame')
        right.grid(row=1,column=1,sticky='nsew',padx=(7,0))
        right.columnconfigure(0,weight=1)
        right.rowconfigure(2,weight=1)
        ttk.Label(right,text='2. SPRAWDŹ ETYKIETY',style='Header.TLabel').grid(row=0,column=0,sticky='w')
        self.summary = tk.StringVar(value='Dodaj wiadomość i kliknij Rozpoznaj pozycje.')
        ttk.Label(right,textvariable=self.summary,style='Muted.TLabel',wraplength=530).grid(
            row=1,column=0,sticky='w',pady=(4,8))
        table = ttk.Frame(right, style='Panel.TFrame')
        table.grid(row=2,column=0,sticky='nsew')
        self.tree = ttk.Treeview(table,columns=('cat','name','price','copies'),show='headings',selectmode='browse')
        for key,label,width in [('cat','Kategoria',105),('name','Etykieta',280),('price','Cena',80),('copies','Szt.',45)]:
            self.tree.heading(key,text=label)
            self.tree.column(key,width=width,stretch=key=='name',anchor='center' if key=='copies' else 'w')
        self.tree.pack(side='left',fill='both',expand=True)
        sb=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        sb.pack(side='right',fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.select_item())
        self.tree.bind('<Double-1>',lambda _:self.select_item())
        editor=ttk.LabelFrame(right,text='Edytuj zaznaczoną etykietę',padding=8)
        editor.grid(row=3,column=0,sticky='ew',pady=(8,3))
        editor.columnconfigure(1,weight=1)
        self.edit_name = tk.StringVar()
        self.edit_price = tk.StringVar()
        self.edit_cat = tk.StringVar()
        self.edit_copies = tk.StringVar(value='1')
        for i,(label,var) in enumerate((('Nazwa',self.edit_name),('Kategoria',self.edit_cat),
                                        ('Cena (może być pusta)',self.edit_price),('Liczba kopii',self.edit_copies))):
            ttk.Label(editor,text=label,style='Panel.TLabel').grid(row=i,column=0,sticky='w',pady=1)
            ttk.Entry(editor,textvariable=var).grid(row=i,column=1,sticky='ew',padx=8,pady=1)
        b=ttk.Frame(editor,style='Panel.TFrame')
        b.grid(row=4,column=0,columnspan=2,sticky='ew',pady=(6,0))
        ttk.Button(b,text='Zapisz zmiany',command=self.save_item).pack(side='left')
        ttk.Button(b,text='Dodaj nową',command=self.add_item).pack(side='left',padx=5)
        ttk.Button(b,text='Usuń zaznaczoną',command=self.remove_item).pack(side='right')
        layout = ttk.LabelFrame(right,text='3. FORMAT I DRUK',padding=8)
        layout.grid(row=4,column=0,sticky='ew',pady=(8,0))
        ttk.Label(layout,text='Kategoria:',style='Panel.TLabel').grid(row=0,column=0,sticky='w')
        self.category_selector=tk.StringVar()
        combo=ttk.Combobox(layout,textvariable=self.category_selector,state='readonly',width=24)
        combo.grid(row=0,column=1,sticky='ew',padx=5)
        combo.bind('<<ComboboxSelected>>',lambda _:self.refresh_template())
        self.category_combo=combo
        ttk.Label(layout,text='Szablon:',style='Panel.TLabel').grid(row=1,column=0,sticky='w',pady=5)
        self.template_selector=tk.StringVar()
        self.template_combo=ttk.Combobox(layout,textvariable=self.template_selector,values=TEMPLATES,state='readonly',width=35)
        self.template_combo.grid(row=1,column=1,sticky='ew',padx=5,pady=5)
        ttk.Button(layout,text='Zastosuj',command=self.set_template).grid(row=1,column=2,padx=4)
        self.cut_lines=tk.BooleanVar(value=True)
        ttk.Checkbutton(layout,text='Delikatne linie cięcia',variable=self.cut_lines).grid(row=2,column=0,columnspan=3,sticky='w')
        ttk.Button(layout,text='WYGENERUJ PDF DO DRUKU',style='Accent.TButton',command=self.export).grid(
            row=3,column=0,columnspan=3,sticky='ew',pady=(8,1))
        layout.columnconfigure(1,weight=1)
        self.status=tk.StringVar(value='Gotowe. Wiadomości IMAP są pobierane tylko po kliknięciu.')
        ttk.Label(self,textvariable=self.status,foreground='#a7b4c8').grid(
            row=2,column=0,columnspan=2,sticky='w',pady=(8,0))

    @staticmethod
    def _settings_path():
        folder=Path(os.environ.get('APPDATA') or Path.home()/'.config')/'ImpozycjonerStudio'
        return folder/'mail_settings.json'

    def _load_mail_settings(self):
        try:
            data=json.loads(self._settings_path().read_text(encoding='utf-8'))
            for key, variable in (('host',self.host),('port',self.port),
                                  ('login',self.login),('search',self.search)):
                if isinstance(data.get(key),str): variable.set(data[key])
        except (OSError,ValueError,TypeError):
            pass

    def _save_mail_settings(self):
        path=self._settings_path()
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({
                'host':self.host.get().strip(), 'port':self.port.get().strip(),
                'login':self.login.get().strip(), 'search':self.search.get().strip()
            },ensure_ascii=False,indent=2),encoding='utf-8')
            self.status.set('Zapamiętano serwer i adres; hasło nie jest zapisywane.')
        except OSError as exc:
            messagebox.showerror('Ustawienia',str(exc),parent=self)

    def _imap_args(self):
        try:
            port=int(self.port.get().strip())
            if not 1 <= port <= 65535: raise ValueError()
        except ValueError:
            raise ValueError('Port IMAP musi być liczbą 1–65535.')
        return (self.host.get().strip(),port,self.login.get().strip(),self.password.get())

    def _work(self, target, finish):
        if self._busy: return
        self._busy=True
        self.status.set('Łączenie z serwerem poczty…')
        def run():
            try:
                result=target()
                self.after(0,lambda:self._finish(finish,result,None))
            except Exception as exc:
                self.after(0,lambda err=str(exc):self._finish(finish,None,err))
        threading.Thread(target=run,daemon=True).start()

    def _finish(self, finish, result, err):
        self._busy=False
        if err:
            self.status.set('Błąd połączenia. Sprawdź dane IMAP.')
            messagebox.showerror('Poczta IMAP',err,parent=self)
            return
        finish(result)

    def fetch_list(self):
        try: args=self._imap_args()
        except ValueError as exc:
            messagebox.showerror('IMAP',str(exc));return
        self._work(lambda:mail_list(*args),self._show_mails)

    def _show_mails(self, found):
        self.mail_headers=found
        self.mailbox.delete(*self.mailbox.get_children())
        needle=self.search.get().strip().casefold()
        shown=0
        for i,item in enumerate(found):
            if needle and needle not in (item.subject+' '+item.sender).casefold():
                continue
            self.mailbox.insert('', 'end', iid=str(i), values=(item.sender,item.subject))
            shown+=1
        self.status.set(f'Pobrano nagłówki {len(found)} maili; wyświetlono {shown}. Wybierz wiadomość.')

    def fetch_mail(self):
        selection=self.mailbox.selection()
        if not selection:
            messagebox.showinfo('Mail','Zaznacz wiadomość z listy.',parent=self)
            return
        try: args=self._imap_args()
        except ValueError as exc:
            messagebox.showerror('IMAP',str(exc));return
        uid=self.mail_headers[int(selection[0])].uid
        self._work(lambda:mail_read(*args,uid),self._show_mail)

    def _show_mail(self, text):
        self.body.delete('1.0','end')
        self.body.insert('1.0',text)
        self.parse()
        self.status.set('Załadowano mail (bez oznaczania jako przeczytany). Sprawdź pozycje i ceny.')

    def paste(self):
        try: text=self.clipboard_get()
        except tk.TclError: text=''
        if text:
            self.body.delete('1.0','end')
            self.body.insert('1.0',text)
            self.parse()

    def open_file(self):
        file=filedialog.askopenfilename(parent=self,filetypes=[('Treść poczty','*.txt *.eml'),('Wszystkie','*.*')])
        if not file:return
        try:
            raw=Path(file).read_bytes()
            if file.lower().endswith('.eml'):
                from labels import decode_email
                text=decode_email(raw)
            else:
                text=raw.decode('utf-8-sig')
            self.body.delete('1.0','end')
            self.body.insert('1.0',text)
            self.parse()
        except Exception as exc:
            messagebox.showerror('Otwieranie maila',str(exc),parent=self)

    def parse(self):
        found=parse_mail(self.body.get('1.0','end'))
        if not found:
            messagebox.showwarning('Generator','Nie wykryto pozycji. Sprawdź, czy produkty są listą pod nazwą kategorii.',parent=self)
            return
        self.items=found
        self.template_choices={}
        self.refresh_items()
        self.status.set(f'Rozpoznano {len(found)} pozycji. Sprawdź nazwy oraz ceny przed eksportem.')

    def refresh_items(self, select=0):
        self.tree.delete(*self.tree.get_children())
        for i,item in enumerate(self.items):
            self.tree.insert('', 'end', iid=str(i), values=(item.category,item.name,item.price or '—',item.copies))
        cats=list(dict.fromkeys(x.category for x in self.items))
        self.category_combo['values']=cats
        if cats:
            if self.category_selector.get() not in cats:self.category_selector.set(cats[0])
            self.refresh_template()
        self.summary.set(f'{len(self.items)} pozycji · {sum(x.copies for x in self.items)} etykiet · '+
                         ', '.join(f'{cat}: {sum(x.copies for x in self.items if x.category==cat)}' for cat in cats))
        if self.items:
            selected=min(max(0,select),len(self.items)-1)
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))
            self.select_item()

    def select_item(self):
        sel=self.tree.selection()
        if not sel:return
        item=self.items[int(sel[0])]
        self.edit_name.set(item.name)
        self.edit_cat.set(item.category)
        self.edit_price.set(item.price)
        self.edit_copies.set(str(item.copies))

    def _edit_values(self):
        name=self.edit_name.get().strip()
        category=self.edit_cat.get().strip() or 'Inne'
        copies=int(self.edit_copies.get())
        if not name or not 1 <= copies <= 5000:
            raise ValueError('Podaj nazwę i liczbę etykiet od 1 do 5000.')
        price=normalize_price(self.edit_price.get()) if self.edit_price.get().strip() else ''
        return LabelItem(category,name,price,copies)

    def save_item(self):
        sel=self.tree.selection()
        if not sel:return
        try: item=self._edit_values()
        except ValueError as exc:
            messagebox.showerror('Etykieta',str(exc));return
        ix=int(sel[0]);self.items[ix]=item
        self.refresh_items(ix)

    def add_item(self):
        try: item=self._edit_values()
        except ValueError as exc:
            messagebox.showerror('Etykieta',str(exc));return
        self.items.append(item)
        self.refresh_items(len(self.items)-1)

    def remove_item(self):
        sel=self.tree.selection()
        if sel:
            self.items.pop(int(sel[0]))
            self.refresh_items()

    def refresh_template(self):
        cat=self.category_selector.get()
        records=[x for x in self.items if x.category==cat]
        if records:
            self.template_selector.set(self.template_choices.get(cat,infer_template(cat,records)))

    def set_template(self):
        cat=self.category_selector.get()
        choice=self.template_selector.get()
        if cat and choice in TEMPLATES:
            self.template_choices[cat]=choice
            self.status.set(f'Kategoria „{cat}” używa szablonu „{choice}”.')

    def export(self):
        if not self.items:
            messagebox.showwarning('Generator','Najpierw wczytaj wiadomość i sprawdź pozycje.',parent=self);return
        file=filedialog.asksaveasfilename(parent=self,defaultextension='.pdf',
            initialfile='etykiety_do_druku.pdf',filetypes=[('PDF do druku','*.pdf')])
        if not file:return
        try:
            pages=make_labels_pdf(self.items,file,self.template_choices,self.cut_lines.get())
        except Exception as exc:
            messagebox.showerror('Generowanie PDF',str(exc),parent=self)
            return
        self.status.set('Zapisano PDF: '+file)
        messagebox.showinfo('Gotowy PDF',f'Zapisano: {file}\n\n'+
           '\n'.join(f'{c}: {n} str. A4' for c,n in pages.items())+
           '\n\nSprawdź podgląd i wykonaj wydruk próbny w skali 100%.',parent=self)
