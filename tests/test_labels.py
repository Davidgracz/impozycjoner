"""Mail parsing and vector PDF production regression checks."""
from pathlib import Path
from email.message import EmailMessage

import pymupdf as fitz
import pytest

from labels import (
    LabelItem, TEMPLATE_BAKERY, TEMPLATE_ICE, TEMPLATE_STANDARD,
    _dims, decode_email, infer_template, make_labels_pdf, normalize_price,
    parse_mail,
)


def sample():
    return Path(__file__).parent.parent / 'examples/mail_przykladowy_etykiety.txt'


def test_mail_sample_extracts_18_items_and_2_categories():
    rows=parse_mail(sample().read_text(encoding='utf-8'))
    assert len(rows)==18
    assert [r.category for r in rows].count('Ciastka')==11
    assert [r.category for r in rows].count('Lody')==7
    assert rows[0].price=='26 zł'
    assert rows[2].price==''  # missing price must stay missing
    assert rows[11].price==''
    assert rows[-1].name=='Lody waniliowe z migdałami'
    assert all('Pozdrawiam' not in x.name for x in rows)


def test_mail_headings_and_bullets():
    rows=parse_mail('Dzień dobry\nWypieki:\n- Babka cytrynowa 12 zł\n- Sernik 22,50 PLN\nLody\n* Mango\n* Czekolada\nPozdrawiamy')
    assert [(x.category,x.name,x.price) for x in rows]==[
        ('Wypieki','Babka cytrynowa','12 zł'),
        ('Wypieki','Sernik','22,50 zł'),
        ('Lody','Mango',''),('Lody','Czekolada','')]


def test_ignore_unstructured_mail_prose_and_signatures():
    rows=parse_mail('Zamówienie nr 123\n- Proszę pilnie odpisać\nProdukty:\n• Muffinka 12 zł\nZ poważaniem\n• Kontakt: telefon')
    assert len(rows)==1 and rows[0].name=='Muffinka'


def test_mime_plain_text_preferred_over_html():
    msg=EmailMessage()
    msg['Subject']='Etykiety'
    msg.set_content('Wypieki:\n• Orzechowiec 16 zł')
    msg.add_alternative('<p>Lody:</p><ul><li>Truskawka</li></ul>',subtype='html')
    assert decode_email(msg.as_bytes()).startswith('Wypieki:')
    rows=parse_mail(decode_email(msg.as_bytes()))
    assert len(rows)==1 and rows[0].price=='16 zł'


def test_html_only_mail():
    msg=EmailMessage()
    msg.set_content('<div>Ciastka:</div><ul><li>Babka cytrynowa 12 zł</li></ul><div>Lody</div><ul><li>Malina</li></ul>',subtype='html')
    rows=parse_mail(decode_email(msg.as_bytes()))
    assert [(x.category,x.name) for x in rows]==[('Ciastka','Babka cytrynowa'),('Lody','Malina')]


def test_prices_preserved_and_missing_not_invented():
    assert normalize_price('26 zł')=='26 zł'
    assert normalize_price('24,5 PLN')=='24,50 zł'
    assert normalize_price('0 zł')=='0 zł'
    assert normalize_price('')==''
    with pytest.raises(ValueError):normalize_price('bez ceny')


def test_preferred_old_layouts():
    assert infer_template('Ciastka',[LabelItem('Ciastka','Sernik','20 zł')])==TEMPLATE_BAKERY
    assert infer_template('Lody',[LabelItem('Lody','Malina')])==TEMPLATE_ICE
    assert _dims(TEMPLATE_BAKERY)==(110,50,True,(297,210))
    assert _dims(TEMPLATE_ICE)==(90,50,False,(210,297))


