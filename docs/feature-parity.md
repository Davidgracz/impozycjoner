# Zgodność funkcjonalna z Impozycjonerem 4 (feature parity)

Rejestr **każdej** funkcji z Feature Map oryginału (Impozycjoner 4.0.4.0) oraz funkcji, które Studio ma
ponad nią. Dla każdej: zależności, status, źródło dowodów i test akceptacyjny. Zachowanie i hipotezy:
`docs/behavior-spec.md`. Architektura: `docs/architecture.md`. Kolejność prac: `docs/roadmap.md`.

Tabelę sprawdza `python scripts/parity.py` (oraz `tests/test_docs_parity.py`). Narzędzie nie uruchamia
testów; pilnuje, żeby dokument nie obiecywał więcej, niż da się sprawdzić mechanicznie.

## Statusy

| Status | Znaczenie |
|---|---|
| `missing` | Brak implementacji (albo świadoma decyzja „poza zakresem” — wpisana w opisie). |
| `partial` | Jest część funkcji albo kod bez kompletnego testu akceptacyjnego. Brakujący zakres opisano w „PLAN:”. |
| `working` | Funkcja działa w opisanym zakresie, a **wszystkie** wskazane testy zostały uruchomione i przeszły; wpis „Przebieg: RRRR-MM-DD” mówi kiedy i jak. |
| `working†` | Funkcja istnieje i ma testy w repozytorium, ale testy **nie zostały uruchomione** w sesji tworzącej ten rejestr (brak PyMuPDF/pytest). Dziedziczone z wcześniejszych wersji; do potwierdzenia przebiegiem regresji. |
| `verified` | `working` **oraz** oczekiwane wartości testu pochodzą z dowodu E1 lub E3 (opis lub obserwacja oryginału), a test ten wykonano. **Dziś nie ma żadnego wiersza `verified`** — brak E3, a pełna funkcja wymaga też sprawdzenia UI. |

Status oznacza „co potrafimy udowodnić testem”, nie „jak bardzo działa”. Brak testu = brak statusu `working`.

## Poziomy dowodów

| Poziom | Źródło |
|---|---|
| E1 | Własne streszczenie tekstów interfejsu i pomocy oryginału |
| E2 | Statyczna struktura instalacji (XML, konfiguracja, lista plików) |
| E3 | Obserwacja uruchomionego oryginału (**żadna funkcja jej dziś nie ma**) |
| E4 | Własny kod, testy, dokumenty Studio |

## Podsumowanie

<!-- PODSUMOWANIE:START -->
| Status | Liczba |
|---|---|
| missing | 76 |
| partial | 17 |
| working | 8 |
| working† | 12 |
| verified | 0 |
| razem | 113 |
<!-- PODSUMOWANIE:END -->

## Rdzeń silnika

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-COR-BOXES | Odczyt MediaBox/CropBox/TrimBox/BleedBox, normalizacja współrzędnych (przesunięty MediaBox), obrót strony źródłowej, odrzucenie TrimBox poza MediaBox | — | working† | E4 `engine.media_rect`, `_place_pdf` | `tests/test_engine.py::test_media_box_normalization_and_22_page_preflight`, `tests/test_engine.py::test_offset_mediabox_exports_without_dropping_page_or_bleed`, `tests/test_engine.py::test_truly_invalid_trimbox_outside_media_is_rejected`, `tests/test_engine.py::test_source_rotation_can_match_net_dimensions` |
| F-COR-RENDER | Wektorowe osadzanie stron w slotach arkusza (form XObject, bez rasteryzacji), zachowanie tekstu i wymiarów | F-COR-BOXES | working† | E4 `engine.render_side` | `tests/test_engine.py::test_export_preserves_text_and_dimensions`, `tests/test_engine.py::test_rotated_bleed_90_keeps_bleed_vector` |
| F-SYS-DEPS | Czytelny błąd zamiast `AttributeError`, gdy brakuje PyMuPDF; logika planowania działa bez niego | — | working | E4 `engine.require_pymupdf` | `tests/test_plan_baseline.py::MissingPyMuPDF` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |

