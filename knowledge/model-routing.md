# Modele, jakość i kontrola kosztów

Obowiązuje zasada: maksymalna jakość, ale bez przepalania pieniędzy tam, gdzie tańsze rozwiązanie daje wynik tej samej jakości.

Wszystkie płatne modele są wywoływane przez OpenRouter. Lokalne narzędzia nie korzystają z API.

## Dobór specjalistów — decyzja 13.09.2026

Użytkownik wymaga taniego koordynatora i mocnych specjalistów dla każdego zadania. Pracujemy na CAŁEJ rolce 15-challenger-bordeaux-baza.mp4, bez zastępowania jej próbką. Wdrożono konfigurację Cline i komendy `reel:specialist`; instrukcja: `knowledge/specialist-operations.md`. Testy lokalne nie zastępują testu płatnych usług na całym Bordeaux. Takiego wywołania w ramach konfiguracji nie wykonano.

| Rola | Wybrany model / wykonawca | Zakres odpowiedzialności |
| --- | --- | --- |
| Koordynator Cline | `deepseek/deepseek-v4-flash-0731` | Stan workflow, wywołanie istniejących etapów, krótkie raporty; nie ocenia obrazu ani nie zastępuje specjalistów |
| Transkrypcja całego źródła | `microsoft/mai-transcribe-2` przez OpenRouter STT | Polski, verbatim, verbose_json, timestamp_granularities word; słownik nazw jako podpowiedź, nie przymusowa podmiana |
| Weryfikacja zgodności mowy i napisów | `google/gemini-3.1-pro-preview` | Całe audio oraz nowa transkrypcja, różnice z timestampami; nie wymyśla precyzyjnych czasów słów zamiast STT |
| Analiza wideo i wybranych assetów | `google/gemini-3.1-pro-preview` | Całe źródło i wybrane z indeksu ujęcia; identyfikacja, akcja, kontekst i niepewności |
| Reżyseria | `openai/gpt-5.6-sol-pro` | Jedno ograniczone zlecenie na kompletnym transkrypcie i analizie AV, pełny plan do akceptacji; bez wielokrotnego czytania repo i nadzoru renderu |
| Korekta ekspozycji, kadru, grafiki i końcowa kontrola AV | `google/gemini-3.1-pro-preview` + lokalne pomiary | Porównanie źródła, całego renderu i wzorca; osobno twarz, czerń, napisy, semantyka i audio |
| Timestampy, walidacja, render, pomiary i oczekiwanie | Istniejące narzędzia lokalne | Wykonanie deterministyczne; nie wymaga rozmowy modelu przez cały czas procesu |

To dobór na podstawie dostępności, funkcji i dostępnych dowodów jakości; żaden cennik nie dowodzi absolutnie najlepszego montażu. MAI-Transcribe-2 ma według Microsoft czołowe wyniki wielojęzyczne, polski i czasowanie słów. Scribe v2 jest mocnym specjalistą z dowodami dla polskiego, ale nie występuje w odczytanym katalogu STT OpenRouter; nie wprowadzamy po cichu innego konta. Gemini obsługuje audio i wideo, Sol Pro jest istniejącym specjalistą reżyserii, nie koordynatorem. Nowszy Gemini 3.8 Flash jest dostępny, lecz sam numer wersji nie dowodzi przewagi jakości nad Pro w tym zadaniu.

### Wierność transkrypcji

Zachowaj oddzielnie surowy wynik STT, zweryfikowany zapis dosłowny oraz warstwę napisów. Każda zmiana słów ma źródło i czas w audio. Nie zmieniaj kraju, miasta, nazwiska ani wyniku wyłącznie na podstawie wiedzy sportowej lub starego replacements. Korekta faktu wymaga osobnego sprostowania albo zmiany nagrania, nie podszywania się pod wypowiedziane słowa. Pomyłki rozpoznania poprawiamy na podstawie audio. Przed użyciem starych replacements przejrzyj je względem nowej transkrypcji. Zmiana liczby słów wymaga ponownego dopasowania czasów, nie dziedziczenia niezgodnych timestampów.

