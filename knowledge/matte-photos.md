# Matowe zdjęcia — zaakceptowany szablon użytkownika

Użytkownik zatwierdził powrót do wersji z teksturami na CAŁYCH zdjęciach. Bez wycięć postaci, napisów i plakatu Adrian Bogucki sezon 2026/2027. Dowód: examples/matte-photos/accepted.mp4. Nie zmieniać Travel Stories.

Podczas planowania rolki agent dobiera semantycznie właściwe zdjęcia z assets/MATERIALY.md, na podstawie treści wypowiedzi i instrukcji. Nie losuj, nie dobieraj po samej nazwie pliku, nie powtarzaj assetId. Liczba zdjęć wynika z dostępnych pasujących materiałów; nie dopełniaj listy powtórkami. Jeśli nic nie pasuje, zgłoś brak. Zachowaj istniejący workflow akceptacji historii i planu.

Po wyborze przygotuj pokaz:
`npm run photos:prepare -- NAZWA --asset-id ID1 --asset-id ID2`
Dodaj `--render-broll`, aby utworzyć pośrednią przebitkę w assets/library/matte-photos/NAZWA.mp4 i odświeżyć katalog. To render materiału pomocniczego, nie finalnej rolki. Następnie znajdź stabilny assetId gotowej przebitki w katalogu i użyj go jako zwykłego wideo w zaakceptowanym planie overlays. Presentation full, motion none: ruch już jest w pliku. Daj mu pełny czas z analysis/matte-photos/NAZWA/selection.json. Nie zapętlaj i nie obcinaj do domyślnego czasu B-rollu. Jeśli wypowiedź jest krótsza, wybierz mniej zdjęć przed renderem. Finalna rolka nadal przez workflow reel i pipeline.

Długość pokazu: (60 + (N−1)×48)/30 sekund. 1 zdjęcie: 2 s; 3: 5,2 s; 5: 8,4 s; 8: 13,2 s. Wyjątek od minimum 3 s zaakceptowany dla tego konkretnego szablonu. Przejście 0,4 s zmienia zdjęcie, raz w górę, raz w lewo. Pierwsza klatka pełna. Tekstury i papier ciągłe na całej kompozycji.

Nowe zdjęcia: domyślnie pełny kadr i bez zoomu, z zachowaniem proporcji. Po obejrzeniu zdjęcia agent może podać --profiles plik.json: obiekt mapujący assetId na {face:[x,y],contain:true,zoom:1.08}. Współrzędne twarzy znormalizowane w oryginale. Nie udawaj automatycznej detekcji twarzy. Sprawdź maksymalny zoom i krawędzie głowy. Zapisane pięć zdjęć demonstracyjnych ma gotowe profile.

Kompozycja BaronMattePhotos jest dostępna w Studio. Bez nowych pakietów, bez API. To adaptacja efektu zatwierdzona w rozmowie, nie paper-collage ani cutout.

## Dźwięk przejść
Kompozycja zawiera whoosh przy każdej zmianie zdjęcia (N−1 efektów), 2 klatki przed początkiem przesunięcia; volume 0.14, speechDucking 0.72, obwiednia z istniejącego SoundEffects. Przy jednym zdjęciu brak dźwięków. Uzasadnienie: podkreślenie rzeczywistej zmiany zdjęcia.

photos:prepare zapisuje także analysis/matte-photos/NAZWA/sound-effects-relative.json. Pipeline wycisza audio przebitek: przy dodaniu pokazu do rolki przenieś te cue do głównego soundEffects planu, dodając do timelineStartMs czas rozpoczęcia pokazu. Nie nadpisuj istniejących cue i nie dodawaj drugi raz tego samego id. Zachowaj reason. Plik wideo ma audio do samodzielnego podglądu; w rolce źródłem dźwięku są cue, dlatego pozostaw przebitkę muted. Nie dodawaj osobnego whoosh reżysera w tych samych punktach.

## Aktualne dźwięki użytkownika — Dragon Studio
Zastępują wcześniejszy whoosh-soft: dragon-whoosh (oryginalny dramatic-whoosh-swing-487667.mp3, 1,92 s) przy zmianie zdjęcia, volume .14. Dragon-camera (pierwsze 0,36 s camera-shutter-390292.mp3 z wygaszeniem końcówki) raz na zoom, po ukończeniu wejścia zdjęcia; przy pierwszym zdjęciu od początku. Volume .12, speechDucking .72. Bez zoomu nie dodawać migawki. Oryginały zachowane w assets/sfx. Źródło: pliki dostarczone przez użytkownika, bez nowego pobierania. Pipeline obsługuje oba typy; sidecar automatycznie używa nowych nazw. Pozostaje obowiązek przeniesienia cue ze względnych czasów do planu rolki.

### Pętla migawki — aktualizacja
Migawka powtarza się co 11 klatek w całym oknie między whooshami, również na nieruchomym zdjęciu. Whoosh używa dragon-whoosh-short.wav (0,7 s, z wygaszonym ogonem); oryginał pozostaje. Migawka milczy od startu whoosha przez 21 klatek. Ostatnie powtórzenie skracane przez durationMs, żeby nie nachodziło na whoosh. Przy przenoszeniu cue do planu zachowaj durationMs. Pierwsza pętla zaczyna się od początku filmu, ostatnia kończy wraz z nim. Zastępuje regułę pojedynczej migawki na zoom.

## Zdjęcia pojedyncze i sekwencje — korekta użytkownika 13.09.2026

Pojedyncze zdjęcie, w tym zdjęcie areny, jest zwykłą przebitką: może mieć delikatny zoom lub panoramowanie. Wideo areny pozostaje zwykłym klipem. Nie stosuj do nich BaronMattePhotos. Sama obecność zdjęć w bazie lub kilku osobnych przebitek fotograficznych nie uruchamia tej animacji.

BaronMattePhotos, zatwierdzone na zdjęciach Adriana Boguckiego, stosuj do świadomie zaplanowanej, wspólnej sekwencji co najmniej dwóch fotografii. Nie łącz automatycznie zdjęć z różnych segmentów. Plansze danych, schematy i dokumenty zachowują osobny sposób prezentacji.

Dla takiej sekwencji przed importem reżyserii dobierz unikalne zdjęcia, przygotuj animację przez photos:prepare --render-broll, odśwież pakiet reżysera, aby zawierał wynikowy assetId, i użyj jej jako pełnego wideo full/still. Nie zmieniaj etapu akceptacji. Długość 2 zdjęć to 3,6 s, 3 to 5,2 s, 5 to 8,4 s; nie przycinaj gotowej animacji. Dopasuj segmenty wypowiedzi przed przygotowaniem propozycji. Przenieś cue ze względnym przesunięciem; zachowaj durationMs, nie dubluj dźwięków. W raporcie przed renderem pokaż listę zdjęć, ich kolejność i profile.
