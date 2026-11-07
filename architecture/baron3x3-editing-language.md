# Baron3x3: reguły automatycznego montażu

Źródłem tej specyfikacji jest sposób pracy widoczny w `exedoAI.drp`: 83 klipy
wideo, z których 46 ma do 150 klatek, oraz warstwa napisów podzielona na krótkie
frazy. Efekty RGB split, blur, glitch i podobne przejścia nie należą do tego
profilu automatycznego.

## 1. Cięcia

Automat nie tnie dlatego, że wykrył ciszę. Tnie dopiero wtedy, gdy występuje
jedna z decyzji redakcyjnych:

- usunięcie zawahania, powtórzenia lub błędu;
- przejście do nowej myśli;
- wejście w liczbę, nazwisko, werdykt lub pytanie;
- miejsce, w którym B-roll ma wyjaśnić wypowiadane słowa;
- zmiana energii wypowiedzi.

Każdy wybrany fragment musi kończyć pełną myśl. Domyślna długość ujęcia A-roll
to 2–5 s, lecz ważniejsza jest intencja zdania niż stały interwał. Cięcie nie
może urwać słowa, oddechu potrzebnego dla rytmu ani ruchu twarzy.

## 2. Przybliżenia

Przybliżenie ma zaznaczać znaczenie, a nie wypełniać czas.

- start rolki: skala 1.00;
- kluczowa teza lub nazwa: punch-in 1.06–1.10;
- liczba, mocny werdykt lub puenta: punch-in 1.10–1.14;
- nowa myśl albo powrót z B-rollu: reset do 1.00;
- maksymalnie dwa mocne przybliżenia na 30 s;
- nigdy dwa przybliżenia jedno po drugim bez nowej informacji.

Każdy zoom zapisuje się w EditPlanie z czasem, skalą i uzasadnieniem. Pierwsza
wersja używa bezpiecznych, edytowalnych punch-inów; płynny push jest dodawany
tylko przez zatwierdzony preset Fusion.

## 3. B-roll z biblioteki

B-roll nie jest ozdobą. Wchodzi wtedy, gdy obraz może pokazać to, co właśnie
jest powiedziane: zawodnika, rzut, miasto, turniej, reakcję lub konkretny
kontekst. Wybór zawsze korzysta z indeksu biblioteki, bez ponownej analizy
całego archiwum.

- długość pojedynczej przebitki: zwykle 1.0–2.5 s;
- wejście dokładnie na słowie/frasie, którą ilustruje;
- B-roll nie przykrywa twarzy, gdy emocja mówcy jest istotniejsza;
- po przebitce wraca A-roll, zwykle z resetem skali;
- nie powtarzamy tego samego klipu, jeśli istnieje równie trafna alternatywa;
- każda pozycja planu zawiera powód użycia i konkretne słowa z narracji.

## 4. Napisy `Baron Caption Pro`

SRT jest wyłącznie źródłem tekstu i czasu. Na timeline powstają natywne,
edytowalne klipy Text+ — nie wypalony obraz i nie finalna ścieżka SRT.

1. SRT jest rozbijany na słowa z czasami.
2. Cała interpunkcja znika z tekstu widocznego na ekranie.
3. Kropka zamyka scenę napisową; kolejna fraza pojawia się od nowa.
4. Frazy mają 2–3 słowa i maksymalnie dwie linie.
5. Tekst jest biały, ciężki i czytelny; aktywne słowo ma zieleń Baron3x3.
6. Dla każdego słowa powstaje krótki stan Text+ z tym samym tekstem, ale innym
   zielonym słowem. Daje to efekt karaoke bez rastra i pozostawia pełną edycję.
7. Wejście frazy: dyskretne 4–6 klatek skali/opacity. Brak podskoków każdego
   słowa, bo pogarszają czytelność.
8. Pozycja jest w dolnej bezpiecznej strefie obrazu; cień i obrys są częścią
   presetu, aby tekst pozostał czytelny na B-rollu.

## 5. Kolejność decyzji automatu

1. Dopasowanie i oczyszczenie transkrypcji.
2. Cięcia A-rollu zgodnie z sensem wypowiedzi.
3. Przebitki tylko tam, gdzie wzmacniają konkretną frazę.
4. Zoomy po ustaleniu cięć i B-rollu.
5. Text+ z finalnie zmapowanych czasów timeline'u.
6. SFX tylko pod zaakceptowanymi akcentami obrazu.
7. Preview oraz kontrola: tempo, czytelność napisów, zgodność przebitek,
   brak przypadkowych cięć i bezpieczne obszary obrazu.
