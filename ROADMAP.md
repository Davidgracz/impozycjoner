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
- [ ] Podgląd Recto/Verso oraz nadrukowalnych pól i obszaru chwytu
- [x] Podstawowy raport preflight: format, fizyczny spad, progi DPI obrazów, próba weryfikacji fontów
- [ ] Pełny preflight: RGB/CMYK/spot, ICC, transparencje, PDF/X; znaczniki netto/brutto, pasery, paski kontrolne i opisy
- [ ] Testy z rzeczywistymi plikami produkcyjnymi

## 0.3 — Zaawansowane akcydensy
- [ ] Gang-run (różne formaty i nakłady na jednym arkuszu)
- [ ] Optymalizacja wielowariantowa: odpady/nakłady/koszt rozcięcia
- [ ] Ręczne przesuwanie/obracanie/użytkowanie na podglądzie
- [ ] Kreator podziału arkusza, szablony prac
- [x] Przypisywanie ról całemu PDF lub dowolnym stronom: przód, tył sparowany, tył wspólny, pomiń
- [ ] Montaż wieloarkuszowy i pełny edytor pojedynczych użytków recto/verso (również osobne obroty, niezależne wyrównanie)

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
- [ ] Presety maszyn, integracja z workflow drukarni
- [ ] Eksport/druk wsadowy, testy wydajności 1000+ stron
- [ ] Opcjonalny natywny port Rust po ustaleniu stabilnego silnika

**Priorytet:** zgodność rzeczywistych wynikowych PDF-ów i bezpieczeństwo druku przed kopiowaniem wyglądu UI piksel w piksel.

- [x] 0.2.8: TAXI side TIFF and rear vector-cut AI/EPS/SVG batch generator (replaces withdrawn email-label module).
- [ ] Confirm import and cutting fidelity in actual CorelDRAW X4 and the shop plotter.

- [x] 0.3.1 first phase: manual cell selection, recto/verso editing, registration overlay.
- [ ] Next: native drag/drop, single-slot rotation, manual nudge and per-side registration offsets.
