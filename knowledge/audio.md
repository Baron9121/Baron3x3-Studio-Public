# Audio

## Reguły startowe

- Priorytetem jest czytelna mowa bez przesterowania.
- Nie normalizuj ani nie odszumiaj destrukcyjnie pliku wejściowego; operacje wykonuj na kopii roboczej.
- Muzyka i efekty nie mogą utrudniać zrozumienia wypowiedzi.
- Dostępne lokalne SFX to `whoosh`, `impact` i `click`; ich źródła i zastosowanie opisuje `assets/sfx/README.md`.
- Domyślne poziomy SFX: `whoosh 0.14`, `impact 0.22`, `click 0.09`. Twarde maksima: odpowiednio `0.18`, `0.24`, `0.12`; walidator odrzuca wyższe wartości.
- Każdy SFX ma obwiednię attack/release i `speechDucking` w zakresie 0.4–1.0, domyślnie 0.72. Dzięki temu impuls nie przykrywa sylaby ani nie kończy się twardym kliknięciem.
- `whoosh` stosuj przy wyraźnej zmianie skali lub wejściu B-rollu, `impact` wyłącznie na statystykę albo najmocniejszą puentę, a `click` na lekki element interfejsowy, ramkę lub waveform.
- Nie dodawaj SFX na każdym cięciu. Referencja grupuje impulsy przy mocnych transformacjach, a wiele zwykłych zmian obrazu pozostawia bez efektu.
- Nie dodawaj efektu dźwiękowego bez odpowiadającego mu cięcia, przejścia, karty albo wyraźnej puenty.

## Do nauczenia

- Docelowa głośność mowy:
- Poziom muzyki względem mowy:
- Preferowane odszumianie:
- Preferowana częstotliwość SFX: oszczędna; wyłącznie akcenty narracyjne i duże zmiany wizualne.

## Zaakceptowany wzorzec

- 2026-09-06: użytkownik wybrał wariant `B` z testu R1 dla rolki Adriana Boguckiego.
- Wzorzec B oznacza: mowa pozostaje na pierwszym planie, `speechDucking: 0.72`, obwiednie attack/release, osobny `click` dla waveform/UI, `impact` dla statystyki oraz oszczędne `whoosh` tylko przy dużych zmianach wizualnych.
- Plik wzorcowy A/B: `output/r1-b-reference-ducked.mp4`. Pełny zaakceptowany render: `output/16-adrian-bogucki-baza-render.mp4`.
