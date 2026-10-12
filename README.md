# Impozycjoner Studio 0.2.2

Rozwijana **wersja alpha** niezależnej, darmowej aplikacji do impozycji PDF, wzorowanej funkcjonalnie na procesach znanych z programu Impozycjoner 4. Wersja 0.2.2 **nie jest jeszcze pełnym zamiennikiem Impozycjonera 4**. Nie zawiera jego kodu, plików ani znaków handlowych.

## Uruchomienie na Windows 10/11

1. Zainstaluj Python 3.11 lub nowszy z python.org (zaznacz *Add Python to PATH*).
2. Rozpakuj ZIP do folderu na komputerze.
3. Kliknij dwukrotnie **`START_WINDOWS.bat`**. Plik automatycznie instaluje zależności i uruchamia aplikację. Przy kolejnych uruchomieniach korzysta z tego samego środowiska.
4. Jeśli pip jest nieobecny w `.venv`, launcher sam spróbuje `ensurepip`, a w razie potrzeby odtworzy środowisko. Skrypt `BOOTSTRAP_WINDOWS.bat` służy do samego przygotowania/naprawy środowiska.
5. Aby wygenerować własny katalog z plikiem .exe uruchom **`BUILD_EXE_WINDOWS.bat`**, potem `dist/Impozycjoner-Studio/Impozycjoner-Studio.exe`.

## Co jest dostępne

- Import wielostronicowych PDF, wiele plików i różne nakłady.
- Arkusze predefiniowane: SRA3/SRA4/A3/A4/B2; dowolny rozmiar w mm.
- Automatyczna siatka z obrotem 0/90° wybierająca więcej użytków.
- Ręcznie ustawiane wymiary, spady, odstępy, marginesy i kolumny/wiersze.
- Aktualizowany podgląd prawdziwego wynikowego PDF.
- Montaż jednostronny; dwustronny: kolejne 2 strony źródła traktowane jako przód i tył użytku, obracanie po krótkiej/długiej krawędzi arkusza.
- Podstawowa broszura zeszytowa 2-up, oprawa zeszytowa; automatyczne puste strony do wielokrotności czterech.
- Linie cięcia (wektorowe), numery stron; wektorowy wynikowy PDF bez rasteryzacji zawartości.
- **Jawne skalowanie wielostronicowego PDF do innego formatu netto**: Bez skalowania (blokada niezgodnych formatów), Dopasuj (proporcjonalnie, cała treść, możliwe marginesy) lub Wypełnij (proporcjonalnie, przycięcie). Brak rozciągania w trybach skalowania.
- Presety formatów docelowych: A6 pion/poziom, A5 pion/poziom i A4 pion/poziom oraz wymiary własne.
- **Eksportuj pojedyncze strony**: tworzy nowy wielostronicowy PDF, w którym każda strona ma docelowy format netto (albo format netto + skonfigurowany spad). Alternatywnie można skalować bezpośrednio podczas montażu na arkuszu.
- Poprawna interpretacja MediaBox z przesuniętym początkiem (również przy CropBox/TrimBox/BleedBox) — bez fałszywego błędu TRIMBOX; ten sam układ jest stosowany przy eksporcie.
- **Preflight PDF**: kontrola wymiarów TrimBox każdej strony, dostępnego fizycznego spadu, uproszczone DPI obrazów i fontów, TXT/JSON; błędy geometrii blokują eksport, a ostrzeżenia wymagają potwierdzenia.
- Poprawione umieszczanie spadów przy obrocie użytków 90/180/270° i źródłowych stron PDF z /Rotate; źródłowego PDF nie rozciągamy automatycznie, jeśli format nie pasuje.
- Zapis/odczyt projektu `.psimp` (archiwum ZIP + JSON, względne ścieżki PDF, oryginalne pliki nie są kopiowane do projektu).

## Ograniczenia — ważne w druku produkcyjnym

- Poprawka 0.2.1 została sprawdzona na syntetycznych PDF z przesuniętym MediaBox. Przed nakładem zawsze zweryfikuj plik kontrolny, zwłaszcza przy nietypowych eksportach DTP.

