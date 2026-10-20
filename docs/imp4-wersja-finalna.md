# Jak działa wersja finalna Impozycjonera 4 — mapa funkcji i porównanie z Studio 0.4.1

Źródło: analiza statyczna instalacji Impozycjonera 4.0.4.0 (REA `inspect_managed_artifact`: zestaw 88 zasobów
programu, metadane kompletne) oraz własny odczyt tekstów okien, podpowiedzi i komunikatów z zasobów
`.resources` (2026-10-20). Program **nie był uruchamiany** — to opis interfejsu i reguł podanych w jego tekstach,
a nie obserwacja działania. Kod jest zaciemniony; ciał metod nie czytano i nie obchodzono zabezpieczeń.
Opis jest własnymi słowami; nazwy przycisków podano tylko jako odnośniki.

Legenda kolumny „Studio 0.4.1”: **jest** · **częściowo** · **brak** · **nowe** (dodane w tej wersji).

## 1. Okno główne i projekt

| Funkcja oryginału | Jak działa (z tekstów) | Studio 0.4.1 |
|---|---|---|
| Dwa moduły na wstędze | „Impozycja akcydensów” i „Impozycja książek i broszur”, każdy z własną tabelą użytków i przyciskiem WYKONAJ IMPOZYCJĘ | częściowo — tylko akcydensy (książki świadomie ukryte) |
| Nowa impozycja / wczytaj / zapisz / zapisz jako | Skróty Ctrl+N, Ctrl+W, Ctrl+S, Shift+Ctrl+S; Ctrl+O otwiera PDF | **nowe**: Ctrl+N, Ctrl+W, Shift+Ctrl+S (Ctrl+O i Ctrl+S już były) |
| Ustawienia | Okno z m.in. metadanymi wyniku (Tytuł/Autor/Temat/Słowa kluczowe, puste = nazwa pliku), dopiskiem `--IMPOZYCJONER`, wersją PDF (domyślnie 1.5), folderem MyImpozycjoner | **nowe**: metadane i dopisek; brak wersji PDF |
| Nazwa pliku wynikowego | Zakaz znaków `# % & * : < > ? / \ { }` i pionowej kreski; nie może być nazwą pliku przetwarzanego | **nowe** |
| Po impozycji otwórz | Przełączniki: otwórz ostatni plik / folder; podgląd JPG (72 ppi); „optymalizacja PDF” (funkcja testowa) | brak |
| Łączenie plików wynikowych | Wynik w jeden plik / w arkusze / każdy osobno i ich kombinacje | brak (zawsze jeden plik) |
| Zapis ustawień wstęgi jako domyślnych | Ustawienia wstęgi pamiętane przy starcie | częściowo — szablony prac |
| Reset do ustawień poinstalacyjnych | Z zachowaniem albo bez własnych papierów, płyt, kolorów, znaczników wycinarek | brak |

## 2. Montaż akcydensów

