# Instalacja i uruchomienie Baron3x3-Local

Ten dokument jest jedyną obowiązującą ścieżką instalacji. Praca jest podzielona na małe etapy z punktami kontrolnymi, aby po przerwaniu sesji albo wyczerpaniu limitu Codexa można było wznowić dokładnie od ostatniego ukończonego miejsca.

Przed rozpoczęciem zawsze przeczytaj:

1. `AGENTS.md`;
2. `SETUP-STATUS.md`;
3. bieżący etap tego dokumentu;
4. `knowledge/model-routing.md` przed pierwszym płatnym wywołaniem.

## Zasady prowadzenia instalacji

- Wykonuj tylko jeden etap naraz.
- Nie powtarzaj etapu oznaczonego jako ukończony, chyba że zapisany test przestał przechodzić.
- Po każdym etapie natychmiast aktualizuj `SETUP-STATUS.md`.
- Każdy etap kończy się jednoznacznym testem i listą utworzonych lub zmienionych plików.
- Nie przechodź dalej, jeśli test bieżącego etapu nie przeszedł.
- Nie używaj płatnego API przed etapem 4.
- Nie uruchamiaj pełnego montażu przed przejściem testu tekstowego i testu wideo.
- Nie wysyłaj tego samego filmu ponownie, jeśli poprzedni upload albo analiza są nadal dostępne.
- Klucza OpenRoutera nie zapisuj w projekcie, terminalowym logu ani rozmowie.
- Stary folder `/Users/bartoszperz/Desktop/Baron3x3-Reels` jest poza zakresem i nie wolno go modyfikować.

## Etap 0 — bezpieczeństwo i folder projektu

Cel: potwierdzić, że pracujemy wyłącznie w nowym projekcie.

Sprawdź:

```text
/Users/bartoszperz/Desktop/Baron3x3-Local
```

Warunki zaliczenia:

- folder istnieje;
- nazywa się dokładnie `Baron3x3-Local`;
- `Baron3x3-Reels` nie został zmieniony;
- istnieją `input/`, `assets/`, `analysis/`, `output/`, `remotion/`, `scripts/`, `knowledge/`, `examples/` i `instructions/`.

Koszt API: 0 USD.

## Etap 1 — VS Code

Cel: uruchomić bezpłatny edytor niezależny od kredytów Cursora.

Aktualnie wykryta aplikacja:

```text
/Users/bartoszperz/Downloads/Visual Studio Code.app
```

Zalecane miejsce docelowe:

```text
/Applications/Visual Studio Code.app
```

Przeniesienie do `Applications` jest zalecane, ale nie może zostać wykonane bez sprawdzenia, czy w miejscu docelowym nie istnieje druga kopia. Po uruchomieniu VS Code wybierz `File -> Open Folder...` i otwórz `Baron3x3-Local`.

Warunki zaliczenia:

- VS Code uruchamia się natywnie na Apple Silicon;
- otwarty workspace wskazuje na `Baron3x3-Local`;
- terminal VS Code otwiera się w głównym folderze projektu.

Koszt API: 0 USD.

## Etap 2 — Cline

Cel: dodać agenta, który korzysta z własnego dostawcy modeli zamiast kredytów Cursora.

Oficjalny identyfikator rozszerzenia:

```text
saoudrizwan.claude-dev
```

Wersja zweryfikowana podczas instalacji:

```text
4.1.16
```

Warunki zaliczenia:

- Cline jest widoczne w panelu VS Code;
- rozszerzenie uruchamia się bez błędu;
- workspace Cline wskazuje na `Baron3x3-Local`;
- nie jest zainstalowany porzucony Roo Code jako element tego środowiska.

Koszt API: 0 USD.

## Etap 3 — bezpieczna konfiguracja OpenRoutera

Cel: podłączyć jeden klucz do wszystkich płatnych modeli.

W panelu Cline:

1. Otwórz ustawienia dostawcy.
2. Wybierz `OpenRouter` jako `API Provider`.
3. Wklej klucz bezpośrednio w pole `OpenRouter API Key`.
4. Nie wklejaj klucza do czatu Cline, Codexa, pliku `.env`, README ani joba.
5. Ustaw najniższy dostępny limit budżetu testowego po stronie OpenRoutera.
6. Na pierwszy test wybierz tani model z obsługą narzędzi; model produkcyjny zostanie sprawdzony później.

