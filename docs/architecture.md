# Architektura Impozycjonera Studio

Cel: niezależna implementacja o możliwie wysokiej zgodności funkcjonalnej z Impozycjonerem 4, rozwijana
**na istniejącym kodzie**, bez przepisywania od zera. Ten dokument opisuje stan dzisiejszy, cztery
warstwy docelowe (silnik, komendy, UI, pliki), zasady zależności i decyzje, które już podjęto.

## 1. Zasady

1. **Silnik jest niezależny od UI.** Nic w `engine.py`, `naming.py`, `commands.py` nie importuje Tk.
2. **Planowanie jest czyste.** Co i gdzie trafia na arkusz (`plan_sides`) zależy tylko od modelu i liczby
   stron plików; nie wymaga PyMuPDF. Dzięki temu da się to testować wszędzie i porównywać różnicowo.
3. **Jedna droga zmiany modelu: komendy.** UI nie modyfikuje `Project` bezpośrednio dla nowych funkcji
   (stare akcje — dodaj/usuń/zmień nakład — przejdą na komendy w Etapie 1).
4. **Dane, nie kod.** Presety (falcowanie, plotter, papiery) to pliki danych z własnymi parserami;
   znaczniki rysujemy kodem. Nie kopiujemy zasobów oryginału.
5. **Rozszerzamy addytywnie.** Nowe pola w `.psimp` są opcjonalne; domyślne wartości dają stare zachowanie.
6. **Błędy dla operatora są po polsku**, rzucane jako `ValueError` (silnik) lub `CommandError` (komendy).

## 2. Stan obecny (v0.2.6 + Etap 0)

```
app.py ──────► commands.py ──► engine.py ◄──── preflight.py
  │               │              │  ▲
  │               └─► naming.py  │  └─ (PyMuPDF: render, odczyt PDF)
  ├─► preflight.py               └─► .psimp (ZIP + JSON)
  └─► taxi_ui.py ─► taxi_generator.py        (niezależny moduł TAXI)
```

| Moduł | Rola | Zależności zewnętrzne |
|---|---|---|
| `engine.py` | Model (`Settings`, `Job`, `Project`), geometria siatki, plan arkuszy (jednostronnie, dupleks, broszura), render do PDF, eksport, podgląd, zapis/odczyt `.psimp` | PyMuPDF (opcjonalny przy imporcie), Pillow (podgląd) |
| `naming.py` | Reguły nazw plików (powtórzenia z nazwy) | brak |
| `commands.py` | Komendy modelu z walidacją i cofaniem, `CommandStack`, `execute`, `parse_int_field` | brak (tylko `engine`, `naming`) |
| `preflight.py` | Kontrola PDF przed eksportem | PyMuPDF |
| `app.py` | Okno Tk: lista plików, ustawienia, podgląd, eksport | Tk, Pillow |
| `taxi_*.py` | Generator naklejek TAXI | Pillow, fonttools |
| `scripts/` | `parity.py` (spójność rejestru), `diff_planning.py` (regresja planowania), publikacja | — |

## 3. Warstwy docelowe

### 3.1 Silnik

Podział (bez zmiany interfejsu `from engine import …`; każdy krok chroniony `scripts/diff_planning.py`):

| Część | Odpowiedzialność | PyMuPDF? |
|---|---|---|
| model | `Settings`, `Job`, `Project`, `Slot`, `Placement`, `SheetSide` | nie |
| plan | `geometry`, `plan_sides`, `_duplex_pairs`, `_booklet_sides`; w przyszłości `Layout` | nie |
| render | `_place_pdf`, `render_side`, skalowanie, TrimBox/BleedBox | tak |
| marks | znaczniki rysowane wektorowo (dziś `_draw_marks`) | tak (tylko `draw_line` itp.) |
| io | `open_sources`, `export_pdf`, `export_pages`, `preview` | tak |

**Największa zmiana architektoniczna przed nami:** dziś siatka jest regularna (`columns × rows` z jednym
odstępem poziomym i pionowym). Tabela użytków oryginału (wakaty, obrót per wiersz, spady per strona,
odstępy per użytek) wymaga jawnego modelu `Layout` — listy slotów z własnymi atrybutami — z `geometry()`
jako generatorem układu domyślnego. Wprowadzamy to w Etapie 2 tak, żeby domyślny układ dawał
identyczne sloty jak dziś (test różnicowy).