## Wejście i pliki

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-WEJ-PDF | Wczytanie jednego lub wielu PDF (też wielostronicowych); podsumowanie liczby stron i formatu | F-COR-BOXES | working† | E4 `engine.open_sources`, `source_summary` | `tests/test_engine.py::test_media_box_normalization_and_22_page_preflight`, `tests/test_engine.py::test_a4_to_a6_22_pages_fit_preserves_page_order_and_vectors` |
| F-WEJ-PROT | Odrzucenie PDF zabezpieczonych hasłem, uszkodzonych i plików nie-PDF z czytelnym komunikatem | F-WEJ-PDF | partial | E4 `engine.open_sources` | PLAN: test z PDF zaszyfrowanym i z plikiem tekstowym `.pdf` → `ValueError`, źródła zamknięte, brak wyjątku z PyMuPDF; kod istnieje, testu brak. |
| F-WEJ-SCALE | Jawne skalowanie strony źródłowej do netto: Bez skalowania / Dopasuj / Wypełnij (rozszerzenie Studio; w oryginale pokrewna jest korekta obszaru netto ze skalą) | F-COR-RENDER | working† | E4 `engine.scaling_layout`; E1 pokrewne | `tests/test_engine.py::test_scaling_explicitly_opt_in_and_project_roundtrip`, `tests/test_engine.py::test_fill_mode_crops_to_target_without_stretch_or_spill`, `tests/test_engine.py::test_scaled_bleed_uses_output_mm_not_source_mm` |
| F-WEJ-TRIMFIX | Korekta położenia i rozmiaru obszaru netto per PDF: wymiar H×V, odsunięcia L/P/G/D, skala, orientacja; zakres stron (wszystkie/parzyste/nieparzyste); przycięcie do netto albo do brutto = netto + 3 mm; zapis nowego PDF | F-COR-BOXES | missing | E1 (okno „Koryguj położenie i rozmiar obszaru netto”) | PLAN: PDF 90×50 z odsunięciem netto o 2 mm w lewo → wynik ma TrimBox 90×50 w nowym położeniu; zakres „nieparzyste” zmienia tylko strony 1,3,5…; wartości liczbowe z E3. |
| F-WEJ-OUTSIZE | Rozmiar wyjściowy: papier / papier + chwyt / pole zadruku / pole zadruku + chwyt / płyta / „podruk”; TrimBox i MediaBox bez zmian lub poprawione, spad 0 lub 3 mm | F-AKC-SHEET | missing | E1 (lista opcji), OQ-03 | PLAN: dla arkusza 450×320 i chwytu 11 mm rozmiar „papier + chwyt” ma wymiary zgodne z definicją z E3; „podruk” wymaga rozstrzygnięcia OQ-03. |
| F-WEJ-OUTNAME | Nazwa pliku wynikowego: zakaz znaków `# % & * : < > ? / \ { }` i pionowej kreski, zakaz nazwy równej przetwarzanemu plikowi, dopiski `--IMPOZYCJONER` i fraza uzupełniająca | — | missing | E1 P-04, P-05 | PLAN: lista nazw zabronionych → odrzucone z komunikatem; nazwa = źródło → odrzucona; opcja dopisku dodaje dokładnie `--IMPOZYCJONER` (test jednostkowy czystej funkcji w `naming.py`). |
| F-WEJ-META | Metadane wyniku: Autor, Tytuł, Temat, Słowa kluczowe (puste = nazwa pliku); wersja PDF (domyślnie 1.5) | — | missing | E1 P-07, E2 `Pdf_version` | PLAN: puste pola → nazwa pliku w metadanych; wersja nagłówka PDF zgodna z wyborem (odczyt z pliku wynikowego). |
| F-WEJ-PAGECNT | Ostrzeżenie, gdy nakładane pliki mają różną liczbę stron, z pytaniem o kontynuację | F-WEJ-PDF | missing | E1 P-08 | PLAN: dwa pliki 3 i 5 stron → ostrzeżenie w preflight i pytanie w UI; jeden plik → brak ostrzeżenia. |
| F-WEJ-ROWDUP | Powielanie zaznaczonych wierszy tabeli stron (okno „Ilość powtórzeń”): kopie wstawiane bezpośrednio pod wierszem źródłowym, z przepisaniem wszystkich komórek; liczba z pola albo z nazwy pliku (N − 1 kopii) | F-WEJ-PDF | missing | E1 P-09, P-16; E2 P-14, P-15, P-17, P-18 (REA-05…REA-09) | PLAN: tabela z trzema wierszami pliku `Arkusz_3.pdf`, zaznaczone wszystkie, tryb „z nazwy” → 9 wierszy w kolejności 1,1,1,2,2,2,3,3,3; zaznaczony tylko wiersz 2 → 1,2,2,2,3; tryb „z pola” — wartość oczekiwana dopiero z E3 (H-13); `0`, pusty fragment i ponad zakres — H-14. |
| F-WEJ-CHGPAGE | „Zmień plik/stronę”: podmiana pliku i numeru strony wybranego wiersza tabeli stron (pole „Strona: n z m”, przycisk „Otwórz…”) | F-WEJ-PDF | missing | E1 (teksty okna `Form_DodajPlik`; REA-04) | PLAN: po podmianie wiersz wskazuje nowy plik i stronę, pozostałe wiersze bez zmian; zachowanie przy stronie spoza zakresu i przy zmianie liczby stron — nieznane (wymaga E3). |
| F-WEJ-OUTMERGE | Łączenie plików wynikowych: siedem wariantów (w jeden plik / w arkusze / każdy osobno oraz ich kombinacje) | F-COR-RENDER | missing | E1 (teksty okna `Form_LaczeniePlikow`; REA-04) | PLAN: dla dwóch plików i trzech arkuszy każdy wariant daje oczekiwany zestaw plików wynikowych; nazewnictwo wyników — dopiero z E3 (powiązane: F-WEJ-OUTNAME). |

