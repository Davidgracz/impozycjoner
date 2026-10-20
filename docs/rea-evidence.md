# Rejestr dowodów REA, inwentarz formularzy i plan pokrycia

Dokument roboczy trybu **REA-first** (zob. `AGENTS.md`, zasada 6). Odpowiada na pytania: czym faktycznie
dysponujemy w analizie oryginału, co z niej wynika dla konkretnych funkcji, czego nie wiemy i co zablokuje dalsze
prace. Reguły zachowania: `docs/behavior-spec.md`; rejestr funkcji: `docs/feature-parity.md`.

Zasada krytyczna: **nie zastępujemy dostępnej analizy domysłami.** Wszystko poniżej jest podpisane poziomem dowodu
(E1–E4) i odnosi się do wpisu REA-nn; co nie jest dowodem, jest oznaczone jako hipoteza (H-nn) albo pytanie (OQ-nn).

## 1. Etap A — środowisko REA (stan: 2026-10-20)

| Element | Stan | Dowód |
|---|---|---|
| Serwer MCP „rea” (agents 6.7.0) | Działa; udostępnia 207 narzędzi (statyczne, mobilne, webowe, natywne, debugger, Frida…) | REA-01 |
| Analiza pakietu zarządzanego (`inspect_managed_artifact`, `inspect_managed_members`, `inspect_managed_native_boundaries`, `inspect_pe_resources`, `inspect_analysis_view`) | **Działa bez dostawcy** — to jedyna ścieżka, z której pochodzą wszystkie dowody IL poniżej | REA-02…REA-10 |
| Dostawca głębokiej analizy natywnej: Ghidra | `not_configured`: brak zmiennej `GHIDRA_INSTALL_DIR` w procesie serwera REA i brak bezwzględnej ścieżki do `java.exe`. **Zainstalowana Ghidra 12.1.4 (katalog podany przez użytkownika) wymaga JDK ≥ 21** (`application.java.min=21`), a na dysku są tylko JDK 16.0.2 i JRE 1.8 | REA-11, REA-12 |
| Ghidra a nasz cel | Provider Windows „P0” przyjmuje wyłącznie natywne PE x86/x64/ARM; **pliki zarządzane są wprost nieobsługiwane**. Wydanie 12.1.4 nie zawiera procesora CIL (`Ghidra/Processors`: brak CIL/.NET; są m.in. Dalvik i JVM). Impozycjoner.exe jest w całości zarządzany, więc Ghidra nie zdekompiluje jego logiki, niezależnie od konfiguracji | REA-11, REA-12 |
| Hopper | Nieobsługiwany na Windows | REA-02 |
| IDA | Nie skonfigurowana | REA-02 |
| Kuna | Tylko ELF/Mach-O | REA-02 |
| Dostawca dekompilacji CIL (dla `import_managed_reconstruction`) | **Brak.** REA nie zawiera dekompilatora CIL; ścieżka wymaga zewnętrznego wyniku (rodzina ILSpy/dnSpy). Patrz decyzja D-1 w sekcji 8 | REA-02 |
| Pseudokod i asembler (`procedure_pseudo_code`, `procedure_assembly`, `xrefs`) dla Impozycjoner.exe | **Niedostępne** (wymagają dostawcy natywnego); `binary_overview` i `list_documents` zwracają `provider_unavailable` | REA-02 |
| Obserwacja uruchomionego oryginału | Narzędzia `observe_native_ui`/`capture_native_ui_scenario` są nastawione na Mach-O i dostępność; nie próbowano. Uruchomienie oryginału na pulpicie użytkownika (computer use) jest możliwe, ale wymaga zgody — decyzja D-2 | — |

Co **mamy** zamiast pseudokodu: dla każdej metody — rozmiar IL, skrót normalizowany, licznik każdego kodu operacji,
**kotwice** (rozgałęzienia, wywołania, pola, stałe z operandem, zmienne `ldloc.s/stloc.s`), regiony wyjątków, krawędzie
wywołań (47 730 w oknie głównym) i dostępy do pól. Z kotwic i długości instrukcji da się odtworzyć brakujące,
jednobajtowe instrukcje (rachunek bajtów, sekcja 4). To wnioskowanie **statyczne i pochodne** (`confidence: derived`):
jest dowodem E2, ale nie zastępuje dekompilacji ani obserwacji E3.

## 2. Proces (etapy A–F) i reguły dowodowe

