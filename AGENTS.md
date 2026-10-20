# AGENTS.md — zasady pracy nad Impozycjonerem Studio

Dla ludzi i agentów. Cel projektu: **niezależna implementacja** o możliwie wysokiej zgodności funkcjonalnej
z Impozycjonerem 4, rozwijana na istniejącym kodzie. Prawda o stanie prac jest w `docs/feature-parity.md`.

| Dokument | Po co |
|---|---|
| `docs/feature-parity.md` | Rejestr funkcji: zależności, status, dowody, test akceptacyjny |
| `docs/behavior-spec.md` | Fakty (P-nn), hipotezy (H-nn), pytania otwarte (OQ-nn), formaty, przypadki brzegowe |
| `docs/architecture.md` | Silnik, komendy, UI, pliki; zasady zależności; decyzje |
| `docs/roadmap.md` | Etapy, priorytety, testy porównawcze, lista kontrolna UI |

## 1. Zasady, które nie podlegają negocjacji

1. **Nie twórz atrap.** Przycisk, opcja ani wiersz w dokumentacji nie może udawać funkcji, której nie ma.
   Funkcja jeszcze nieobsługiwana zgłasza to jawnym błędem (jak powtórzenia w broszurze), a nie ciszą.
2. **Status `verified` tylko po teście, który przeszedł** i ma oczekiwane wartości z dowodu E1 lub E3.
   `working` wymaga wpisu „Przebieg: RRRR-MM-DD” z faktycznego uruchomienia. `working†` znaczy „testy istnieją, nie
   uruchomiono”. Nie podnoś statusu bez uruchomienia testów.
3. **Zachowaj działające funkcje.** Zmiany silnika są addytywne; domyślne wartości dają stare zachowanie;
   nie zmieniaj etykiet ról ani formatu `.psimp` w sposób niezgodny wstecz.
4. **Fakty oddzielaj od hipotez.** Wszystko, czego nie potwierdził tekst lub plik oryginału (E1/E2) ani obserwacja
   (E3), jest hipotezą `H-nn` z testem opisującym przyjęte zachowanie. Brak dowodu zapisz jako `OQ-nn`.
5. **Czysta implementacja.** Nie kopiujemy kodu, grafik, plików z `Base.dat`, ciągów zasobów 1:1 ani nazw prywatnych
   metod oryginału. Opisujemy własnymi słowami, rysujemy znaczniki kodem. Nie obchodzimy zaciemnienia kodu i nie
   dotykamy warstwy licencyjnej. Nazw ani danych licencjobiorcy z instalacji nie umieszczamy w repozytorium.
6. **REA tylko do luk.** Użycie narzędzi analizy oryginału uzasadnia konkretny `OQ-nn`/`H-nn`; wynik i jego
   ograniczenia wpisz do dziennika dowodów (`docs/behavior-spec.md`, sekcja 7). Analiza statyczna to E1/E2, nigdy E3.
7. **Jedna droga zmiany modelu: komendy** (`commands.py`) dla nowych funkcji; UI jest cienkie.

## 2. Komendy

Środowisko Windows (zob. `README.md`): `BOOTSTRAP_WINDOWS.bat` tworzy `.venv` i instaluje zależności, `START_WINDOWS.bat`
uruchamia aplikację, `BUILD_EXE_WINDOWS.bat` buduje plik wykonywalny.

| Zadanie | Polecenie |
|---|---|
| Wszystkie testy (jak CI) | `python -m pytest -q` (Windows: `.venv\Scripts\python.exe -m pytest -q`) |
| Testy bez PyMuPDF/Tk (każde środowisko) | `python -m unittest tests.test_naming tests.test_commands tests.test_plan_repeats tests.test_plan_baseline tests.test_docs_parity` |
| Jeden plik testów | `python -m pytest -q tests/test_repeats_pdf.py` |
| Spójność rejestru zgodności | `python scripts/parity.py` (z `--write` odświeża blok „Podsumowanie”) |
| Regresja planowania względem rewizji | `python scripts/diff_planning.py --rev <rewizja> --runs 6000` |
| Uruchomienie aplikacji | `python app.py` |

Zależności: `pip install -r requirements.txt pytest`. CI (`.github/workflows/tests.yml`) uruchamia `pytest -q`
na Windows i Ubuntu, Python 3.11 i 3.13.

