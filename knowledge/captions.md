# Napisy

## Reguły startowe

- Format danych odpowiada typowi Remotion `Caption`: `text`, `startMs`, `endMs`, `timestampMs`, `confidence`.
- Napisy muszą pozostać w bezpiecznym obszarze pionowego kadru.
- Transkrypcję nazw własnych i terminów koszykarskich sprawdzaj przed finalnym renderem.
- Model produkcyjny: `mlx-community/whisper-large-v3-turbo`; model tiny służy wyłącznie do testów technicznych.
- Każda plansza napisów zawiera 2–3 słowa. Dłuższe frazy dziel równomiernie, aby nie zostawiać samotnego słowa na kolejnej planszy.
- Kropka, przecinek, dwukropek, średnik i wielokropek zawsze zamykają planszę, ale nie są wyświetlane. Następne słowo musi rozpocząć nową planszę.
- Wyświetlaj wyłącznie pytajnik i wykrzyknik; one również zamykają planszę.
- Granica cięcia również zawsze zamyka planszę napisów.
- Aktualnie wypowiadane słowo pozostaje białe z cienkim czarnym obrysem. Zaznaczaj je dokładnie pierwotnym zielonym tłem `#39E508`, bez dodatkowej ramki. Tło ma obejmować samo słowo — nie obejmuje spacji przed nim — i używa tylko 1 px pionowego oraz 3 px poziomego wypełnienia. Nie zmieniaj aktywnego słowa na czarne.
- Alternatywny tryb `white-outline` stosuj tylko wtedy, gdy instrukcja konkretnej rolki tego wymaga.
- Każda rolka ma osobny plik korekt w `instructions/jobs/NAZWA.replacements.json`.

## Do nauczenia

- Krój: Arial Black / Arial, 66 px, grubość 900.
- Pozycja: około 1320 px od góry, 72 px marginesu po bokach.