## Akcydensy (moduł „Impozycja akcydensów”)

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-AKC-ITEM | Rozmiar użytku netto (szer. × wys.); opcje: „= rozmiar zaznaczonej strony”, zamiana szer./wys., wyzerowanie | F-COR-BOXES | partial | E1 P-20; E4 `Settings.trim_w/trim_h`, preset „Z PDF (oryginał)” | PLAN: dodać zamianę szer./wys. i rozmiar z zaznaczonej strony (komendy, test jednostkowy); istniejące: `tests/test_plan_baseline.py::GridGeometry`. |
| F-AKC-GAP | Odstępy użytków (wycinka): prawy i dolny **osobno dla każdego użytku**; Studio ma jeden odstęp poziomy i jeden pionowy dla całej siatki | F-AKC-ITEM | partial | E1 (okno „Nowy rozmiar użytku”); E4 `Settings.gap_x/gap_y` | PLAN: siatka 3 kolumny z odstępami 2/5 mm → pozycje slotów wg ręcznego rachunku; istniejące: `tests/test_plan_baseline.py::GridGeometry`. OQ-08. |
| F-AKC-GRID | Automatyczna siatka kolumny × wiersze, wybór obrotu 0°/90° o największej pojemności, centrowanie, ręczne kolumny/wiersze | F-AKC-ITEM, F-AKC-SHEET | working | E4 `engine.geometry` (S-01) | `tests/test_plan_baseline.py::GridGeometry` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |
| F-AKC-ROT | Obrót użytków 0°/90°/180°(/270°): Studio — globalnie; oryginał — także per użytek, wiersz, kolumna, arkusz | F-AKC-GRID | partial | E1 P-20; E4 `Settings.rotation` | PLAN: obrót pojedynczego wiersza o 180° zmienia `Slot.rotation` tylko tego wiersza i obraca zawartość w PDF; istniejące: `tests/test_plan_baseline.py::GridGeometry`. |
| F-AKC-BLEED | Spady wokół użytku: Studio — jedna wartość; oryginał — osobno dla każdej strony | F-AKC-ITEM | partial | E1 P-20; E4 `Settings.bleed` | PLAN: spady 3/2/3/2 mm per strona → komórka i rzut zgodne; istniejące: `tests/test_engine.py::test_rotated_bleed_90_keeps_bleed_vector`, `tests/test_engine.py::test_scaled_bleed_uses_output_mm_not_source_mm` (nieuruchomione). |
| F-AKC-BLEEDWARN | Ostrzeżenie o różnych spadach na jednym arkuszu (kłopot z wykrojeniem) | F-AKC-BLEED | missing | E1 P-22 | PLAN: dwa użytki o spadach 2 i 3 mm na jednym arkuszu → ostrzeżenie w preflight; równe spady → brak. |
| F-AKC-SHEET | Papier i arkusz: rozmiar papieru, płyta, chwyt [mm] (domyślnie 11), margines techniczny „na łapki”, redukcja płyty [pt]. Studio: rozmiar arkusza i symetryczne marginesy X/Y | — | partial | E1 P-20; E2 `Chwyt = 11`; E4 `Settings.sheet_*`, `margin_*` | PLAN: chwyt 11 mm po stronie wskazanej krawędzi odejmuje pole zadruku; płyta ≠ papier; test geometrii z wartościami z E3; istniejące: `tests/test_plan_baseline.py::GridGeometry`. |
| F-AKC-PAPERS | Baza papierów: nazwa, wymiary, oznaczenie offset/cyfra; arkusze podstawowe A1/B1 (krótszy/dłuższy bok, DL-A, DL-B), zapis jako domyślne. Studio: stała lista presetów | F-AKC-SHEET | partial | E1 (okna „Dodaj nowy papier”, „Arkusz podstawowy”); E4 `app.PRESETS` | PLAN: dodanie papieru zapisuje go w profilu użytkownika i jest dostępne po restarcie; test jednostkowy warstwy plików. |
| F-AKC-KIND | Rodzaj arkusza: składany (offset) vs nieskładany (cyfra) | F-AKC-SHEET | missing | E1 | PLAN: wybór wpływa na dostępne opcje (np. chwyt); wartości i reguły z E3. |
| F-AKC-ECON | „Rozmieść ekonomicznie”: kolumny × wiersze dla wskazanych rozmiarów papieru, wg bieżących ustawień znaczników, z pominięciem paska kontrolnego | F-AKC-GRID, F-MRK-PASKI | missing | E1 | PLAN: dla 3 papierów z bazy zwraca kolumny × wiersze; zgodność z `engine.geometry` przy tych samych marginesach (test porównawczy) i z E3 co do pominięcia paska. |
| F-AKC-ITEMTABLE | Tabela użytków: zaznaczanie wiersza/kolumny, wstaw/wyczyść wakat, zamiana/przesunięcie/skalowanie/obrót stron, „zastosuj do wszystkich w wierszu / kolumnie / na stronie” | F-AKC-GRID | missing | E1 | PLAN: komendy edycji tabeli (zamiana dwóch użytków, wyczyszczenie wiersza) jako odwracalne komendy z testami jednostkowymi; wygląd i skróty — E3. |
| F-AKC-BLANKS | Wakaty (puste miejsca) kontrolowane przez operatora. Studio dopełnia puste miejsca tylko automatycznie (verso, broszura) | F-AKC-ITEMTABLE | partial | E1; E4 `engine._duplex_pairs`, `_booklet_sides` | PLAN: operator zaznacza slot jako wakat → eksport zostawia go pustym, a kolejne strony przesuwają się zgodnie z regułą z E3; istniejące: `tests/test_plan_baseline.py::BookletCharacterisation`. |
| F-AKC-AUTOFILL | Autowypełnianie: narożnik startu (LG/LD/PG/PD), kierunek, wszystkie/nieparzyste/parzyste strony, powtórzenia na stronę. Studio: kolejne sloty wierszami od lewego górnego rogu | F-AKC-GRID, F-AKC-REP | partial | E1; E4 `engine.plan_sides` | PLAN: start z PD, kierunek w dół → kolejność slotów wg ręcznego rachunku; filtr „parzyste” pomija strony nieparzyste (OQ-11); istniejące: `tests/test_plan_baseline.py::SingleSidedOrder`. |
| F-AKC-PATTERN | „Wypełnienie według wzoru” pierwszego arkusza | F-AKC-MULTISHEET | missing | E1 | PLAN: pierwszy arkusz ma układ A; wzór kopiuje układ na kolejne arkusze z pozostałymi pracami. |
| F-AKC-REP | **Powtórzenia każdej strony**: wpisane ręcznie albo odczytane z nazwy pliku (część po ostatnim „_”, tylko cyfry, brak cyfr = 1). Pierwszy pionowy fragment. W oryginale odpowiada mu operacja „Powtórzenia” na wierszach tabeli stron (`F-WEJ-ROWDUP`); Studio powiela wszystkie strony pliku naraz (kolejność 1,1,2,2…) | F-AKC-GRID, F-WEJ-PDF, F-SYS-PROJECT | partial | E1 P-01, P-02, P-09, P-16; E2 P-14, P-15, P-17, P-18 (REA-05…REA-09); E4 `naming.py`, `commands.py`, `engine.py`, `app.py` | PLAN: dokończyć po stronie Windows: (1) `python -m pytest -q tests/test_repeats_pdf.py` (PDF `Arkusz_2.pdf` → każda strona 2×, kolejność 1,1,2,2,3,3), (2) ręczna lista kontrolna UI z `docs/roadmap.md`, Etap 0. Uruchomione: `tests/test_naming.py::OriginalHelpExamples`, `tests/test_commands.py::SetPageRepeatTests`, `tests/test_plan_repeats.py::SingleSidedRepeats` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS. Nieuruchomione: `tests/test_repeats_pdf.py::test_name_to_pdf_each_page_twice_in_order`, UI Tk. RÓŻNICE WOBEC ORYGINAŁU (nierozstrzygnięte, patrz spec): wpisana liczba w oryginale zapewne oznacza N dodatkowych kopii (H-13), a z nazwy N wystąpień (P-16); `0`/pusty/ponad zakres inaczej (H-14); operacja działa na zaznaczeniu, nie na całym pliku (`F-WEJ-ROWDUP`). Status `verified` dopiero po E3. |
| F-AKC-COPIES | „Nakład pliku” — powtórzenie całego pliku (1,2,3,1,2,3). Rozszerzenie Studio; Feature Map nie zna takiej funkcji | F-AKC-GRID | working | E4 `Job.copies` (S-02) | `tests/test_plan_baseline.py::SingleSidedOrder` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |
| F-AKC-RUNNAME | Nakład z nazwy pliku dla wszystkich stron pliku w tabeli kalkulatora (`test_2000.pdf` → 2000) | F-AKC-CALC | missing | E1 P-03; H-05 | PLAN: po powstaniu kalkulatora `test_2000.pdf` wypełnia nakład 2000 dla każdej strony pliku; parser już istnieje (`naming.parse_repeats`, `tests/test_naming.py::OriginalHelpExamples`). |
| F-AKC-CALC | Kalkulator nakładów: rozkład użytków prac na arkuszach o minimalnej liczbie impozycji i odpadzie; cena arkusza 0,30, cena narzędzia 120; wczesne zatrzymanie; auto-przeliczanie lub F6; usuwanie PKM; F2/dwuklik zmienia nakład | F-AKC-GRID, F-AKC-MULTISHEET | missing | E1 P-10, P-12, P-13; H-10; OQ-04 | PLAN: zestawy nakładów 100/1000/3000 oraz ≥ 10 innych → rozkład i koszt zgodne z tabelą z E3. Bez E3 nie da się zdefiniować wartości oczekiwanych — nie implementujemy „na oko”. |
| F-AKC-NWD | Opcja NWD: nakłady 100/1000/3000 liczone jak 1/10/30 i przemnożone; wynik może się nieznacznie różnić | F-AKC-CALC | missing | E1 P-11 | PLAN: właściwość z pomocy: `rozkład(100,1000,3000, NWD)` = 100 × `rozkład(1,10,30)`; wartości rozkładu — E3 (OQ-04). |
| F-AKC-SPLIT | Kreator podziału arkusza (np. dwa razy, 3×DL) | F-AKC-GRID | missing | E1 | PLAN: podział arkusza SRA3 na 2 części daje dwie siatki zgodne z E3. |
| F-AKC-MULTISHEET | Wiele arkuszy impozycyjnych z różnymi pracami (gang-run); ilości użytków na kolejnych arkuszach | F-AKC-GRID | missing | E1 P-13 | PLAN: dwa arkusze o różnych układach w jednym projekcie; eksport zawiera oba, kolejność i liczba zgodne z definicją. |
| F-AKC-MULTIITEM | Użytki wieloarkuszowe (jedna praca rozłożona na kilka arkuszy) | F-AKC-MULTISHEET | missing | E1 | PLAN: praca 3-stronicowa na 2 arkuszach — reguły z E3. |
| F-AKC-DIECUT | Wykrojnik: montaż wykrojników i nakładanie PDF z wykrojnikiem (nazwa pliku ze zmontowanym wykrojnikiem) | F-AKC-GRID | missing | E1 | PLAN: wykrojnik jako warstwa nad arkuszem; zgodność położenia z E3. |
| F-AKC-SHIFT | Przesunięcia stron parzystych/nieparzystych (P/NP) oraz przesunięcie obrazu lewa ↔ prawa | F-AKC-ITEMTABLE | missing | E1 | PLAN: przesunięcie NP o 1 mm w prawo przesuwa tylko strony nieparzyste o 1 mm. |
| F-AKC-PARTIAL | Impozycja cząstkowa: bez znaczników / znaczniki 1 mm / 2 mm | — | missing | E1 P-28; H-11 | PLAN: trzy warianty dają trzy różne zestawy znaczników; znaczenie 1/2 mm — E3. |
| F-AKC-MOCKUP | „Makieta” — szybki, uproszczony podgląd. Studio renderuje rzeczywisty podgląd jednego arkusza | F-STU-PREVIEW | missing | E1 | PLAN: tryb makiety rysuje prostokąty użytków z numerami stron bez renderowania PDF; czas dla 1000 stron < 0,2 s (pomiar). |
| F-AKC-RUNMODES | „Wykonaj impozycję”: wszystkie arkusze / tylko aktywny / wszystkie poza aktywnym | F-AKC-MULTISHEET | missing | E1 | PLAN: trzy tryby dają odpowiednio N, 1 i N−1 arkuszy w pliku wynikowym. |
| F-AKC-SHEETRNG | Wybór zakresu arkuszy do wykonania: „wszystkie arkusze” albo „tylko arkusze z zakresu” (składnia z przykładu: `-3, 6, 9-11, 15-`; dozwolone przecinek, minus i cyfry) | F-AKC-RUNMODES | missing | E1 (teksty okna `Form_ZakresArkuszy`; REA-04) | PLAN: zakres `-3, 6, 9-11, 15-` przy 20 arkuszach; znaczenie otwartych końców (`-3`, `15-`) i błędnych zapisów — dopiero z E3, do tego czasu błąd z komunikatem. |
| F-AKC-SIGN | Sposób oznaczania arkusza i strony (nazwa, numeracja arkusza, strony, sygnatury) w opisie impozycji | — | missing | E1 | PLAN: wzorzec numeracji „Ark. 2/5” → tekst w opisie; wzorce z E3. |

