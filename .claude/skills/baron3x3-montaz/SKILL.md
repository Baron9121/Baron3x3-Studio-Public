---
name: baron3x3-montaz
description: Prowadź lokalny montaż rolki Baron3x3 Studio z transkrypcją, planem JSON i trzema akceptacjami. Użyj przy „zmontuj NAZWA” lub poprawkach elementów istniejącej rolki. Rozwój szablonu jest osobnym zadaniem.
---

# Baron3x3 Studio

Pracuj w istniejącym Baron3x3-Local. Instrukcja komend: [Studio](../../../../docs/STUDIO.md).
Uruchamiaj `npm run baron -- status projekty/NAZWA` na początku i po wznowieniu. Sprawdź komunikaty o nieaktualnych wejściach. Nie utożsamiaj istnienia pliku z zaliczeniem kontroli.

## Rozpoznanie

Jedna rolka = jedna wstępnie pocięta baza. Zachowaj pełną wypowiedź. Nie zgaduj, który MP4 odpowiada scenariuszowi: sprawdź istniejące `instructions/jobs/`, a przy niejednoznaczności zapytaj. Źródeł nie nadpisuj. Projekt ma własne `przebitki/` i opcjonalne `scenariusz.md`, `audio/`.

## Trzy akceptacje

1. Przygotuj A-roll, transkrypcję lokalnym faster-whisper i raport cięć. Popraw nazwiska przez `poprawki_slow.json`, potem przelicz raport. Pokaż `work/cuts.md` oraz słowa o niskiej pewności. Zatrzymaj się po propozycji. Dopiero po jawnej zgodzie użytkownika wykonaj `approve-cuts --ids ... --note "treść zgody"`, potem `cut`. `none` oznacza świadomą akceptację bez dodatkowych cięć. Granice Whispera bywają przesunięte o 0,1–0,3 s: przy ręcznym cięciu sprawdź ciszę w pasmach dźwięku, daj użytkownikowi klip do odsłuchu i dopiero granicę przez niego zaakceptowaną oznacz w `cuts.json` jako `"sprawdzone_na_sluch": true`. Wtedy `cut` przycina słowa na tej granicy zamiast ją blokować.
2. Dobierz przebitki według sekcji „Źródło przebitek”, potem zrób katalog miniatur i obejrzyj używane materiały. Nie wysyłaj filmów do modeli. Miniatury nie dowodzą tożsamości ani ciągłości akcji; brak pewności opisz. `plan` tworzy wyłącznie bazowe napisy, więc operator dodaje uzasadnione Z/B/M/S według sekcji „Rytm przebitek”. Raport `report` pokazuje ID, czasy, materiał i cytat. Waliduj i pokaż użytkownikowi przed akceptacją. Po zgodzie wykonaj `approve-plan --note ...` i `preview`.
3. Pokaż `wynik/PODGLAD.mp4` i arkusz klatek. Po poprawkach potrzebna jest walidacja, odnowienie akceptacji planu i nowy podgląd. Dopiero po zgodzie na konkretny podgląd wykonaj `approve-preview --note ...`, potem `final`. Final czyta wyłącznie `plan.zatwierdzony.json` i sprawdza hashe wejść.

Nigdy nie wpisuj zgody za użytkownika, nie używaj testowej notatki jako jego akceptacji. Budowa systemu nie jest akceptacją konkretnej rolki. Techniczne testy mają oddzielny, syntetyczny projekt i jawne testowe akceptacje.

## Źródło przebitek

Jeśli użytkownik nie wrzucił przebitek do `przebitki/`, wybierz je sam z biblioteki wideo `assets/library/Baron3x3/video` (indeks `README.md`).

- `kandydaci projekty/NAZWA --zapytanie '…'` filtruje indeks według `config/przebitki.json` i zapisuje `work/kandydaci.md`. Nie czytaj całego indeksu, pracuj na tej liście.
- Zakazane: rozgrywki reprezentacji (MŚ, ME, Europe Cup, World Cup, igrzyska, mecze reprezentacji) oraz klipy z koszykarkami. Tylko koszykarze w grze.
- „Sprawdź” oznacza turniej klubowy, w którym zespół nazwano krajem albo opis wspomina reprezentację. Użyj tylko po potwierdzeniu na miniaturach, że grają kluby.
- Dobieraj semantycznie do wypowiedzi, nie po samej nazwie pliku. Kopiuj wyłącznie przez `dodaj-przebitki projekty/NAZWA ID…`, które odrzuca klipy wykluczone.
- Po `catalog` obejrzyj arkusze wybranych klipów. Kobieta, strój reprezentacji albo napis MŚ/ME w kadrze wyklucza klip mimo opisu. Opisy indeksu są automatyczne.
- W raporcie planu wypisz ID klipów i powód wyboru.

## Stock (opcjonalny)

Stock tylko dosłownie do tego, co pada w scenariuszu, i tylko gdy coś takiego pada. Rolka bez stocku jest w porządku. Bez metafor (karty do gry za „dziką kartę”, schody za „awans”).

