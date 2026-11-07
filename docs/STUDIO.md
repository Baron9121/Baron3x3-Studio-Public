# Baron3x3 Studio — obsługa

System działa wewnątrz istniejącego Baron3x3-Local. Kod i konfiguracja są w Git; produkcyjne media w ignorowanym `projekty/`. Dawne skrypty pozostają dostępne, lecz nie są wywoływane przez Studio.

## Instalacja

Node 22+, Python 3.12 i FFmpeg muszą być dostępne. W folderze repozytorium:

```sh
npm ci
python3.12 -m venv .venv-studio
.venv-studio/bin/pip install -r requirements-studio.lock.txt
npm run check:studio
npm run test:studio
```

Na innych systemach użyj `requirements-studio.txt`, jeśli macOS-owy zestaw przypiętych zależności nie ma odpowiednich pakietów. Faster-whisper działa na CPU int8; pierwsza transkrypcja pobiera model. Domyślny model `small` jest kompromisem szybkości i jakości, do oceny na polskich nazwiskach. `--model medium` zmienia go dla danego przebiegu. Media nie są wysyłane do API.

## Jedna rolka

W Claude Code otwórz ten folder i wpisz `zmontuj lorenzo`. Skill prowadzi proces, ale wszystkie komendy działają też bez agenta:

```sh
npm run baron -- init projekty/lorenzo --source 'input/#1.mp4' --scenario instructions/scenarios/01-francja-lorenzo-scenariusz.md
npm run baron -- prepare projekty/lorenzo
npm run baron -- transcribe projekty/lorenzo
npm run baron -- suggest-cuts projekty/lorenzo
```

1. **Akceptacja cięć:** przeczytaj `work/cuts.md`. Nazwiska popraw w `poprawki_slow.json` (mapa tekst → tekst, także frazy) i ponów `suggest-cuts`. `none` zachowuje całość; `K01,K03` usuwa wskazane propozycje. Zmiana granic w `cuts.json` musi być pokazana i zaakceptowana. Detekcja dubli jest heurystyczna.

```sh
npm run baron -- approve-cuts projekty/lorenzo --ids none --note 'Użytkownik zaakceptował brak dodatkowych cięć'
npm run baron -- cut projekty/lorenzo
npm run baron -- catalog projekty/lorenzo
npm run baron -- plan projekty/lorenzo
```

Skopiuj wybrane media do `przebitki/`, audio do `audio/` przed katalogowaniem. Katalog tworzy 5 klatek, proxy i metadane, nie wymyśla opisów. `plan` tworzy napisy w grupach do 3 słów; operator dopisuje uzasadnione przebitki i zoomy według rytmu opisanego w skillu `baron3x3-montaz`. Plansze tekstowe i karty statystyk są wyłączone. Składnia elementów: `schemas/plan.schema.json`. Czasy w sekundach na **zmontowanym** A-rollu, 30 fps, źródła względne wewnątrz projektu. Zdjęcia JPG/PNG/WebP. Jedna aktywna przebitka, grupa napisów i zoom na danej ścieżce; audio może się nakładać.

Przykład dopisania elementów i pierwszej walidacji:

```json
{"id":"Z01","type":"zoom","start":3,"end":7,"scale_from":1.15,"scale_to":1.15}
```

```sh
npm run baron -- validate projekty/lorenzo --pozwol Z01,B01,M01
npm run baron -- report projekty/lorenzo
```

2. **Akceptacja planu:** `work/plan.md` zawiera ID, czas i wypowiadany tekst. Po zgodzie na tę wersję:

```sh
npm run baron -- approve-plan projekty/lorenzo --note 'Zgoda użytkownika na pokazany plan'
npm run baron -- preview projekty/lorenzo
```

3. **Akceptacja podglądu:** obejrzyj i odsłuchaj `wynik/PODGLAD.mp4`. Arkusz `PODGLAD-klatki.jpg` pomaga ocenić obraz, ale nie zastępuje odsłuchu.

