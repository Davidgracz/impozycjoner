# Plan wdrożenia zgodności z Impozycjonerem 4

Plan etapów, priorytety i testy porównawcze. Funkcje i ich statusy: `docs/feature-parity.md`;
zasady pracy i kryteria ukończenia: `AGENTS.md`; ogólna mapa produktu: `ROADMAP.md` (wersje 0.x).

## 1. Zasady priorytetyzacji

1. **Wartość dla drukarni.** Akcydensy (wizytówki, ulotki, dyplomy) przed książkami i narzędziami dodatkowymi.
2. **Bezpieczeństwo wydruku.** Walidacje i ostrzeżenia, które chronią przed błędnym wydrukiem, mają pierwszeństwo przed wygodą.
3. **Dowód przed implementacją.** Funkcję z wartościami liczbowymi (kalkulator, creep, falcowanie) zaczynamy dopiero,
   gdy mamy dowód E3 (próbka z oryginału) albo jednoznaczny opis E1. Bez tego powstaje „atrapa zgodności”.
4. **Pion przed szerokością.** Każda funkcja idzie całą drogą: wejście → komenda → silnik → UI → wynik → test.
5. **Zachowanie istniejącego.** Każdy etap kończy się regresją (pełne testy + `scripts/diff_planning.py`).

## 2. Etapy

| Etap | Cel | Główne funkcje (ID) | Warunek zakończenia |
|---|---|---|---|
| **0 — Fundamenty i pierwszy pion** *(zrobiony po stronie kodu; czeka na przebieg na Windows)* | Dokumentacja zgodności, lint rejestru, pierwsza funkcja od nazwy pliku do PDF | F-AKC-REP, F-SYS-DEPS, F-SYS-PROJECT (powtórzenia) | Testy czyste przechodzą (zrobione); `pytest -q` na Windows zielony; ręczna lista kontrolna UI wypełniona; wtedy F-AKC-REP → `working` |
| **1 — Bezpieczne wejście i narzędzia modelu** | Zielona regresja wszystkich testów, stabilne ID zadań w komendach, reszta panelu plików na komendach, tolerancyjny wczytywacz projektu, zbieranie próbek E3 | F-SYS-UNDO, F-WEJ-PROT, F-WEJ-OUTNAME, F-WEJ-PAGECNT, F-AKC-ITEM, F-SYS-PROJECT (odporność) | Wszystkie wiersze `working†` zweryfikowane i zamienione na `working`; ≥ 6 próbek E3 w `tests/oracle/` |
| **2 — Rdzeń akcydensu** | Jawny model układu (`Layout`), edycja użytków, spady/odstępy per strona, chwyt i łapki, autowypełnianie | F-AKC-ITEMTABLE, F-AKC-BLANKS, F-AKC-ROT, F-AKC-BLEED, F-AKC-GAP, F-AKC-SHEET, F-AKC-AUTOFILL, F-AKC-PAPERS, F-SYS-SETTINGS | Układ domyślny identyczny jak dziś (test różnicowy); próbki E3 dla siatek z chwytem zgodne co do 0,01 mm |
| **3 — Znaczniki** | Komplet znaczników wektorowych sterowanych ustawieniami; dupleks MB/MC potwierdzony | F-MRK-NETTO, -BRUTTO, -PASERY, -BRUTPAS, -PASKI, -WYCINKA, -MARGINS, -CROPBOX, -OPIS, -WLASNY, F-DUP-MB, F-DUP-MC | Pozycje znaczników zgodne z próbkami E3; wycinka z regułą parzystych kolumn |
| **4 — Wiele arkuszy i kalkulator** | Gang-run i kalkulator nakładów | F-AKC-MULTISHEET, F-AKC-CALC, F-AKC-NWD, F-AKC-RUNNAME, F-AKC-ECON, F-AKC-SPLIT, F-AKC-PATTERN, F-AKC-RUNMODES | Rozkłady zgodne z tabelą E3 (≥ 10 zestawów); własność NWD spełniona |
| **5 — Książki i falcowanie** | Oprawy, składki, falcowanie, creep | F-KSI-BIND, -SIG, -FOLD, F-MRK-FALC, -SYGN, -CREEP | Kolejność stron i znaczniki zgodne z próbkami E3 |
| **6 — Narzędzia dodatkowe** | Kolejno: operacje na stronach → kody kreskowe → reszta | F-NAR-* | Każde narzędzie z testem na danych publicznych (wektory standardów) lub próbce E3 |
| **7 — Ergonomia** | Skróty, pomoc, cofanie w całym oknie, CLI i hot folder, wydajność 1000+ stron | F-SYS-SHORTCUTS, F-SYS-HELP, F-SYS-UNDO | Pomiary wydajności w CI; lista skrótów z E1 działa |

