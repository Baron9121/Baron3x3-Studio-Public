# Porównanie kolejnej rolki ze wzorcem Baron3x3

Obowiązuje również `knowledge/editing-precision.md`: standard precyzji Adriana, weryfikacja materiałów, pełna oś montażu, zgodność wersji i obowiązkowa kontrola redakcyjna wyniku. Przed nagraniem czasy pozostają planowane; weryfikację na rzeczywistej osi wykonaj po otrzymaniu MP4.

Wzorcem bazowym jest `examples/adrian-bogucki-approved/`. Porównanie wykonuj bez informacji, jaki model przygotował kandydat.

## Warunki twarde

- brak reguły z `hardBans` w `knowledge/style-memory.json`;
- pełne słowa na granicach cięć i poprawna polszczyzna;
- zgodny semantycznie B-roll, pełna kulminacja akcji i brak przypadkowych powtórek;
- lokalne `qa:preview` i `qa:attention` zaliczone;
- brak planszy na twarzy oraz brak ucięcia głównego bohatera.

## Ocena 100 punktów

- historia i hook: 20;
- semantyczny dobór obrazu: 20;
- rytm cięć i zoomów: 15;
- polszczyzna i napisy: 15;
- efekty, grafiki i zgodność z pamięcią stylu: 15;
- kadrowanie i czytelność: 10;
- dźwięk: 5.

Wynik poniżej 85/100 albo naruszenie warunku twardego oznacza, że pipeline nie generalizuje jeszcze poprawnie. Ocena użytkownika ma wskazać konkretne `decisionId`, które potwierdza, zmienia albo odrzuca; nowa globalna reguła wymaga jawnego potwierdzenia.