## Dwustronność

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-DUP-SINGLE | Wydruk jednostronny: kolejność stron w slotach, pojemność arkusza, numeracja arkuszy | F-AKC-GRID | working | E4 `engine.plan_sides` (S-02) | `tests/test_plan_baseline.py::SingleSidedOrder` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |
| F-DUP-VERSO | Dwustronnie: arkusz recto i verso z lustrzanymi slotami wg krawędzi odwracania | F-AKC-GRID | working | E4 `engine._flip_slot` (S-04) | `tests/test_plan_baseline.py::DuplexFlipCharacterisation` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |
| F-DUP-MB | Dwustronnie przez znacznik boczny MB („work-and-turn”) | F-DUP-VERSO | partial | E1 P-29; H-07; OQ-06 | PLAN: próbka z oryginału (E3) z MB → verso lustrzane identycznie jak w Studio dla właściwej krawędzi; istniejące: `tests/test_plan_baseline.py::DuplexFlipCharacterisation`. |
| F-DUP-MC | Dwustronnie przez znacznik czołowy MC („work-and-tumble”) | F-DUP-VERSO | partial | E1 P-29; H-07; OQ-06 | PLAN: jak wyżej dla MC; istniejące: `tests/test_plan_baseline.py::DuplexFlipCharacterisation`. |
| F-DUP-PARTIAL | Dwustronnie częściowe (tylko część użytków ma verso) | F-DUP-VERSO | missing | E1 P-29 | PLAN: arkusz z 5 użytkami recto i 3 verso → verso ma puste sloty w wyznaczonych miejscach (reguły z E3). |
| F-DUP-ROLES | Role stron: Normalnie / Przód / Tył sparowany / Tył wspólny / Pomiń (rozszerzenie Studio 0.2.4) i ich walidacja | F-DUP-VERSO | working | E4 `engine._duplex_pairs` (S-03) | `tests/test_plan_baseline.py::DuplexRolesCharacterisation`, `tests/test_plan_repeats.py::DuplexRepeats` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |

