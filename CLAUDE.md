# Baron3x3 Studio

Główny proces: lokalny faster-whisper → propozycje cięć → zatwierdzenie → plan → zatwierdzenie → Remotion preview → zatwierdzenie → final.

Przy „zmontuj NAZWA” przeczytaj `.claude/skills/baron3x3-montaz/SKILL.md` i `docs/STUDIO.md`; zacznij od `npm run baron -- status projekty/NAZWA`.

- Nie wysyłaj wideo do modeli ani płatnych API. Agent pracuje na tekście i miniaturach.
- Nie modyfikuj źródeł, nie odtwarzaj planu po lokalnej poprawce.
- Final tylko z `plan.zatwierdzony.json`, po akceptacji aktualnego podglądu.
- Nie zmieniaj szablonu/skryptów podczas montażu. Rozwój na oddzielnej gałęzi.
- Media, cache, katalogi i rendery są lokalne, poza Git.
- Zasady precyzji: `knowledge/editing-precision.md`. Nowy proces Studio zastępuje dawne wymagania Cline/OpenRouter/Resolve i dawne polecenia finalnego renderu.