Kontrakt planowania: `plan_sides(jobs, documents, settings)` przyjmuje `documents` jako odwzorowanie
ścieżka → coś, co ma `len()`; zwraca leniwie `SheetSide`. To pozwala testować kolejność stron bez PDF
(`tests/test_plan_baseline.py`, `tests/test_plan_repeats.py`).

### 3.2 System komend

```
UI (Tk)  ──►  execute(stack, factory) ──►  Command.apply(project)  ──►  Project
                    │                              ▲
                    └─ Outcome(ok, message)        └─ undo(project)
```

| Element | Stan |
|---|---|
| `Command` (`apply`, `undo`, `label`) | gotowe |
| `CommandStack` (`run`, `undo`, `redo`) | gotowe, w UI użyte dla powtórzeń stron |
| `SetPageRepeat` (ręcznie i z nazwy pliku) | gotowe — pierwszy pion |
| `execute` / `Outcome` / `parse_int_field` | gotowe — granica UI: wyjątek walidacji zamienia się w komunikat |
| Komendy dla pozostałych akcji panelu plików (dodaj, usuń, przesuń, nakład, role) | Etap 1 |
| Komendy edycji ustawień i układu | Etapy 1–2 |

Reguły: komenda waliduje w `apply`; błąd nie zmienia projektu i nie trafia do historii; `undo` przywraca
poprzedni stan; komenda nie zna Tk ani PDF. **Znane ograniczenie:** komendy adresują pliki indeksem na liście,
więc UI czyści historię przy dodaniu/usunięciu/przesunięciu pliku i wczytaniu projektu. W Etapie 1 indeks
zastąpi stabilny identyfikator zadania, a czyszczenie stanie się zbędne.

### 3.3 UI

Tkinter (`app.py`), ciemny motyw, trzy kolumny: pliki, podgląd, ustawienia. Zasady dla nowego kodu UI:

- procedura obsługi przycisku jest cienka: odczytuje zaznaczenie, buduje fabrykę komendy, woła `execute`,
  pokazuje `messagebox` przy `Outcome.ok == False`, odświeża listę i podgląd;
- logika, której da się nie robić w Tk, ląduje w `commands.py` albo w czystych funkcjach (`naming.py`);
- UI nie jest testowane automatycznie (brak Tk w CI i w środowisku agenta); zamiast tego jest **ręczna lista
  kontrolna** dla każdej funkcji pionowej (`docs/roadmap.md`, Etap 0) i cienka warstwa, którą testy pokrywają;
- `app.py` rośnie (36 KB); wydzielanie paneli zaplanowano po Etapie 2, gdy układ stabilizuje się.

### 3.4 Warstwa plików

| Obszar | Format | Stan | Zasady |
|---|---|---|---|
| Projekt | `.psimp` = ZIP z `project.json` (`format: psimp`, `version: 1`) | działa | zmiany tylko addytywne; pola opcjonalne zapisywane wyłącznie gdy ≠ domyślne; **do zrobienia:** wczytywanie ignoruje nieznane klucze ustawień (dziś `Settings(**data['settings'])` zawiodłoby na kluczu z nowszej wersji) i zapis atomowy (plik tymczasowy + zamiana) |
| Presety falcowania i plotera | XML kompatybilny w strukturze z `FoldMark.xml` / `Ploter.xml` | brak | własny parser, przyjmuje przecinek **i** kropkę dziesiętną w tym samym pliku, jednostki w punktach PDF (H-08), własne pliki testowe |
| Profil użytkownika | JSON w katalogu danych aplikacji | brak | wartości domyślne z `docs/behavior-spec.md` (P-21, P-33); własne znaczniki w katalogu użytkownika |
| Wejście PDF | PyMuPDF | działa | pliki użytkownika otwierane tylko do odczytu; wyniki zapisywane tam, gdzie wskaże użytkownik; nazwa wyniku ≠ nazwa źródła (F-WEJ-OUTNAME) |
| Nazwy plików | `naming.py` | powtórzenia | czyste funkcje, jeden test na regułę |