| Etap | Co robimy | Dowód powstaje w |
|---|---|---|
| A | Test połączenia i dostawców; blokady zapisujemy tu, nie ukrywamy | sekcja 1 |
| B | Inwentarz: formularze (81 nazwanych), zasoby, typy, granice natywne; mapowanie na wiersze rejestru | sekcja 5, `feature-parity.md` |
| C | Dla jednej funkcji naraz: procedura → wywołujący/wywoływane → kotwice → przepływ danych → hipotezy | sekcje 3, 4 |
| D | Implementacja własna, dopiero po C, z testem akceptacyjnym wynikającym z dowodów | `feature-parity.md` |
| E | Porównanie oryginał ↔ rekonstrukcja na tych samych danych (**wymaga E3**) | `roadmap.md` §5 |
| F | Ciągły audyt: ten dokument, rejestr funkcji, lista niewyjaśnionych obszarów (sekcja 6, także `record_unknown` w REA) | cały zestaw dokumentów |

Dopóki nie ma E3, żadna funkcja nie przechodzi do `verified`. Obowiązują ograniczenia czystej implementacji
(`AGENTS.md`, zasada 5): nie odczytujemy zaszyfrowanych literałów, nie ruszamy warstwy licencyjnej, nie kopiujemy
kodu ani nazw prywatnych metod — wskazujemy je numerem tokenu (build-local; ważny tylko dla pliku o podanym skrócie i MVID).

Plik analizowany: `Impozycjoner.exe`, SHA-256 `b34052e33494e36a641f737e7f490690005bcb811bdc12f191094452a25b0d7b`,
MVID `e3756c48-361b-4399-a0e0-fee97e27be87`, x86, 9 877 712 bajtów.

## 3. Rejestr dowodów REA

Wszystkie wpisy: autorytet `shipped-artifact`, pewność `derived`, **analiza statyczna** (nic nie uruchamiano).

| ID | Narzędzie / widok | Co zwróciło | Identyfikator dowodu | Ograniczenia |
|---|---|---|---|---|
| REA-01 | połączenie MCP, lista narzędzi | serwer „rea”, 207 narzędzi | — | to nie jest wynik analizy pliku |
| REA-02 | `binary_session`, `binary_overview`, `list_documents` | stan dostawców (sekcja 1); dwa ostatnie: `provider_unavailable` | wyniki sesji (bez ID dowodu) | blokada środowiska, nie wynik o pliku |
| REA-03 | `inspect_managed_artifact` | tożsamość zestawu, metadane kompletne, 88 zasobów zarządzanych | `ev_19456f59b6ee6af8a5d8591c6d0210da77c888d5c7dae5b10477197e463bb603` (rodzic `ev_26b0a2ec6f033249ea6f00c36cfbd6b5b6eda65eca847cf37d9985ef959a7c4b`) | metadane, nie zachowanie |
| REA-04 | `inspect_pe_resources` + `inspect_analysis_view` (zasoby) | 88 zasobów, w tym 83 pakiety `.resources` z tekstami formularzy (odczytane własnym parserem) | `ev_bbc0179bab68f21a548f497317c8ad1661d9fb6299d98b308f2d89603ce1c88b` | teksty UI to E1; część literałów jest w kodzie, zaszyfrowana |
| REA-05 | `inspect_managed_members`, typ `Form_Powtorzenia` (20 metod) | okno „Ilość powtórzeń”: konstruktor, obsługa trzech przycisków, inicjalizacja kontrolek, stała 1 000 000 | `ev_279e71f22c95c317a3c98fe54de3c238293312a118e2a2c030bf1d762cf8ab1f` (rodzic `ev_5590f41ebce39608310139cd8c2dd7100a14d79bc14f40f2390f185a87e47b84`) | tylko kotwice; początkowe wartości stałych jednobajtowych nieodczytane |
| REA-06 | `inspect_managed_members`, typ `Form_Glowna` | okno główne: 2 057 metod, 815 kontrolek | `ev_42fd7cb25a2f9c96f719e28881782aefb391e31567fba0a22e4f9347f214077b` (rodzic `ev_51b22d403d61891deaee1765179d0f5678ae216eb41786ef862590af6940c8ef`) | budżet reprezentacji wymusza `type_names` i stronicowanie |
| REA-07 | `inspect_analysis_view` → `call_edges` (3 strony po ≤ 16 000) | 47 730 krawędzi wywołań okna głównego; wszystkie strony pobrane | `ev_e6cc198e62c6a944027dd8147a0c92b6dda0dd89c55c8ec3ae4e1b0d6415d00f`, `ev_b04c3838cb8f65f6670e062b5b0a9dc1c48d9977a4f2d1baa660760e3dc97724`, `ev_d774323bd54a4b995854b9ddf3fb7d42a6c3184a01715d28a10431078244bed8` | brak wywołań spoza zbioru typów |
| REA-08 | `inspect_analysis_view` → `methods` (strony 0–400 i 1850–2057) | procedura obsługująca „Powtórzenia” (token 0x06002b40: 1 508 B IL, 447 instrukcji, 290 kotwic, 2 regiony `try/finally`) i procedura reguły z nazwy (0x06002b41: 75 B, 30 instrukcji) | `ev_a305892c26f83943e259ac55a1c54ec4e8d8339001285a045d44ae583c826b19`, `ev_f068c025b34745bb0a5547c7cb963fc90d1df76d31bdb3fe451e5a55dd059e4f` | kotwice, nie pełny strumień IL |
| REA-09 | `inspect_analysis_view` → `user_strings` (Form_Glowna) | jedyny literał ładowany przez `ldstr` w całym oknie głównym to **pusty ciąg**; pozostałe literały są pobierane przez wywołanie funkcji deszyfrującej | `ev_60888c8157c8e164bbf003350d6ef2be4e049f5b04fc05f607d9392dcace8bc1` | zaszyfrowanych literałów nie odczytujemy (zasada 5) |
| REA-10 | `inspect_analysis_view` → `field_accesses`, `member_refs` | pola okna głównego (14 000 dostępów), odwołania do członków | `ev_1dfac925cbd33a2597e4e254aabfd8e579469858aa01b56ca9a1d41a653be402`, `ev_878fa08c403fcf271c7b3b26c7db114ced23026040623e4a664a2cf5b8300dfb` | — |
| REA-11 | odczyt `Ghidra/application.properties`, `support/launch.properties` | wersja 12.1.4, `java.min=21` | plik użytkownika (nie dowód REA) | dotyczy konfiguracji, nie oryginału |
| REA-12 | listing `Ghidra/Processors`, `Extensions` | brak procesora CIL; rozszerzenia: Jython, SymbolicSummaryZ3, Lisa, MachineLearning, BSim, GnuDisassembler | j.w. | — |

