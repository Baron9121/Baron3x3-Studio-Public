# Styl montażu Baron3x3

Status: aktywny kontrakt jest kompilowany z `knowledge/style-memory.json`.

## Priorytety

- Zachowaj sens wypowiedzi i naturalną energię mówcy.
- Pierwsze sekundy mają szybko wyjaśniać temat lub obietnicę materiału.
- Każda reguła stylu musi mieć `userConfirmed: true`, powód i dowód; wzorcem bazowym jest `examples/adrian-bogucki-approved/`.

## Zasada aktualizacji

- `accepted` z `autoApply: true` trafia do promptu reżysera;
- `rejected` trafia do twardych zakazów;
- `experimental` nie może zostać użyte automatycznie;
- nową globalną regułę zapisuj dopiero po jawnym potwierdzeniu użytkownika.
