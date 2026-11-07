# Baron3x3 Studio

Lokalny montaż z planem JSON, trzema akceptacjami i Remotion. Nowa ścieżka: [instrukcja Studio](docs/STUDIO.md). Kod rozwijamy w istniejącym folderze Baron3x3-Local.

```sh
npm run baron -- status projekty/lorenzo
```

[Stan wdrożenia](docs/WDROZENIE.md) · [Kontrakt planu](schemas/plan.schema.json) · [Skill](.claude/skills/baron3x3-montaz/SKILL.md)

Niżej pozostaje dokumentacja dotychczasowej wersji. Płatne API i Resolve nie są częścią nowego procesu.

---

# Baron3x3-Local

Lokalne środowisko do montażu rolek: VS Code + Cline + OpenRouter + Remotion + MLX Whisper.

- VS Code jest bezpłatnym edytorem.
- Cline jest agentem pracującym na plikach projektu i uruchamiającym pipeline.
- OpenRouter udostępnia płatne modele przez jeden klucz API.
- Whisper, analiza techniczna i render Remotion działają lokalnie na Macu.
- Cursor, Roo Code, Aider i OpenCode nie są wymagane.

## Instalacja na Macu

Kompletna instalacja, testy etapowe i procedura wznowienia znajdują się w [INSTALLATION.md](INSTALLATION.md). Aktualny postęp jest zapisywany w [SETUP-STATUS.md](SETUP-STATUS.md). Nie pomijaj tych plików i nie powtarzaj zaliczonych płatnych testów.

### 1. VS Code

Projekt wymaga Visual Studio Code dla Apple Silicon. Jeżeli aplikacja znajduje się w `Downloads`, zalecane jest przeniesienie jej do `Applications`, aby aktualizacje i skróty działały przewidywalnie.

W VS Code wybierz `File -> Open Folder...` i otwórz:

```text
/Users/bartoszperz/Desktop/Baron3x3-Local
```

### 2. Cline

Oficjalne rozszerzenie Cline jest zainstalowane w VS Code pod identyfikatorem:

```text
saoudrizwan.claude-dev
```

Jeżeli trzeba je ponownie zainstalować, otwórz panel Extensions w VS Code, wyszukaj `Cline` i wybierz rozszerzenie wydawcy Cline.

Nie instaluj Roo Code. Projekt został zakończony i nie jest elementem tego środowiska.

### 3. OpenRouter

W ustawieniach Cline:

1. Ustaw `API Provider` na `OpenRouter`.
2. Wklej klucz bezpośrednio do bezpiecznego pola `OpenRouter API Key`.
3. Nie zapisuj klucza w README, `AGENTS.md`, promptach, plikach jobów ani repozytorium.
4. Do pierwszego testu wybierz tani model obsługujący narzędzia.
5. Modele produkcyjne zostaną przypisane do etapów pipeline'u po przejściu testów jakości.

Minimalny test połączenia w nowym czacie Cline:

```text
Przeczytaj AGENTS.md i podaj wyłącznie nazwę bieżącego folderu projektu. Nie zmieniaj plików i nie uruchamiaj renderu.
```

Test jest poprawny, jeśli Cline odczyta projekt `Baron3x3-Local`, nie zgłosi błędu OpenRoutera i nie wykona niezamówionych operacji.

### 4. Zależności lokalne

W terminalu VS Code, w głównym folderze projektu:

```bash
npm install
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm run check
```

`npm run check` musi przejść przed pierwszym montażem. Klucz OpenRoutera nie jest potrzebny do lokalnego testu Remotion i Whispera.

## Montaż pliku w Cline

1. Włóż główny MP4 do `input/`.
2. Zdjęcia i filmy na przebitki włóż do `assets/library/` albo skonfiguruj ich istniejący folder w `assets/sources.json`.
3. Otwórz nowy czat Cline dla folderu `Baron3x3-Local`.
4. Wpisz jedno polecenie workflow wraz z nazwą pliku i instrukcjami, np.:

```text
/baron3x3-montaz.md
Plik: nazwa-pliku.mp4
Wybierz historię o przywództwie, maksymalnie 40 sekund. Dużo tematycznych
przebitek, ale nie zdradzaj bohatera przed wypowiedzeniem nazwiska.
```

Cline uruchomi lokalny workflow, który zapisze instrukcje, odświeży bibliotekę, wykona lub wykorzysta transkrypcję Whispera, zastosuje pamięć stylu i przygotuje historię. Następnie zatrzyma się na akceptacji. Po każdej odpowiedzi użytkownika stan jest odczytywany z `analysis/nazwa-pliku/workflow/state.json`, więc można bezpiecznie kontynuować także w nowym czacie.

Workflow ma obowiązkowe punkty zatrzymania:

1. akceptacja historii i cięć;
2. akceptacja reżyserii obrazu i dźwięku;
3. osobne polecenie „renderuj”.

Finalny render najpierw powstaje jako `preview-check`. Dopiero po zaliczeniu attention QA i technicznego QA zastępuje poprzedni poprawny MP4. Jeden płatny etap Cline ma limit 0,30 USD i nie może automatycznie ponawiać się więcej niż raz po błędzie JSON.

Nie wklejaj promptu montażowego do zwykłego terminala. Polecenie w języku naturalnym wpisuje się w panelu Cline.

Ręczny odpowiednik pierwszego kroku:

```bash
npm run reel:start -- nazwa-pliku.mp4 --instructions-file instrukcje.md
```