| Funkcja oryginału | Jak działa | Studio 0.4.1 |
|---|---|---|
| Użytek i obrót | Rozmiar poziomo/pionowo, obrót 0°/90°/180°; „Dodaj +180°” do zajętych i wolnych (z Shift — tylko zajętych), na aktywnym arkuszu albo wszystkich | jest (obrót), częściowo (+180° tylko w edytorze użytków) |
| Tabela K × W | Kolumny/wiersze; własna szerokość kolumn i wysokość wierszy; „pomiń krańcowe prawe/dolne, jeśli puste” | jest (K/W), brak (własne szerokości, pomijanie krańcowych) |
| Spady | Osobno L/P/G/D „dla obrotu 0°”; ostrzeżenie przy różnych spadach na arkuszu | częściowo — jeden spad na stronę |
| Arkusz | Papier, płyta, chwyt (domyślnie 11 mm), margines techniczny „na łapki”, redukcja rozmiaru płyty [pt]; relacja płyta > papier > PDF na podglądzie | częściowo — arkusz i marginesy |
| Rodzaj arkuszy | Jednostronny; dwustronny pełny/niepełny przez markę boczną (MB, work-and-turn) albo czołową (MC, work-and-tumble); falcowane (offset) / niefalcowane (cyfra) | częściowo — jedno-/dwustronnie (krawędź), ekonomiczny |
| Rozmiar wynikowego PDF | Papier / papier + chwyt / pole zadruku / pole zadruku + chwyt / płyta / rozmiar poddruku, każdy z ± ZMB; TrimBox bez zmian lub z korektą, spady 0 lub 3 mm | brak (PDF = arkusz) |
| Wiele arkuszy | Dodaj arkusz po zaznaczonym, usuń arkusz, usuń nieaktywne; arkusze aktywne/nieaktywne (Druk: TAK/NIE) | częściowo — arkusze wynikają z planu |
| Wykonaj impozycję | Wszystkich arkuszy / tylko aktywnego / wszystkich oprócz aktywnego; tryb makiety (podgląd uproszczony) | **nowe**: trzy tryby (pole „Wykonaj:” pod przyciskiem) |
| Kalkulator ilości arkuszy, „Rozmieść ekonomicznie” | Funkcja testowa; rozkład użytków prac o minimalnej liczbie impozycji | częściowo — tryb ekonomiczny (własny algorytm) |
| Kreator podziału arkusza | Podziel na 2×, na 3×DL, usuń podział | brak |
| Autowypełnianie, wypełnienie według wzoru | Z narożnika (LG/LD/PG/PD), centralnie; wzór pierwszego arkusza na kolejne | brak |
| Użytek wieloarkuszowy | Zmiany użytku dotyczą bieżącego arkusza albo wszystkich | brak |
| Przesunięcia P/NP | Przesunięcie środka strony parzystej/nieparzystej, symetrycznie albo niezależnie; „przesunięcie obrazu L<>P” | częściowo — przesunięcie verso X/Y (kalibracja) |
| Impozycja cząstkowa | Bez znaczników / znaczniki 1 mm / 2 mm | brak |
| Wykrojnik zewnętrzny | Plik PDF ze zmontowanym wykrojnikiem pokazywany na podglądzie | brak |

## 3. Tabela stron (menu prawego przycisku)

| Funkcja oryginału | Studio 0.4.1 |
|---|---|
| Zaznacz wszystkie / parzyste / nieparzyste / odwróć zaznaczenie | **nowe** |
| Zaznacz ujęte / nieujęte w impozycji, zaznacz takie same | brak |
| Znajdź pierwszy arkusz z tą stroną | **nowe** |
| Ustaw rozmiar użytka równy rozmiarom zaznaczonej strony | **nowe** (spad bez zmian, brutto idzie za netto) |
| Ustal rozmiar użytka na największą szerokość i wysokość w tabeli | brak |
| Usuń zaznaczone wiersze (strony) | **nowe** jako „Pomiń zaznaczone strony” / „Przywróć” (rola Pomiń; PDF bez zmian) |
| Usuń wszystkie wiersze z pliku | **nowe** w menu (było: Delete) |
| Wstaw wakat przed/po/tutaj, usuń dodane wakaty | brak |
| Wstaw plik przed/po, zamień plik, zamień stronę na inną z pliku | brak |
| Kopiuj / wytnij / wklej, przesuń wiersz wyżej/niżej | częściowo — przesuwanie plików ↑↓ |
| Otwórz plik w czytniku PDF | **nowe** |
| Zapisz zaznaczone wiersze do pliku | brak |

## 4. Znaczniki (14 rodzajów)

W oryginale każdy rodzaj ma okno ustawień, prawy przycisk myszy włącza/wyłącza go, a pojedynczy klawisz jest
skrótem: netto **N**, brutto **B**, pasery **P**, pasery v2 **S**, paski kalibracyjne **K**, wycinka **W**,
marginesy **M**, docięcie TrimBox **T**, falcowanie **F**, opis **O**, własne **U**, wycinarki **C**, sygnatura
grzbietowa **G**, redukcja (creep) **R**. Ustawienia zapisuje się jako domyślne dla bieżącego zestawu (dwa zestawy);
jest też „Wyłącz wszystkie znaczniki”.