```sh
npm run baron -- approve-preview projekty/lorenzo --note 'Zgoda użytkownika na podgląd'
npm run baron -- final projekty/lorenzo
```

Final: `wynik/FINAL.mp4`, 1080×1920. Podgląd: 540×960. Obie ścieżki odczytują zatwierdzony snapshot. Notatki w przykładach wpisuj dopiero po rzeczywistej zgodzie — nie są gotową akceptacją.

## Poprawka jednego elementu

Edytuj `plan.json`, np. tylko B03.source i Z02.end:

```sh
npm run baron -- validate projekty/lorenzo --pozwol B03.source,Z02.end
npm run baron -- history projekty/lorenzo
npm run baron -- restore projekty/lorenzo 2 --note 'Powrót wskazany przez użytkownika'
```

Walidacja zawsze porównuje z ostatnią zapisaną wersją. Niedozwolona zmiana zostaje zablokowana przed historią i akceptacją. Ręcznie edytowany plik roboczy pozostaje do poprawienia; zatwierdzony snapshot nie jest naruszany. Przywracanie nie zatwierdza. Zmiana materiału, nawet o tej samej długości, lub szablonu unieważnia akceptację. Po zmianie A-rollu utwórz nowy projekt; nie przenoś czasów ręcznie.

Ochrona to lokalna kontrola spójności, nie kryptograficzny podpis człowieka: osoba mająca dostęp do plików może je ręcznie zmienić. Agent ma obowiązek respektować trzy bramki. W obrębie projektu komendy są blokowane przed równoczesnym wykonaniem.

## Biblioteka i pomiary

```sh
npm run baron -- search assets/library/Baron3x3 'Lorenzo Francja' --top 10
npm run baron -- kandydaci projekty/lorenzo --zapytanie 'World Tour wsad' --top 40
npm run baron -- dodaj-przebitki projekty/lorenzo 3885005881976326480 3888804431668019988
npm run baron -- kandydaci projekty/lorenzo --zdjecia --zapytanie 'Challenger MVP' --top 40
npm run baron -- dodaj-zdjecia projekty/lorenzo F307352 F7759e7
npm run baron -- status projekty/lorenzo
```

`kandydaci` filtruje `assets/library/Baron3x3/video/README.md` według `config/przebitki.json`: bez rozgrywek reprezentacji i bez koszykarek; turnieje klubowe z zespołem nazwanym krajem są oznaczone „Sprawdź”. `dodaj-przebitki` kopiuje do projektu tylko klipy, które przeszły filtr. `--zdjecia` stosuje te same reguły do `images/README.md`, a `dodaj-zdjecia` kopiuje zdjęcia do `zdjecia/` projektu (ID `F…` to skrót nazwy pliku). Element `photo` renderuje je jako BaronMattePhotos; tekstury i dźwięki z `remotion/public/matte-photos` są lokalne i wchodzą do odcisku akceptacji planu. Wyniki wyszukiwania po nazwach i opisach są kandydatami. Materiały projektu mają pierwszeństwo. `work/timing.jsonl` zapisuje czasy komend, `work/preview.json` i `final.json` wyniki technicznego QA. B-roll jest wyciszony; muzyka/SFX mają jawny poziom i fade. Muzyka pod głosem wymaga dobrania `volume`; automatyczny sidechain nie jest wdrożony.

## Ograniczenia i dalszy odbiór

Wygląd wymaga oceny na 2–3 rolkach, dopiero wtedy zamrażamy wersję szablonu. Nazwiska, brak trzasków i synchronizację ocenia człowiek. Cel 90 s filmu w 30 minut nie został potwierdzony. FCPXML jest poza obecną implementacją.

Implementacja korzysta z istniejącej wersji Remotion 4.0.518 i lokalnego faster-whisper. Dokumentacja: [Remotion Video](https://www.remotion.dev/docs/media/video), [render CLI](https://www.remotion.dev/docs/cli/render), [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Warunki komercyjnego użycia Remotion sprawdź w [oficjalnej licencji](https://www.remotion.dev/license).
