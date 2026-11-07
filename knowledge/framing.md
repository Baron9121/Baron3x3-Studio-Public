# Kadrowanie

## Reguły startowe

- Format bazowy: 1080x1920, 30 fps.
- Twarz i kluczowe elementy utrzymuj poza obszarem zasłanianym przez interfejs platformy.
- Ważny tekst trzymaj co najmniej 80 px od boków i 100 px od góry oraz dołu.
- Przed uznaniem renderu za finalny uruchom `npm run qa:attention -- NAZWA.mp4`.
- Główna twarz jest twardo chroniona przed planszami, napisami i ucięciem przy krawędzi. Małe twarze publiczności są tylko wskazówką, nie automatycznym błędem.
- Obszary `textLike`, `salient` i `roundCandidates` pomagają wybrać wolną przestrzeń, ale nie wolno nazywać kandydata piłką, obręczą lub herbem bez potwierdzenia semantycznego albo ręcznego opisu.
- Dostępne strefy plansz to `top`, `top-left`, `top-right` i `center`; wybieraj strefę o najniższym konflikcie, preferując stabilne `top`, jeśli jest bezpieczne.

## Do nauczenia

- Bazowy crop `wide`: mnożnik 1,00 względem ręcznie ustawionego kadru bazowego.
- Kadr `medium`: mnożnik 1,16 względem kadru bazowego.
- Kadr `close`: mnożnik 1,30 względem kadru bazowego.
- Czas przejścia zoomu: około 0,42 s, bez odbicia.