## 4. Studium przypadku: „Powtórzenia” (okno `Form_Powtorzenia` + jedyny odbiorca)

To pierwsza funkcja oryginału zbadana od okna po algorytm. Wyniki trafiły do `behavior-spec.md` (P-09, P-14…P-18,
H-13…H-15, OQ-14…OQ-17). Streszczenie własnymi słowami:

1. **Okno** (REA-05, E1+E2): tytuł „Ilość powtórzeń:”, pole liczbowe (maksimum 1 000 000 — stała w kodzie),
   trzy przyciski: OK, „Liczba duplikatów w nazwie pliku −1”, Anuluj. Oba przyciski akceptujące zamykają okno z wynikiem
   „OK”; różni je zapisany **tryb** (0 = liczba z pola, 1 = z nazwy pliku). Podpowiedź drugiego przycisku zawiera regułę
   z P-01/P-02 — **to jest jej właściwe źródło** (wcześniej przypisywaliśmy ją polu z okna autowypełniania).
2. **Odbiorca** (REA-07/08): jedyny wywołujący okno i jedyny wywołujący procedurę „nakład z nazwy” w całym oknie
   głównym. Po „OK” przechodzi po zaznaczonych wierszach aktywnej tabeli (okno ma dwie tabele stron, przełączane
   zaszyfrowanym znacznikiem trybu — OQ-16), aktualizuje wskaźnik postępu i dla każdego wiersza:
   * tryb 0: powtarza pętlę „liczba z pola” razy,
   * tryb 1: odczytuje nazwę pliku z komórki wiersza, odcina rozszerzenie, wylicza N regułą z nazwy i powtarza pętlę **N − 1** razy,
   * każdy obrót pętli wstawia jeden nowy wiersz **bezpośrednio pod wierszem źródłowym** i kopiuje do niego wartości wszystkich komórek,
   * na końcu przywraca kursor i woła aktualizację stanu okna po zmianie tabeli.
3. **Reguła z nazwy** (REA-08): nazwa dzielona po znaku `_` (kod znaku 95); bierze się **ostatni** element; regex
   z pustym zastępnikiem usuwa z niego pewne znaki (wzorzec jest w zaszyfrowanym literale — nie odczytujemy, zgodny z E1
   „usunięcie znaków innych niż cyfry” jest hipotezą roboczą); wynik zamieniany funkcją konwersji VB na liczbę całkowitą;
   **dowolny wyjątek daje 1**.

