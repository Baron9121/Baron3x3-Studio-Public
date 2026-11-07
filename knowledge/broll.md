# B-roll

## Reguły startowe

- B-roll ma wzmacniać konkretną informację, nie zasłaniać mówcy bez powodu.
- Zapisuj źródło i prawa do każdego assetu.
- Brak B-rollu jest lepszy niż luźno powiązany materiał.
- Przed planowaniem przeczytaj aktualny `assets/MATERIALY.md`.
- Pierwszeństwo mają pasujące materiały użytkownika: wideo, następnie zdjęcia.
- Wybieraj materiał po osobie, zespole, miejscu, typie akcji i kontekście zdania; zgodność samego nazwiska w nazwie pliku nie wystarcza do wyboru konkretnego fragmentu.
- Materiał w planie wskazuj przez `assetId`, aby działał także wtedy, gdy oryginał znajduje się w skonfigurowanym folderze zewnętrznym.
- Zdjęcie poziome wymaga świadomego `objectPosition`; nie przycinaj twarzy, herbu ani piłki.
- Darmowy stock może uzupełniać miasta, stadiony i neutralny kontekst dopiero wtedy, gdy katalog użytkownika nie zawiera lepszego materiału.
- Herbów klubów i federacji nie pobieraj automatycznie ze stocków. Używaj plików dostarczonych przez użytkownika albo oficjalnych materiałów prasowych z potwierdzonym prawem użycia.
- Licencja stockowa nie oznacza automatycznie prawa do sugerowania poparcia przez widoczną osobę, klub lub markę.
- Liczba przebitek nie jest stała. Wynika z liczby mocnych, semantycznie pasujących materiałów oraz rytmu konkretnej historii.
- Nie używaj wszystkich dostępnych plików tylko dlatego, że istnieją. Każdy materiał musi wnieść nową informację, emocję, dowód albo zmianę miejsca/czasu.
- Gdy biblioteka zawiera kilka ujęć tej samej osoby, dobieraj je po funkcji: portret do przedstawienia, akcję do konkretnego zachowania, emocję do reakcji, grafikę klubową do informacji o klubie.
- Preferuj serię pojedynczych pełnoekranowych przebitek zgodnych z referencją. Nie twórz kolażu, splitu ani warstwowej planszy, jeśli nie wynika to z jawnie zaakceptowanego przykładu.
- Materiał może pozostać niewykorzystany. Jakość i zgodność są ważniejsze niż procent wykorzystania biblioteki.
- Nie ujawniaj bohatera zdjęciem ani wideo przed pierwszym wypowiedzeniem jego imienia i nazwiska. Hook ma budować ciekawość. Wyjątek: imię i nazwisko padają od razu na początku.
- Jeśli przed ujawnieniem bohatera narrator wskazuje miejsce, wydarzenie lub miasto, pokaż najpierw odpowiedni stock albo neutralny kontekst tego miejsca. Dla zdania o Challengerze w Bordeaux właściwym pierwszym wyborem jest stock Bordeaux.
- Od chwili wypowiedzenia nazwiska obowiązuje hierarchia dopasowania: `bohater > jego zespół > miasto`. Materiał pokazujący właściwego zawodnika może pochodzić z innego turnieju lub miasta, jeżeli nie fałszuje opowiadanej akcji. Przykład: akcja Adriana Boguckiego z Wiednia może ilustrować wypowiedź o Boguckim z Bordeaux.
- Nie podpisuj przebitki jako konkretnej akcji z Bordeaux, jeśli pochodzi z Wiednia. Służy ona wtedy jako ilustracja bohatera, nie dowód miejsca ani meczu.

## Lokalny B-roll Planner

- `npm run broll:plan -- NAZWA.mp4` dzieli zaakceptowaną narrację na fragmenty i tworzy raport `analysis/NAZWA/broll-plan.md`.
- Planner punktuje zgodność osoby, zespołu, rywala, miejsca, wydarzenia, rodzaju akcji i opisu zastosowania.
- Samo luźne słowo, ogólny tag albo nazwa zespołu bez zgodności kontekstu nie wystarczają do automatycznego wyboru.
- Planner korzysta z opisanych przedziałów `Najlepsze fragmenty` i nie ustawia przebitki dłuższej niż dostępny fragment źródłowy.
- Istniejące ręczne przebitki mają pierwszeństwo i nie są nadpisywane.
- Raport jest propozycją. Dopiero jawnie zatwierdzone `npm run broll:apply -- NAZWA.mp4 --approved` wpisuje materiały do `overlays`.
- Zastosowanie planera, walidacja i render są lokalne i kosztują 0 USD.

## Visual Fallback Planner

- Brak materiału uruchamia drabinę: pasujący materiał użytkownika → zatwierdzony stock miejsca → uzasadniona animacja → kontrolowane utrzymanie prowadzącego → świadomy brak warstwy.
- `stock-needed` powstaje wyłącznie przy konkretnym miejscu nazwanym w narracji. Nie zastępuj Bordeaux dowolnym europejskim miastem.
- `kinetic-text` jest dozwolony tylko dla jednoznacznej tezy lub kontrastu, którego sens można skrócić bez zmiany znaczenia. Nie powtarza pełnych napisów dialogowych.
- `audio-waveform` jest dozwolony tylko przy transmisji, słyszalnym głosie, komunikacji lub dźwięku.
- `speaker-hold` oznacza świadome pozostawienie prowadzącego i istniejącego zoomu; nie jest brakiem pracy, tylko narzędziem suspensu.
- `intentional-hold` wygrywa z przypadkowym stockiem i dekoracyjnym efektem.
- Fallbacki są deterministyczne, mają zapisany powód i wymagają tej samej jawnej akceptacji co B-roll.