## Znaczniki (14 okien oryginału)

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-MRK-NETTO | Znaczniki rozmiaru netto: narożniki LG/LD/PG/PD, długości, grubość [pt], strony wszystkie/parzyste/nieparzyste. Studio: stały zestaw włosowych kresek 3 mm | F-COR-RENDER | partial | E1 (okno „Netto”); E4 `engine._draw_marks` (S-06) | PLAN: długość, grubość i wybór narożników sterowane ustawieniami; istniejące: `tests/test_plan_baseline.py::MarksCharacterisation` (domyślny zestaw). |
| F-MRK-BRUTTO | Znaczniki rozmiaru brutto (długości LP i GD, grubość, strony) | F-COR-RENDER | missing | E1 | PLAN: znaczniki na obrysie brutto = netto + spad; test pozycji kresek. |
| F-MRK-PASERY | Pasery: wariant 1/2/3, średnica, grubość, odległość X po długim i krótkim boku, odsunięcie H od brutto | F-COR-RENDER | missing | E1 | PLAN: pasery w polach z parametrów; test pozycji i liczby obiektów wektorowych. |
| F-MRK-BRUTPAS | Pasery w polu brutto (H1, H2, V1, V2, grubość) | F-MRK-PASERY | missing | E1 | PLAN: jak wyżej dla wariantu brutto. |
| F-MRK-PASKI | Paski kontrolne kolorów: pozycja, odsunięcie od innych elementów, strefy, rozmiar i kolory komórek; ładowanie pasków z zewnętrznych PDF | F-COR-RENDER | missing | E1 | PLAN: pasek z N komórek o zadanym rozmiarze i kolorach CMYK rysowany jako wektor; wczytanie pasków z PDF użytkownika. Własnych grafik z oryginału nie kopiujemy. |
| F-MRK-WYCINKA | Wycinka (środkowy odstęp cięcia): szerokość pionowa i pozioma, grubość; rysowana tylko gdy możliwa — pionowa wymaga parzystej liczby kolumn | F-AKC-GRID | missing | E1 P-23 | PLAN: 4 kolumny → wycinka pionowa rysowana; 3 kolumny → nie rysowana i komunikat; test na siatkach 2,3,4,5 kolumn. |
| F-MRK-UCHIDA | Znacznik pozycjonowania wykrojnika Uchida: wymiary H1/H/H2 i V1/V/V2, odstęp noży, noże krzyżowe/podłużne, kierunek podawania | F-COR-RENDER | missing | E1 | PLAN: parametry → położenie znaczników wg E3. |
| F-MRK-WLASNY | Własne znaczniki z czterech PDF (`U1L`, `U1R`, `U2L`, `U2R`) w katalogu użytkownika; brak pliku wyłącza przełącznik; położenie H/V | F-COR-RENDER | missing | E1 P-26; E2 | PLAN: plik `U1L.pdf` w katalogu użytkownika → znacznik na lewej krawędzi pierwszej strony; brak pliku → przełącznik nieaktywny. Dostarczamy własne przykłady, nie kopie z `Base.dat`. |
| F-MRK-FALC | Znaczniki falcowania („cross-fold”) tylko dla arkuszy po 8/12/16 stron; presety `FoldMark.xml` (6 wpisów, pozycje w pt) | F-KSI-BOOKLET2UP | missing | E1 P-25; E2 P-30, P-31; H-08, H-12 | PLAN: parser presetów przyjmuje przecinek i kropkę dziesiętną („558,4” i „0.5”); 6 presetów z `docs/behavior-spec.md` daje pozycje 97/197, 100/200, 99/198, 211/422, 208/419, 297/297 mm; własny plik testowy, bez kopiowania oryginału. |
| F-MRK-SYGN | Sygnatura grzbietowa/krawędziowa: szerokość i długość, V startu, góra/dół, szerokość paska kleju | F-KSI-BOOKLET2UP | missing | E1 | PLAN: sygnatura rośnie schodkowo wg numeru składki; reguły z E3. |
| F-MRK-CREEP | Redukcja (creep) w oprawie zeszytowej: grubość papieru, liczba stron z okładką, „jakość zszycia”, obliczone H | F-KSI-BOOKLET2UP | missing | E1; OQ-10 | PLAN: wzór z E3 lub pomocy kontekstowej; test: 0 mm grubości → 0 przesunięcia, przesunięcie rośnie monotonicznie ku środkowi. |
| F-MRK-MARGINS | Dodatkowe marginesy: odległość znaczników od użytków; opcja zerowania spadów; spady przy odstępach rysowane tylko gdy odstęp ≥ 2 × odległość znaczników (i tylko dla spadu 0 i odległości > 0) | F-MRK-NETTO | missing | E1 P-24 | PLAN: odstęp 5 mm i odległość 2 mm → rysowane; odstęp 3 mm i odległość 2 mm → nie rysowane (granica 2×). |
| F-MRK-CROPBOX | Dodatkowe przycięcie TrimBox „crop”: włos [pt], z lewej na parzystych, z prawej na nieparzystych; ostrzeżenie przy rozkładówkach | F-COR-BOXES | missing | E1 P-27 | PLAN: crop 0,5 pt → TrimBox strony parzystej zmniejszony po lewej o 0,5 pt, nieparzystej po prawej. |
| F-MRK-OPIS | Opis impozycji (slug): nazwa pliku, oznaczenie arkusza/strony, informacje dodatkowe (pole zadruku, netto/brutto/spad, tekst, data i godzina), czcionka i rozmiar, położenie (krawędź górna, boczne, środkowe odstępy). Pokrewne w Studio: numery stron (`show_page_labels`) | F-AKC-SIGN | missing | E1 | PLAN: opis zawiera nazwę pliku, datę i oznaczenie arkusza w zadanym miejscu; test tekstu w PDF. |
| F-MRK-DEFAULTS | „Zapisz jako domyślne dla bieżącego zestawu” w oknach znaczników; kolory znaczników | F-MRK-SETS | missing | E1 | PLAN: zapis i odczyt ustawień znacznika per zestaw w profilu użytkownika. |
| F-MRK-SETS | Dwa zestawy definicji dodatkowych elementów („pomarańczowy” i „niebieski”, etykiety C i O) | F-SYS-SETTINGS | missing | E1; E2 `Oznaczenie_Zestawu_1/2`; OQ-12 | PLAN: przełączenie zestawu zmienia komplet znaczników; zawartość zestawów z E3. |
| F-MRK-TOGGLE | Włączanie/wyłączanie znaczników skrótem klawiszowym i prawym przyciskiem myszy | F-SYS-SHORTCUTS | missing | E1 | PLAN: skrót przełącza znacznik (test warstwy komend), prawy przycisk — lista kontrolna UI. |

