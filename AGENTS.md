# Aktualny proces Studio — 29.09.2026

Na polecenie użytkownika główną ścieżką jest lokalne Studio opisane w `CLAUDE.md`, `.claude/skills/baron3x3-montaz/SKILL.md` i `docs/STUDIO.md`. W montażu Studio używaj `npm run baron -- ...`. Wymagania niżej dotyczące Cline, specialist, OpenRouter, Gemini, DaVinci i `npm run pipeline` są historyczne; nie obowiązują nowej ścieżki. Zachowaj ochronę materiałów, precyzję redakcyjną i jawne akceptacje. Nie usuwaj legacy podczas migracji. Testy techniczne z syntetycznymi danymi nie wymagają akceptacji redakcyjnej użytkownika.

---

# Baron3x3 — zasady pracy agenta

To jest czysty, lokalny projekt montażu rolek. Głównym interfejsem jest VS Code z agentem Cline. Modele płatne są dostępne wyłącznie przez zaakceptowany przez użytkownika klucz OpenRouter. Nie używaj agenta Cursora, Roo Code, Aidera ani OpenCode.

## Wznawianie pracy i instalacja

- Przed każdą pracą instalacyjną przeczytaj `INSTALLATION.md` oraz `SETUP-STATUS.md`.
- Kontynuuj od pierwszego nieukończonego etapu. Nie powtarzaj zaliczonych testów API bez wykazania, że przestały działać.
- Po każdym etapie natychmiast zaktualizuj `SETUP-STATUS.md`, podając test, wynik i rzeczywisty koszt API.
- Wykonuj tylko jeden etap instalacji naraz. Nie rozpoczynaj następnego, dopóki bieżący nie spełnia warunków zaliczenia.

## Bezpieczeństwo

- Nie czytaj, nie kopiuj i nie modyfikuj starego projektu `Baron3x3-Reels`.
- Pracuj wyłącznie w tym folderze, chyba że użytkownik jawnie wskaże kopię pliku testowego.
- Materiały źródłowe trafiają do `input/`; nigdy ich nie nadpisuj.
- Pliki pośrednie trafiają do `analysis/`, a gotowe rendery do `output/`.
- Nigdy nie odczytuj, nie wyświetlaj ani nie zapisuj klucza OpenRoutera w plikach projektu, logach lub odpowiedziach.

## Cline jako koordynator

Obowiązuje `.clinerules/00-specialist-coordinator.md` i `knowledge/specialist-operations.md`. Cline uruchamia specjalistów przez `reel:specialist`; nie zastępuje ich własną reżyserią, transkrypcją ani oceną obrazu. Ta reguła zastępuje wcześniejsze domyślne przypisanie tych prac do Cline.

## OpenRouter i koszty

- Przed wyborem modelu i budżetu przeczytaj `knowledge/model-routing.md`; jest to obowiązująca polityka jakości i eskalacji.
- Whisper, metadane, walidację, FFmpeg i render Remotion wykonuj lokalnie, jeśli nie obniża to jakości.
- Model wideo wykorzystuj do rozumienia obrazu, dźwięku i referencji; model reżyserski wykorzystuj do decyzji dotyczących historii i montażu.
- Nie wysyłaj ponownie tego samego materiału, jeśli można użyć istniejącego identyfikatora pliku, cache albo zapisanej analizy.
- Nie obniżaj jakości tylko po to, aby użyć tańszego modelu. Tańszy model przejmuje etap dopiero po przejściu testów porównawczych.
- Wykonuj maksymalnie dwie automatyczne rundy poprawek jednego renderu. Następnie zatrzymaj zadanie i opisz problem.
- Każde zadanie API ma zapisywać model, zużycie i koszt bez zapisywania sekretów.
- Przekroczenie skonfigurowanego limitu kosztu ma zatrzymać zadanie przed kolejnym płatnym wywołaniem.

## Instrukcje z promptu użytkownika

