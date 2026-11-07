# Roadmapa rozbudowy pipeline'u na podstawie rolki referencyjnej

Obowiązuje również `knowledge/editing-precision.md`: standard precyzji Adriana, weryfikacja materiałów, pełna oś montażu, zgodność wersji i obowiązkowa kontrola redakcyjna wyniku. Przed nagraniem czasy pozostają planowane; weryfikację na rzeczywistej osi wykonaj po otrzymaniu MP4.

Ten dokument oddziela funkcje zaakceptowane przez użytkownika od prototypów technicznych. Sam fakt, że renderer potrafi narysować efekt, nie oznacza, że wolno go użyć w montażu.

## Decyzje nadrzędne

- `paper-collage` jest trwale pominięty, dopóki użytkownik jawnie nie zmieni decyzji.
- Pominięcie obejmuje cały zestaw składowy tego kierunku: gazetową ścianę, kolorowe zakładki, papierowe karty zdjęciowe, papierowe szwy/rozdarcia oraz motion-poster lub cutout zaproponowany jako jego kontynuacja.
- Prototypy `paper-reveal` i `paper-collage` nie mogą trafić do propozycji reżysera, aktywnego joba ani renderu.
- Samodzielne przejścia `flash`, `zoom-blur`, subtelne RGB/chromatic aberration, `whip` i miękkie slice'y nie należą do `paper-collage`. Pozostają dostępne, ponieważ zostały wcześniej zaakceptowane jako przejścia między zwykłymi scenami.
- Minimalna długość jednej sceny pozostaje 3 s, nawet jeśli rolka referencyjna miejscami montuje szybciej.
- `split`, `stack` i `cutout` są wyłącznie eksperymentami technicznymi. Nie są częścią zaakceptowanego stylu i nie mogą być wybierane automatycznie bez osobnego przykładu oraz akceptacji użytkownika.

## Status elementów referencji

| Obszar | Status | Co działa / decyzja |
| --- | --- | --- |
| Analiza obrazu, scen i dźwięku referencji | ZROBIONE | Lokalny raport, przekroje klatek, detekcja zmian i analiza widma są zapisane w `analysis/reference/`. |
| Poprawiona polska transkrypcja | ZROBIONE | Lokalny MLX Whisper, korekta słownika i kontrola pełnych słów na granicach. |
| Napisy po 2–3 wyrazy | ZROBIONE | Interpunkcja rozdziela plansze; `. , : ; …` są ukryte, `! ?` pozostają; aktywne słowo ma czytelny zielony kontrast. |
| Trzy poziomy kadrowania i spokojny rytm zoomów | ZROBIONE | Stabilne bloki około 3–7 s; zoom zmienia się semantycznie, nie co chwilę. |
| Premium przejścia między scenami | ZROBIONE | Zoom blur, ograniczona aberracja RGB, whip, flash, light-leak i miękkie slice'y; szkolny czerwono-niebieski glitch jest zablokowany. |
| Animowane statystyki | ZROBIONE | Liczniki, opóźnione jednostki, gradient i impact na karcie `5 PTS / 10 REB`. |
| Dobór B-rollu z biblioteki | ZROBIONE | Automatyczny katalog zdjęć i wideo, trwałe opisy w `assets/MATERIALY.md`, wybór po osobie, zespole, miejscu i akcji. |
| Darmowe stocki | ZROBIONE | Review-first dla Pexels i Wikimedia, kontrola licencji oraz pobranie dopiero po akceptacji. |
| Logika ujawnienia bohatera | ZROBIONE | Najpierw kontekst, potem nazwisko i bohater; po ujawnieniu priorytet `zawodnik > zespół > miasto`. |
| Pełna akcja i kulminacja | ZROBIONE | Klipy są dobierane tak, by wsad, blok lub inna akcja nie urywały się przed finałem. |
| Minimalna długość i brak powtórek | ZROBIONE | Sceny minimum 3 s, domyślnie unikalne assety, ostatnia plansza nie zanika przypadkowo. |
| Plansze zastępujące brak materiału | ZROBIONE | `kinetic-text`, `audio-waveform`, świadomy hold prowadzącego i stock miejsca są wybierane semantycznie. |
| Lokalna i semantyczna kontrola preview | ZROBIONE | 12 lokalnych bramek oraz opcjonalna płatna kontrola znaczenia obrazu z limitem kosztu. |
| Paper reveal / paper collage | POMINIĘTE | Cały moduł i wszystkie jego elementy składowe są poza roadmapą. Aktywny render cofnięto do dwóch zwykłych zdjęć editorial. |
| Split / stack / cutout / motion-poster | EKSPERYMENTALNE — WYŁĄCZONE | Nie używać automatycznie. Nie są uznane za część stylu Baron3x3. |