**Środowisko bez PyMuPDF** (np. agent bez dostępu do sieci): uruchom testy bez PyMuPDF z tabeli wyżej, zapisz
wyraźnie, których testów **nie** dało się uruchomić, i nie podnoś statusów zależnych od nich.

## 3. Definicja ukończenia funkcji

Funkcja jest „zrobiona” dopiero, gdy **wszystko** poniżej jest prawdą:

- [ ] Wiersz w `docs/feature-parity.md` istnieje: zależności, dowody (E1–E4), test akceptacyjny.
- [ ] Reguły z dowodów E1/E2 są w `docs/behavior-spec.md` jako P-nn; wszystko inne to H-nn/OQ-nn.
- [ ] Logika jest w warstwie bez UI (silnik, `naming.py`, `commands.py`) z testami jednostkowymi, w tym
      przypadków brzegowych i błędów (zły wpis nie zmienia projektu).
- [ ] Silnik obsługuje funkcję w każdym trybie (jednostronnie, dupleks, broszura) **albo** jawnie odmawia z komunikatem
      i `OQ-nn`.
- [ ] Pole w `.psimp` jest opcjonalne, domyślnie daje stare zachowanie; test odczytu starego pliku.
- [ ] UI: przycisk/pole, komunikat błędu po polsku, odświeżenie podglądu; ręczna lista kontrolna w `docs/roadmap.md`.
- [ ] Test przekrojowy z PDF (wejście → wynik) napisany; uruchomiony tam, gdzie jest PyMuPDF.
- [ ] Pełna regresja: `pytest -q` zielony **albo** wprost zapisane, czego nie uruchomiono; `scripts/diff_planning.py`
      bez różnic; `scripts/parity.py` OK.
- [ ] Status w rejestrze odpowiada faktom (zasada 2); wpis w `CHANGELOG.md`.

## 4. Raportowanie postępu

Po każdym etapie raport (w commicie, PR lub odpowiedzi) zawiera, w tej kolejności:

1. **Co się zmieniło** — funkcje (ID z rejestru), pliki, decyzje; jedno zdanie na pozycję.
2. **Testy** — polecenie, liczba uruchomionych i zaliczonych; osobno **nieuruchomione** i dlaczego.
3. **Regresja** — wynik pełnych testów i `diff_planning.py`; czy wszystkie dotychczasowe funkcje działają.
4. **Zmiana rejestru** — wiersze, których status się zmienił (z → na), oraz nowe H-nn/OQ-nn.
5. **Commit** — skrót i gałąź.
6. **Ryzyka i następny krok** — co blokuje kolejne funkcje (zwykle brak E3).

Nie raportuj „działa” bez przebiegu testu; pisz „napisane, nieuruchomione” albo „uruchomione, zaliczone”.

## 5. Git

- Gałąź robocza na etap: `parity/etap-N-opis`; `main` zmienia się przez merge po zielonej regresji.
- Commit po każdym etapie (osobno kod i dokumentacja, jeśli etap jest duży). Temat po angielsku, w trybie rozkazującym,
  jak w historii repozytorium (`Add …`, `Fix …`); w treści numery funkcji z rejestru.
- Nie zatwierdzaj plików z `.venv`, `__pycache__`, wyników eksportu ani zasobów oryginału.
- Końce linii: `.gitattributes` wymusza LF dla `.py`/`.md`/`.yml` i CRLF dla `.bat`/`.ps1`.

## 6. Mapa repozytorium

| Ścieżka | Zawartość |
|---|---|
| `engine.py` | model, geometria, plan arkuszy, render, eksport, `.psimp` |
| `naming.py`, `commands.py` | czysta logika: nazwy plików; komendy z cofaniem |
| `preflight.py` | kontrola PDF |
| `app.py`, `taxi_ui.py` | interfejs Tk |
| `taxi_generator.py` | generator naklejek TAXI (niezależny moduł) |
| `tests/` | testy; `test_plan_*`, `test_naming`, `test_commands`, `test_docs_parity` działają bez PyMuPDF |
| `scripts/` | `parity.py`, `diff_planning.py`, `publish-github.ps1` |
| `docs/` | dokumenty zgodności i architektury; `examples/` — przykładowe PDF-y i projekty |