- Przed produkcją **sprawdź kontrolny PDF i wydruk dwustronny**, szczególnie orientację recto/verso na konkretnej maszynie.
- W tej wersji nie ma jeszcze gang-run, impozycji wykrojników, offsetowych paserów, pełnego preflightu CMYK/spot/ICC/PDF-X, creep ani kompletnych schematów falcowania.
- W montażu wielostronicowego PDF jedna strona to jeden użytek. W duplex kolejne pary stron w danym PDF to przód/tył, bez przechodzenia par pomiędzy różnymi plikami.
- W trybie broszury jest tylko jeden plik wejściowy, a ustawiona szerokość/wysokość użytku dotyczy **pojedynczej strony po złożeniu**. To prosty układ 2-up, bez korekcji creep.
- Program **nie tworzy nowych spadów z powietrza**. Jeśli źródło PDF nie ma fizycznego obrazu poza TrimBox, obszar spadu pozostanie pusty. Kontrola sprawdza dostępny obszar w geometrii pliku, **nie** potwierdza, że grafika faktycznie wypełnia spad.
- Preflight jest **uproszczony**: wykrywa część potencjalnie nieosadzonych fontów i niskie DPI rastrowe, ale nie zastępuje profesjonalnej inspekcji separacji, overprintu czy PDF/X. Próg DPI weryfikuje obrazki heurystycznie, nie analizuje całego wyglądu strony.
- Przy ustawieniu **Bez skalowania** rozmiar TrimBox źródłowego PDF musi odpowiadać użytkowi (tolerancja 0,5 mm). Przy różnych rozmiarach wyświetlany jest błąd. W trybach **Dopasuj / Wypełnij** operator jawnie decyduje o przeskalowaniu.
- Znaczniki przy małych odstępach mogą wchodzić w obszar innych użytków, dlatego przed produkcją wykonaj kontrolę podglądu.
- Przy dużych nakładach eksport odbywa się w głównym wątku GUI i może chwilowo blokować okno.

## Przykład: 22-stronicowy A4 do A6

1. Wczytaj wielostronicowy PDF A4 (22 strony). Nie trzeba dzielić go na osobne pliki.
2. W zakładce **UŻYTEK / STRONA** wybierz **A6 105 × 148 mm**.
3. Wybierz **Skalowanie PDF → Dopasuj**. W tym przykładzie stosowana skala ≈49,83%; treść zostaje w całości, na bokach mogą zostać białe marginesy ok. 0,18 mm. Alternatywa **Wypełnij** to skala 50% i przycięcie po 0,25 mm od góry/dołu.
4. Zaznacz spad **0 mm**, jeżeli chcesz otrzymać zwykłe strony A6 bez dodatkowych milimetrów. Jeśli druk wymaga spadów, ustaw ich wartość i zweryfikuj je w preflight: skalowanie nie potrafi utworzyć brakującego obrazu.
5. Kliknij **Preflight PDF**, a następnie **Eksportuj pojedyncze strony** — otrzymasz PDF A6 z 22 kolejnymi stronami, bez impozycji. Możesz też kliknąć **Eksportuj PDF**, żeby wykonać montaż na arkuszu SRA3/SRA4.

Wynikowy tekst/wektory nie są rasteryzowane. Fotografie zachowują istniejącą liczbę pikseli, więc zmienia się tylko ich fizyczna wielkość i efektywna rozdzielczość w druku. Tryb **Wypełnij** może usuwać treść przy samych krawędziach — przed nakładem sprawdź podgląd PDF.

## Testy

```powershell
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest -q
```

## Architektura

- `engine.py` — geometria arkusza, plan stron, osadzanie stron PDF i eksport, format projektów.
- `preflight.py` — podstawowa diagnostyka PDF i raporty TXT/JSON.
- `app.py` — interfejs desktopowy (Tkinter + Pillow).
- `tests/` — automatyczne testy regresyjne PDF.
- `ROADMAP.md` — moduły planowane do pełnej parytetowej funkcjonalności.

## ArtCraft

Inspiracja dotyczy podejścia: lokalny program, otwarty kod, brak abonamentu i profesjonalny interfejs. **Obecna wersja jest napisana w Pythonie**, nie w Rust. Port na Rust/egui jest możliwy po ustabilizowaniu algorytmów, ale nie został tu zrobiony.

## GitHub — osobny projekt

Docelowe repozytorium: https://github.com/Davidgracz/impozycjoner

Aby opublikować lokalne zmiany ze swojego Windowsa, uruchom **`GITHUB_PUBLISH_WINDOWS.bat`**. Skrypt:

1. Sprawdza Git i instaluje (jeśli potrzeba) GitHub CLI przez `winget`.
2. Prosi o zalogowanie do GitHub w przeglądarce (jeżeli nie jesteś zalogowany).
3. Tworzy lokalne repozytorium i pierwszy commit.
4. Rozpoznaje istniejące repozytorium `Davidgracz/impozycjoner`.
5. Przesyła lokalne zmiany na gałąź `main` tylko gdy historia GitHuba pozwala na bezpieczny push (bez `--force`).

Jeśli repozytorium już istnieje, skrypt próbuje zwykły `git push`, **bez `--force`**.

Po pierwszej publikacji zwykły workflow to `git add .`, `git commit -m "Short English change note"`, `git push`. GitHub Actions uruchamia testy na Windows i Linux dla Python 3.11/3.13.

**Prywatność:** w repozytorium nie ma lokalnego `.venv`, danych logowania ani cudzych plików klientów. Przykładowe PDF-y są sztuczne. Prawa/licencję otwartoźródłową ustalimy przed ewentualnym udostępnieniem repo publicznie.

![Podgląd interfejsu v0.1.0](docs/interface-v0.1.0.png)