### Integracja i koszty

Komenda `reel:specialist transcribe` obsługuje endpoint OpenRouter `/api/v1/audio/transcriptions`. Zweryfikowany wynik instaluje `apply-transcript --approved`; do tego czasu aktywna transkrypcja pozostaje bez zmian. Nowa transkrypcja musi pokrywać całe 136,9 s; ewentualny podział techniczny ma zachować wszystkie fragmenty i globalne czasy.

Koordynator nie ma przejmować zadania specjalisty po błędzie. Zapisuje błąd i używa kontrolowanej ścieżki naprawy. Brak dostępnego specjalisty oznacza nieukończony etap. Nie uruchamiaj dodatkowych subagentów bez konkretnego zadania i budżetu.

Orientacyjne ceny katalogowe: DeepSeek 0731 0,04/0,08 USD za mln tokenów wejścia/wyjścia; Gemini Pro 2/12 USD; Sol Pro 2/10 USD. MAI-Transcribe-2 0,10 USD za godzinę audio, więc 136,9 s to około 0,0038 USD za pojedynczą transkrypcję, bez weryfikacji i retry. Przed wywołaniem sprawdź cenę dostawcy i warunki długości kontekstu.

Raport kosztów MUSI oddzielać koordynatora Cline, STT, analizę, reżyserię, QA i poprawki. Koszt nieznany zapisuj jako nieznany, nigdy zero. Limit kontrolowanego klienta nie ogranicza automatycznie sesji Cline. Wymagany jest wspólny limit i rozliczenie wszystkich etapów przed kolejnym płatnym krokiem. Nie sumuj niepełnych danych jako całkowitego rachunku.

Źródła sprawdzone 13.09.2026:
- https://openrouter.ai/api/v1/models
- https://openrouter.ai/api/v1/models?output_modalities=transcription
- https://openrouter.ai/docs/guides/overview/multimodal/stt
- https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe
- https://microsoft.ai/models/mai-transcribe-2/
- https://ai.google.dev/gemini-api/docs/video-understanding

## Złoty wynik i test tańszych modeli

Dla bieżącego zadania oceniaj całą rolkę Bordeaux. Nie zastępuj pracy próbką. Przy przyszłym porównaniu modeli używaj dokładnie tych samych materiałów i oceń:

- poprawność polszczyzny;
- jakość historii;
- zachowanie pełnych słów na granicach cięć;
- wybór hooka;
- rytm;
- zgodność z referencją;
- napisy;
- kadrowanie;
- ślepą ocenę użytkownika bez informacji, który model wykonał wariant.

Tańszy model przejmuje etap wyłącznie wtedy, gdy nie obniża jakości. Wynik porównania zapisz w `analysis/evals/`; nie opieraj decyzji na pojedynczym wrażeniu agenta.

## Obowiązkowy przebieg rolki

```text
materiał + polecenie użytkownika + referencje
                    ↓
analiza całego obrazu i dźwięku
                    ↓
poprawiona transkrypcja
                    ↓
reżyserski plan historii i cięć
                    ↓
automatyczna kontrola techniczna
                    ↓
render próbny
                    ↓
model ogląda preview i porównuje je z referencjami
                    ↓
maksymalnie 1–2 rundy poprawek
                    ↓
render finalny
                    ↓
ocena użytkownika trafia do pamięci stylu
```

Jeżeli dwie rundy poprawek nie wystarczą, zatrzymaj pipeline i pokaż konkretny problem. Nie uruchamiaj kolejnych płatnych prób automatycznie.

## Oszczędzanie bez utraty jakości