Rachunek bajtów, na którym opiera się część wniosków (E2 pochodne): kotwice podają przesunięcie IL i długość operandu,
więc luki między nimi to instrukcje jednobajtowe, których rodzaj wynika z liczników kodów operacji.
Przykład (reguła z nazwy, 75 B): wywołanie konwersji kończy się na przesunięciu 48, potem `stloc` i `leave`; w obsłudze
wyjątku brakujące bajty to `dup`, `stloc.1`, `ldc.i4.1`, `stloc.0` — jedyna stała w tym fragmencie to `ldc.i4.1`
(liczniki: `ldc.i4.1` = 3, `ldc.i4.0` = 1, a indeks tablicy zużywa `ldc.i4.0`), czyli wartość zwracana po wyjątku to **1**.
Analogicznie po wywołaniu reguły z nazwy brakują dwa bajty `ldc.i4.1; sub` (trzeci z trzech `sub` w procedurze;
pozostałe dwa liczą kolumny), co zgadza się z etykietą przycisku („−1”, E1). W trybie 0 między odczytem pola a zapisem
granicy pętli **nie ma** żadnej instrukcji — stąd H-13 (liczba kopii = wartość pola).

**Wniosek dla Studio.** Tabela, na której działa oryginał, to „Tabela stron do impozycji” (E1: tekst okna „Nakład”):
wiersz = strona pliku. Powielenie wszystkich wierszy pliku daje kolejność 1,1,…,2,2,… — tak działa nasze F-AKC-REP
(`Job.page_repeat`) w trybie „z nazwy”. Różnice, których nie wolno zatajać: oryginał (a) działa na **zaznaczonych**
wierszach, a nie na całym pliku, (b) w trybie „z pola” zapewne dodaje N kopii (N+1 wystąpień; H-13), a nie N wystąpień,
(c) inaczej traktuje 0, pusty fragment i przekroczenie zakresu (H-14), (d) tworzy fizyczne wiersze, które potem można
niezależnie edytować (F-WEJ-CHGPAGE). Rejestr zawiera te różnice w `F-AKC-REP` i nowym `F-WEJ-ROWDUP`.

## 5. Inwentarz formularzy oryginału → wiersze rejestru

81 nazwanych formularzy (plus 2 pakiety zasobów bez nazwy formularza). Teksty interfejsu są odczytane dla wszystkich
(E1); strukturę IL zbadano dla jednego formularza w całości i dla jednej procedury okna głównego.
Wiersze oznaczone „(nowy)” dodano w tym etapie, bo wcześniej żaden wiersz rejestru ich nie obejmował.