Funkcje oznaczone w rejestrze jako „poza zakresem” (licencjonowanie) nie wchodzą do żadnego etapu.

## 3. Priorytety wewnątrz Etapu 1 (następny)

1. Uruchomić pełne testy na Windows i podnieść `working†` → `working` albo zgłosić regresję.
2. Zamienić indeks zadania w komendach na stabilne `job_id` (usuwa czyszczenie historii).
3. Przenieść na komendy: dodaj/usuń/przesuń plik, zmień nakład, role stron. Cofanie w UI dla całego panelu plików.
4. Wczytywacz projektu ignorujący nieznane klucze ustawień + zapis atomowy.
5. Test dla F-WEJ-PROT (PDF zaszyfrowany, plik nie-PDF) oraz F-WEJ-PAGECNT.
6. Zebranie próbek E3 (sekcja 5) — odblokowuje Etapy 2–5.

## 4. Testy porównawcze

| Rodzaj | Co porównuje | Narzędzie | Kiedy |
|---|---|---|---|
| **Z tekstu oryginału (E1)** | wynik funkcji vs przykłady z pomocy (np. `Arkusz_300s.pdf` → 300) | `unittest`/`pytest`, czyste funkcje | od razu, przy każdej funkcji z opisanymi przykładami |
| **Różnicowe względem poprzedniej rewizji** | plany arkuszy przed i po zmianie dla losowych konfiguracji | `scripts/diff_planning.py --rev <rewizja>` | po każdym etapie i każdej zmianie silnika |
| **Charakteryzujące** | utrwalone dotychczasowe zachowanie | `tests/test_plan_baseline.py` | stale w CI |
| **Z PDF (struktura)** | kolejność stron na arkuszach, tekst, boxy, wymiary — nie piksele | `pytest` z PyMuPDF | stale w CI |
| **Wyrocznia E3** | pozycje, kolejność i liczby z wyjścia oryginału vs Studio, tolerancja 0,01 mm | `tests/oracle/<id>/` (wejście, `expected.json`, `README.md` ze źródłem próbki) | od Etapu 1, gdy dostępne próbki |
| **Rejestr** | spójność dokumentacji z testami | `python scripts/parity.py` | stale w CI |

Porównujemy **dane o układzie** (współrzędne slotów, numery stron, liczba arkuszy, położenia kresek), a nie
obrazy: wynik jest wtedy powtarzalny, niezależny od silnika renderującego i łatwy do zrozumienia przy różnicy.

## 5. Zbieranie dowodów E3 (do wykonania przez właściciela legalnej kopii oryginału)

Dla każdej próbki zapisz: pliki wejściowe, ustawienia (zrzut ekranu okien), plik wynikowy PDF oraz krótką notatkę
(wersja programu, data). Pliki trafiają do `tests/oracle/<id>/` wraz z `README.md`; nie dołączamy zasobów
zastrzeżonych (paski, pliki z `Base.dat`).