Reguły podane w tekstach: wycinka pionowa tylko przy parzystej liczbie kolumn; spady na krawędziach wycinki gdy
szerokość wycinki ≥ 2 × odstęp znaczników od użytków (i tylko dla spadu 0 mm oraz odstępu > 0); docięcie TrimBox to
„włos” z lewej na stronach parzystych i z prawej na nieparzystych; znaczniki falcowania dla arkuszy 8/12/16 stron.

**Studio 0.4.1:** linie cięcia i numery stron. Pozostałe rodzaje — brak.

## 5. Programy dodatkowe

| Program oryginału | Studio 0.4.1 |
|---|---|
| Rozetnij strony PDF (kolumny × wiersze, zakładki) / rozetnij rozkładówki | brak (jest „Rozdziel na pojedyncze strony” — strona = plik) |
| Wydziel strony; wydziel zakresy stron | **nowe** (zakres, każda osobno, plik bez wydzielonych, parzyste/nieparzyste, okładka i wkład, po N stron) |
| Połącz pliki PDF | **nowe** |
| Obróć strony | **nowe** (kąt, zakres, +180° dla parzystych; bez „obrotów z czytnika”) |
| Powiel strony | **nowe** |
| Tasuj strony/kartki | **nowe** (1,2,3,4 → 4,3,2,1 lub 3,4,1,2 — przykłady z oryginału) |
| Generator kodów EAN-13/EAN-8 | **nowe** (wektorowo; oryginał tworzy adnotacje) |
| Generator kodów EAN-13 v2, EAN-128, CODE128, QR | brak |
| Skaluj strony, dodaj spady, przenumeruj strony, wstaw strony, spłaszcz formularze | brak (skalowanie istnieje tylko w montażu) |
| Bitmapy ↔ PDF, rasteryzacja RGB | brak |
| Znaczniki falcowania, znaczniki dla ploterów tnących, oczka banerów | brak |
| Nałóż strony PDF (3 wersje), generator pasków densytometrycznych, kreator kalendarzy | brak |
| Ponumeruj pliki PDF w folderze, zmiana nazw | brak |

## 6. Decyzje własne przy nowych funkcjach (hipotezy — do sprawdzenia na działającym oryginale)

| ID | Decyzja |
|---|---|
| H-13 | Zakres stron: wynik rosnąco, bez powtórzeń; spacje dozwolone; strona spoza dokumentu = błąd. |
| H-14 | Powielanie: każda wskazana strona N razy pod rząd, w miejscu oryginału. |
| H-15 | Dopisek `--XX`: co najmniej 2 cyfry z zerami (3 cyfry od 100 stron). |
| H-16 | Nazwy plików narzędzia „Wydziel”: `--wydzielone`, `--bez_wydzielonych`, `--parzyste`, `--nieparzyste`, `--okladka`, `--wklad`; części `--XX`. |
| H-17 | Okładka = strony 1, 2, przedostatnia i ostatnia. |
| H-18 | Obrót z narzędzia dodaje się do bieżącego obrotu strony. |
| H-19 | Nazwa wyniku porównywana z wejściem bez katalogu i bez wielkości liter. |
| H-20 | Kody EAN jako wektory; błędne wiersze pliku tekstowego pomijane i raportowane. |
| — | „Usuń zaznaczone wiersze” w Studio = rola Pomiń (strona zostaje w pliku i może wrócić). |
| — | „Wykonaj tylko aktywny arkusz” w trybie dwustronnym obejmuje recto i verso tego arkusza. |

## 7. Proponowana kolejność dalszych prac

1. Znaczniki: wycinka (reguła parzystych kolumn), docięcie TrimBox, dodatkowe marginesy — reguły są opisane w tekstach.
2. Rozmiar wynikowego PDF (papier/pole zadruku/płyta, chwyt) — wymaga modelu chwytu i płyty.
3. Wakaty w tabeli stron i wstawianie/zamiana plików.
4. Kody CODE128 i QR (normy publiczne), skalowanie, dodawanie spadów i wstawianie stron jako programy dodatkowe.
5. Do potwierdzenia na działającym oryginale (próbki wejście → wynik): MB/MC, algorytm kalkulatora, autowypełnianie.