| Formularz (typ) | Tytuł okna | Kontrolek | Wiersz(e) rejestru | Głębokość analizy |
|---|---|---|---|---|
| `DialogForm` | Ostrzeżenie! | 9 | — (ogólny komunikat) | E1 (teksty UI); IL: nie |
| `DialogFormNowaWersja` | Ważna informacja! | 5 | F-SYS-LICENSE (informacja o wersji) | E1 (teksty UI); IL: nie |
| `DodatkoweEAN128` | Generator kodów EAN-128 | 63 | F-NAR-EAN128 | E1 (teksty UI); IL: nie |
| `DodatkoweEAN13` | Generator kodów EAN-13 | 63 | F-NAR-EAN13 | E1 (teksty UI); IL: nie |
| `Dodatkowe_Autoobliczanie` | Kalkulator ilości arkuszy impozycyjnych • Użytków na arkuszu: | 43 | F-AKC-CALC, F-AKC-NWD | E1 (teksty UI); IL: nie |
| `Dodatkowe_Autowypelnianie` | Autowypełnianie arkusza | 23 | F-AKC-AUTOFILL, F-AKC-REP | E1 (teksty UI); IL: nie |
| `Dodatkowe_Code128` | Generator kodów CODE 128 | 48 | F-NAR-CODE128 | E1 (teksty UI); IL: nie |
| `Dodatkowe_EAN13_v1` | Generator kodów EAN-13/EAN-8 | 42 | F-NAR-EAN13 | E1 (teksty UI); IL: nie |
| `Dodatkowe_Falcownica_OK` | Dodaj znaczniki falcowania | 68 | F-NAR-FOLDMARK, F-MRK-FALC | E1 (teksty UI); IL: nie |
| `Dodatkowe_FlattenForm` | Spłaszcz formularze | 10 | F-NAR-FLATTEN | E1 (teksty UI); IL: nie |
| `Dodatkowe_GeneratorPaskow` | Paski kontroli koloru | 46 | F-NAR-STRIPGEN | E1 (teksty UI); IL: nie |
| `Dodatkowe_KonwersjaBitmap` | Zamień bitmapy na pdf | 62 | F-NAR-IMG2PDF | E1 (teksty UI); IL: nie |
| `Dodatkowe_KreatorK` | Kreator kalendarzy | 166 | F-NAR-CALENDAR | E1 (teksty UI); IL: nie |
| `Dodatkowe_NakStary` | Nałóż strony pdf (wersja 3) | 243 | F-NAR-OVERLAY | E1 (teksty UI); IL: nie |
| `Dodatkowe_Nakladacz` | Nałóż strony pdf (wersja 1) | 114 | F-NAR-OVERLAY | E1 (teksty UI); IL: nie |
| `Dodatkowe_Obracacz_OK` | Obróć strony | 24 | F-NAR-ROTATE | E1 (teksty UI); IL: nie |
| `Dodatkowe_Oczkowator2` | Rysuj miejsca oczek na banerach | 131 | F-NAR-EYELETS | E1 (teksty UI); IL: nie |
| `Dodatkowe_Ploterownica` | Dodaj znaczniki dla ploterów tnących | 123 | F-NAR-PLOTTER | E1 (teksty UI); IL: nie |
| `Dodatkowe_Powielacz` | Powiel strony | 17 | F-NAR-DUP | E1 (teksty UI); IL: nie |
| `Dodatkowe_Przekladacz` | Wstaw strony pdf | 17 | F-NAR-INSERT | E1 (teksty UI); IL: nie |
| `Dodatkowe_QR` | Generator kodów QR | 42 | F-NAR-QR | E1 (teksty UI); IL: nie |
| `Dodatkowe_RasteryzatorRGB` | Zamiana stron pdf na formaty rastrowe | 33 | F-NAR-RASTER | E1 (teksty UI); IL: nie |
| `Dodatkowe_RenameName` | Hurtowa zmiana nazw plików typu pdf we wskazanym folderze | 33 | F-NAR-RENAME | E1 (teksty UI); IL: nie |
| `Dodatkowe_Renumerator` | Dodaj znaczniki dla ploterów tnących | 86 | F-NAR-RENUM (!) | E1 (teksty UI); IL: nie |
| `Dodatkowe_Rozcinacz_OK` | Rozetnij strony pdf | 38 | F-NAR-SPLIT | E1 (teksty UI); IL: nie |
| `Dodatkowe_Rozcinacz_RW` | Rozetnij rozkładówki | 20 | brak wiersza (rozkładówki) | E1 (teksty UI); IL: nie |
| `Dodatkowe_Scalacz_OK` | Połącz pliki pdf | 18 | F-NAR-MERGE | E1 (teksty UI); IL: nie |
| `Dodatkowe_Skalowacz_OK` | Skaluj (zmień rozmiar) strony | 39 | F-NAR-SCALE | E1 (teksty UI); IL: nie |
| `Dodatkowe_Spadododawacz_OK` | Dodaj spady | 75 | F-NAR-BLEEDADD | E1 (teksty UI); IL: nie |
| `Dodatkowe_Tasowacz_OK` | Tasuj strony/kartki | 10 | F-NAR-SHUFFLE | E1 (teksty UI); IL: nie |
| `Dodatkowe_Wydzielacz2_OK` | Wydziel zakresy stron | 13 | F-NAR-EXTRACT | E1 (teksty UI); IL: nie |
| `Dodatkowe_Wydzielacz_OK` | Wydziel strony | 17 | F-NAR-EXTRACT | E1 (teksty UI); IL: nie |
| `Dodatkowe_Wypelniacz` | Nałóż strony pdf (wersja 2) | 102 | F-NAR-OVERLAY | E1 (teksty UI); IL: nie |
| `Form_ArkuszStronaDefinicja` | Sposób oznaczania arkusza i strony | 11 | F-AKC-SIGN | E1 (teksty UI); IL: nie |
| `Form_Autoobliczanie` | Kalkulator ilości arkuszy impozycyjnych • Użytków na arkuszu: | 56 | F-AKC-CALC, F-AKC-NWD | E1 (teksty UI); IL: nie |
| `Form_DodajPapier` | Dodaj nowy papier | 16 | F-AKC-PAPERS | E1 (teksty UI); IL: nie |
| `Form_DodajPlik` | Zmień plik/stronę | 16 | F-WEJ-CHGPAGE (nowy) | E1 (teksty UI); IL: nie |
| `Form_DodajPlyte` | Dodaj nowy papier | 18 | F-AKC-PAPERS | E1 (teksty UI); IL: nie |
| `Form_DomyslnaKolejnoscNiepelnych` | Definiowanie kolejności arkuszy niepełnych w składce/bloku: | 24 | F-KSI-SIG | E1 (teksty UI); IL: nie |
| `Form_Glowna` | Impozycjoner | 815 | okno główne: F-AKC-*, F-DUP-*, F-SYS-* | IL: częściowo (REA-06…REA-10; 1 procedura z 2057) |
| `Form_InfoDodatkoweDefinicja` | Informacje dodatkowe: | 9 | F-MRK-OPIS | E1 (teksty UI); IL: nie |
| `Form_KolejnoscNiepelnych` | Określanie położenia arkuszy niepełnych w bloku: | 9 | F-KSI-SIG | E1 (teksty UI); IL: nie |
| `Form_Kolor` | Definiowanie koloru | 41 | F-MRK-DEFAULTS | E1 (teksty UI); IL: nie |
| `Form_KonwersjaBitmap` | Konwersja do formatu pdf | 55 | F-NAR-IMG2PDF | E1 (teksty UI); IL: nie |
| `Form_Koryguj` | Korekta położenia i rozmiaru obszaru netto | 87 | F-WEJ-TRIMFIX | E1 (teksty UI); IL: nie |
| `Form_LaczeniePlikow` | Łączenie plików wynikowych: | 11 | F-WEJ-OUTMERGE (nowy) | E1 (teksty UI); IL: nie |
| `Form_Naklady` | Nakład (ESC = anuluj): | 7 | F-AKC-RUNNAME | E1 (teksty UI); IL: nie |
| `Form_NiepelneSkladki` | Rozkład stron na składkach niekompletnych | 65 | F-KSI-SIG | E1 (teksty UI); IL: nie |
| `Form_NowyRozmiar` | Nowy rozmiar użytka | 26 | F-AKC-ITEM | E1 (teksty UI); IL: nie |
| `Form_OProgramie` | O programie Impozycjoner | 8 | — (okno „O programie”) | E1 (teksty UI); IL: nie |
| `Form_Opcje` | Opcje i ustawienia | 192 | F-SYS-SETTINGS | E1 (teksty UI); IL: nie |
| `Form_Ostrzezenie2` | Ostrzeżenie! | 4 | — (ostrzeżenie) | E1 (teksty UI); IL: nie |
| `Form_OznaczenieRodzajuPracy` | Wybór oznaczenia definicji zestawów elementów dodatkowych | 77 | F-MRK-SETS | E1 (teksty UI); IL: nie |
| `Form_PKlawiszMulti` | Strona i obrót: | 6 | F-AKC-ITEMTABLE | E1 (teksty UI); IL: nie |
| `Form_PapieryWyjscioweKreator` | Definicja wymiarów arkusza podstawowego A1 i B1 | 55 | F-AKC-PAPERS | E1 (teksty UI); IL: nie |
| `Form_PasekWykonaj` | Generowanie plików... | 7 | F-SYS-PROGRESS (nowy) | E1 (teksty UI); IL: nie |
| `Form_PasekWykonajPloterownica` | Generowanie plików... | 5 | F-SYS-PROGRESS (nowy) | E1 (teksty UI); IL: nie |
| `Form_Powtorzenia` | Ilość powtórzeń: | 7 | F-WEJ-ROWDUP (nowy), F-AKC-REP | IL: tak (REA-05, REA-09) |
| `Form_PrzesuniecieLP_na_plycie` | Przesunięcie obrazu impozycji na stronie (-L/+P) [mm]: | 9 | F-AKC-SHIFT | E1 (teksty UI); IL: nie |
| `Form_RozmiescWstepnie` | Obliczanie ekonomicznego rozmieszczenia użytków | 24 | F-AKC-ECON | E1 (teksty UI); IL: nie |
| `Form_WyborKreatora` | Wybór arkusza | 27 | F-AKC-SPLIT | E1 (teksty UI); IL: nie |
| `Form_ZakresArkuszy` | Wybór zakresu arkuszy | 7 | F-AKC-SHEETRNG (nowy) | E1 (teksty UI); IL: nie |
| `Generator_Zmiennej_Tekstowej` | Zamień pliki txt na pdf | 96 | F-NAR-TXT2PDF | E1 (teksty UI); IL: nie |
| `LicenseSelectFormEDU` | Wybór rodzaju licencji | 12 | F-SYS-LICENSE (poza zakresem) | E1 (teksty UI); IL: nie |
| `Ostrzezenie_Symetrycznie` | Ostrzeżenie! | 8 | — (ostrzeżenie; powiązanie z F-AKC-BLEEDWARN niepotwierdzone) | E1 (teksty UI); IL: nie |
| `Show_1poziom_form` | — | 1 | — (pomocniczy, bez napisów) | E1 (teksty UI); IL: nie |
| `SplashScreen1` | — | 7 | — (ekran startowy) | E1 (teksty UI); IL: nie |
| `Znaczniki_BrutPas` | Parametry paserów w polu brutto | 25 | F-MRK-BRUTPAS | E1 (teksty UI); IL: nie |
| `Znaczniki_Brutto` | Parametry znaczników rozmiaru brutto | 26 | F-MRK-BRUTTO | E1 (teksty UI); IL: nie |
| `Znaczniki_Crop` | Dodatkowe przycięcie rozmiaru TrimBox | 13 | F-MRK-CROPBOX | E1 (teksty UI); IL: nie |
| `Znaczniki_Falcowanie` | Znacznik łamania krzyżowego | 18 | F-MRK-FALC | E1 (teksty UI); IL: nie |
| `Znaczniki_Marginesy` | Parametry dodatkowych marginesów | 19 | F-MRK-MARGINS | E1 (teksty UI); IL: nie |
| `Znaczniki_Netto` | Parametry znaczników rozmiaru netto | 39 | F-MRK-NETTO | E1 (teksty UI); IL: nie |
| `Znaczniki_Opis` | Parametry opisu impozycji | 64 | F-MRK-OPIS | E1 (teksty UI); IL: nie |
| `Znaczniki_Pasery` | Parametry paserów | 36 | F-MRK-PASERY | E1 (teksty UI); IL: nie |
| `Znaczniki_Paski` | Parametry pasków kontroli koloru | 56 | F-MRK-PASKI | E1 (teksty UI); IL: nie |
| `Znaczniki_Redukcja` | Redukcja wysunięcia stron przy oprawie zeszytowej | 21 | F-MRK-CREEP | E1 (teksty UI); IL: nie |
| `Znaczniki_Sygnatura` | Sygnatura grzbietowa/krawędziowa | 32 | F-MRK-SYGN | E1 (teksty UI); IL: nie |
| `Znaczniki_UCHIDA` | Znacznik pozycjonujący dla wycinarek | 57 | F-MRK-UCHIDA | E1 (teksty UI); IL: nie |
| `Znaczniki_Wlasny` | Parametry znaczników własnych | 37 | F-MRK-WLASNY | E1 (teksty UI); IL: nie |
| `Znaczniki_Wycinka` | Parametry wycinki środkowej (pionowej i poziomej) | 30 | F-MRK-WYCINKA | E1 (teksty UI); IL: nie |

