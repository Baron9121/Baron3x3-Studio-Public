# Standard wywiadów Baron3x3

Lokalna adaptacja zasad z dokumentu `MONTAZ-WYWIADOW-KATOWICE.md` wskazanego przez użytkownika. Dokument źródłowy był referencją; stary projekt nie jest zależnością tego pipeline’u.

## Historia i cięcia

- Jedna rolka opowiada jedną zamkniętą historię, zwykle w 25–45 sekund.
- Zaczynaj od pytania, mocnej tezy albo interesującej odpowiedzi; kończ pełnym zdaniem lub puentą.
- Usuwaj wyłącznie zbędne pauzy, powtórzenia, kaszel, zawahania i błędne podejścia.
- Nie tnij sylab, końcówek słów ani oddechu należącego do frazy. Każdą granicę sprawdź z timestampami słów.
- Nie dodawaj górnego tytułu ani podpisu osoby bez wyraźnego polecenia.

## Obraz

- Format 1080x1920, 30 fps.
- Kadruj aktualnie mówiącą osobę; oczy, twarz i mikrofon nie mogą być przypadkowo ucięte.
- Zoomy wynikają ze znaczenia: teza, liczba, nazwa, cel, puenta lub zmiana wątku. Typowy zakres 1,015–1,12, płynnie przez 10–20 klatek.
- Pipeline odczytuje model kamery, Tone Curve/Picture Style, gamut, transfer, macierz, zakres i ISO przez ExifTool oraz FFprobe. LUT wejściowy dobiera z **profilu nagrania**, nie z samej nazwy aparatu. W plikach Cinema EOS ogólne MakerNotes `Standard/sRGB` nie są wystarczającym dowodem, że obraz jest już Rec.709 — jeśli transfer pozostaje `unknown`, render ma się zatrzymać i wymagać jawnego `sourceColorProfile`. Canon Log 2/3 korzysta wyłącznie ze zgodnego oficjalnego LUT-u Canona. Kreatywny look jest osobną warstwą po transformacji wejściowej.

## Napisy

- Produkcyjny Whisper musi mieć polski język, timestampy słów, słownik Baron3x3 i osobną korektę językową.
- Zawsze zapisuj `3x3`; weryfikuj nazwiska, miasta, daty i terminy turniejowe.
- Domyślny styl: Arial Black / Arial, 66 px, biały tekst. Aktywne słowo również pozostaje białe, ma cienki czarny obrys i dokładnie pierwotne zielone tło `#39E508`. Bez dodatkowej ramki; tło ma obejmować samo słowo bez poprzedzającej spacji.
- Wyświetlaj 2–3 słowa na planszę. Interpunkcja (`.`, `,`, `?`, `!`, `:`, `;`, `…`) kończy planszę, a następne słowo zaczyna nową. Na ekranie pozostawiaj tylko `!` i `?`; pozostałe znaki są niewidoczne. Dziel czterowyrazową frazę na 2+2 zamiast 3+1.
- Dla rolek studyjnych można jawnie wybrać `white-outline`: białe wersaliki, czarny obrys i cień, bez zielonego tła.

## Przebitki i dźwięk

- Przebitka musi odpowiadać treści, być wyciszona i zwykle trwać 2,5–4,5 s.
- Akcji sportowej nie kończ przed koszem, blokiem, przechwytem, zbiórką albo jednoznacznym końcem posiadania. Zostaw 0,2–0,7 s po rezultacie.
- Głos wywiadu ma grać nieprzerwanie pod przebitką.
- Eksport: H.264, CRF 18, `yuv420p`, AAC 256 kb/s. Punkt startowy miksu: około −14 do −15 LUFS i true peak do −1 dBTP, po odsłuchu.
