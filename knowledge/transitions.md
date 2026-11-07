# Przejścia

## Reguły startowe

- Dla wywiadu studyjnego rytm obrazu budują trzy konfiguracje: `wide` (100%, odpowiednik pierwszego screena), `medium` (pośredni, odpowiednik trzeciego screena) oraz `close` (maksymalny, odpowiednik drugiego screena).
- Zmieniaj poziom przede wszystkim na początku mocnej tezy, kontraście, ważnej liczbie lub puencie.
- Zoom grupuje kilka krótkich beatów tekstowych w jeden stabilny blok obrazu. Domyślnie jeden poziom utrzymuj 4–7 s; 3 s jest minimum dla wyjątkowo mocnej puenty. Nie zmieniaj kadru co 1–2 s tylko dlatego, że zaczyna się nowe zdanie.
- Każdy nowy blok obrazu po otwarciu ma widoczne, ale krótkie przejście. Nie wolno pozostawić serii samych `smooth`, bo daje to mechaniczne przeskoki skali.
- Przejście zoomu trwa do około 0,64 s i używa beziera z mikroskopijnym overshootem oraz stabilizacją końcową.
- `blur` oznacza optyczny zoom blur skupiony na twarzy, a nie równomierne rozmycie całej klatki. `rgb` oznacza subtelną aberrację chromatyczną do 8 px bez czerwono-niebieskich pasów. `split` rozsuwa połówki najwyżej o 13 px i dodaje delikatne rozmycie krawędzi.
- Na najmocniejszych przejściach do `close` stosuj naprzemiennie trzy czytelne efekty: `blur` (do 6 px), `rgb` (czerwono-turkusowe rozszczepienie do 16 px) oraz `split` (rozsunięcie połówek obrazu do 22 px). Efekt osiąga maksimum w połowie przejścia i całkowicie znika po 0,42 s.
- W fragmentach bez wyraźnego akcentu zmieniaj poziom w deterministycznie zróżnicowanych odstępach 3–6 s. Nigdy nie używaj niedeterministycznej losowości podczas renderu.

## Do nauczenia

- Dozwolone przejścia: `smooth`, `blur`, `rgb`, `split`.
- Długości przejść: do około 19 klatek przy 30 fps.
- Efekty `blur`, `rgb` i `split` są zakazane przy zwykłej zmianie kadru i nie mogą pozostawać na obrazie po zakończeniu zoomu.
- Dodatkowe przejścia pełnoekranowe i stylizacje opisuje `knowledge/effects.md`. `whip`, `flash` i `light-leak` stosuj tylko na uzasadnionym akcencie narracyjnym lub zmianie rodzaju materiału.