| # | Próbka | Rozstrzyga |
|---|---|---|
| 1 | Wizytówka 90×50, spad 2 mm, SRA3 450×320, chwyt 11 mm, jednostronnie — wynik i ustawienia | F-AKC-SHEET, F-AKC-GRID, OQ-07, OQ-08 |
| 2 | To samo, dwustronnie z MB oraz z MC (osobno) | F-DUP-MB, F-DUP-MC, OQ-06, H-07 |
| 3 | Pliki `Plik5_.pdf`, `Arkusz_.pdf`, `x_000.pdf`, `Plik7.pdf`, `a_5x10.pdf`, `2000_test.pdf` w kalkulatorze i w polu powtórzeń | H-01, H-03, H-05, OQ-02 |
| 4 | Kalkulator: nakłady 100/1000/3000 oraz co najmniej 9 innych zestawów, z NWD i bez | F-AKC-CALC, F-AKC-NWD, OQ-04 |
| 5 | Wycinka pionowa przy 3 i 4 kolumnach; spady przy odstępie 3 i 5 mm (odległość znaczników 2 mm) | F-MRK-WYCINKA, F-MRK-MARGINS |
| 6 | Autowypełnianie z każdego narożnika, kierunki, parzyste/nieparzyste, z powtórzeniami | F-AKC-AUTOFILL, OQ-11 |
| 7 | Broszura 12 i 14 stron: zeszytowa i klejona | F-KSI-BIND, F-KSI-SIG, OQ-09 |
| 8 | Znaczniki: netto, brutto, pasery, crop — po jednym arkuszu | F-MRK-* |

## 6. Ręczna lista kontrolna UI — Etap 0 (F-AKC-REP)

Wykonaj w aplikacji (`START_WINDOWS.bat`), po `pytest -q` na zielono. Wynik wpisz do `docs/feature-parity.md`
(rejestr uruchomień), a przy pełnym powodzeniu zmień status F-AKC-REP na `working`.

1. Utwórz PDF 3-stronicowy o rozmiarze 90×50 mm i nazwie `Arkusz_2.pdf`. Dodaj go (`+ Dodaj PDF`).
   Oczekiwane: kolumna **Powt.** pokazuje 1, podgląd pokazuje strony 1, 2, 3.
2. Zaznacz plik i kliknij **Z nazwy pliku**. Oczekiwane: kolumna Powt. = 2; podpowiedź pod przyciskami:
   „Z nazwy „Arkusz_2” (po ostatnim „_”: „2”) odczytano 2.”; podgląd pokazuje 1, 1, 2, 2, 3, 3.
3. Wpisz 3 w polu **Powtórzenia każdej strony** i naciśnij Enter (lub **Zmień**). Oczekiwane: Powt. = 3.
4. Wpisz `abc`, potem `0`, potem `1000001`. Oczekiwane: komunikat błędu za każdym razem; wartość w tabeli bez zmian.
5. Kliknij **Cofnij**: Powt. = 2 (cofnięto krok 3); kliknij ponownie: Powt. = 1 (cofnięto krok 2); kliknij trzeci raz:
   „Nie ma czego cofać.” (nieudane próby z kroku 4 nie trafiły do historii).
6. Dodaj plik `Instrukcja.pdf`, zaznacz go i kliknij **Z nazwy pliku**. Oczekiwane: Powt. = 1 i komunikat o braku cyfr w nazwie.
7. Ustaw powtórzenia 2, zapisz projekt, zamknij program, otwórz projekt. Oczekiwane: Powt. = 2.
8. Przełącz tryb na **Broszura**. Oczekiwane: komunikat „Powtórzenia stron nie są dostępne w trybie Broszura”;
   po powrocie do trybu jednostronnego podgląd działa.
9. Eksportuj PDF: liczba arkuszy = ⌈(strony × powtórzenia) / pojemność⌉; w pliku strony w kolejności 1,1,2,2,3,3.
10. Wczytaj `examples\demo_montaz.psimp` — projekt otwiera się i wygląda jak przed zmianą (Powt. = 1).
