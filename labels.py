"""Mail-to-print label generator. No email credentials or message bodies are stored.

Uses Unicode TrueType fonts installed on the operating system. PDF pages are
real A4 sheets with vector text; labels are never rasterized.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
import imaplib
import re
import sys

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

MM = 72 / 25.4

TEMPLATE_BAKERY = 'Wypieki 110 × 50 mm (cena)'
TEMPLATE_ICE = 'Lody 90 × 50 mm (bez ceny)'
TEMPLATE_STANDARD = 'Uniwersalne 90 × 50 mm (cena)'
TEMPLATES = (TEMPLATE_BAKERY, TEMPLATE_ICE, TEMPLATE_STANDARD)


@dataclass
class LabelItem:
    category: str
    name: str
    price: str = ''
    copies: int = 1


@dataclass(frozen=True)
class MailHeader:
    uid: str
    sender: str
    subject: str
    date: str


class _MailHtml(HTMLParser):
    def __init__(self):
        super().__init__()
        self.output: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self.skip += 1
        elif not self.skip:
            if tag == 'li':
                self.output.append('\n• ')
            elif tag in ('br', 'p', 'div', 'ul', 'ol', 'tr', 'h1', 'h2', 'h3'):
                self.output.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'):
            self.skip = max(0, self.skip - 1)
        elif not self.skip and tag in ('p', 'div', 'li', 'ul', 'ol', 'tr', 'h1', 'h2', 'h3'):
            self.output.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.output.append(data)


def _html_to_text(html: str) -> str:
    h = _MailHtml()
    h.feed(html)
    return ''.join(h.output)


def decode_email(raw: bytes) -> str:
    """Plain-text MIME part wins; HTML-only mail is converted to readable lines."""
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    plain: list[str] = []
    html: list[str] = []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_disposition() == 'attachment':
            continue
        if part.get_content_type() not in ('text/plain', 'text/html'):
            continue
        try:
            value = part.get_content()
            if isinstance(value, bytes):
                value = value.decode(part.get_content_charset() or 'utf-8', errors='replace')
            if part.get_content_type() == 'text/plain':
                plain.append(value)
            else:
                html.append(value)
        except (LookupError, UnicodeError, ValueError):
            continue
    return '\n'.join(plain).strip() or _html_to_text('\n'.join(html)).strip()


_GREETING = re.compile(
    r'^(dzień dobry|dzien dobry|witam|cześć|czesc|szanowni|pozdrawiamy|pozdrawiam|zespół|zespol|'
    r'przesyłam|przesylam|proszę|prosze|serdecznie|zamówienie nr|zamowienie nr|z poważaniem|z powazaniem|--|sent from|wysłano z)', re.I)
_BULLET = re.compile(r'^\s*(?:[•●·*\-–—]\s+|\d+[.)]\s+)(.+)$')
_PRICE = re.compile(r'(?<!\w)(\d{1,5}(?:[,.]\d{1,2})?)(?:\s*[,\-]\s*)?\s*(?:zł(?:otych)?|zl|pln)\b\s*[.!]?$', re.I)


def normalize_price(value: str) -> str:
    value = value.strip().replace('\u00a0', ' ').replace('PLN', 'zł').replace('zl', 'zł')
    if not value:
        return ''
    matched = _PRICE.search(value)
    if not matched or matched.start() > 1:
        raise ValueError(f'Nie rozpoznano ceny: {value!r}. Przykład: 26 zł albo 26,50 zł.')
    try:
        amount = Decimal(matched.group(1).replace(',', '.'))
    except InvalidOperation as exc:
        raise ValueError('Nieprawidłowa cena') from exc
    if amount < 0:
        raise ValueError('Cena nie może być ujemna')
    result = f'{amount:.2f}'.replace('.', ',')
    if result.endswith(',00'):
        result = result[:-3]
    return result + ' zł'


def parse_mail(text: str) -> list[LabelItem]:
    """Recognise category headings followed by bullet items, with optional PLN prices.

    Intentional conservative parsing: mail signatures, greetings, order numbers,
    prose and non-list text must not become printable labels.
    """
    normalized = text.replace('\r', '').replace('\u00a0', ' ').replace('\u200b', '')
    lines = [re.sub(r'\s+', ' ', s).strip() for s in normalized.split('\n')]
    items: list[LabelItem] = []
    category = ''
    active = False
    for i, line in enumerate(lines):
        if not line:
            continue
        if _GREETING.match(line):
            if line.lower().startswith(('pozdrawiam', 'z poważaniem', 'z powazaniem')):
                active = False
            continue
        bullet = _BULLET.match(line)
        if bullet:
            if not active:
                # Do not convert arbitrary bulleted prose before a product section.
                continue
            content = bullet.group(1).strip()
            m = _PRICE.search(content)
            price = normalize_price(m.group()) if m else ''
            name = content[:m.start()].strip(' -–—;:.,') if m else content.strip(' -–—;:.,')
            if name:
                items.append(LabelItem(category, name, price))
            continue
        # A category heading has a trailing colon or precedes a bullet line.
        next_nonempty = next((s for s in lines[i+1:] if s), '')
        heading = (line.endswith(':') or bool(_BULLET.match(next_nonempty)))
        heading = heading and len(line) <= 65 and not _PRICE.search(line)
        if heading and not _GREETING.match(line):
            category = line.rstrip(':').strip()
            active = True
            continue
        # Wrapped description after a bullet: only append if line is indented
        # in original mail. Non-list ordinary prose is deliberately ignored.
    return items


def infer_template(category: str, records: list[LabelItem]) -> str:
    n = category.casefold()
    if 'lod' in n or 'sorbet' in n:
        return TEMPLATE_ICE
    if any(w in n for w in ('ciast', 'wypiek', 'cukier', 'tort')):
        return TEMPLATE_BAKERY
    return TEMPLATE_STANDARD if any(x.price for x in records) else TEMPLATE_ICE


def _font_pair() -> tuple[str, str]:
    """Find system-installed Unicode fonts (no font distribution in the ZIP)."""
    candidates: list[tuple[str, str]] = []
    if sys.platform == 'win32':
        root = Path('C:/Windows/Fonts')
        candidates.extend([
            (str(root/'futura.ttf'), str(root/'futurab.ttf')),
            (str(root/'arial.ttf'), str(root/'arialbd.ttf')),
            (str(root/'segoeui.ttf'), str(root/'segoeuib.ttf')),
        ])
    candidates.extend([
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        ('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'),
    ])
    for regular, bold in candidates:
        if Path(regular).is_file() and Path(bold).is_file():
            return regular, bold
    raise RuntimeError('Brak czcionki TrueType z polskimi znakami (Futura, Arial lub Segoe UI).')


def _register_fonts():
    regular, bold = _font_pair()
    if 'ISLabelRegular' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ISLabelRegular', regular))
    if 'ISLabelBold' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ISLabelBold', bold))


def _wrap_words(text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split('\n'):
        current = ''
        for word in paragraph.split():
            attempt = (current + ' ' + word).strip()
            if pdfmetrics.stringWidth(attempt, font, size) <= max_width:
                current = attempt
            else:
                if current:
                    lines.append(current)
                current = ''
                while word and pdfmetrics.stringWidth(word, font, size) > max_width:
                    # Split very long unbroken names instead of overflowing the cell.
                    cut = 1
                    while cut < len(word) and pdfmetrics.stringWidth(word[:cut+1], font, size) <= max_width:
                        cut += 1
                    lines.append(word[:cut])
                    word = word[cut:]
                current = word
        if current:
            lines.append(current)
    return lines or ['']


def _fitted_lines(name: str, font: str, max_w: float, max_h: float) -> tuple[float, list[str]]:
    for size_int in range(36, 11, -1):  # 18 → 6 pt at 0.5pt increments
        size = size_int / 2
        lines = _wrap_words(name, font, size, max_w)
        if len(lines) * size * 1.26 <= max_h:
            return size, lines
    raise ValueError(f'Nazwa etykiety nie mieści się nawet przy 6 pt: {name!r}. Zwiększ wymiar etykiety lub skróć nazwę.')


def _dims(template: str) -> tuple[float, float, bool, tuple[float, float]]:
    if template == TEMPLATE_BAKERY:
        return 110, 50, True, (297, 210)  # A4 landscape, 2x4
    if template == TEMPLATE_ICE:
        return 90, 50, False, (210, 297)  # A4 portrait, 2x5
    if template == TEMPLATE_STANDARD:
        return 90, 50, True, (210, 297)
    raise ValueError(f'Nieznany szablon: {template}')


def _draw_label(pdf: canvas.Canvas, item: LabelItem, x: float, y: float,
                width_mm: float, height_mm: float, show_price: bool, cut_lines: bool):
    w, h = width_mm * MM, height_mm * MM
    if cut_lines:
        pdf.setStrokeColorRGB(.67, .67, .67)
        pdf.setLineWidth(.25)
        pdf.rect(x, y, w, h, stroke=1, fill=0)
    pad = 6 * MM
    has_price = show_price and bool(item.price)
    if has_price:
        pdf.setStrokeColorRGB(.68, .68, .68)
        pdf.setLineWidth(.35)
        pdf.line(x + pad, y + 14*MM, x + w - pad, y + 14*MM)
        pdf.setFillColorRGB(.07, .07, .07)
        pdf.setFont('ISLabelBold', 19)
        pdf.drawCentredString(x+w/2, y+4.7*MM, item.price)
    pdf.setFillColorRGB(.35, .35, .35)
    pdf.setFont('ISLabelRegular', 7.2)
    pdf.drawCentredString(x+w/2, y+h-8.5*MM, item.category.upper())
    low = y + (17*MM if has_price else 5*MM)
    high = y+h-11*MM
    free_h = high - low
    name_font = 'ISLabelBold'
    size, lines = _fitted_lines(item.name, name_font, w-2*pad, free_h)
    block_h = len(lines)*size*1.26
    top = low+(free_h+block_h)/2 - size
    pdf.setFont(name_font, size)
    pdf.setFillColorRGB(0, 0, 0)
    for i, line in enumerate(lines):
        pdf.drawCentredString(x+w/2, top-i*size*1.26, line)


def make_labels_pdf(items: list[LabelItem], output: str | Path,
                    category_templates: dict[str, str] | None = None,
                    cut_lines: bool = True) -> dict[str, int]:
    """Group by category; each category may have a different sheet orientation.

    Returns pages per category, and rejects clipping / missing content instead
    of silently truncating long descriptions.
    """
    if not items:
        raise ValueError('Brak etykiet do wydrukowania.')
    if sum(x.copies for x in items) > 5000:
        raise ValueError('Limit: 5000 etykiet na jeden eksport.')
    for item in items:
        if not item.name.strip() or item.copies < 1:
            raise ValueError('Każda etykieta musi mieć nazwę i nakład >= 1.')
    _register_fonts()
    groups: dict[str, list[LabelItem]] = OrderedDict()
    for item in items:
        groups.setdefault(item.category, []).append(item)
    output = str(output)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    pages: dict[str, int] = {}
    pdf = canvas.Canvas(output, pageCompression=1)
    try:
        for category, records in groups.items():
            template = (category_templates or {}).get(category, infer_template(category, records))
            cell_w, cell_h, show_price, (paper_w, paper_h) = _dims(template)
            cols = int((paper_w-8)//cell_w)
            rows = int((paper_h-8)//cell_h)
            if cols < 1 or rows < 1:
                raise ValueError('Etykiety nie mieszczą się na formacie papieru.')
            margin_x = (paper_w - cols*cell_w)/2 * MM
            margin_y = (paper_h - rows*cell_h)/2 * MM
            pdf.setPageSize((paper_w*MM, paper_h*MM))
            copies = (item for item in records for _ in range(item.copies))
            pos = 0
            pages[category] = 0
            for item in copies:
                if pos == cols*rows:
                    pdf.showPage()
                    pages[category] += 1
                    pos = 0
                    pdf.setPageSize((paper_w*MM, paper_h*MM))
                c, r = pos % cols, pos // cols
                x = margin_x + c*cell_w*MM
                y = paper_h*MM - margin_y-(r+1)*cell_h*MM
                _draw_label(pdf, item, x, y, cell_w, cell_h, show_price, cut_lines)
                pos += 1
            pdf.showPage()
            pages[category] += 1
        pdf.save()
    except Exception:
        # ReportLab canvas can leave an incomplete output: remove it to avoid misprints.
        try:
            Path(output).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return pages


def _decode_header(value: str | None) -> str:
    try:
        return str(make_header(decode_header(value or '')))
    except (UnicodeError, LookupError):
        return value or ''


def mail_list(host: str, port: int, username: str, password: str,
              limit: int = 35, folder: str = 'INBOX') -> list[MailHeader]:
    """Read only headers, without deleting or marking mail as read."""
    if not host or not username or not password:
        raise ValueError('Uzupełnij serwer IMAP, login i hasło.')
    with imaplib.IMAP4_SSL(host, int(port), timeout=18) as conn:
        conn.login(username, password)
        status, _ = conn.select(folder, readonly=True)
        if status != 'OK':
            raise RuntimeError('Nie można otworzyć folderu poczty.')
        status, data = conn.uid('SEARCH', None, 'ALL')
        if status != 'OK':
            raise RuntimeError('Błąd wyszukiwania wiadomości IMAP.')
        uids = data[0].split()[-limit:][::-1] if data and data[0] else []
        result = []
        for uid in uids:
            status, raw = conn.uid('FETCH', uid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            if status != 'OK':
                continue
            block = next((x[1] for x in raw if isinstance(x, tuple) and isinstance(x[1], bytes)), None)
            if not block:
                continue
            msg = BytesParser(policy=policy.default).parsebytes(block, headersonly=True)
            result.append(MailHeader(uid.decode('ascii'), _decode_header(msg.get('From')),
                                     _decode_header(msg.get('Subject')), str(msg.get('Date') or '')))
        return result


def mail_read(host: str, port: int, username: str, password: str,
              uid: str, folder: str = 'INBOX') -> str:
    if not re.fullmatch(r'\d+', uid):
        raise ValueError('Nieprawidłowy identyfikator wiadomości.')
    with imaplib.IMAP4_SSL(host, int(port), timeout=18) as conn:
        conn.login(username, password)
        status, _ = conn.select(folder, readonly=True)
        if status != 'OK':
            raise RuntimeError('Nie można otworzyć folderu IMAP.')
        status, data = conn.uid('FETCH', uid, '(BODY.PEEK[])')
        if status != 'OK':
            raise RuntimeError('Nie można pobrać wiadomości.')
        payload = next((x[1] for x in data if isinstance(x, tuple) and isinstance(x[1], bytes)), None)
        if not payload:
            raise ValueError('Brak treści wiadomości.')
        return decode_email(payload)
