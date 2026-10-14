# ROADMAP — funkcjonalna zgodność z Impozycjonerem 4

Odniesienie: https://www.impozycjoner.pl/dokumentacja/v4

## 0.1.0: MVP
- [x] PDF import, nakłady, tabela plików
- [x] Automatyczna siatka / obrót użytków
- [x] Proste spady i znaczniki cięcia
- [x] Podgląd, wektorowy eksport, plik `.psimp`
- [x] Podstawowy duplex, broszura 2-up
- [x] Testy geometrii i kolejności stron

## 0.2 — Produkcyjna kontrola PDF (w toku — część ukończona)
- [x] Wektorowe osadzanie ze spadami, MediaBox/CropBox/TrimBox oraz obroty 0/90/180/270 (dla regularnych stron PDF)
- [x] Walidacja TrimBox każdej strony, detekcja brakujących spadów i blokowanie niejawnego skalowania
- [x] Jawne skalowanie źródłowego PDF do netto: Dopasuj/Wypełnij, eksport pojedynczych stron A6/A5/A4
- [x] Podgląd porównania recto/verso oraz profile przesunięcia tyłu (0.3.6); obszar chwytu nadal do opracowania
- [x] Podstawowy raport preflight: format, fizyczny spad, progi DPI obrazów, próba weryfikacji fontów
- [ ] Pełny preflight: RGB/CMYK/spot, ICC, transparencje, PDF/X; znaczniki netto/brutto, pasery, paski kontrolne i opisy
- [ ] Testy z rzeczywistymi plikami produkcyjnymi

## 0.3 — Zaawansowane akcydensy
- [x] 0.4.0: gang-run różnych projektów i nakładów **w tym samym formacie użytku**, jednostronnie; raport liczby arkuszy i CSV
- [ ] Gang-run **różnych fizycznych formatów** użytków / nesting i wielowariantowe koszty cięcia
- [ ] Optymalizacja wielowariantowa: odpady/nakłady/koszt rozcięcia
- [x] Ręczne przesuwanie/obracanie/użytkowanie na podglądzie (0.3.5: drag/drop, pola puste, obrót ±90°, przesuw 0,1 mm)
- [ ] Kreator podziału arkusza, szablony prac
- [x] Przypisywanie ról całemu PDF lub dowolnym stronom: przód, tył sparowany, tył wspólny, pomiń
- [x] Montaż wieloarkuszowy i edytor pojedynczych użytków recto/verso (0.3.5: osobne obroty/pozycje, zapis i eksport)

## 0.4 — Montaż książek i falcowanie
- [ ] Oprawa klejona, zeszytowa, szyta; składki 4/8/12/16/32
- [ ] Schematy falcowania, kolejność arkuszy i składki niepełne
- [ ] Creep, sygnatura grzbietowa i korekty
- [ ] Wizualne przeciąganie numerów stron

## 0.5 — Wykrojniki i narzędzia
- [ ] Montaż wykrojników i nakładanie wykrojników
- [ ] Narzędzia: rozcięcie, łączenie, obrót, skalowanie, dodawanie spadów, przeplatanie
- [ ] Kody QR/EAN128, znaczniki plotera, oczkowanie bannerów

## 0.6 — Ergonomia i automatyzacja
- [ ] W pełni natywne GUI z szerokim ekranem i edycją użytków na żywo
- [ ] Hot folders, CLI, automatyzacja JSON
- [x] Lokalne profile kalibracji X/Y i odwracania na maszynę (0.3.6)
- [ ] Rozszerzone presety maszyn i integracja z workflow drukarni
- [ ] Eksport/druk wsadowy, testy wydajności 1000+ stron
- [ ] Opcjonalny natywny port Rust po ustaleniu stabilnego silnika

- [x] 0.3.4: three-size crop workflow from source PDF through use with bleed to net trim, with 1:1 physical crop.

**Priorytet:** zgodność rzeczywistych wynikowych PDF-ów i bezpieczeństwo druku przed kopiowaniem wyglądu UI piksel w piksel.

- [x] 0.2.8: TAXI side TIFF and rear vector-cut AI/EPS/SVG batch generator (replaces withdrawn email-label module).
- [ ] Confirm import and cutting fidelity in actual CorelDRAW X4 and the shop plotter.

- [x] 0.3.1 first phase: manual cell selection, recto/verso editing, registration overlay.
- [x] 0.3.5: native drag/drop, single-slot rotation, independent manual nudge on recto/verso.
- [x] 0.3.6: machine-specific whole-side verso registration offsets X/Y (0.1 mm), local printer profiles and preflight/export validation.
- [ ] Next: sheet-registration measurement chart and tighter preview of overprint/crosshair differences.

- [x] 0.3.7: Print-and-measure duplex registration sheet and guided front-view correction calculator.

- [x] 0.4.0: ekonomiczne mieszanie różnych nakładów o wspólnej geometrii, preflight ilości, raport CSV i przykład SRA3.

- [x] 0.4.1: intelligent original → net → bleed → gross panel, per-PDF original auto-detection, practical format presets and draggable crop preview with safe 0.1-mm per-file X/Y offsets.
- [ ] 0.4.2: *different physical target* sizes for each PDF on the same sheet (variable rectangles, mixed-format layout, new cutting constraints); not part of 0.4.1.
- [ ] Advanced asymmetric bleed (left/right/top/bottom) and fully separate per-PDF net sizes require updating the placement model and crop-mark geometry.