Warunki zaliczenia:

- Cline pokazuje OpenRouter jako aktywnego providera;
- pole klucza jest zapisane jako sekret;
- w projekcie nie pojawił się klucz ani plik zawierający klucz;
- nie wykonano jeszcze płatnego zapytania.

Koszt API: 0 USD.

## Etap 4 — minimalny test tekstowy OpenRoutera

Cel: potwierdzić połączenie, zanim prześlemy jakikolwiek film.

W nowym czacie Cline wpisz:

```text
Przeczytaj AGENTS.md oraz SETUP-STATUS.md. Podaj wyłącznie nazwę bieżącego folderu projektu. Nie zmieniaj plików, nie uruchamiaj terminala i nie renderuj filmu.
```

Limit:

- jedno zapytanie;
- brak automatycznej kontynuacji;
- docelowy koszt poniżej 0,01 USD.

Warunki zaliczenia:

- odpowiedź wskazuje `Baron3x3-Local`;
- brak błędu autoryzacji albo nieobsługiwanego modelu;
- OpenRouter rejestruje pojedyncze zapytanie;
- żaden plik nie został zmieniony.

Po zaliczeniu zapisz w `SETUP-STATUS.md` model, datę i rzeczywisty koszt.

## Etap 5 — lokalne zależności i testy

Cel: potwierdzić, że render i transkrypcja działają bez API.

W głównym folderze projektu:

```bash
npm install
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm run check
```

Następnie wykonaj wyłącznie testy smoke:

- minimalny render Remotion;
- minimalna lokalna transkrypcja Whisper;
- odczyt metadanych testowego MP4.

Warunki zaliczenia:

- Remotion renderuje plik testowy;
- Whisper zwraca tekst i timestampy;
- test nie używa OpenRoutera;
- wyniki znajdują się w `analysis/` lub `output/`.

Koszt API: 0 USD.

## Etap 6 — klient OpenRoutera w pipeline

Cel: przygotować kontrolowaną warstwę API niezależną od interfejsu Cline.

Warstwa musi zapewniać:

- wybór modelu według `knowledge/model-routing.md`;
- ustrukturyzowane odpowiedzi JSON;
- timeouty i maksymalną liczbę prób;
- brak sekretów w logach;
- rejestrowanie tokenów i kosztu;
- limit kosztu na job;
- przerwanie przed przekroczeniem limitu;
- cache lub ponowne użycie analizy, jeśli provider to obsługuje;
- brak dowolnych komend terminalowych generowanych przez model.

Warunki zaliczenia:

- testy jednostkowe działają na atrapach odpowiedzi bez płatnego API;
- błędna odpowiedź modelu nie przechodzi walidacji;
- brak klucza w kodzie i repozytorium.

Koszt API: 0 USD.

## Etap 7 — test klienta na prawdziwym API

Cel: sprawdzić naszą warstwę, a nie tylko czat Cline.

Wykonaj jedno krótkie zapytanie tekstowe wymagające poprawnego JSON. Nie wysyłaj filmu.

Limit:

- jedno żądanie i najwyżej jedna poprawka po błędzie technicznym;
- docelowy koszt poniżej 0,02 USD.

Warunki zaliczenia:

- odpowiedź przechodzi walidację schematu;
- zapisano model, tokeny, koszt i czas;
- sekret nie pojawił się w logu;
- ponowienie nie wystąpiło bez uzasadnionego błędu.

## Etap 8 — minimalny test MP4/MOV

Cel: potwierdzić, że model przez OpenRouter analizuje jednocześnie obraz i dźwięk.

Użyj krótkiego pliku testowego lub krótkiej kopii materiału. Nie zaczynaj od pełnej rolki referencyjnej.

Model ma zwrócić:

- opis obrazu;
- streszczenie wypowiedzi;
- jeden lub więcej timestampów;
- informację o pewności analizy.

Limit:

- jeden upload;
- jedno zapytanie analityczne;
- bez modelu Pro, chyba że model domyślny nie potrafi poprawnie przetworzyć pliku;
- docelowy koszt poniżej 0,10 USD.

Warunki zaliczenia:

- model rozpoznaje treść obrazu i audio;
- odpowiedź zawiera sensowne timestampy;
- rezultat jest zapisany w `analysis/api-smoke/`;
- rzeczywisty koszt został zapisany w `SETUP-STATUS.md`.

## Etap 9 — złoty plan montażu bez renderu finalnego

Cel: sprawdzić jakość decyzji przed wydaniem pieniędzy na pełny proces.

Na jednym reprezentatywnym materiale:

1. wykonaj lokalną transkrypcję;
2. popraw polszczyznę;
3. przeanalizuj materiał modelem wideo;
4. przygotuj plan historii najmocniejszym zaplanowanym modelem;
5. zweryfikuj pełne słowa na granicach;
6. ustaw job jako `ready` dopiero po przejściu walidacji;
7. nie wykonuj jeszcze automatycznych porównań tańszych modeli.

Warunki zaliczenia:

- użytkownik akceptuje historię i plan;
- plan ma poprawne zakresy źródłowe;
- napisy nie zawierają oczywistych błędów języka polskiego;
- zapisano pełny koszt przygotowania planu.

## Etap 10 — render próbny i kontrola

Cel: wykonać pierwszy kontrolowany montaż end-to-end.

1. Renderuj lokalnie w Remotion.
2. Sprawdź technicznie dekodowanie, długość, audio, napisy i granice cięć.
3. Prześlij preview do modelu wideo tylko raz.
4. Wykonaj maksymalnie dwie rundy poprawek.
5. Po drugiej nieudanej poprawce zatrzymaj pipeline i poproś użytkownika o decyzję.

Warunki zaliczenia:

- gotowy render znajduje się w `output/`;
- raport QA znajduje się w `analysis/`;
- użytkownik ocenił wynik;
- całkowity koszt mieści się w limicie joba.

## Etap 11 — test tańszych modeli

Cel: obniżyć koszt dopiero po uzyskaniu jakości referencyjnej.

Wykonaj testy z `knowledge/model-routing.md` na tych samych danych. Nie renderuj wszystkich wariantów, jeśli różnicę można ocenić na planie, korekcie lub analizie.

Warunki zaliczenia:

- wyniki znajdują się w `analysis/evals/`;
- użytkownik wykonał ślepą ocenę tam, gdzie ma ona znaczenie;
- tańszy model został włączony tylko na etapach, na których nie obniżył jakości;
- zaktualizowano routing i budżet.

## Etap 12 — codzienne używanie

Po ukończeniu instalacji użytkownik powinien wykonywać tylko następujące czynności:

1. skopiować MP4/MOV do `input/`;
2. otworzyć `Baron3x3-Local` w VS Code;
3. wpisać polecenie w panelu Cline, nie w terminalu;
4. podać historię, maksymalną długość, tempo, przebitki, napisy i referencje;
5. zaakceptować plan albo preview, jeśli pipeline wymaga decyzji;
6. odebrać wynik z `output/`.

Przykład:

```text
Zmontuj input/nazwa-pliku.mp4 zgodnie z AGENTS.md.

Dodatkowe instrukcje:
- historia: ...
- maksymalna długość: ...
- tempo: ...
- przebitki: ...
- styl napisów: ...
- referencje: ...

Najpierw popraw transkrypcję i pokaż plan. Renderuj dopiero po przejściu walidacji i ustawieniu statusu ready.
```

## Wznowienie po przerwaniu sesji

Nowa sesja ma rozpocząć od polecenia:

```text
Przeczytaj AGENTS.md, INSTALLATION.md i SETUP-STATUS.md. Kontynuuj wyłącznie od pierwszego nieukończonego etapu. Nie powtarzaj testów API oznaczonych jako zaliczone i nie uruchamiaj płatnego wywołania bez sprawdzenia pozostałego budżetu.
```

Jeśli stan zapisany w `SETUP-STATUS.md` jest niezgodny z plikami, najpierw wykonaj kontrolę tylko do odczytu i opisz rozbieżność.