Stock pokazuje to, co wychodzi poza koszykówkę: miejsca, rzeczy i sytuacje z wypowiedzi. Proponuj go tylko tam, gdzie uznasz, że wniesie więcej niż przebitka meczowa. Decyzja należy do użytkownika przy akceptacji planu:

- W `plan.md` kolumna „Źródło” oznacza element jako `STOCK`. W wiadomości z planem wypisz propozycje stocku osobno: ID elementu, zdanie, co widać, ID `S…` i arkusz podglądu.
- Element planu wymaga pliku w projekcie, więc przed walidacją planu zapytaj o zgodę na pobranie wybranych klipów (liczba, źródło, orientacyjny rozmiar) i dopiero wtedy `dodaj-stock … --zatwierdzone`.
- Gdy użytkownik odrzuci stock („B05 na bibliotekę”), podmień `source`/`source_start` tego elementu na klip z biblioteki (`validate --pozwol B05.source,B05.source_start`) bez zmiany czasów.

- Miejsce turnieju lub miasto → ujęcie miasta z lotu ptaka, rynek, charakterystyczny budynek (`rodzaj: miasto`). Nazwa drużyny, która brzmi jak miasto (Warsaw, Utsunomiya), nie jest miejscem.
- Kraj → flaga (`kraj`), klub → herb (`klub`, zdjęcie z Commons), stadion lub budynek → ten obiekt (`obiekt`), pieniądze → liczarka banknotów (`pieniadze`), podróż → samolot (`podroz`).
- Motywy wpisz do `work/stock-motywy.json` (`id`, `fraza`, `rodzaj`, `nazwa`, opcjonalnie `aliasy` i `typ`), potem `stock-motywy` i `stock-miniatury` (`docs/STOCK.md`). Szablony zapytań są w `config/stock.json`.
- Dla miejsc wynik przechodzi tylko, gdy nazwa lub alias jest w tytule, opisie albo adresie źródła. Aliasy muszą być jednoznaczne (Ateny tak, „Acropolis” nie, bo pasuje też do Lindos). Pusty wynik znaczy: brak stocku, a nie „weź coś podobnego”.
- Najpierw wideo (Pexels), zdjęcia z Commons tylko gdy wideo brak, jako MattePhoto.
- Pełne pliki pobieraj (`dodaj-stock … --zatwierdzone`) dopiero po zgodzie użytkownika. Przy finale przekaż `wynik/ATRYBUCJE.md`.

## Dźwięki

Zasady zaakceptowane przez użytkownika. Mowa ma pierwszeństwo, bez podkładu muzycznego. Efekty, głośności, limity i licencje: `config/dzwieki.json`. Syreny i gwizdka użytkownik nie chce.

| Efekt | Kiedy | Limit |
|---|---|---|
| whoosh | automatycznie: przejście z twarzy na blok przebitek (MattePhoto ma własne) | — |
| impact | puenta albo mocna liczba, w pauzie po zdaniu | 2 |
| swish | klatka, w której piłka wpada do kosza na przebitce (z arkusza końca przebitki) | 3 |
| doping | zwycięstwo, awans, trofeum | 1 |
| riser | narasta do cięcia, po którym pada odpowiedź na pytanie z haka | 1 |
| zegar | mowa o czasie: 12 s na akcję, końcówka meczu | 2 |
| liczarka | pieniądze i nagrody, najlepiej ze stockiem liczarki | 2 |

- Efekt tylko tam, gdzie treść go uzasadnia; rolka bez żadnego efektu poza whooshem jest w porządku.
- Między dźwiękami co najmniej 5 s; wybrane efekty wygrywają z automatycznym whooshem.
- Po ułożeniu przebitek: `dzwieki projekty/NAZWA --efekty impact:29.55,swish:41.2`, potem `validate --pozwol` z dodanymi ID `S…`. Czas to moment, w który ma trafić efekt (wpadnięcie piłki, cięcie po pytaniu), a nie początek pliku. Pominięte efekty i powód są w wyniku komendy; wypisz dźwięki w wiadomości z planem.

## Plansze

Styl A (ciemne tło, gradient róż–fiolet–niebieski). Element `graphic` (`G01`…) zajmuje obraz jak przebitka, trwa co najmniej 3 s i liczy się do udziału przebitek. 1–3 plansze na rolkę, tylko przy liczbach i miejscach ważnych dla historii; wypisz je w wiadomości z planem. Użytkownik nie chce tablicy wyniku, tabeli grupy, ścieżki awansu ani paska z nazwiskiem.

- `counter`: `{"value": 32, "label": "punkty w turnieju", "land_at": 26.4}` (opcjonalnie `from`, `of`, `suffix`). `land_at` = czas wypowiedzenia liczby; licznik tyka (dźwięk z `config/dzwieki.json`) i staje dokładnie na nim.
- `globe`: `{"city": "Antwerpia", "country": "Belgia", "lat": 51.22, "lon": 4.40}` (opcjonalnie `date`, `from: {name, lat, lon}` rysuje łuk lotu). Przy pierwszej wzmiance o miejscu turnieju, najlepiej 4–4,5 s. Współrzędne sprawdź; nazwa drużyny brzmiąca jak miasto nie jest miejscem.

