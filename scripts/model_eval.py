#!/usr/bin/env python3
"""Prepare and run a controlled cheap-model evaluation for Baron3x3.

Preparation is fully local. The paid run is deliberately separate, permits
one request only, never edits the active job and never starts a render.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .asset_catalog import refresh_catalog
    from .beat_director import (
        DIRECTOR_SCHEMA,
        compact_style_rules,
        validate_proposal,
        verify_model,
    )
    from .broll_planner import parse_note_fields, split_beats, timeline_words
    from .openrouter_client import OpenRouterClient
    from .openrouter_keychain import load_openrouter_key
else:
    from asset_catalog import refresh_catalog
    from beat_director import DIRECTOR_SCHEMA, compact_style_rules, validate_proposal, verify_model
    from broll_planner import parse_note_fields, split_beats, timeline_words
    from openrouter_client import OpenRouterClient
    from openrouter_keychain import load_openrouter_key


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "instructions" / "jobs"
ANALYSIS = ROOT / "analysis"
EVAL_ID = "stage11-cheap-director-v1"
CANDIDATE_MODEL = "openai/gpt-5.6-luna"
REASONING_EFFORT = "high"
APPROVED_BUDGET_USD = 0.03
MAX_COMPLETION_TOKENS = 8000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def paths(job_name: str) -> dict[str, Path]:
    directory = ANALYSIS / "evals" / f"{job_name}-director"
    return {
        "directory": directory,
        "input": directory / "candidate-input.json",
        "gold": directory / "gold-approved.json",
        "rubric": directory / "rubric.json",
        "manifest": directory / "manifest.json",
        "candidate": directory / "candidate-luna.json",
        "report": directory / "candidate-luna.md",
    }


def available_assets() -> list[dict[str, Any]]:
    catalog = refresh_catalog(ROOT)
    result = []
    for item in catalog.get("items", []):
        if item.get("status") != "available":
            continue
        result.append(
            {
                "assetId": str(item["id"]),
                "name": str(item["name"]),
                "kind": str(item["kind"]),
                "durationMs": int(item.get("durationMs") or 0),
                "description": parse_note_fields(str(item.get("userNotes", ""))),
                "stock": item.get("stock"),
            }
        )
    return result


def rubric() -> dict[str, Any]:
    return {
        "version": 1,
        "passRule": "Tańszy model przejmuje etap wyłącznie bez spadku jakości i po ślepej ocenie użytkownika.",
        "criteria": [
            {"id": "story", "weight": 20, "label": "jedna zamknięta historia i mocny hook"},
            {"id": "semantics", "weight": 20, "label": "obraz zgodny dokładnie z wypowiadanym sensem"},
            {"id": "reveal", "weight": 12, "label": "brak ujawnienia Adriana przed imieniem i nazwiskiem"},
            {"id": "asset_priority", "weight": 12, "label": "priorytet bohater > zespół > miasto"},
            {"id": "rhythm", "weight": 12, "label": "stabilne sceny, zwykle co najmniej 3 s, bez nerwowych zoomów"},
            {"id": "no_repetition", "weight": 8, "label": "brak powtarzania materiału, gdy istnieje właściwa alternatywa"},
            {"id": "effects", "weight": 8, "label": "efekty i SFX uzasadnione narracją, bez amatorskich ozdobników"},
            {"id": "technical", "weight": 8, "label": "istniejące assetId, poprawne zakresy i pełny ścisły JSON"},
        ],
    }


def prepare(job_name: str) -> dict[str, Any]:
    plan_path = JOBS / f"{job_name}.json"
    transcript_path = ANALYSIS / job_name / "transcript.json"
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)
    if not transcript_path.is_file():
        raise FileNotFoundError(transcript_path)
    plan = read_json(plan_path)
    transcript = read_json(transcript_path)
    if plan.get("status") != "ready":
        raise ValueError("Ewaluacja wymaga zatwierdzonej historii ze statusem ready.")

    candidate_input = {
        "version": 1,
        "evalId": EVAL_ID,
        "job": job_name,
        "approvedStory": plan.get("instructions", ""),
        "sourceRanges": plan.get("sourceRanges", []),
        "timelineDurationMs": sum(
            int(item["sourceEndMs"]) - int(item["sourceStartMs"])
            for item in plan.get("sourceRanges", [])
        ),
        "timelineBeats": split_beats(timeline_words(transcript, plan.get("sourceRanges", []))),
        "availableAssets": available_assets(),
        "hardRules": compact_style_rules(),
        "evaluationConstraints": [
            "Nie zmieniaj timestampów beatów.",
            "Nie ujawniaj Adriana obrazem przed wypowiedzeniem imienia i nazwiska.",
            "Przy doborze kontekstu obowiązuje priorytet: bohater, potem zespół, na końcu miasto.",
            "Brak przebitki jest lepszy niż materiał o innej osobie lub zdarzeniu.",
            "Traktuj decyzje dla beatów jako plan semantyczny; nie renderuj i nie modyfikuj aktywnego joba.",
        ],
    }
    gold = {
        "version": 1,
        "job": job_name,
        "source": "zatwierdzony plan po poprawkach użytkownika z etapu 10K",
        "visualBeats": plan.get("visualBeats", []),
        "overlays": plan.get("overlays", []),
        "effectCues": plan.get("effectCues", []),
        "soundEffects": plan.get("soundEffects", []),
        "captionStyle": plan.get("captionStyle"),
        "minimumSceneDurationMs": plan.get("minimumSceneDurationMs", 3000),
    }
    estimated_input_tokens = max(1, len(json.dumps(candidate_input, ensure_ascii=False)) // 4)
    manifest = {
        "version": 1,
        "evalId": EVAL_ID,
        "createdAt": utc_now(),
        "status": "prepared-no-api-call",
        "job": job_name,
        "candidateModel": CANDIDATE_MODEL,
        "reasoningEffort": REASONING_EFFORT,
        "maxCompletionTokens": MAX_COMPLETION_TOKENS,
        "approvedBudgetRequiredUsd": APPROVED_BUDGET_USD,
        "maxAttempts": 1,
        "rendersPlanned": 0,
        "apiCallsExecuted": 0,
        "actualCostUsd": 0.0,
        "estimatedInputTokensUpperBound": estimated_input_tokens,
        "candidateInputSha256": digest(candidate_input),
        "goldSha256": digest(gold),
        "rubricSha256": digest(rubric()),
    }
    output = paths(job_name)
    write_json(output["input"], candidate_input)
    write_json(output["gold"], gold)
    write_json(output["rubric"], rubric())
    write_json(output["manifest"], manifest)
    return manifest


def run(job_name: str, approved_budget: float | None) -> dict[str, Any]:
    if approved_budget is None or abs(approved_budget - APPROVED_BUDGET_USD) > 1e-9:
        raise RuntimeError(
            f"Jedna płatna próba wymaga jawnego limitu {APPROVED_BUDGET_USD:.2f} USD. "
            f"Użyj --approved-budget {APPROVED_BUDGET_USD:.2f}."
        )
    output = paths(job_name)
    candidate_input = read_json(output["input"])
    manifest = read_json(output["manifest"])
    if manifest.get("candidateInputSha256") != digest(candidate_input):
        raise RuntimeError("Pakiet wejściowy zmienił się po przygotowaniu. Uruchom prepare ponownie.")
    verify_model(CANDIDATE_MODEL, False)
    key = load_openrouter_key()
    if not key:
        raise RuntimeError("Brak klucza OpenRouter w macOS Keychain; klucza nie wklejaj do terminala ani pliku.")
    client = OpenRouterClient(api_key=key, max_attempts=1, timeout_seconds=360)
    result = client.complete_json(
        job_id=f"eval-{job_name}-luna",
        stage="edit_plan_eval",
        model=CANDIDATE_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Jesteś reżyserem montażu premium Baron3x3. Zaprojektuj obraz i SFX dla każdego "
                    "beatu. Dobieraj przebitki semantycznie, utrzymuj uwagę bez chaosu i używaj wyłącznie "
                    "podanych assetId. Nie widzisz złotego wyniku. Zwróć wyłącznie ścisły JSON."
                ),
            },
            {"role": "user", "content": json.dumps(candidate_input, ensure_ascii=False)},
        ],
        schema_name="baron3x3_stage11_director_eval",
        schema=DIRECTOR_SCHEMA,
        budget_limit_usd=APPROVED_BUDGET_USD,
        max_request_cost_usd=APPROVED_BUDGET_USD,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        token_limit_field="max_tokens",
        reasoning_effort=REASONING_EFFORT,
        use_cache=False,
        enable_provider_prompt_cache=True,
        enable_response_healing=True,
    )
    validation_package = {
        "timelineBeats": candidate_input["timelineBeats"],
        "assets": candidate_input["availableAssets"],
    }
    validate_proposal(result.data, validation_package)
    artifact = {
        "version": 1,
        "evalId": EVAL_ID,
        "status": "needs-blind-review",
        "createdAt": utc_now(),
        "job": job_name,
        "model": result.model,
        "reasoningEffort": REASONING_EFFORT,
        "requestId": result.request_id,
        "promptTokens": result.prompt_tokens,
        "completionTokens": result.completion_tokens,
        "costUsd": result.cost_usd,
        "proposal": result.data,
    }
    write_json(output["candidate"], artifact)
    manifest.update(
        {
            "status": "candidate-ready-for-blind-review",
            "apiCallsExecuted": 1,
            "actualCostUsd": result.cost_usd,
            "candidateSha256": digest(artifact),
        }
    )
    write_json(output["manifest"], manifest)
    output["report"].write_text(render_candidate_report(artifact, candidate_input), encoding="utf-8")
    return artifact


def render_candidate_report(artifact: dict[str, Any], candidate_input: dict[str, Any]) -> str:
    texts = {item["id"]: item["text"] for item in candidate_input["timelineBeats"]}
    assets = {item["assetId"]: item["name"] for item in candidate_input["availableAssets"]}
    lines = [
        f"# Kandydat do ślepej oceny — {artifact['job']}",
        "",
        "Ten wariant nie został zastosowany ani wyrenderowany. Oceń decyzje względem rubryki; nazwę modelu zachowuje osobny artefakt JSON.",
        "",
    ]
    for beat in artifact["proposal"]["beats"]:
        visual = beat["onScreen"]
        if beat["assetId"]:
            visual += f" — {assets.get(beat['assetId'], beat['assetId'])}"
        lines.extend(
            [
                f"## {beat['timelineStartMs'] / 1000:.2f}–{beat['timelineEndMs'] / 1000:.2f} s",
                "",
                f"> {texts[beat['beatId']]}",
                "",
                f"Obraz: `{visual}` · zoom: `{beat['zoomLevel']}` · przejście: `{beat['transitionEffect']}`",
                "",
                f"Efekt/SFX: `{beat['visualEffect']}` / `{beat['soundEffect']}` · {beat['reason']}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "status"])
    parser.add_argument("source", help="Nazwa MP4 z input/ albo nazwa joba")
    parser.add_argument("--approved-budget", type=float)
    args = parser.parse_args()
    job_name = Path(args.source).stem
    output = paths(job_name)
    if args.command == "prepare":
        manifest = prepare(job_name)
        print(f"Ewaluacja przygotowana: {output['directory']}")
        print(
            f"Model: {manifest['candidateModel']} · maks. 1 próba · "
            f"wymagany limit: {manifest['approvedBudgetRequiredUsd']:.2f} USD · koszt teraz: 0 USD"
        )
    elif args.command == "run":
        artifact = run(job_name, args.approved_budget)
        print(f"Kandydat: {output['report']} · koszt: {artifact['costUsd']:.6f} USD")
        print("Aktywny plan nie został zmieniony. Render nie został uruchomiony.")
    else:
        print(output["manifest"].read_text(encoding="utf-8") if output["manifest"].is_file() else "brak")


if __name__ == "__main__":
    main()