## Sposób pokazania przebitki

- `full` — pełnoekranowy materiał akcji lub pionowy klip, bez dekoracyjnej ramki.
- `editorial` — całe zdjęcie lub szeroki kadr na przyciemnionym, rozmytym tle; używaj, gdy agresywne `cover` ucięłoby twarz, piłkę, herb albo ważny kontekst.
- `archive` — monochrom, delikatna winieta, skanlinie i cienka jasna ramka; wyłącznie dla materiałów faktycznie archiwalnych albo wspomnieniowych.
- `split` — dwa semantycznie powiązane materiały w jednym diagonalnym kadrze, np. zawodnik + drużyna albo akcja + reakcja.
- `stack` — dwie warstwowe plansze w stylu redakcyjnym/magazynowym; używaj do przedstawienia bohatera, kontrastu albo krótkiej sekwencji dowodowej.
- `cutout` — przezroczysty PNG, WebP lub AVIF z wyciętą postacią na ciemnym tle i dużym hasłem; zwykłego prostokątnego zdjęcia nie wolno udawać jako cutout.
- `paper-collage` nie należy do dostępnych prezentacji. Cały kierunek został pominięty decyzją użytkownika.
- Ruch wybieraj jawnie jako `push-in`, `pull-out`, `pan-left`, `pan-right` albo `still`. Ma być powolny przez cały czas przebitki, bez przypadkowego szarpania.
- Lokalny planner domyślnie nadaje zdjęciom `editorial` + `push-in`, a wideo `full` + `still`. Reżyser może zmienić wariant tylko z uzasadnieniem semantycznym.
- Krótkie wejście i wyjście jest miękkie, ale nie może zamieniać przebitki w pokaz slajdów. Mocniejszy `whip`, `flash` lub `light-leak` nadal wymaga osobnego cue na prawdziwym akcencie narracyjnym.
- Jedna scena lub przebitka trwa co najmniej 3 sekundy. Krótszy fragment jest dozwolony wyłącznie po jawnej zmianie tej reguły przez użytkownika.
- Gdy biblioteka zawiera inne poprawne materiały, nie powtarzaj tego samego `assetId` w jednej rolce. Powtórzenie wymaga jawnego wyjątku i uzasadnienia w planie.
- Kolejne materiały mają przechodzić bez zbędnego odsłaniania prowadzącego pomiędzy nimi. Szczególnie sekwencja `stock miejsca → ujawnienie bohatera` ma być bezpośrednia i stabilna.
- Ostatnia plansza dochodząca do końca filmu nie może wygaszać się do prowadzącego. Ustaw `fadeOut: false`, jeżeli ma pozostać widoczna do ostatniej klatki.
- `split` i `stack` wymagają dwóch oddzielnych `assetId`, które opisują tę samą osobę, zespół, miejsce lub logiczną parę akcja–reakcja. Sam podobny kolor albo sport nie wystarcza.
- Nie proponuj ani nie dodawaj `paper-collage`, dopóki użytkownik jawnie nie cofnie decyzji o pominięciu tego etapu.
- Hasło redakcyjne ma najwyżej 70 znaków, kicker 32 znaki. Nie powtarzaj całego napisu dialogowego: hasło ma syntetyzować beat w 1–5 słowach.

## Do nauczenia

- Moment pierwszego B-rollu:
- Preferowane typy ujęć:
- Maksymalna długość:

## Zdjęcia pojedyncze i sekwencje — korekta użytkownika 13.09.2026

Pojedyncze zdjęcie, w tym zdjęcie areny, jest zwykłą przebitką: może mieć delikatny zoom lub panoramowanie. Wideo areny pozostaje zwykłym klipem. Nie stosuj do nich BaronMattePhotos. Sama obecność zdjęć w bazie lub kilku osobnych przebitek fotograficznych nie uruchamia tej animacji.

BaronMattePhotos, zatwierdzone na zdjęciach Adriana Boguckiego, stosuj do świadomie zaplanowanej, wspólnej sekwencji co najmniej dwóch fotografii. Nie łącz automatycznie zdjęć z różnych segmentów. Plansze danych, schematy i dokumenty zachowują osobny sposób prezentacji.

Dla takiej sekwencji przed importem reżyserii dobierz unikalne zdjęcia, przygotuj animację przez photos:prepare --render-broll, odśwież pakiet reżysera, aby zawierał wynikowy assetId, i użyj jej jako pełnego wideo full/still. Nie zmieniaj etapu akceptacji. Długość 2 zdjęć to 3,6 s, 3 to 5,2 s, 5 to 8,4 s; nie przycinaj gotowej animacji. Dopasuj segmenty wypowiedzi przed przygotowaniem propozycji. Przenieś cue ze względnym przesunięciem; zachowaj durationMs, nie dubluj dźwięków. W raporcie przed renderem pokaż listę zdjęć, ich kolejność i profile.
