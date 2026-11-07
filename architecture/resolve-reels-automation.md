# Decyzja architektoniczna: automatyczny montaż paczki rolek

## Wejście

Użytkownik dostarcza do `input/` paczkę 10–15 **już pociętych** plików MP4.
Każdy plik jest jedną niezależną rolką. Automat nie dzieli surowego nagrania
na tematy i nie tworzy master timeline'u.

```text
input/
├── 01-powrot-fredette.mp4
├── 02-rzut-za-dwa.mp4
├── 03-lider-miami.mp4
└── ...
```

## Wykonanie

Dla każdego pliku automat:

1. odczytuje istniejący scenariusz/instrukcję, jeśli jest dostępny;
2. robi lub odczytuje transkrypcję słowo po słowie;
3. analizuje gotową wypowiedź, aby zaplanować B-roll, napisy, zoomy, efekty i audio;
4. tworzy jeden timeline Resolve o nazwie pliku;
5. dodaje natywne, edytowalne Text+, przebitki i zatwierdzone efekty Fusion;
6. renderuje preview, przeprowadza QA i zapisuje finalny MP4.

Każdy timeline, EditPlan, preview, rewizja i render są odizolowane. Awaria lub
poprawka jednej rolki nie zmienia żadnej pozostałej.

## Styl

Profil `Baron3x3 Dynamic` zostanie stosowany do każdej rolki:

- napisy Text+ po 2–3 słowa, bez interpunkcji i z nowym pojawieniem po kropce;
- zielone słowo aktywne;
- B-roll wyłącznie z zatwierdzonej biblioteki;
- zoomy i krótkie efekty tylko przy uzasadnionych momentach;
- flash, glitch, RGB split, shake i blur z limitami częstotliwości;
- SFX sparowane z istotnymi akcentami;
- preview i QA przed finalnym renderem.

## Rezultat

Po jednym poleceniu automat przechodzi całą paczkę, a użytkownik otrzymuje
pojedyncze timeline'y Resolve oraz osobne pliki wynikowe dla każdej pozycji.