Uwagi z audytu (kandydaci do weryfikacji, nie fakty):
* `Dodatkowe_Renumerator` ma ten sam tytuł okna co `Dodatkowe_Ploterownica` („Dodaj znaczniki dla ploterów tnących”),
  więc nazwa wiersza `F-NAR-RENUM` („Renumeracja”) może być błędna — **U-05**.
* `Dodatkowe_Rozcinacz_RW` („Rozetnij rozkładówki”) nie ma osobnego wiersza; wiersz `F-NAR-SPLIT` obejmuje tylko „Rozetnij strony pdf” — **U-06**.
* `Form_Opcje` (192 kontrolek) i `Form_Glowna` (815) to największe nieopisane powierzchnie; `F-SYS-SETTINGS` to pojedynczy wiersz — **U-07**.
* `Ostrzezenie_Symetrycznie` i `Form_Ostrzezenie2` są komunikatami o nieustalonym powiązaniu z funkcjami — **U-08**.

## 6. Obszary niewyjaśnione

| ID | Obszar | Czego brakuje | Narzędzie / dowód, który to rozstrzygnie |
|---|---|---|---|
| U-01 | Treść algorytmów (kalkulator nakładów, siatka, autowypełnianie, znaczniki) | ciała metod; kotwice nie wystarczają | dekompilat CIL jako wejście `import_managed_reconstruction` (D-1) albo E3 |
| U-02 | Zaszyfrowane literały (wzorce regex, przełączniki trybów, nazwy plików presetów w kodzie) | wartości | **nie odczytujemy** (zasada 5); wnioski tylko z zachowania (E3) |
| U-03 | Zachowanie „Powtórzeń” poza przypadkiem typowym: H-13, H-14, H-15, OQ-14, OQ-16 | obserwacja | E3: 6 próbek (pole = 1/2/5; nazwy `A_0`, `A_`, `A_99999999999`) |
| U-04 | Implementacja reguły nakładu w kalkulatorze (`Form_Naklady`): czy to ta sama reguła (H-05) | kod odbiorcy poza oknem głównym | `inspect_managed_members` dla typów `Form_Autoobliczanie`/`Dodatkowe_Autoobliczanie` + E3 |
| U-05 | Czy `F-NAR-RENUM` ma poprawną nazwę | porównanie zasobów dwóch formularzy | E1: pełna lista napisów obu okien |
| U-06 | „Rozetnij rozkładówki” bez wiersza | wiersz rejestru | E1 teksty okna `Dodatkowe_Rozcinacz_RW` |
| U-07 | Ustawienia (`Form_Opcje`) i okno główne | rozbicie na funkcje | E1: karty formularzy (sekcja 7, fala 1) |
| U-08 | Komunikaty ostrzegawcze | powiązanie z funkcjami | E1 + referencje do konstruktorów okien w krawędziach wywołań |
| U-09 | Format projektu oryginału (OQ-01) | brak próbki pliku | E3: plik zapisany przez oryginał |
| U-10 | Natywna `DPDFViewerNative_x86.dll` (biblioteka zewnętrzna, 3,9 MB) | — | Ghidra po skonfigurowaniu (JDK 21 + `GHIDRA_INSTALL_DIR`); niski priorytet, to nie jest logika imposycji |