## Książki i broszury

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-KSI-BOOKLET2UP | Broszura zeszytowa 2-up: kolejność stron, dopełnienie pustymi do wielokrotności 4 | F-COR-RENDER | working | E4 `engine._booklet_sides` (S-05); E1 pokrewne | `tests/test_plan_baseline.py::BookletCharacterisation` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |
| F-KSI-BIND | Oprawy: klejona, zeszytowa, szyta-klejona (Studio: tylko zeszytowa 2-up) | F-KSI-BOOKLET2UP | partial | E1 | PLAN: oprawa klejona składa składki sekwencyjnie, nie zeszytowo; kolejność stron wg E3; istniejące: `tests/test_plan_baseline.py::BookletCharacterisation`. |
| F-KSI-SIG | Składki 1–12 „czwórek”, składki niepełne, warianty kopii/stosu | F-KSI-BIND | missing | E1; H-09; OQ-09 | PLAN: 24 strony w składkach po 8 → kolejność wg E3; składka niepełna dopełniana wg reguły z E3. |
| F-KSI-FOLD | Schematy falcowania i kod składek (np. wartość domyślna `Kod_default`) | F-KSI-SIG | missing | E2 P-33; H-09; OQ-09 | PLAN: parser kodu ze zdefiniowaną składnią (po rozstrzygnięciu OQ-09); testy na przykładach z E3. |

