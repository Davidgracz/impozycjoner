# Specyfikacja zachowania — Impozycjoner Studio względem Impozycjonera 4

Ten dokument opisuje, **co wiemy** o zachowaniu oryginału (Impozycjoner 4.0.4.0), **skąd to wiemy**
i **czego nie wiemy**. Jest podstawą wartości oczekiwanych w testach akceptacyjnych
(`docs/feature-parity.md`). Niczego tu nie przepisujemy 1:1 z oryginału: reguły są opisane własnymi
słowami, bez kodu, bez grafik i bez plików z instalacji (patrz `AGENTS.md`, „Czysta implementacja”).

## 1. Jak czytać ten dokument

| Oznaczenie | Znaczenie |
|---|---|
| **P-nn** | Fakt potwierdzony tekstem lub plikiem z instalacji oryginału (poziom dowodu E1 lub E2). |
| **H-nn** | Hipoteza: nasza decyzja lub wniosek, którego **nie** potwierdziła obserwacja działającego oryginału. |
| **OQ-nn** | Pytanie otwarte: wiemy, że czegoś nie wiemy, i opisujemy, jak to rozstrzygnąć. |

Poziomy dowodów (te same w całym repozytorium):

| Poziom | Źródło | Przykład |
|---|---|---|
| E1 | Własne streszczenie tekstów interfejsu i pomocy oryginału (zasoby programu, tooltipy, etykiety) | reguła „powtórzenia z nazwy pliku” |
| E2 | Statyczna struktura instalacji: pliki XML, konfiguracja, lista plików, metadane | `FoldMark.xml`, `Ploter.xml` |
| E3 | Obserwacja **uruchomionego** oryginału (zrzuty, wyjściowe PDF-y z próbek) | **brak — oryginał nie był uruchamiany** |
| E4 | Własny kod, testy i dokumenty Studio | `engine.py`, `tests/…` |

Konsekwencje braku E3: żadna funkcja nie ma dziś statusu `verified`, a zachowanie liczbowe
(algorytmy, zaokrąglenia, kolejności przy remisach) jest w większości hipotezą. Najtańszy sposób
na E3 to próbki wejście → wyjście wykonane w legalnie posiadanej kopii programu (patrz sekcja 6).

## 2. Fakty potwierdzone (E1/E2)

### 2.1 Reguły nazw plików