## Rytm przebitek

Wzorzec: ręcznie zmontowane rolki użytkownika (Fredette, Warsaw–Hongcheon).

- Bez plansz tekstowych i kart statystyk: wyglądają tandetnie. Schemat ich nie przyjmuje. Liczby, etapy i zastrzeżenia pokazuj przebitką albo twarzą z zoomem.
- Każda scena trwa co najmniej 3 s: ujęcie przebitki, fragment twarzy i każdy poziom zoomu. Twarda reguła użytkownika.
- Przebitki zajmują co najmniej 50% osi (cel 50–60%). Cięcia twarde, na początku słowa.
- Bloki przebitek mogą łączyć kilka ujęć, każde od 3 s. Twarz między blokami 3–6 s.
- Zoom na twarzy to skok kadru na początku zdania, bez płynnego najazdu: `scale_from` = `scale_to`, poziomy około 1,0 / 1,15 / 1,3. Łączenie ujęć po cięciu maskuj skokiem zoomu lub przebitką, gdy skok dałby scenę krótszą niż 3 s.
- Przebitki wideo: lekki ruch `scale_from` 1,0 → `scale_to` 1,03.

## Napisy

Styl zaakceptowany przez użytkownika: Helvetica Neue, wyśrodkowane, fraza do dwóch linii (do 6 słów i 30 znaków), słowa pojawiają się po jednym w chwili wypowiedzenia.

- Słowa kluczowe (nazwiska, drużyny, liczby, nazwy turniejów, puenta zdania) oznacz `"highlight": true` w `words`: są większe i mają białą poświatę. Umiar: zwykle jedno wyróżnienie na frazę, nie w każdej.
- Wyróżnienia wypisz w raporcie planu, bo wchodzą do akceptacji planu.

## Zdjęcia (BaronMattePhotos)

Element `photo` (ID `P01`…) to seria zdjęć w stylu BaronMattePhotos: papier, rysy, przejścia na przemian w górę i w lewo, whoosh i migawka (`"sfx": false` wycisza).

- Zdjęcia wybieraj sam z `assets/library/Baron3x3/images` według tych samych kryteriów co wideo: `kandydaci projekty/NAZWA --zdjecia --zapytanie '…'`, potem `dodaj-zdjecia projekty/NAZWA F…` (kopiuje do `zdjecia/`) i `catalog`. Kryteria zmienia tylko użytkownik.
- Bez kolaży z napisami, plakatów i grafik z tekstem. Obowiązuje zakaz powtórek między rolkami (SHA-256).
- Cała animacja to jedna scena: minimum 3 s. Zdjęcia w środku mogą zmieniać się szybciej, wzorzec to 1,6 s na zdjęcie; walidator odrzuca poniżej 1 s. Czas na zdjęcie = (długość − 0,4 s) / liczba zdjęć.
- `photo` dzieli ścieżkę z przebitkami i liczy się do udziału przebitek.
- Na zdjęcie: `face` [x, y] w ułamkach (punkt najazdu), `contain` (domyślnie true: całe zdjęcie na rozmytym tle, jak w przykładach), `zoom` 1,0–1,3 (domyślnie 1,06).

## Poprawki

- Modyfikuj tylko wskazane ID/pola; nie generuj planu ponownie. `validate --pozwol B03.source,Z02.end` porównuje z ostatnią zwalidowaną wersją. `--before` musi odpowiadać tej bazie. Pole główne planu i kolejność elementów są chronione.
- Napisy mają C001 itd.; korekta przed powstaniem planu jest w `poprawki_slow.json`, a po planie także w konkretnym Cxxx.words z dozwoleniem użytkownika. Zachowaj korektę w osobnym pliku dla przyszłych transkrypcji.
- Nie zmieniaj A-rollu po planowaniu: utwórz nowy projekt, jeśli użytkownik zmieni bazę lub zakres cięć. Nie przenoś starych czasów na nowe wejście.
- `history` i `restore` przywracają tylko plan roboczy. Snapshot akceptacji nie jest roboczym plikiem do ręcznej edycji.
- Podczas produkcji nie zmieniaj skryptów ani szablonu. Rozwój wyglądu: oddzielne polecenie użytkownika, osobna gałąź, stały materiał testowy, podgląd do oceny. Nie zapisuj stylu jako zaakceptowany bez zgody.

## Ocena i czas

Czytelność, nazwiska, treść i synchronizacja wymagają obejrzenia oraz odsłuchu. Nie deklaruj tego po samym arkuszu klatek. Błędy blokują oznaczenie rolki jako gotowej do publikacji. Automatyczne QA sprawdza wymiary, długość, obecność audio i pełne dekodowanie; nie ocenia sensu przebitek ani zrozumiałości mowy.

`work/timing.jsonl` mierzy komendy; cel 30 minut obejmuje także decyzje i akceptacje użytkownika. Nie obiecuj wyniku czasowego bez testu całej prawdziwej rolki. Nie korzystaj z dawnych płatnych komend `reel:*`, OpenRouter ani Resolve w ścieżce Studio.