Stan można sprawdzić bez żadnego API:

```bash
npm run reel:status -- nazwa-pliku.mp4
```

Nie uruchamiaj ręcznie kolejnego kroku, jeśli `nextAction` nadal wymaga akceptacji użytkownika.

## Dobieranie przebitek

Po przygotowaniu historii i planu cięć utwórz lokalny raport propozycji:

```bash
npm run broll:plan -- nazwa-pliku.mp4
```

Czytelny raport znajduje się w `analysis/nazwa-pliku/broll-plan.md`. Zawiera
podział narracji, najlepiej pasujące materiały, wybrane fragmenty źródłowe,
uzasadnienia, brakujące ujęcia i procent pokrycia. Utworzenie raportu nie zmienia
planu montażu i nie uruchamia API.

Po zaakceptowaniu raportu:

```bash
npm run broll:apply -- nazwa-pliku.mp4 --approved
```

Jawna flaga `--approved` chroni przed przypadkowym zastosowaniem propozycji.
Komenda zachowuje ręcznie ustawione przebitki i nadal nie uruchamia renderu.

## Darmowe stocki

Brakujące ujęcia miast, aren i neutralnego kontekstu można wyszukiwać w
Wikimedia Commons oraz Pexels. Pełna instrukcja znajduje się w
`docs/STOCK.md`.

```bash
npm run stock:status
npm run stock:search -- "Warsaw skyline" --provider commons --type image
```

Wyszukiwanie tworzy raport i niczego automatycznie nie pobiera. Pobranie
wymaga wskazania konkretnego wyniku oraz flagi `--approved`. Każdy pobrany
materiał zachowuje źródło, autora, licencję, podpis i sumę kontrolną w
`assets/STOCK-LICENSES.md`. Pexels wymaga darmowego klucza API zapisanego poza
projektem; Wikimedia Commons działa bez klucza.

## Podgląd w VS Code

```bash
npm run studio
```

Studio pokazuje kompozycję `BaronReel`. Aktywny job znajduje się w `remotion/public/job.json`.

## Biblioteka efektów

Plan montażu może sterować sześcioma lokalnymi efektami wizualnymi przez `effectCues`: `flash`, `whip`, `light-leak`, `film-frame`, `rec` i `stat-card`. Pole `soundEffects` obsługuje własne lokalne dźwięki `whoosh`, `impact` i `click`. Format, limity i zasady użycia znajdują się w `knowledge/effects.md` oraz `knowledge/audio.md`.

Techniczny podgląd całej biblioteki, niezależny od bieżącej rolki:

```bash
npm run test:effects
```

Wynik trafia do `output/effects-smoke.mp4`. Ta komenda nie używa API i nie zmienia planu żadnej rolki.

## Semantyczny Reżyser Beatów w Cline

Reżyser łączy zatwierdzoną historię, transkrypcję, bibliotekę materiałów, klatki kontrolne i DNA rolki referencyjnej. Właściwym interfejsem jest Cline z zapisanym lokalnie kluczem OpenRouter. Skrypty projektu nigdy nie proszą o drugi egzemplarz tego klucza.

```bash
npm run director:prepare -- nazwa-pliku.mp4
```

Następnie w czacie Cline uruchom workflow `/baron3x3-rezyser.md` i podaj nazwę pliku. Cline korzysta z własnej konfiguracji OpenRouter. Zapisany wynik przechodzi lokalną walidację:

```bash
npm run director:import-cline -- nazwa-pliku.mp4
```

Powstaje `analysis/nazwa-pliku/director/proposal.md`. Walidator blokuje nieistniejący `assetId`, przesunięte granice beatu i niezaakceptowane efekty.

Po przeczytaniu raportu:

```bash
npm run director:apply -- nazwa-pliku.mp4 --approved
```

Zastosowanie nie korzysta z API i nie renderuje filmu. Klucz pozostaje wyłącznie w ustawieniach Cline.

## Modele Whisper

Domyślny model produkcyjny to lokalny `mlx-community/whisper-large-v3-turbo`. Model tiny pozostaje wyłącznie testem technicznym.

```bash
npm run pipeline -- nazwa-pliku.mp4 --force-transcribe
```

Pierwsze użycie danego modelu pobiera go lokalnie; kolejne korzystają z pamięci podręcznej.

## Kontrola kosztów API

- Szczegółowy podział modeli, zasady eskalacji i kryteria jakości znajdują się w `knowledge/model-routing.md` i są obowiązkowe dla agenta.
- Render, FFmpeg, Whisper i walidacja techniczna mają działać lokalnie bez opłat API.
- Film wysyłaj do modelu wideo tylko wtedy, gdy wymaga tego analiza treści lub referencji.
- Ten sam przesłany materiał powinien być ponownie używany zamiast wysyłany przy każdej poprawce.
- Tani model może zastąpić droższy dopiero po porównaniu jakości na tych samych materiałach.
- Jedno zadanie może wykonać maksymalnie dwie automatyczne rundy poprawek renderu.
- Pipeline ma raportować koszt każdego etapu i zatrzymywać się po osiągnięciu ustawionego limitu.

Obecna wersja projektu ma działający lokalny Whisper, Remotion, kontrolowany klient OpenRoutera oraz lokalny katalog zdjęć i wideo. Katalog nie wykonuje płatnej analizy treści: opisuje technicznie pliki i łączy je z notatkami użytkownika. Automatyczne rozpoznawanie konkretnych akcji wewnątrz długich nagrań jest osobnym, kolejnym etapem.