| ID | Fakt | Dowód |
|---|---|---|
| P-01 | **Powtórzenia każdej strony z nazwy pliku.** Bierze się część nazwy po *ostatnim* znaku „_”; gdy go nie ma — całą nazwę. Z wybranej części usuwa się wszystko, co nie jest cyfrą. Brak cyfr daje 1. | E1, podpowiedź przycisku przy polu „Ilość powtórzeń każdej strony” |
| P-02 | Przykłady z tej samej podpowiedzi: `Arkusz_300s.pdf` → 300; `Ulotka_dla_sklepu_500stron.pdf` → 500; `Dyplom200.pdf` → 200; `Instrukcja.pdf` → 1. | E1 |
| P-03 | **Nakład w kalkulatorze z nazwy pliku.** Jeśli „ostatnia fraza przed znakiem dolnego podkreślenia” w nazwie PDF jest nakładem, tabela kalkulatora dostaje ten nakład dla wszystkich stron tego pliku widocznych w tabeli stron do impozycji. Przykład: `test_2000.pdf` → 2000. | E1, opis w oknie kalkulatora |
| P-04 | Nazwa pliku wynikowego nie może zawierać znaków: `#` `%` `&` `*` `:` `<` `>` `?` `/` `\` `{` `}` oraz znaku pionowej kreski; nie może też być nazwą pliku przetwarzanego. | E1, podpowiedź i komunikat walidacji |
| P-05 | Dostępne są dwie opcje dopisków do nazwy wyniku: stała fraza `--IMPOZYCJONER` oraz fraza z informacjami uzupełniającymi. | E1 |
| P-06 | Narzędzie podziału zapisuje każdą stronę wybranego PDF osobno; nazwa to oryginalna nazwa z dopiskiem `--XX` (numer strony) i wybranym rozszerzeniem. | E1 |
| P-07 | Metadane wyniku: pola Autor, Tytuł, Temat i Słowa kluczowe; pole puste oznacza „użyj nazwy pliku”. Domyślna wersja PDF w konfiguracji: 1.5. | E1 + E2 (`Pdf_version = v1_5`) |
| P-08 | Gdy nakładane pliki mają różną liczbę stron, program ostrzega, że może to być przyczyną błędu, i pyta o kontynuację. | E1 |

### 2.2 Kalkulator nakładów

| ID | Fakt | Dowód |
|---|---|---|
| P-10 | Dane wejściowe: nakłady kilku prac, cena arkusza (domyślnie 0,30), cena narzędzia (domyślnie 120). Wynik: rozkład użytków prac na kolejnych arkuszach impozycyjnych o minimalnej liczbie impozycji i minimalnych odpadach. | E1 + E2 (`CenaArkusza`, `CenaNarzadu`) |
| P-11 | Opcja NWD (największy wspólny dzielnik): prace o nakładach 100, 1000 i 3000 liczone są jak o nakładach 1, 10 i 30 (NWD = 100), a wynikowe nakłady mnoży się przez NWD. Skraca obliczenia, ale wyniki z NWD i bez mogą się „nieznacznie różnić”. | E1 |
| P-12 | Liczenie może być automatyczne (po każdej zmianie nakładu lub parametrów) albo ręczne (klawisz F6). Obliczenia można przerwać, gdy wyniki zaczynają się pogarszać. | E1 |
| P-13 | Obsługa: usuwanie pliku z kalkulatora — prawy klawisz myszy; zmiana nakładu — F2 lub dwukrotne kliknięcie; tabela pokazuje „ilości użytków zajmowanych przez prace na kolejnych arkuszach”. | E1 |

### 2.3 Parametry akcydensu i znaczniki

| ID | Fakt | Dowód |
|---|---|---|
| P-20 | Akcydens: rozmiar użytku (szerokość × wysokość), obrót 0°/90°/180° (per użytek, wiersz, kolumna lub cały arkusz), spady per strona, chwyt [mm], margines techniczny „na łapki” [mm], redukcja płyty [pt], rozmiar papieru i płyty. | E1 |
| P-21 | Domyślny chwyt w konfiguracji: 11; marginesy: 0; zestaw: 1; etykiety zestawów: „C” i „O”. | E2 (`Impozycjoner.exe.config`) |
| P-22 | Ostrzeżenie: różne spady na jednym arkuszu mogą uniemożliwić poprawne wykrojenie. | E1 |
| P-23 | Wycinka pionowa (pionowy odstęp środkowy) jest rysowana tylko wtedy, gdy liczba kolumn jest parzysta. | E1 |
| P-24 | Spady na krawędziach odstępu są rysowane tylko wtedy, gdy szerokość odstępu ≥ 2 × odległość znaczników; opcja działa wyłącznie dla użytków z zerowym spadem i dodatnią odległością znaczników. | E1 |
| P-25 | Znaczniki falcowania („cross-fold”) są dostępne tylko dla arkuszy po 8, 12 i 16 stron. | E1 |
| P-26 | Własne znaczniki to cztery pliki PDF w katalogu użytkownika `MyImpozycjoner/PDFs`: `U1L`, `U1R` (pierwsza strona, lewy/prawy) oraz `U2L`, `U2R` (druga strona). Brak pliku wyłącza odpowiedni przełącznik. | E1 + E2 (`Base.dat` zawiera wzorce o tych nazwach) |
| P-27 | Przycięcie TrimBox „crop” to włosowe przesunięcie (pt): z lewej na stronach parzystych, z prawej na nieparzystych, aby ukryć skrawek sąsiedniej strony. Program ostrzega przy rozkładówkach środkowych. | E1 |
| P-28 | Impozycja cząstkowa ma trzy warianty: bez znaczników, ze znacznikami 1 mm, ze znacznikami 2 mm. | E1 |
| P-29 | Tryb wydruku dwustronnego: pełny lub częściowy, przez znacznik boczny (MB, „work-and-turn”) albo czołowy (MC, „work-and-tumble”). | E1 |

Parametry każdego z 14 okien znaczników (kolory, długości, grubości w pt, położenia, strony
wszystkie/parzyste/nieparzyste) są zebrane w osobnym dokumencie projektu „impo”:
`claude/impozycjoner4-mark-and-paper-schemas.md` (E1).

### 2.4 Formaty danych oryginału (E2)

**`FoldMark.xml`** — korzeń `Falcownica`, dzieci `F1` lub `F2` z atrybutem `name`. Pola każdego wpisu:
`PZ1…PZ6`, `PI1…PI6`, `ZnacznikiFalcOdleglosc`, `ZnacznikiFalcGrubosc`, `FalcownicaNaStronach`
oraz kolor znacznika (typ `CmykColor`, tusz `All (Registration)`, C/M/Y/K i tint).

| P-30 | Wpis | Element | PZ (pt) | PZ (mm, przeliczone) |
|---|---|---|---|---|
| a | A4>DL (C) Recto | F2 | 275; 558,4 | 97; 197 |
| b | A4>DL (C) Verso | F2 | 283,5; 566,9 | 100; 200 |
| c | A4>DL (Z) Recto Verso | F1 | 280,6; 561,3 | 99; 198 |
| d | 3xA4>A4 (C) Recto | F2 | 598,1; 1196,2 | 211; 422 |
| e | 3xA4>A4 (C) Verso | F2 | 589,6; 1187,7 | 208; 419 |
| f | 3xA4>A4 (Z) Recto Verso | F1 | 841,9; 841,9 | 297; 297 |

Wspólne wartości: odległość znaczników 2, grubość 0.5, strony `All`, kolor C0 M0 Y0 K30 (tint 100),
wszystkie `PI*` równe 0. **Separator dziesiętny jest niespójny nawet w jednym pliku**: pozycje `PZ*`
mają przecinek („558,4”), grubość ma kropkę („0.5”). Parser musi przyjmować oba (P-31).

**`Ploter.xml`** — korzeń `Ploterownica`: `Version` 1.0.0.0; `Obroty` (obrót pliku wejściowego i
wyjściowego, 0); `Skalowanie` (procentowo 100 % × 100 %, flagi proporcji, wartość stała
2976,37 × 2097,63); `Marker` (typ „C”, liczba osi X: góra 3 / dół 3, rozmiar 17,00787, grubość
8,503937, strona 0, krawędź włączona o szerokości 8,503937, pole ochronne wyłączone);
`MarkerKolor` (CMYK 0/0/0/100, tint 100); `Marginesy` (czołowy 56,69292; tylny 226,7717;
lewy/prawy 58,11024; X i Y pliku PDF 8,503937); `chb_Optymalizacja` False. Separator dziesiętny: przecinek.

| ID | Fakt | Dowód |
|---|---|---|
| P-32 | `Base.dat` jest archiwum ZIP z zasobami: PDF-y znaczników (`U1L`, `U1R`, `U2L`, `U2R`, `VMB`, `HMB`, `cm`, `mm`, `SM`), pasek kontrolny kolorów (PDF), `FoldMark.xml`, `Ploter.xml`, przykładowy PDF plotera oraz bibliotekę kompresji. **Nie kopiujemy** tych plików; własne znaczniki rysujemy kodem. | E2 |
| P-33 | Konfiguracja użytkownika zawiera m.in. cenę arkusza 0,3, cenę narzędzia 120, chwyt 11, wersję PDF `v1_5`, marginesy 0, kod domyślny `8:4:2:16*16:8:4*X:12*12:X*12:X*4:2:8*8:4*8:4*2:4` (znaczenie: H-09) oraz ustawienia licencji i aktualizacji, które są **poza zakresem** (nie implementujemy licencjonowania). | E2 |

### 2.5 Format projektu Studio (`.psimp`, E4 — nie jest formatem oryginału)

Archiwum ZIP z jednym plikiem `project.json`:
`{"format":"psimp","version":1,"settings":{…pola Settings…},"jobs":[{"path","copies","role","page_roles"[, "page_repeat"]}]}`.
Ścieżki wewnątrz katalogu projektu są względne. Pole `page_repeat` jest zapisywane **tylko** gdy ≠ 1,
więc projekty bez powtórzeń są bajt w bajt takie same jak przed zmianą; starsze pliki bez tego pola
wczytują się z wartością 1. Wersja formatu pozostaje 1 (zmiana jest addytywna).

## 3. Zachowanie Studio potwierdzone testami (E4)

To jest zachowanie **naszego** silnika, które chronimy przed regresją. Nie twierdzimy, że równa się oryginałowi.

| ID | Zachowanie | Test |
|---|---|---|
| S-01 | Komórka użytku = netto + 2 × spad. Liczba kolumn/wierszy = ⌊(dostępne + odstęp) / (komórka + odstęp)⌋. Rozważane obroty 0° i 90°; wygrywa większa pojemność, przy remisie obrót 0°. Siatka jest centrowana, sloty rosną wierszami od lewego górnego rogu. | `tests/test_plan_baseline.py::GridGeometry` |
| S-02 | Tryb jednostronny wypełnia sloty kolejno; `Nakład pliku` powtarza **cały plik** (1,2,3,1,2,3). | `tests/test_plan_baseline.py::SingleSidedOrder` |
| S-03 | Dupleks: dla trybu „Normalnie” pary kolejnych stron (nieparzysta ostatnia strona dostaje pusty verso); role Przód / Tył sparowany / Tył wspólny / Pomiń tworzą pary po kolejności plików i stron; niespójne przypisania są odrzucane z komunikatem. | `tests/test_plan_baseline.py::DuplexRolesCharacterisation` |
| S-04 | Verso jest lustrzane względem wybranej krawędzi odwracania (zależnie od orientacji arkusza). | `tests/test_plan_baseline.py::DuplexFlipCharacterisation` |
| S-05 | Broszura 2-up: liczba stron dopełniana pustymi do wielokrotności 4; kolejność zeszytowa (np. 8 stron: [8,1] [2,7] [6,3] [4,5]); jeden plik naraz; strony „Pomiń” są usuwane przed impozycją. | `tests/test_plan_baseline.py::BookletCharacterisation` |
| S-06 | Znaczniki cięcia Studio: do ośmiu włosowych kresek 3 mm na użytek, zaczynających się 0,8 mm za spadem; kreski wychodzące poza arkusz nie są rysowane. | `tests/test_plan_baseline.py::MarksCharacterisation` |
| S-07 | **Powtórzenia każdej strony** (`Job.page_repeat`): w trybie jednostronnym i w eksporcie pojedynczych stron strona *k* występuje N razy pod rząd, potem strona *k+1*; łączy się z `Nakład pliku` (cały cykl powtarza się `copies` razy). Strony „Pomiń” nie są powtarzane. W dupleksie powtarzane są **pary** recto/verso (w rolach jawnych — przody i tyły razem; tył wspólny pozostaje jeden). W broszurze powtórzenia są odrzucane (OQ-05). | `tests/test_plan_repeats.py`, `tests/test_repeats_pdf.py` |
| S-08 | Przy `page_repeat = 1` plany arkuszy są identyczne z planami sprzed zmiany (porównanie różnicowe na losowych konfiguracjach). | `scripts/diff_planning.py` |

## 4. Hipotezy

### H-01 — rozszerzenie „.pdf” nie jest częścią nazwy
- **Treść:** przed odczytem cyfr usuwamy końcówkę `.pdf` (bez względu na wielkość liter).
- **Podstawa:** wszystkie przykłady z pomocy mają `.pdf` bez cyfr, więc nie odróżniają obu wariantów.
- **Ryzyko:** dla nazw bez „_” i z cyframi w rozszerzeniu (nie występują w plikach PDF) — pomijalne.
- **Rozstrzygnięcie:** E3 — jedna próbka `Plik7.pdf` vs `Plik.pdf` w oryginale.
- **Kod/testy:** `naming.py`, `tests/test_naming.py::HypothesesNotConfirmedByTheOriginal`.

### H-02 — za cyfry uznajemy wyłącznie ASCII 0–9
- **Podstawa:** brak. Oryginał jest aplikacją .NET; jej klasyfikacja znaków Unicode może być szersza.
- **Ryzyko:** nazwy z „²” lub cyframi arabsko-indyjskimi dałyby inny wynik. Praktycznie nieistotne.
- **Rozstrzygnięcie:** E3 albo pominąć (niski priorytet).

### H-03 — pusta część po ostatnim „_” daje 1
- **Treść:** `Arkusz_.pdf` → 1. Pomoc mówi „brak cyfr → 1”, ale nie rozstrzyga, czy w tym przypadku program sięga do wcześniejszych fragmentów nazwy.
- **Rozstrzygnięcie:** E3 (próbka `Arkusz_.pdf`, `Plik5_.pdf`).

### H-04 — katalogi w ścieżce są ignorowane
- **Treść:** czytamy tylko nazwę pliku; separatory `/` i `\` są obsługiwane na każdym systemie.
- **Podstawa:** logika rzeczy: pomoc mówi o „nazwie pliku”.

### H-05 — jedna reguła dla „powtórzeń strony” i „nakładu w kalkulatorze”
- **Treść:** pomoc opisuje obie funkcje innymi słowami (P-01: „część po ostatnim `_`”; P-03: „ostatnia fraza przed znakiem `_`”, przykład `test_2000.pdf`). Przyjmujemy, że to ta sama reguła, bo przykład P-03 jest z nią zgodny.
- **Ryzyko:** gdyby P-03 oznaczało „fraza *przed* ostatnim `_`”, zachowanie kalkulatora byłoby inne. Przykład `test_2000` przemawia przeciwko temu.
- **Rozstrzygnięcie:** E3 (`2000_test.pdf` w kalkulatorze).
- **Kod:** `naming.parse_repeats` jest współdzielone; kalkulator jeszcze nie istnieje.

### H-06 — powtórzenia w dupleksie dotyczą par recto/verso
- **Treść:** w trybie dwustronnym powtarzamy parę (przód + jego tył), a nie osobno stronę. Alternatywa (powtarzanie przodów i tyłów niezależnie) rozjechałaby pary.
- **Podstawa:** brak opisu w E1; wybór wynika z konieczności zachowania sensu wydruku.
- **Testy:** `tests/test_plan_repeats.py::DuplexRepeats`.

### H-07 — MB ↔ obrót wokół osi pionowej, MC ↔ wokół poziomej
- **Treść:** znacznik boczny (MB, „work-and-turn”) odpowiada odwróceniu arkusza wokół osi pionowej, czołowy (MC, „work-and-tumble”) — poziomej. Studio ma wybór „Długa / Krótka krawędź”, którego efekt zależy od orientacji arkusza (S-04).
- **Ryzyko:** odwrotne przyporządkowanie → lustrzane verso w wydruku. **Do czasu E3 funkcje MB/MC mają status `partial`.**
- **Rozstrzygnięcie:** E3 — próbka dwustronna z każdym znacznikiem; ewentualnie REA na tekstach pomocy do tych przycisków.

### H-08 — wartości w `FoldMark.xml` i `Ploter.xml` są w punktach PDF
- **Podstawa (silna):** wszystkie liczby po przeliczeniu `pt × 25,4 / 72` dają okrągłe milimetry (97, 197, 100, 200, 99, 198, 211, 422, 208, 419, 297 oraz 20, 80, 20,5, 3, 6, 1050, 740).
- **Pozostaje:** początek odliczania (od której krawędzi strony liczone jest `PZ*`) i sens `PI*` (wszystkie zerowe w próbkach).

### H-09 — `Kod_default` zapisuje schematy składek/falcowania
- **Treść:** ciąg `8:4:2:16*16:8:4*X:12*12:X*12:X*4:2:8*8:4*8:4*2:4` to lista schematów rozdzielonych `*`, w każdym liczby stron składek rozdzielone `:`; „X” oznacza zmienną/pustą pozycję. Nie wiemy, jak je interpretować.
- **Rozstrzygnięcie:** dopiero przy module książkowym (OQ-09); wymaga E3 lub celowanego REA na tekstach pomocy modułu książek.

### H-10 — koszt w kalkulatorze = cena arkusza × arkusze + cena narzędzia × impozycje
- **Podstawa:** nazwy parametrów („CenaArkusza”, „CenaNarzadu”) i opis kryteriów (minimalna liczba impozycji, minimalne odpady). Wzór jest zgadywany.
- **Rozstrzygnięcie:** OQ-04.

### H-11 — „impozycja cząstkowa” ogranicza znaczniki do wersji 0/1/2 mm
- **Treść:** tryb służy do wydruku fragmentu arkusza (np. dodruk części użytków) z uproszczonymi znacznikami. Sens 1 mm / 2 mm (długość? odstęp?) nieznany.
- **Rozstrzygnięcie:** E3.

### H-12 — `F1` oznacza wspólny zestaw znaczników dla recto i verso, `F2` — osobne zestawy
- **Podstawa:** w próbkach `F1` występuje tylko w nazwach „Recto Verso”, a `F2` w parach „Recto” / „Verso”.

## 5. Pytania otwarte

| ID | Pytanie | Wpływ | Jak rozstrzygnąć |
|---|---|---|---|
| OQ-01 | Czy format pliku projektu oryginału da się odczytać i zapisać? Nie widzieliśmy takiego pliku na dysku. | Wymiana projektów z oryginałem. | Próbka projektu zapisana przez oryginał (E3). Do tego czasu `.psimp` jest wyłącznie nasz. |
| OQ-02 | Jak oryginał traktuje „0” i bardzo duże liczby w nazwie, oraz kilka grup cyfr (`5x10`)? | Rzadkie nazwy plików. | E3: kilka nazw testowych. Studio: 0 jest błędem (komunikat), > 1 000 000 jest błędem, grupy łączą się (P-01 dosłownie). |
| OQ-03 | Co dokładnie znaczy rozmiar wyjściowy „podruku”? | Opcje rozmiaru wyjścia. | E3 albo REA na tooltipie kontrolki. |
| OQ-04 | Algorytm kalkulatora nakładów: przestrzeń przeszukiwana, kryterium zatrzymania, funkcja kosztu, rozstrzyganie remisów. | Cały `F-AKC-CALC`. | E3: tabela wejście → wynik dla ≥ 10 zestawów nakładów. Samo REA nie wystarczy (kod zaciemniony). |
| OQ-05 | Czy i jak oryginał pozwala powtarzać strony w broszurze? | Studio odmawia (jawny błąd). | Pomoc modułu książek (E1) lub E3. |
| OQ-06 | Dokładne mapowanie MB/MC na krawędź odwracania i lustro verso (H-07). | Poprawność wydruku dwustronnego. | E3. |
| OQ-07 | Reguła wyboru obrotu przy remisie pojemności w „Auto”. | Układ przy kwadratowych użytkach. | E3 (próbka z użytkiem np. 100 × 100). |
| OQ-08 | Jak siatka liczy odstępy prawy/dolny osobno dla użytków i spady różne na stronach? | Dokładność układu. | E3. |
| OQ-09 | Składnia i znaczenie `Kod_default` / kodów składek (H-09). | Moduł książek. | Pomoc modułu książek, E3. |
| OQ-10 | Wzór redukcji (creep): rola „jakości zszycia”, sposób obliczenia przesunięcia H. | Znaczniki zeszytowe. | E3 lub pomoc kontekstowa okna Redukcja. |
| OQ-11 | Autowypełnianie: dokładna kolejność przy kierunku i narożniku, filtr parzyste/nieparzyste, interakcja z powtórzeniami. | `F-AKC-AUTOFILL`. | E3. |
| OQ-12 | Zawartość i znaczenie zestawów „C” / „O” (dodatkowe elementy). | Domyślne znaczniki. | E3 (porównanie ustawień obu zestawów). |
| OQ-13 | Treść dwóch prywatnych bloków zasobów oraz nazw metod (zaciemnione). | Potencjalne ukryte reguły. | Nie rozstrzygamy: obchodzenie zaciemnienia jest poza zakresem projektu. |

## 6. Przypadki brzegowe

| Przypadek | Co wiemy | Zachowanie Studio | Test |
|---|---|---|---|
| Nazwa bez cyfr | P-01: wynik 1 | 1 | `tests/test_naming.py::OriginalHelpExamples` |
| Cyfry tylko przed ostatnim „_” | P-01 (dosłownie): ignorowane → 1 | 1 | `tests/test_naming.py::LiteralReadingOfTheRule` |
| Wiele grup cyfr (`5x10`) | P-01 dosłownie: łączymy → 510 (OQ-02) | 510 | `tests/test_naming.py::LiteralReadingOfTheRule` |
| Cyfry `000` | nieznane (OQ-02) | błąd komendy, plik bez zmian | `tests/test_commands.py::SetPageRepeatTests` |
| Wartość > 1 000 000 | nieznane | błąd komendy, plik bez zmian | `tests/test_commands.py::SetPageRepeatTests` |
| Pusty fragment po „_” | H-03 | 1 | `tests/test_naming.py::HypothesesNotConfirmedByTheOriginal` |
| Powtórzenia + broszura | OQ-05 | błąd planowania „Powtórzenia stron nie są dostępne w trybie Broszura” | `tests/test_plan_repeats.py::BookletRepeats` |
| Przody powtórzone, tyły nie | — | błąd „Tyłów jest X, przodów Y” | `tests/test_plan_repeats.py::DuplexRepeats` |
| Strona „Pomiń” z powtórzeniami | — | pomijana w całości | `tests/test_plan_repeats.py::SingleSidedRepeats` |
| Nieparzysta liczba stron w dupleksie | — | ostatnia strona z pustym verso | `tests/test_plan_baseline.py::DuplexRolesCharacterisation` |
| Liczba stron broszury nie jest wielokrotnością 4 | — | puste strony na końcu | `tests/test_plan_baseline.py::BookletCharacterisation` |
| Wycinka pionowa przy nieparzystej liczbie kolumn | P-23: nie rysować | brak znacznika wycinki w Studio | PLAN w `F-MRK-WYCINKA` |
| Liczby z przecinkiem i z kropką w jednym pliku XML | P-31 | do zaimplementowania w parserze presetów | PLAN w `F-MRK-FALC` |
| Przesunięty MediaBox, obrócona strona źródłowa | — | obsługiwane (normalizacja układu współrzędnych) | `tests/test_engine.py::test_offset_mediabox_exports_without_dropping_page_or_bleed` |
| Przestarzały numer pliku w komendzie (po usunięciu/przesunięciu) | — | błąd „Wybierz plik z listy”; historia komend jest czyszczona przy zmianie listy | `tests/test_commands.py::SetPageRepeatTests` |
| Bardzo duże `copies × page_repeat × strony` | nieznane | tryb dwustronny buduje listę par w pamięci (jak dotąd dla `copies`); granice 1 000 000 chronią przed skrajnościami, ale nie przed pamięcią | brak — do zmierzenia w etapie „wydajność” |

## 7. Użycie REA i dziennik dowodów

REA służy **wyłącznie** do rozstrzygania konkretnych luk (OQ-nn lub H-nn). Zasady:

1. Zapytanie musi wskazywać numer luki i oczekiwany rodzaj dowodu (tekst pomocy, struktura pliku, dane).
2. Wynik trafia do tabeli poniżej: data, luka, narzędzie, co znaleziono, **ograniczenia**.
3. Wniosek ze statycznej analizy to E1 lub E2, nigdy E3. Hipoteza staje się faktem (P-nn) dopiero po wpisie w dzienniku.
4. Nie omijamy zaciemnienia kodu, nie ruszamy warstwy licencyjnej i nie kopiujemy kodu, grafik ani plików z instalacji.

| Data | Luka | Narzędzie | Wynik | Ograniczenia |
|---|---|---|---|---|
| 2026-10-20 | Inwentarz funkcji | REA: analiza pakietu zarządzanego i zasobów PE | Struktura typów, zasoby interfejsu (około 18 tys. napisów w programie i 2,7 tys. w pakiecie językowym), `Base.dat` | Analiza statyczna; nic nie uruchamiano |
| 2026-10-20 | Reguły nazw plików (P-01…P-08) | Własny odczyt zasobów `.resources` z pliku wykonywalnego | Dokładne brzmienie podpowiedzi i przykłady | Tekst pomocy, nie obserwacja zachowania (E1, nie E3) |
| 2026-10-20 | Formaty presetów (P-30…P-32) | Odczyt `FoldMark.xml`, `Ploter.xml` z `Base.dat` | Struktura pól i wartości; przeliczenie jednostek (H-08) | Brak opisu semantyki pól `PI*` |
| 2026-10-20 | Granice natywne i licencja | REA: granice zarządzane/natywne | Potwierdzenie warstwy licencyjnej; pominięta celowo | Poza zakresem projektu |
| 2026-10-20 | OQ-13 | REA: widoki typów | Nazwy typów czytelne, nazwy metod i pól zaciemnione, ciała metod niedostępne bez obchodzenia zaciemnienia | Nie rozstrzygamy |