## Narzędzia dodatkowe (32 w Feature Map, zgrupowane w 25 wierszy)

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-NAR-OVERLAY | Nakładanie stron (trzy wersje narzędzia) | F-COR-RENDER | missing | E1 | PLAN: strona A nałożona na B w wyniku zawiera tekst obu; trzy warianty — definicje z E3. |
| F-NAR-CALENDAR | Kreator kalendarza z zapisem i otwieraniem szablonów | F-COR-RENDER | missing | E1 | PLAN: kalendarz miesięczny z poprawnymi dniami tygodnia dla zadanego roku (test dat). |
| F-NAR-PLOTTER | Znaczniki plotera tnącego (preset `Ploter.xml`: typ, liczba osi, rozmiar, grubość, marginesy, pole ochronne) | F-COR-RENDER | missing | E2 `Ploter.xml`; H-08 | PLAN: parser presetu przyjmuje przecinek dziesiętny; marker 6 mm i grubość 3 mm (wartości z presetu) rysowane w zadanych miejscach. |
| F-NAR-EYELETS | Oczkowanie bannerów | F-COR-RENDER | missing | E1 | PLAN: oczka co zadany odstęp na obwodzie banera; liczba i pozycje wg obliczenia. |
| F-NAR-STRIPGEN | Generator pasków kolorów | F-MRK-PASKI | missing | E1 | PLAN: pasek z zadanych kolorów CMYK jako wektor. |
| F-NAR-EAN13 | Kod kreskowy EAN-13 oraz EAN-13/EAN-8 | F-COR-RENDER | missing | E1 | PLAN: znane wektory testowe EAN-13 (suma kontrolna, wzór kresek) — wartości publiczne ze standardu. |
| F-NAR-EAN128 | Kod EAN-128 | F-COR-RENDER | missing | E1 | PLAN: wektory testowe GS1-128 ze standardu. |
| F-NAR-CODE128 | Kod CODE 128 | F-COR-RENDER | missing | E1 | PLAN: wektory testowe Code 128 ze standardu (sumy kontrolne). |
| F-NAR-QR | Kod QR | F-COR-RENDER | missing | E1 | PLAN: wygenerowany kod odczytywany dekoderem referencyjnym do tego samego tekstu. |
| F-NAR-BLEEDADD | Dodawanie spadów do PDF | F-COR-BOXES | missing | E1 | PLAN: PDF bez spadu → wynik z 3 mm spadu wg wybranej metody (lustro/rozciągnięcie — E3). |
| F-NAR-RASTER | Rasteryzacja PDF do RGB | F-COR-RENDER | missing | E1 | PLAN: strona 90×50 mm w 300 dpi → obraz 1063×591 px; profil RGB. |
| F-NAR-IMG2PDF | Bitmapy do PDF | F-COR-RENDER | missing | E1 | PLAN: obraz o znanym rozmiarze i dpi → strona PDF o wymiarach z rachunku. |
| F-NAR-TXT2PDF | Tekst do PDF | F-COR-RENDER | missing | E1 | PLAN: plik tekstowy UTF-8 → PDF z identycznym tekstem (ekstrakcja). |
| F-NAR-RENAME | Zbiorcza zmiana nazw plików | — | missing | E1 | PLAN: wzorzec nazw na liście plików → nowe nazwy; kolizje wykrywane. |
| F-NAR-RENUM | Renumeracja | — | missing | E1 | PLAN: pliki `a_1…a_10` → numeracja z zerami; kolejność zachowana. |
| F-NAR-SCALE | Skalowanie PDF jako samodzielne narzędzie. Pokrewne w Studio: „Eksportuj pojedyncze strony” z wyborem Dopasuj/Wypełnij | F-WEJ-SCALE, F-STU-PAGES | partial | E1; E4 `engine.export_pages` | PLAN: skalowanie procentowe i do rozmiaru, tak jak w oknie narzędzia; istniejące: `tests/test_engine.py::test_a4_to_a6_22_pages_fit_preserves_page_order_and_vectors` (nieuruchomione). |
| F-NAR-SPLIT | Podział PDF na pojedyncze strony z dopiskiem `--XX` w nazwie | F-WEJ-OUTNAME | missing | E1 P-06 | PLAN: PDF 12-stronicowy → 12 plików `nazwa--01…--12` z jedną stroną. Wiodące zera: E3. |
| F-NAR-ROTATE | Obrót stron | F-COR-RENDER | missing | E1 | PLAN: obrót o 90° zmienia wymiary strony i zawartość. |
| F-NAR-EXTRACT | Wyodrębnianie stron i zakresów | F-COR-RENDER | missing | E1 | PLAN: zakres `1,3-5` daje 4 strony w tej kolejności. Pokrewne: parser zakresów w oknie ról (`app.edit_page_roles`). |
| F-NAR-DUP | Powielanie stron | F-COR-RENDER | missing | E1 | PLAN: strona ×3 → 3 kopie; kolejność wg definicji z E3. |
| F-NAR-INSERT | Wstawianie stron | F-COR-RENDER | missing | E1 | PLAN: wstawienie strony pustej w zadane miejsce. |
| F-NAR-SHUFFLE | Przetasowanie (mieszanie kolejności) stron | F-COR-RENDER | missing | E1 | PLAN: kolejność wg zdefiniowanego wzoru (E3). |
| F-NAR-MERGE | Łączenie PDF | F-COR-RENDER | missing | E1 | PLAN: dwa PDF 3 i 4 strony → 7 stron w kolejności wejścia. |
| F-NAR-FLATTEN | Spłaszczanie formularzy | F-COR-RENDER | missing | E1 | PLAN: PDF z polami formularza → wynik bez pól, z widocznymi wartościami. |
| F-NAR-FOLDMARK | Narzędzie znaczników falcowania na dowolnym PDF | F-MRK-FALC | missing | E1 | PLAN: jak `F-MRK-FALC` na pliku wejściowym użytkownika. |

## Kontrola PDF (preflight) — rozszerzenia Studio

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-PRE-BOX | Sprawdzanie formatu i TrimBox względem netto; błąd przy niezgodności | F-COR-BOXES | working† | E4 `preflight.inspect_project` | `tests/test_engine.py::test_preflight_warning_missing_bleed_and_error_wrong_size`, `tests/test_engine.py::test_media_box_normalization_and_22_page_preflight` |
| F-PRE-BLEED | Wykrywanie brakującego fizycznego spadu | F-PRE-BOX | working† | E4 `preflight.py` | `tests/test_engine.py::test_preflight_warning_missing_bleed_and_error_wrong_size` |
| F-PRE-DPI | Rozdzielczość obrazów po skalowaniu, grupowana per strona, szczegóły w JSON | F-PRE-BOX | working† | E4 `preflight.py` | `tests/test_engine.py::test_dpi_grouped_per_page_and_preserved_individually_in_json`, `tests/test_engine.py::test_dpi_calculated_after_downscaling` |
| F-PRE-MIXED | Mieszane rozmiary stron w jednym PDF raportowane jako osobne zakresy; sprawdzane tylko unikalne strony | F-PRE-BOX | working† | E4 `preflight.py` | `tests/test_engine.py::test_mixed_a4_a6_pages_are_reported_as_distinct_ranges`, `tests/test_engine.py::test_preflight_checks_only_unique_source_pages` |
| F-PRE-ROLES | Walidacja przypisań ról przód/tył przed eksportem | F-DUP-ROLES | working† | E4 `preflight.py` | `tests/test_engine.py::test_024_preflight_rejects_unmatched_backs_and_multiple_shared`, `tests/test_engine.py::test_024_roles_require_duplex_mode_to_prevent_misprint` |
| F-PRE-COLOR | Pełny preflight: RGB/CMYK/spot, ICC, przezroczystości, PDF/X, kontrola znaczników | F-PRE-BOX | missing | E4 `ROADMAP.md` | PLAN: PDF z elementem RGB w zadaniu CMYK → ostrzeżenie; PDF z kolorem dodatkowym (spot) → wymieniony z nazwą. |

