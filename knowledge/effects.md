# Efekty wizualne i karty

## Dostępna biblioteka

- `flash` — bardzo krótki biały błysk na cięciu lub najmocniejszym akcencie.
- `whip` — kierunkowe smugi (`left` albo `right`) do przejścia między wyraźnie różnymi ujęciami.
- `light-leak` — organiczne prześwietlenie optyczne/taśmowe do zmiany sceny lub wejścia materiału archiwalnego; bez geometrycznych kolorowych pasów.
- `film-frame` — przyciemniona winieta i jasna ramka dla fragmentu stylizowanego na materiał archiwalny.
- `rec` — migający znacznik nagrania; stosuj razem z `film-frame`, gdy sens ujęcia uzasadnia konwencję kamery.
- `stat-card` — czarna pełnoekranowa karta z dużą liczbą i krótkim opisem.
- `kinetic-text` — pojedyncza, krótka teza umieszczona w wolnej przestrzeni; label i słowa wchodzą sekwencyjnie, a ostatnie słowo może być głównym akcentem.

## Pominięte i zablokowane

- Cały kierunek `paper-reveal` / `paper-collage` został pominięty decyzją użytkownika po dwóch niezaakceptowanych próbach.
- Zakaz obejmuje gazetową ścianę, kolorowe zakładki, papierowe karty zdjęciowe, rozdarcia/szwy oraz motion-poster lub cutout zaproponowany jako kontynuacja tego kierunku.
- Te elementy nie są częścią dostępnej biblioteki, schematu reżysera ani walidowanego planu.

## Reguły użycia

- Efekt ma podkreślać konkretny beat narracyjny lub zmianę materiału, a nie maskować brak sensownej przebitki.
- `flash` i `whip` trwają zwykle 0,20–0,55 s, a `light-leak` około 0,55–0,90 s. Nie nakładaj ich na każdą zmianę kadru.
- Nie wracaj do `paper-reveal`, `paper-collage` ani ich składowych bez nowej, jawnej decyzji użytkownika.
- Efekt `glitch` z czerwono-niebieskimi prostokątami jest wycofany i pipeline ma go odrzucać.
- `stat-card` pokazuj od momentu wypowiedzenia pierwszej liczby do końca ostatniej statystyki, zwykle 2,0–3,0 s. Nie trzymaj karty przez dalszą część zdania tylko dlatego, że beat jest dłuższy.
- Liczby na `stat-card` są licznikami: startują od zera, dochodzą do wartości przez około 0,9 s, a kolejne metryki wchodzą z przesunięciem około 0,24 s. Jednostka pojawia się dopiero pod koniec liczenia.
- Styl liczb odwzorowuje referencję: czarne tło z bardzo subtelną czerwoną głębią, gradient biały–różowy–czerwony, miękka poświata i krótki błysk wejściowy. Bez neonowych ramek, geometrycznych pasów i przypadkowego glitchu.
- Nie nakładaj dwóch silnych efektów w tym samym czasie. Dopuszczalne połączenie to `film-frame` + `rec`.
- Napisy pozostają nad efektami przejścia, ale karta statystyczna może czasowo zastąpić zwykły obraz.
- `kinetic-text` nie może powtarzać pełnego zdania z napisów. Używaj krótkiej tezy, kontrastu albo puenty; zwykle maksymalnie 2–5 słów plus krótki label.
- Dla położenia `top` gradient czytelności obejmuje wyłącznie górną wolną przestrzeń. Plansza nie może przyciemniać całego kadru ani nachodzić na twarz lub dolne napisy.
- Zaakceptowany wzorzec R2: `LIDER / TO NIE TYLKO PUNKTY` z sekwencyjnym wejściem słów, ostatnim słowem w biało-różowo-czerwonym gradiencie i subtelnymi liniami akcentu. Bez papieru, ramek gazetowych i wycinanek.
- Domyślna intensywność to `1.0`; zakres techniczny wynosi 0.1–1.5. Przekraczaj 1.0 tylko po kontroli preview.

## Format planu

```json
{
  "effectCues": [
    {
      "type": "whip",
      "timelineStartMs": 4200,
      "timelineEndMs": 4680,
      "direction": "right",
      "intensity": 0.9
    },
    {
      "type": "stat-card",
      "timelineStartMs": 8100,
      "timelineEndMs": 9800,
      "value": "12",
      "label": "PUNKTÓW W MECZU",
      "accentColor": "#ff174f"
    }
  ]
}
```

Pipeline odrzuca nieznany typ, niepoprawny czas, kartę bez liczby oraz efekt wychodzący poza długość rolki.