- Dla nowej rolki w Cline używaj `.clinerules/workflows/baron3x3-montaz.md` oraz komend `reel:*`. Najpierw odczytaj zapisany `workflow/state.json` i wykonaj wyłącznie jego `nextAction`; nie omijaj stanów akceptacji bezpośrednimi komendami starszego pipeline'u.
- Dla pliku `input/NAZWA.mp4` zapisuj dodatkowe instrukcje w `instructions/jobs/NAZWA.json`, w polu `instructions`.
- Nie streszczaj instrukcji w sposób, który usuwa warunki lub wyjątki. Zachowaj oryginalny sens promptu.
- Na podstawie promptu, transkrypcji i `knowledge/interview-standard.md` uzupełnij `sourceRanges`, `overlays`, styl napisów i kadrowanie.
- Nigdy nie usuwaj istniejących `sourceRanges`, notatek ani korekt, jeśli użytkownik prosi wyłącznie o zmianę kadrowania lub stylu.
- Kadrowanie zapisuj wyłącznie wewnątrz każdego elementu `sourceRanges`: `scaleFrom`, `scaleTo`, `objectPosition` i opcjonalnie `translate` w formacie `"100px 10px"`. Pole główne `cropping` nie istnieje.
- Ustaw `status` na `ready` dopiero po sprawdzeniu, że rolka opowiada jedną zamkniętą historię, a granice cięć nie urywają słów.
- Jeśli prompt jest niejednoznaczny w kwestii wyboru historii, pozostaw `needs-instructions`; nie renderuj całego pliku jako finalnego montażu.

## Obowiązkowa precyzja montażu

Przed planowaniem i oceną rolki przeczytaj `knowledge/editing-precision.md` i stosuj cały standard Adriana. Gotowa pocięta baza zachowuje pełną wypowiedź, o ile użytkownik nie zleci skracania. Każdy wybrany asset wymaga obejrzenia, cała oś wymaga reżyserii, a gotowość redakcyjna wymaga oglądania i odsłuchu wyniku. Sam stan `complete` nie potwierdza jakości.

## Kolejność pipeline’u

1. Odśwież katalog zdjęć i wideo przez `npm run assets:scan` i przeczytaj `assets/MATERIALY.md`. Pipeline wykonuje ten skan także automatycznie.
2. Sprawdź wejściowy MP4 i jego metadane.
3. Użyj MAI-Transcribe-2 przez reel:specialist transcribe i Gemini Pro verify-transcript. Zweryfikowany tekst zastosuj przez apply-transcript. Lokalny Whisper jest zachowaną ścieżką legacy, nie cichym zamiennikiem specjalisty.
4. Popraw nazwy własne, polską fleksję i interpunkcję w pliku `instructions/jobs/NAZWA.replacements.json`.
5. Przygotuj plan cięć w `instructions/jobs/NAZWA.json`. Zalecana długość to 25–45 s, chyba że pełna myśl wymaga więcej.
6. Dla każdej planowanej przebitki najpierw wyszukaj materiał użytkownika w `assets/MATERIALY.md`. W `overlays` używaj stabilnego `assetId` z katalogu; `assetFile` pozostaje wyłącznie zgodnością wsteczną dla plików bezpośrednio w `assets/`.
   Każda przebitka musi mieć świadomy `presentation` i `motion` zgodnie z `knowledge/broll.md`. Automatycznie wolno wybierać tylko `full`, `editorial` albo uzasadnione `archive`; eksperymentalne `split`, `stack` i `cutout` wymagają osobno zaakceptowanego przykładu. `paper-reveal`, `paper-collage` i wszystkie ich składowe są pominięte i zabronione.
   Domyślne minimum jednej sceny to 3000 ms. Nie powtarzaj `assetId`, gdy dostępny jest inny semantycznie właściwy materiał. Ostatnia plansza dochodząca do końca filmu ma pozostać widoczna (`fadeOut: false`).
