# Darmowe stocki

## W montażu Studio

Stock jest opcjonalny i dosłowny: pojawia się tylko wtedy, gdy w scenariuszu pada konkretne miejsce lub rzecz. Turniej w mieście → miasto z lotu ptaka, rynek albo charakterystyczny budynek. Kraj → flaga, klub → herb, pieniądze → liczarka banknotów, podróż → samolot. Bez metafor.

Motywy wypisuje agent ze scenariusza do `work/stock-motywy.json`:

```json
[{"id": "M01", "fraza": "Challenger w Atenach", "rodzaj": "miasto", "nazwa": "Athens", "aliasy": ["Ateny"]},
 {"id": "M02", "fraza": "pula nagród 100 tysięcy dolarów", "rodzaj": "pieniadze"}]
```

Rodzaje i szablony zapytań są w `config/stock.json`. Dla miasta, kraju, klubu i obiektu wynik przechodzi tylko, gdy nazwa lub alias jest w tytule, opisie albo adresie źródła, bo niepodpisany widok może być innym miastem. Własne `zapytania` zastępują szablony. `typ: image` szuka zdjęć w Commons.

```bash
npm run baron -- stock-motywy projekty/NAZWA                               # do 6 wyników na motyw
npm run baron -- stock projekty/NAZWA 'streetball dunk' --limit 30         # pojedyncze zapytanie
npm run baron -- stock projekty/NAZWA 'Utsunomiya city' --typ image        # zdjęcia z Commons
npm run baron -- stock-miniatury projekty/NAZWA                            # arkusz podglądów do przeglądu
npm run baron -- dodaj-stock projekty/NAZWA S1a2b3c --zatwierdzone         # po akceptacji użytkownika
```

- `stock` niczego nie pobiera. Zapisuje `work/stock-kandydaci.md`: dopuszczone wyniki z ID `S…`, autorem i licencją oraz listę odrzuconych z powodem.
- Wideo: pionowe od 1080×1920 albo poziome od wysokości 1920 (4K, kadr 9:16 nadal ma 1080 px), parzyste wymiary, minimum 3 s. Z plików Pexels wybierany jest ten najbliższy 1080 px szerokości, nie 4K. Commons daje tylko zdjęcia (filmy tam są w WebM i poziome). Zdjęcia: krótszy bok co najmniej 1080 px.
- `stock-miniatury` pobiera małe podglądy dostawcy do `work/stock/` i skleja `work/stock-kandydaci.jpg`. Tytuły stocków są ogólne, więc wybór zawsze po obejrzeniu podglądu.
- `dodaj-stock` pobiera pełny plik do `assets/library/stock/`, zapisuje licencję w `assets/STOCK-LICENSES.md` i kopiuje plik do `przebitki/` albo `zdjecia/` projektu.
- `final` tworzy `wynik/ATRYBUCJE.md` z podpisami stocków użytych w rolce (dopasowanie po SHA-256). Licencje CC BY i CC BY-SA wymagają podpisu w opisie posta.
- Zakaz powtórek między rolkami obejmuje też stock.

## Poza Studio

Moduł działa w trybie „najpierw raport, później pobieranie”. Żaden wynik
wyszukiwania nie trafia automatycznie do filmu.

## Wikimedia Commons — zdjęcia bez klucza

```bash
npm run stock:search -- "Warsaw skyline" --provider commons --type image
```

Moduł dopuszcza wyłącznie czytelnie oznaczone materiały Public Domain, CC0,
CC BY oraz CC BY-SA. Materiały NC, ND i pliki bez rozpoznanej licencji są
odrzucane. Licencje z obowiązkiem uznania autorstwa zachowują gotowy podpis.

## Pexels — pionowe zdjęcia i filmy

Pexels wymaga darmowego klucza API. Klucza nie zapisuj w projekcie. Na Macu
możesz zapisać go w pęku kluczy poleceniem:

```bash
security add-generic-password -U -a "$USER" -s "Baron3x3-Local-Pexels" -w
```

Polecenie poprosi o klucz w osobnym polu. Klucz nie będzie częścią polecenia
ani plików projektu. Następnie można wyszukiwać pionowe wideo:

```bash
npm run stock:search -- "Warsaw city aerial" --provider pexels --type video
```

Alternatywnie klucz może być dostępny tylko w bieżącej sesji jako zmienna
`PEXELS_API_KEY`.

## Akceptacja i pobieranie

Wyniki są zapisywane w `analysis/stock/searches/`. Po obejrzeniu strony
źródłowej i wybraniu jednego wyniku:

```bash
npm run stock:download -- commons:12345 --search-id ID_RAPORTU --approved
```

Plik trafia do `assets/library/stock/`. Moduł zapisuje autora, źródło,
licencję, sugerowany podpis, datę pobrania i SHA-256 w
`assets/STOCK-LICENSES.md`. Następnie odświeża główny katalog materiałów.

Licencja stocku nie musi obejmować wszystkich praw do widocznych osób, marek,
herbów i budynków. Dlatego każdy pobrany materiał zachowuje obowiązek kontroli
przed publikacją. Stock nie jest używany do trenowania ani budowania datasetu.