## System, pliki i interfejs

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-SYS-PROJECT | Zapis i odczyt projektu `.psimp` (ZIP + JSON): ustawienia, pliki, role, powtórzenia; ścieżki względne; zgodność ze starszymi plikami | — | working | E4 `engine.save_project`, `load_project` (rozdz. 2.5 specyfikacji) | `tests/test_plan_repeats.py::ProjectFile` Przebieg: 2026-10-20 (unittest, Linux, bez PyMuPDF) PASS |
| F-SYS-PROJORIG | Odczyt i zapis plików projektu oryginału (Ctrl+S / Ctrl+W w oryginale) | F-SYS-PROJECT | missing | E1; OQ-01 | PLAN: wymaga próbki pliku projektu z oryginału (E3); bez niej nie podejmujemy tej funkcji. |
| F-SYS-UNDO | Warstwa komend z cofaniem/ponawianiem. Dziś tylko `SetPageRepeat`; przycisk „Cofnij” w UI dotyczy tej komendy | — | partial | E4 `commands.py` | PLAN: wszystkie zmiany modelu przechodzą przez komendy; Ctrl+Z/Ctrl+Y w całym oknie; istniejące: `tests/test_commands.py::CommandStackTests`. |
| F-SYS-SETTINGS | Ustawienia użytkownika: marginesy, chwyt, zestaw, kolor interfejsu, ceny, wersja PDF, katalogi (`MyImpozycjoner`) | — | missing | E2 `Impozycjoner.exe.config` | PLAN: zapis i odczyt profilu użytkownika (JSON w katalogu danych aplikacji); wartości domyślne jak w P-21/P-33. |
| F-SYS-SHORTCUTS | Skróty klawiszowe i menu kontekstowe (PKM) oryginału | — | missing | E1 | PLAN: lista skrótów z E1 przypisana do komend; test mapowania skrót → komenda bez Tk. |
| F-SYS-HELP | Podpowiedzi i pomoc kontekstowa przy kontrolkach | — | missing | E1 | PLAN: każda kontrolka z nowej funkcji ma podpowiedź; test, że identyfikatory podpowiedzi istnieją. |
| F-SYS-PROGRESS | Okno postępu „Generowanie plików…” z przerwaniem klawiszem ESC (osobny wariant dla plotera) | F-COR-RENDER | missing | E1 (teksty okien `Form_PasekWykonaj`, `Form_PasekWykonajPloterownica`; REA-04) | PLAN: eksport 22 stron z przerwaniem w połowie nie psuje projektu; stan plików po przerwaniu w oryginale — nieznany (E3). |
| F-SYS-LICENSE | Licencjonowanie, aktywacja, licencja pływająca, sprawdzanie wersji i dostępu do internetu — **poza zakresem** (nie implementujemy) | — | missing | E2 `Impozycjoner.exe.config` | PLAN: poza zakresem — decyzja projektowa, brak testu. |

## Funkcje Studio spoza Feature Map

| ID | Funkcja | Zależności | Status | Dowody | Test akceptacyjny |
|---|---|---|---|---|---|
| F-STU-PAGES | „Eksportuj pojedyncze strony”: jedna strona logiczna na stronę wyniku w rozmiarze netto (+ spad), TrimBox/BleedBox ustawione, bez znaczników; z rolami Pomiń i powtórzeniami | F-COR-RENDER, F-WEJ-SCALE | working† | E4 `engine.export_pages` | `tests/test_engine.py::test_a4_to_a6_22_pages_fit_preserves_page_order_and_vectors`, `tests/test_engine.py::test_024_skip_single_and_overrides` |
| F-STU-PREVIEW | Podgląd rzeczywistego renderu wybranego arkusza (leniwie, tylko żądany arkusz) | F-COR-RENDER | working† | E4 `engine.preview` | `tests/test_engine.py::test_preview` |
| F-STU-LABELS | Etykiety numerów stron przy użytkach (`show_page_labels`) | F-COR-RENDER | partial | E4 `engine.render_side` | PLAN: etykieta „n” w lewym dolnym rogu slotu; wyszukanie tekstu w PDF wynikowym (wymaga PyMuPDF). |
| F-STU-TAXI | Generator naklejek TAXI (TIFF boczne, wektorowe tyły AI/EPS/SVG, paczka ZIP) — niezależny od imposycji | — | working† | E4 `taxi_generator.py`, `taxi_ui.py` | `tests/test_taxi.py::test_number_parser_accepts_batches_and_deduplicates`, `tests/test_taxi.py::test_rear_vector_has_four_objects_and_mirror_transform`, `tests/test_taxi.py::test_build_zip_has_one_complete_set_per_number` |

## Rejestr uruchomień

| Data | Środowisko | Polecenie | Wynik |
|---|---|---|---|
| 2026-10-20 | Linux, Python 3.13, **bez PyMuPDF, pytest i Tk** | `python3 -m unittest tests.test_naming tests.test_commands tests.test_plan_repeats tests.test_plan_baseline tests.test_docs_parity` | 91 testów: **OK** (naming 16, commands 13, plan_repeats 18, plan_baseline 30, docs_parity 14) |
| 2026-10-20 | j.w. | `python3 -I scripts/diff_planning.py --rev HEAD~1 --runs 6000` (HEAD~1 = silnik sprzed Etapu 0) | 2314 identycznych planów + 3686 identycznych błędów walidacji |
| 2026-10-20 | j.w. | `tests/test_plan_baseline.py` uruchomiony na silniku sprzed zmian (`git show b1aec34:engine.py` z atrapą PyMuPDF) | 29 z 30 przeszło; jedyny wynik czerwony to test nowego zachowania (`MissingPyMuPDF`), czyli reszta utrwala zachowanie sprzed zmian |
| 2026-10-20 | j.w. | `python3 scripts/parity.py` | OK |

## Stan weryfikacji (do aktualizacji po każdym etapie)

- Uruchomione i zaliczone w sesji tworzenia: wszystkie testy bez PyMuPDF (wiersze `working` i część `F-AKC-REP`).
- **Nieuruchomione** (wymagają PyMuPDF/pytest/Tk, których nie było w środowisku sesji): 38 testów `tests/test_engine.py`,
  8 testów `tests/test_taxi.py`, 5 testów `tests/test_repeats_pdf.py` oraz ręczna lista kontrolna UI.
  Wiersze `working†` i część `F-AKC-REP` czekają na ten przebieg.
- Polecenie do wykonania na Windows (z repozytorium): `.venv\Scripts\python.exe -m pytest -q`.