- Remotion, FFmpeg, wykrywanie twarzy, metadane, timestampy i walidacja działają lokalnie.
- Materiał wysłany do modelu wideo wykorzystuj ponownie, jeśli OpenRouter i wybrany provider udostępniają identyfikator pliku albo cache.
- Jeżeli ponowne użycie pliku nie jest dostępne, korzystaj z lokalnej analizy i wybranych fragmentów zamiast ponownie wysyłać cały film bez potrzeby.
- Stałe instrukcje i bibliotekę stylu układaj tak, aby korzystały z cache promptu.
- Masową analizę referencji wykonuj w tańszym trybie Batch, jeśli jest dostępny dla wybranego modelu i czas wykonania nie jest krytyczny.
- Nie wysyłaj całego filmu do modelu reżyserskiego. Powinien otrzymać transkrypcję, analizę audiowizualną i tylko potrzebne klatki.
- Nie twórz agentów rozmawiających ze sobą, jeśli jeden kontrolowany przebieg daje ten sam wynik.
- Tani model obsługuje przypadki łatwe; mocny model podejmuje decyzje wpływające na historię i jakość.

## Budżet

Roboczy cel po optymalizacji:

- prosta rolka: około 0,20–1 USD;
- trudny materiał z analizą referencji i kontrolą: około 1–3 USD;
- pierwsze eksperymenty i strojenie mogą kosztować więcej.

To są cele, nie gwarantowane ceny. Przed wdrożeniem pobierz aktualne ceny z OpenRouter. Pipeline ma zapisywać rzeczywisty koszt każdego etapu, na przykład:

```text
Whisper lokalny              $0.00
analiza wideo                $0.08
korekta polskiego            $0.04
plan reżyserski              $0.21
kontrola preview             $0.11
render lokalny               $0.00
RAZEM                        $0.44
```

Każde zadanie musi mieć limit kosztu. Przekroczenie limitu wymaga zgody użytkownika przed następnym płatnym wywołaniem.

## Pamięć stylu

Ocena użytkownika nie trenuje automatycznie modelu. Zaakceptowane i odrzucone decyzje zapisuj jako dane projektu:

- zaakceptowane rolki i ich opisy w `examples/`;
- potwierdzone reguły w `knowledge/`;
- parametry zaakceptowanych animacji jako komponenty Remotion;
- wyniki porównań modeli w `analysis/evals/`;
- uwagi do konkretnego zadania w `instructions/jobs/`.

Nie przenoś pojedynczej preferencji do globalnych reguł stylu bez potwierdzenia użytkownika.

Aktywnym źródłem danych jest `knowledge/style-memory.json`. Waliduj je przez `npm run style:validate`. Nową, jawnie potwierdzoną decyzję można dopisać przez `npm run style:record -- ...`; komenda wymaga powodu, reguły, dowodu i flagi `--user-confirmed`, a istniejącego ID nie nadpisuje po cichu. Skompilowana pamięć jest automatycznie dołączana do pakietu Semantycznego Reżysera.

## Preferencja kosztowa dla serii rolek (decyzja 2026-09-20)

Na polecenie użytkownika, począwszy od rolek #2–#13 (MVI_2000), obowiązuje:

- **Transkrypcja**: lokalny Whisper (domyślnie `mlx-community/whisper-large-v3-turbo`), zamiast płatnego MAI-Transcribe-2.
- **Weryfikacja**: tani model (np. `gpt-4.1-mini` / `gpt-4o`) albo zestawienie transkrypcji ze scenariuszem (scenariusz zawiera poprawne nazwy i poprawną polszczyznę). Zamiast drogiego Gemini Pro na pełnym materiale.
- **Zastrzeżenie techniczne**: lokalny Whisper bywa w tym środowisku zawodny (przy `#1.mp4` zawisł — 0% CPU, mała ilość wolnej pamięci na dużego modelu). Dlatego: używać Whispera, ale gdy zawisnie/niedostępny, NIE pomijać reguły po cichu — zgłosić i wybrać kontrolowaną ścieżkę ratunkową (np. mniejszy Whisper, mniejsze dane, rekord błędów).
- **Rekordy reżyserii**: płatny semantyczny reżyser (`gpt-5.6-sol-pro` / Sol) na pełnej liście assetów bywa kosztowny i wrażliwy na ucięcie odpowiedzi (MAX_OUTPUT_TOKENS przy dużym prompcie/xhigh). Przed płatnym etapem reżyserii ograniczyć pakiet assetów do istotnych dla danej rolki albo podnieść `max_completion_tokens`/złagodzić reasoning — za każdym razem z zaakceptowanym limitem.