REA ma też własny rejestr niewyjaśnionych obszarów (`record_unknown`/`list_unknowns`); kluczowe luki z tabeli zapisano tam
w tej sesji (zob. raport).

## 7. Plan pełnego pokrycia funkcjonalnego

Zasada: jedna funkcja = jedna pełna pętla A→F. Kolejność wynika z tego, ile dowodów da się zdobyć **bez dekompilatora**.

| Fala | Zakres | Narzędzia REA | Wynik | Blokady |
|---|---|---|---|---|
| 0 (zrobiona) | Środowisko; inwentarz formularzy; „Powtórzenia” od okna do algorytmu | `inspect_managed_*`, `inspect_pe_resources`, `inspect_analysis_view` | sekcje 1–5 | brak E3 |
| 1 | **Karty formularzy** dla 81 okien: wszystkie napisy, podpowiedzi, wartości domyślne i zakresy kontrolek (stałe `Decimal` w konstruktorach), listy wyboru, kolejność kontrolek | `inspect_pe_resources`, kotwice konstruktorów (`InitializeComponent`) | wiersze rejestru z E1/E2 zamiast samych nazw; uzupełnienie braków (U-05…U-08) | stałe jednobajtowe są ukryte w kotwicach (rachunek bajtów daje „jednobajtowa”, nie wartość) |
| 2 | Funkcje o małych procedurach (parsery, walidacje, nazwy wyjściowe: P-04…P-08, F-WEJ-OUTNAME, F-WEJ-META, F-WEJ-PAGECNT, F-NAR-SPLIT) | krawędzie wywołań + kotwice + rachunek bajtów | reguły P-nn z E2 | wymagają zgody na rachunek bajtów jako dowód E2 (tu: tak, z oznaczeniem „pochodne”) |
| 3 | Algorytmy (siatka, kalkulator, autowypełnianie, creep, znaczniki) | ciała IL | dekompilat lub E3 | **D-1/D-2** |
| 4 | Narzędzia dodatkowe (F-NAR-*) | wywołania do DynamicPDF/BCL w krawędziach (nazwy publiczne czytelne) | profil wywołań bibliotecznych per narzędzie | j.w. dla logiki |
| 5 | Weryfikacja zgodności (etap E) | `capture_*`, uruchomienie oryginału | tabele wejście → wynik, status `verified` | D-2 |

