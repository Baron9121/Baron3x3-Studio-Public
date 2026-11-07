# Precyzja montażu Baron3x3 — standard Adriana

Obowiązuje od 13.09.2026 na jawne polecenie użytkownika po diagnozie Bordeaux. Wzorzec: examples/adrian-bogucki-approved/. Przenosimy dokładność decyzji, nie sztywną długość, liczbę efektów ani proporcję przebitek z 38-sekundowego filmu.

## 1. Rozpoznaj wejście przed wyborem historii

Zapisz w instrukcjach joba, czy wejście jest surówką, czy gotową pociętą bazą. Gdy użytkownik określa materiał jako gotową bazę, zachowaj kolejność, całą wypowiedź i istniejące cięcia; nie skracaj do domyślnych 25–45 s ani nie usuwaj intro bez polecenia. Sama nazwa pliku nie potwierdza trybu. Sprawdź instrukcje, transkrypcję i materiał. Jeśli tryb nadal jest niejasny, zachowaj całość w propozycji i oznacz założenie. Każde proponowane usunięcie wypowiedzi pokaż osobno wraz z zakresem i powodem.

## 2. Reżyseruj pełną wypowiedź

Każda myśl od hooka do ostatniego zdania ma świadomy wybór obrazu: prowadzący, konkretna przebitka, liczba, teza albo zaplanowana sekwencja zdjęć. Nie kończ opracowania wizualnego po przedstawieniu zawodników. Sprawdź osobno początek, środek i finał; wypisz najdłuższe odcinki samego prowadzącego i wyjaśnij, dlaczego zostają. Nie ma obowiązkowego procentu B-rollu ani mechanicznej zmiany obrazu co kilka sekund. Długi hold jest decyzją narracyjną, nie skutkiem zakończenia poszukiwań assetów.

Zoomy i przejścia przypisuj do zmiany znaczenia. Zachowaj zaakceptowane spokojne bloki zwykle 4–7 s; dłuższy blok uzasadnij konkretną wypowiedzią. Sprawdź rzeczywisty widoczny obraz, ponieważ zoom prowadzącego pod pełnoekranową przebitką nie daje widzowi nowego bodźca.

## 3. Zweryfikuj każdy wybrany materiał

Opis katalogu daje kandydata. Obejrzyj zdjęcie w całości, a dla wideo cały wybrany zakres wraz z początkiem i końcem akcji. Potwierdź osobę, wszystkie widoczne osoby, napisy, turniej i miejsce w zakresie możliwym do ustalenia. Nie nazywaj planszy składu portretem jednego zawodnika. Nierozpoznanego materiału nie oznaczaj jako zweryfikowany.

Dla każdej wstawki zapisz w analysis/<job>/director/material-review.md: assetId i ścieżkę, faktyczną zawartość, dokładny cytat i czas wypowiedzi, czas na osi filmu, źródłowe IN–OUT, sposób kadrowania i ruch, status weryfikacji oraz jej dowód (obejrzany zakres lub klatki). Klatki pomagają ocenić wygląd, lecz nie potwierdzają ciągłości i pełnej kulminacji akcji. Materiał innego turnieju może ilustrować zawodnika lub ogólną skalę areny, jeśli nie sugeruje dowodu konkretnego meczu ani błędnej lokalizacji. W razie potrzeby oznacz archiwum.

Wejście obrazu dopasuj do rzeczywistych słów po montażu. Jeśli hook ukrywa bohatera, nie ujawniaj go przed nazwiskiem; przestrzegaj także dodatkowych ograniczeń użytkownika. Akcja sportowa ma dojść do kulminacji i czytelnego zakończenia. Brak materiału rozwiąż lokalnie odpowiednią planszą lub świadomym A-rollem, nie przypadkowym zawodnikiem.

## 4. Liczby, napisy, zdjęcia i audio

Rozważ czytelną planszę dla wyniku, porównania lub liczby kluczowej dla argumentu; synchronizuj ją z wypowiedzią. Nie wstawiaj karty statystyk tylko dla zaliczenia testu. Brak materiału wideo nie jest powodem rezygnacji ze wszystkich grafik i całej reżyserii. SFX musi mieć konkretną funkcję i pozostawić mowę czytelną; brak SFX także może być świadomym wyborem.

Sprawdź polszczyznę, nazwiska, wyniki i paginację napisów na rzeczywistym podglądzie i w odsłuchu. Samo languageReviewed=true ani nazwa captionStyle nie są dowodem jakości.

Pojedyncze zdjęcie, także areny, pozostaje zwykłą przebitką z opcjonalnym delikatnym ruchem. Wideo areny pozostaje klipem. BaronMattePhotos stosuj wyłącznie do zaplanowanej wspólnej sekwencji co najmniej dwóch fotografii według knowledge/matte-photos.md. Nie łącz automatycznie zdjęć z różnych scen.

## 5. Jedna aktualna wersja do oceny i renderu

Po zmianie długości, sourceRanges lub transkrypcji odśwież pakiet reżysera i propozycję właściwą ścieżką workflow. Nie nakładaj reżyserii skrótu na pełną wypowiedź. Raport review-plan.md musi pochodzić z aktualnego połączonego planu, nie z ręcznie przepisanej tabeli. Porównaj długość, zakresy, assety, IN–OUT, kadrowanie, grafiki i SFX. Rozbieżność oznacza konieczność odświeżenia przed renderem.

Nie omijaj ochrony wersji, ustawiając status ręcznie lub używając starego joba bez podpisu. Dla wznowionej reżyserii przygotuj aktualny raport przez reel:revise-director i ponowny import. Zachowuj istniejące akceptacje, o ile ich przedmiot nie uległ zmianie; nie pytaj ponownie o niezmienione wybory.

## 6. Kontrola redakcyjna wyniku jest obowiązkowa

Po lokalnych bramkach obejrzyj i odsłuchaj cały wynik. Zapisz analysis/<job>/director/editorial-review.md: identyfikację ocenionego MP4 i wersji planu (SHA-256), metodę i zakres oglądania/odsłuchu, błędy z czasami, porównanie z Adrianem według knowledge/style-evaluation.md oraz werdykt. Nie wpisuj punktacji za obszary, których nie sprawdzono. Nie deklaruj pełnego oglądania na podstawie planszy kontaktowej.

Lokalne pass-local-gates-needs-semantic-review i stan complete oznaczają sukces techniczny, nie potwierdzają jakości redakcyjnej. Dopóki pełna kontrola nie została wykonana, komunikuj „render techniczny, wymaga kontroli redakcyjnej”. Przy braku możliwości odsłuchu lub oglądania nazwij ograniczenie i pozostaw ocenę nieukończoną. Kontrola może być wykonana dostępnymi narzędziami lokalnymi; płatne API wymaga istniejącego upoważnienia i limitu, nie jest automatycznie wymagane.

Błędna osoba, mylący turniej, urwana myśl/akcja, niezgodność zaakceptowanego planu z wynikiem lub nieczytelna mowa wykluczają rekomendację jako gotowy montaż. Popraw zgodnie z workflow, maksymalnie dwie automatyczne rundy. Nie wyłączaj globalnie kontroli referencji dla wygody. Jeśli konkretny element nie pasuje do filmu, zapisz rzeczywiste uzasadnienie jego pominięcia; komunikat walidatora nie jest dowodem braku materiałów.

To obowiązujący kontrakt pracy agenta. Nie zastępuje implementacji automatycznej analizy znaczenia; obecne lokalne bramki nie potrafią samodzielnie zagwarantować powyższej jakości.