7. Uruchom `npm run broll:plan -- NAZWA.mp4`. Przeczytaj `analysis/NAZWA/broll-plan.md`; pokaż użytkownikowi propozycje, braki i pokrycie. Nie wpisuj propozycji do planu bez jawnej akceptacji.
8. Jeśli raport wykazuje brak miasta, areny lub neutralnego kontekstu, użyj modułu opisanego w `assets/STOCKS.md`. Najpierw utwórz raport `stock:search`. Nie pobieraj wyniku bez wskazania konkretnego ID i akceptacji użytkownika; nigdy nie pozyskuj automatycznie herbów.
9. Po zatwierdzonym pobraniu ponownie uruchom B-roll Planner. Po akceptacji jego raportu uruchom `npm run broll:apply -- NAZWA.mp4 --approved`. Ta komenda tylko wpisuje zatwierdzone propozycje do `overlays` i nie renderuje filmu.
10. Gdy zadanie dotyczy kadrowania, uruchom `npm run frames -- NAZWA.mp4`, przeczytaj `analysis/NAZWA/framing-analysis.json` i obejrzyj wszystkie wygenerowane PNG z `analysis/NAZWA/review-frames/` przed edycją planu.
11. Przeczytaj `knowledge/reference-roadmap.md`, zwaliduj `knowledge/style-memory.json` komendą `npm run style:validate` i zastosuj skompilowane `acceptedRules` oraz `hardBans`. Nie dopisuj nowych reguł stylu bez jawnego potwierdzenia i dowodu w `examples/`. Efekty wizualne zapisuj w `effectCues`, a lokalne akcenty dźwiękowe w `soundEffects`.
12. Silny efekt lub SFX musi mieć zapisane uzasadnienie w planie. Nie dodawaj losowych efektów tylko po to, aby zwiększyć dynamikę; w jednym momencie stosuj najwyżej jeden efekt silny, z wyjątkiem pary `film-frame` + `rec`.
13. Dla montażu premium przygotuj lokalny pakiet przez `director:prepare`, a płatne etapy uruchamiaj tylko z zaakceptowanym limitem. Przeczytaj `director/proposal.md`; nie stosuj go bez jawnej akceptacji użytkownika.
14. Wygeneruj EDL, napisy słowo po słowie i render do `output/`.
15. Uruchom `npm run qa:attention -- NAZWA.mp4`, a następnie `npm run qa:preview -- NAZWA.mp4`. Finalna komenda pipeline renderuje najpierw plik kontrolny i dopiero po przejściu obu lokalnych bramek atomowo nadaje mu nazwę `NAZWA-render.mp4`; nieudany preview nie może zastąpić ostatniego poprawnego renderu. Dopiero potem sprawdź semantycznie synchronizację napisów, każde łączenie wypowiedzi, poziom SFX oraz zgodność przebitek z wypowiadanym tekstem. Dla każdego stocku potwierdź zapis w `assets/STOCK-LICENSES.md`.

## Uruchamianie i render

- Nie montuj ani nie kadruj finalnego filmu bezpośrednią komendą `ffmpeg`.
- Jedyną komendą finalnego renderu jest `npm run pipeline -- NAZWA.mp4`, uruchomiona w głównym folderze projektu.
- Nazwa `NAZWA-render.mp4` oznacza gotowy wynik. Plan i wejście nadal nazywają się `NAZWA.json` oraz `input/NAZWA.mp4`; nie twórz planu z dopiskiem `-render`.
- Przed renderem uruchom `npm run pipeline -- NAZWA.mp4 --no-render`. Jeśli walidacja zgłasza błąd, popraw plan; nie obchodź walidacji inną komendą.

## Rozwój stylu

Zaakceptowane rolki zamrażaj w `examples/`, a każdą decyzję zapisuj w `knowledge/style-memory.json` ze statusem, powodem, dowodem i `userConfirmed: true`. `accepted` może wejść do automatycznego kontraktu; `rejected` jest twardym zakazem; `experimental` pozostaje wyłączone. Najpierw reguły i przykłady; fine-tuning modelu dopiero wtedy, gdy zgromadzone dane pokażą, że jest potrzebny.

## Scenariusze z rozmowy

- Gdy użytkownik tworzy lub poprawia scenariusz w czacie, aktualizuj odpowiadający mu plik `instructions/scenarios/<id>-scenariusz.md` i tekst do nagrania. Utrzymuj jedną spójną wersję tabel i bilansu; nie dopisuj sprzecznych wariantów na końcu.
- Przy uruchamianiu montażu powiąż MP4 z tym plikiem przez `reel:start --scenario-file`; szczegóły w głównym workflow. Nie zgaduj powiązania, gdy istnieje więcej niż jeden pasujący scenariusz.
- Przed akceptacją reżyserii pokaż `director/review-plan.md` wraz z `proposal.md`. Raport obejmuje również zachowane ręczne ustawienia i zdjęcia wewnątrz animacji. Renderuj dopiero wersję zgodną z zaakceptowanym raportem.