## 4. Zasady zależności

- `naming.py` ← nikogo nie importuje.
- `engine.py` (model i plan) ← `naming.py` tylko jeśli potrzeba; **nie importuje** `commands`, `app`, `preflight`.
- `commands.py` ← `engine`, `naming`. Nie importuje Tk ani PyMuPDF.
- `preflight.py` ← `engine`; wymaga PyMuPDF.
- `app.py` ← wszystko powyżej; jedyny moduł z Tk (poza `taxi_ui.py`).
- Testy czystej logiki (`unittest`, bez PyMuPDF) nie mogą dodawać zależności, której nie ma w środowisku agenta.

## 5. Strategia testów

| Poziom | Co sprawdza | Gdzie | Uruchamianie |
|---|---|---|---|
| Jednostkowe, czyste | reguły nazw, komendy, plan arkuszy, kolejność stron, projekt JSON, lint dokumentacji | `tests/test_naming.py`, `test_commands.py`, `test_plan_*.py`, `test_docs_parity.py` | wszędzie: `python -m unittest …` lub `pytest` |
| Charakteryzujące | utrwalają dotychczasowe zachowanie | `tests/test_plan_baseline.py` | j.w. |
| Różnicowe | plany sprzed/po zmianie identyczne | `scripts/diff_planning.py` | j.w. (potrzebny git) |
| Z PDF | render, boxy, preflight, eksport | `tests/test_engine.py`, `tests/test_repeats_pdf.py`, `tests/test_taxi.py` | wymaga PyMuPDF, Pillow, pytest (CI i Windows) |
| UI | przyciski i okna | ręczna lista kontrolna | Windows |
| Wyrocznia E3 | zgodność liczbowa z oryginałem | `tests/oracle/` (Etap 1+, patrz `docs/roadmap.md`) | wymaga próbek z oryginału |

## 6. Decyzje architektoniczne

| ID | Decyzja | Uzasadnienie |
|---|---|---|
| AD-01 | `import pymupdf` jest warunkowy w `engine.py`; funkcje wymagające PDF zgłaszają czytelny błąd (`require_pymupdf`) | Logikę planowania da się testować w środowiskach bez PyMuPDF (agent, szybkie CI); aplikacja nadal wymaga biblioteki z `requirements.txt` |
| AD-02 | `Job.page_repeat` jest osobne od `Job.copies` | `copies` powtarza cały plik (stare projekty); oryginał powtarza **każdą stronę** (P-01). Mieszanie znaczeń zmieniłoby istniejące wyniki |
| AD-03 | Pole `page_repeat` w `.psimp` zapisujemy tylko gdy ≠ 1; wersja formatu pozostaje 1 | Stare projekty nie zmieniają się bajt w bajt; starsze wersje Studio nadal czytają nowe pliki bez powtórzeń |
| AD-04 | Powtórzenia w broszurze są odrzucane, w dupleksie dotyczą par | Nie zgadujemy semantyki bez dowodu (OQ-05, H-06) |
| AD-05 | Znaczniki i paski rysujemy kodem; nie wczytujemy plików z `Base.dat` | Czysta implementacja; brak kopiowania zasobów własnościowych |
| AD-06 | Zgodność liczymy testem na danych (pozycje, kolejność, liczby), nie porównaniem pikseli | Odporność na różnice renderowania; jasne wartości oczekiwane z E1/E3 |
| AD-07 | Licencjonowanie, aktywacja i kontrola wersji oryginału są poza zakresem | Nie dotykamy mechanizmów ochrony; Studio nie wymaga licencji |

## 7. Ryzyka i dług techniczny

- `engine.py` łączy model, plan i render (≈ 650 linii) — podział po Etapie 1, z testem różnicowym.
- Regularna siatka nie obsłuży tabeli użytków (sekcja 3.1).
- Brak dowodów E3: wszystkie wartości liczbowe zgodności są dziś hipotezami lub wynikają z tekstów pomocy.
- Testy z PDF nie zostały uruchomione w sesji tworzenia tej dokumentacji; statusy `working†` czekają na przebieg.
- `app.py` nie ma testów; każda zmiana UI wymaga ręcznej listy kontrolnej.