Do każdej funkcji przed implementacją: wpis w sekcji 3 (REA-nn), fakty P-nn / hipotezy H-nn / pytania OQ-nn w specyfikacji,
wiersz rejestru z testem akceptacyjnym. Bez tego nie zaczynamy kodu.

## 8. Blokady i decyzje użytkownika

| ID | Decyzja | Skutek |
|---|---|---|
| D-1 | Czy dopuszczamy odczyt IL oryginału dekompilatorem CIL (np. ILSpy/ildasm) jako wejście do `import_managed_reconstruction`? To **nie** odszyfrowuje literałów ani nie dotyka licencji, ale wynik zawiera zaciemnione nazwy i wywołania funkcji deszyfrującej; zasada 5 pozostaje: nie odczytujemy literałów, nie kopiujemy kodu | odblokowuje falę 3 częściowo (struktura algorytmów); bez zgody zostaje E3 |
| D-2 | Czy mogę uruchomić oryginał na komputerze użytkownika (computer use, jawna zgoda w aplikacji) i wykonać próbki z `roadmap.md` §5? | jedyna droga do E3 i statusu `verified` |
| D-3 | Konfiguracja Ghidry: zainstalować JDK 21+, ustawić `GHIDRA_INSTALL_DIR` w środowisku procesu serwera REA (zmienna użytkownika + restart aplikacji) | zadziała tylko dla modułów natywnych (U-10); **nie** dla oryginału |