def test_18_labels_a4_mixed_orientation_vector_and_polish(tmp_path):
    rows=parse_mail(sample().read_text(encoding='utf-8'))
    out=tmp_path/'labels.pdf'
    pages=make_labels_pdf(rows,out)
    assert pages=={'Ciastka':2,'Lody':1}  # 2×4 then 2×5
    with fitz.open(out) as doc:
        assert len(doc)==3
        assert abs(doc[0].rect.width - 297*72/25.4)<.1
        assert abs(doc[0].rect.height - 210*72/25.4)<.1
        assert abs(doc[2].rect.width - 210*72/25.4)<.1
        assert abs(doc[2].rect.height - 297*72/25.4)<.1
        assert 'Drożdżówka z malinami' in doc[0].get_text()
        assert 'Lody waniliowe z' in doc[2].get_text() and 'migdałami' in doc[2].get_text()
        assert '26 zł' in doc[0].get_text()
        assert 'zł' not in doc[2].get_text()
        assert doc[0].get_images(full=True)==[]
        assert doc[2].get_images(full=True)==[]


def test_copies_and_category_template_override(tmp_path):
    rows=[LabelItem('Nowości','Świeży sernik', '12 zł',copies=12)]
    out=tmp_path/'copies.pdf'
    pages=make_labels_pdf(rows,out,{'Nowości':TEMPLATE_STANDARD})
    assert pages=={'Nowości':2}
    with fitz.open(out) as doc:
        assert doc[0].get_text().count('Świeży sernik')==10
        assert doc[1].get_text().count('Świeży sernik')==2


def test_too_many_copies_rejected(tmp_path):
    with pytest.raises(ValueError,match='5000'):
        make_labels_pdf([LabelItem('X','Product',copies=5001)],tmp_path/'x.pdf')


def test_long_name_never_silently_truncated(tmp_path):
    name='Pyszna '+('bardzo ' * 3000)+'ciastko'
    out=tmp_path/'verylong.pdf'
    with pytest.raises(ValueError,match='nie mieści'):
        make_labels_pdf([LabelItem('Ciastka',name,'14 zł')],out)
    assert not out.exists()


def test_imap_read_only_headers_and_message(monkeypatch):
    from labels import mail_list, mail_read
    class FakeIMAP:
        def __init__(self,*a,**kw): self.calls=[]
        def __enter__(self):return self
        def __exit__(self,*a): pass
        def login(self,user,password):
            assert (user,password)==('test@example.org','test-secret')
        def select(self,folder,readonly):
            assert folder=='INBOX' and readonly is True
            return 'OK',[b'2']
        def uid(self,cmd,uid,*args):
            self.calls.append((cmd,uid,args))
            if cmd=='SEARCH':return 'OK',[b'100 101']
            if cmd=='FETCH' and args==('(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])',):
                return 'OK', [(b'', b'From: Zamawiajacy <person@example.org>\r\nSubject: Etykiety\r\nDate: Mon, 12 Oct 2026 08:00:00 +0000\r\n\r\n')]
            if cmd=='FETCH' and args==('(BODY.PEEK[])',):
                return 'OK',[(b'',b'Subject: Etykiety\r\nContent-Type: text/plain; charset="utf-8"\r\n\r\nWypieki:\r\n- Muffinka 12 zl\r\n')]
            raise AssertionError(f'Unexpected IMAP command: {cmd} {uid} {args}')
    monkeypatch.setattr('labels.imaplib.IMAP4_SSL',FakeIMAP)
    heads=mail_list('imap.example.org',993,'test@example.org','test-secret')
    assert [x.uid for x in heads]==['101','100']
    assert heads[0].subject=='Etykiety'
    body=mail_read('imap.example.org',993,'test@example.org','test-secret','101')
    assert len(parse_mail(body))==1


def test_settings_persist_without_password(tmp_path,monkeypatch):
    # Integration UI with Tk requires a graphical display; static check keeps
    # CI runners headless and ensures the password never enters config JSON.
    from labels_ui import LabelGeneratorFrame
    source=Path(__file__).parent.parent.joinpath('labels_ui.py').read_text(encoding='utf-8')
    assert "'host':self.host.get().strip()" in source
    assert 'self.password.get()' not in source[source.index('def _save_mail_settings'):source.index('def _imap_args')]