## Pozostałe etapy

### R1. Referencyjny sound design — ZROBIONE, WARIANT B ZATWIERDZONY

- lokalna analiza referencji wskazała skupienie impulsów przy dużych zmianach scen i transformacjach, a nie przy każdym cięciu;
- osobne role SFX są przypisane semantycznie: `whoosh` do dużej zmiany zoomu/B-rollu, `impact` do statystyki lub najmocniejszej puenty, `click` do waveform/UI;
- działa ducking efektów pod mowę (`speechDucking: 0.72`), obwiednia wejścia/wyjścia i twarde limity głośności: whoosh 0,18, impact 0,24, click 0,12;
- liczba efektów w aktywnym jobie pozostała ograniczona do 5; SFX na każdym cięciu jest zabroniony;
- gotowe są dwa lokalne fragmenty 12,5–21,5 s: `output/r1-a-before.mp4` oraz `output/r1-b-reference-ducked.mp4`;
- pomiar B: −15,32 LUFS-I i −0,94 dBTP; brak przesteru, a różnica głośności całego fragmentu względem A wynosi tylko 0,07 LU;
- użytkownik zatwierdził wariant B; pełny render `output/16-adrian-bogucki-baza-render.mp4` ma 38,059 s, 1080×1920, H.264/AAC i przeszedł 12/12 lokalnych bramek;
- pełne audio ma −15,27 LUFS-I i −0,91 dBTP, więc pozostaje czytelne i bez przesteru;
- obraz nie został zmieniony, dlatego zachowuje ważność wcześniejsza semantyczna kontrola wizualna 94/100 bez ponownego kosztu API.

### R2. Kinetic typography bez kolaży — ZROBIONE, WARIANT B ZATWIERDZONY

- dopracować pojedyncze plansze tezy, liczby i krótkie hasła;
- pozycja musi wynikać z wolnej przestrzeni i nie może zasłaniać twarzy;
- bez gazet, papierowych ramek, wycinanych postaci i wielozdjęciowych kompozycji;
- każda nowa plansza najpierw jako krótki test, potem jawna akceptacja.
- pierwszy test wykorzystuje istniejącą tezę `LIDER / TO NIE TYLKO PUNKTY`: A zachowuje poprzednią planszę, B dodaje lokalny gradient, sekwencyjne wejście słów i wyróżnienie słowa-klucza;
- pliki do oceny: `output/r2-a-before-kinetic.mp4` oraz `output/r2-b-kinetic-editorial.mp4`;
- użytkownik zatwierdził wariant B; został zapisany jako reguła `kinetic-text` w `knowledge/effects.md`;
- pełny render `output/16-adrian-bogucki-baza-render.mp4` ma 38,059 s, 1080×1920, H.264/AAC i przeszedł 12/12 lokalnych bramek;
- istniejąca, wcześniej zaakceptowana karta liczb pozostaje wzorcem dla `stat-card`; R2 nie dodaje zbędnych plansz do każdego zdania.

### R3. Automatyczna mapa uwagi i bezpieczne kadrowanie — ZROBIONE

- lokalny moduł wykrywa twarze, obszary podobne do tekstu, mapę istotności oraz kandydatów okrągłych; twarz głównego bohatera jest wybierana z uwzględnieniem centrum kadru, a nie tylko rozmiaru;
- dla plansz porównuje strefy `top`, `top-left`, `top-right` i `center`, wskazuje wolną przestrzeń i twardo odrzuca kolizję z chronioną twarzą;
- kontroluje dolną strefę napisów oraz kadrowanie każdej przebitki; twarz głównego bohatera dotykająca krawędzi blokuje publikację;
- piłka, obręcz i herb bez pewnego klasyfikatora pozostają uczciwie oznaczone jako kandydaci, a nie automatycznie nazwane obiekty; kulminacja akcji nadal jest zabezpieczana zakresem źródłowym i kontrolą semantyczną;
- render Adriana przeszedł kontrolę 35 klatek: 2/2 plansze bez kolizji, 8/8 przebitek bez ucięcia głównej twarzy, brak twardych błędów;
- finalny pipeline najpierw tworzy `preview-check`, uruchamia lokalną mapę uwagi i kontrolę techniczną, a dopiero po ich zaliczeniu atomowo zastępuje ostatni poprawny render.

### R4. Uczenie stylu z decyzji użytkownika — ZROBIONE

- `knowledge/style-memory.json` przechowuje 13 jawnych decyzji wraz ze statusem, zakresem, powodem, regułami i dowodem: 9 zaakceptowanych, 3 odrzucone i 1 eksperymentalną;
- walidator wymaga `userConfirmed: true`, blokuje automatyczne użycie decyzji odrzuconych i eksperymentalnych oraz nie pozwala po cichu nadpisać istniejącego ID;
- skompilowane `acceptedRules`, `hardBans` i `disabledExperiments` są automatycznie dołączane do pakietu Semantycznego Reżysera;
- schemat reżysera i walidator nie dopuszczają już automatycznego `split`, `stack` ani `cutout`; techniczna dostępność komponentu nie oznacza akceptacji stylu;
- `examples/adrian-bogucki-approved/` jest zamrożonym wzorcem: plan, EDL, transkrypcja, SHA-256 renderu oraz wyniki lokalnego, attention i semantycznego QA 94/100;
- `knowledge/style-evaluation.md` definiuje ślepe porównanie następnej rolki z Adrianem, warunki twarde i ocenę 100-punktową;
- nowe decyzje można dopisywać komendą `style:record`, która wymaga powodu, reguły, dowodu i jawnego potwierdzenia.

### R5. Jedno polecenie w VS Code/Cline — ZROBIONE

- główny workflow Cline to `/baron3x3-montaz.md`; użytkownik podaje w jednym komunikacie nazwę MP4 i zwykłe instrukcje;
- lokalna maszyna stanów `scripts/reel_workflow.py` prowadzi zadanie przez: start, walidację historii, akceptację historii, import reżyserii, akceptację reżyserii i render;
- stan oraz dokładna następna czynność są trwałe w `analysis/NAZWA/workflow/state.json` i `NEXT.md`, więc nowy czat nie zaczyna pracy od początku;
- `reel:start` zachowuje pełny prompt, odświeża bibliotekę, uruchamia lokalnego Whispera lub cache i zatrzymuje się bez renderu;
- plan historii wymaga hooka, łuku, puenty, potwierdzonej korekty polskiego i pełnych słów na każdej granicy; agent nie może sam ustawić `ready`;
- każdy płatny etap Cline ma twardy limit 0,30 USD, zapis kosztu oraz najwyżej jedną poprawkę JSON; sekret nie jest odczytywany przez skrypty;
- po dwóch osobnych akceptacjach i poleceniu „renderuj” istniejący pipeline tworzy `preview-check`, wykonuje attention QA i techniczne QA, a finalny plik zastępuje atomowo;
- rzeczywisty smoke test `pipeline-smoke.mp4` doszedł od jednej komendy do `awaiting-story-approval`, zachował pełne słowa i wykonał 0 płatnych wywołań oraz 0 renderów.

### R6. Test na drugiej rolce

- stan: historia i plan reżyserski dla `MVI_1849.MP4` zatwierdzone, zastosowane i wyrenderowane; finalny plik przeszedł techniczne QA, kontrolę czarnych klatek i kontrolę wzrokową, a teraz oczekuje na ocenę użytkownika;
- materiały HEVC Rext 4:2:2 10-bit są automatycznie konwertowane lokalnie do pionowego H.264 tylko dla zatwierdzonych zakresów; źródło pozostaje nietknięte;
- użyć nowego materiału, a nie dalej stroić jednego filmu;
- sprawdzić generalizację korekty polskiego, doboru B-rollu, rytmu i kosztów;
- porównać wynik z Adrianem według stałej checklisty;
- dopiero po zaliczeniu uznać pipeline za gotowy do codziennego użycia.

## Kolejność od teraz

`R6 ocena finalnego renderu drugiej rolki`

Każdy etap ma najpierw powstać jako krótki, tani test. Pełny render jest wykonywany dopiero po przejściu kontroli i — dla nowego elementu wizualnego — po akceptacji użytkownika.
