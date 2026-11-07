#!/usr/bin/env python3
"""Stage 9: controlled golden edit plan for Adrian, without rendering.

Each paid subcommand performs exactly one OpenRouter request. There is no
automatic chain and no retry after a valid HTTP response.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

try:
    from scripts.openrouter_client import OpenRouterClient
    from scripts.pipeline import validate_plan, validate_word_boundaries
except ModuleNotFoundError:
    from openrouter_client import OpenRouterClient
    from pipeline import validate_plan, validate_word_boundaries


ROOT = Path(__file__).resolve().parents[1]
NAME = "16-adrian-bogucki-baza"
SOURCE = ROOT / "input" / f"{NAME}.mp4"
JOB = ROOT / "instructions" / "jobs" / f"{NAME}.json"
JOB_REPLACEMENTS = ROOT / "instructions" / "jobs" / f"{NAME}.replacements.json"
ANALYSIS = ROOT / "analysis" / NAME
TRANSCRIPT = ANALYSIS / "transcript.json"
FRAMING = ANALYSIS / "framing-analysis.json"
PROXY = ANALYSIS / "stage9-video-proxy.mp4"
POLISH_RESULT = ANALYSIS / "stage9-polish.json"
VIDEO_RESULT = ANALYSIS / "stage9-video-analysis.json"
PLAN_RESULT = ANALYSIS / "stage9-director-plan.json"
CANDIDATE = ANALYSIS / "stage9-candidate-job.json"
CATALOG_URL = "https://openrouter.ai/api/v1/models"
JOB_ID = "stage9-adrian-golden-plan"
JOB_BUDGET_USD = 0.16

MODELS = {
    "polish": "openai/gpt-5.6-terra",
    "video": "google/gemini-3.7-flash",
    "plan": "openai/gpt-5.6-sol",
}

REQUEST_LIMITS = {"polish": 0.04, "video": 0.05, "plan": 0.07}


POLISH_SCHEMA = {
    "type": "object",
    "properties": {
        "correctedText": {"type": "string"},
        "replacements": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["from", "to", "reason"],
                "additionalProperties": False,
            },
        },
        "uncertain": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string"},
        },
    },
    "required": ["correctedText", "replacements", "uncertain"],
    "additionalProperties": False,
}


VIDEO_SCHEMA = {
    "type": "object",
    "properties": {
        "visualContinuity": {"type": "string"},
        "speakerAndFraming": {"type": "string"},
        "audioAndDelivery": {"type": "string"},
        "storyEvidence": {"type": "string"},
        "moments": {
            "type": "array",
            "minItems": 3,
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "startMs": {"type": "integer", "minimum": 0, "maximum": 81600},
                    "endMs": {"type": "integer", "minimum": 0, "maximum": 81600},
                    "observation": {"type": "string"},
                    "editorialValue": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["startMs", "endMs", "observation", "editorialValue", "confidence"],
                "additionalProperties": False,
            },
        },
        "risks": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
    },
    "required": [
        "visualContinuity",
        "speakerAndFraming",
        "audioAndDelivery",
        "storyEvidence",
        "moments",
        "risks",
    ],
    "additionalProperties": False,
}


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "string"},
        "hook": {"type": "string"},
        "arc": {"type": "string"},
        "targetDurationMs": {"type": "integer", "minimum": 25000, "maximum": 42000},
        "sourceRanges": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "sourceStartMs": {"type": "integer", "minimum": 0, "maximum": 81380},
                    "sourceEndMs": {"type": "integer", "minimum": 0, "maximum": 81380},
                    "openingWords": {"type": "string"},
                    "closingWords": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "sourceStartMs",
                    "sourceEndMs",
                    "openingWords",
                    "closingWords",
                    "reason",
                ],
                "additionalProperties": False,
            },
        },
        "captionNotes": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
        "qaNotes": {"type": "array", "maxItems": 10, "items": {"type": "string"}},
    },
    "required": ["story", "hook", "arc", "targetDurationMs", "sourceRanges", "captionNotes", "qaNotes"],
    "additionalProperties": False,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def require_local_inputs() -> None:
    missing = [path for path in (SOURCE, JOB, TRANSCRIPT, FRAMING) if not path.is_file()]
    if missing:
        raise SystemExit("Brak wymaganych plików:\n" + "\n".join(str(path) for path in missing))


def verify_model(stage: str) -> dict[str, Any]:
    with urllib.request.urlopen(CATALOG_URL, timeout=30) as response:
        catalog = json.loads(response.read().decode("utf-8"))
    model = next((item for item in catalog.get("data", []) if item.get("id") == MODELS[stage]), None)
    if not model:
        raise SystemExit(f"Model nie istnieje w aktualnym katalogu OpenRouter: {MODELS[stage]}")
    supported = set(model.get("supported_parameters", []))
    required = {"reasoning_effort", "response_format", "structured_outputs"}
    if not required.issubset(supported):
        raise SystemExit(f"Model {MODELS[stage]} nie obsługuje wymaganych parametrów: {sorted(required - supported)}")
    return model


def require_approved_limit(stage: str, approved_limit: float | None) -> None:
    expected = REQUEST_LIMITS[stage]
    if approved_limit is None or abs(approved_limit - expected) > 1e-9:
        raise SystemExit(
            f"Brak jawnej zgody na limit {expected:.2f} USD dla etapu {stage}. "
            f"Wymagany parametr: --approved-limit {expected:.2f}"
        )


def api_client() -> OpenRouterClient:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "Brak bezpiecznie przekazanego klucza. Interaktywne wpisywanie w terminalu jest wyłączone."
        )
    return OpenRouterClient(api_key=api_key, max_attempts=1, timeout_seconds=240)


def prepare() -> None:
    require_local_inputs()
    transcript = read_json(TRANSCRIPT)
    if transcript.get("source") != SOURCE.name:
        raise SystemExit("Transkrypcja nie należy do bieżącego pliku źródłowego.")

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(SOURCE),
            "-vf",
            "fps=8,scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(PROXY),
        ],
        check=True,
        cwd=ROOT,
    )
    duration = sum(
        int(item["sourceEndMs"]) - int(item["sourceStartMs"])
        for item in read_json(JOB).get("sourceRanges", [])
    )
    report = {
        "source": SOURCE.name,
        "transcriptReused": True,
        "wordCount": sum(len(segment.get("words", [])) for segment in transcript.get("segments", [])),
        "approvedStory": read_json(JOB).get("instructions", ""),
        "existingPlanDurationMs": duration,
        "videoProxy": {"file": PROXY.name, "bytes": PROXY.stat().st_size},
        "rendered": False,
        "apiCostUsd": 0,
    }
    write_json(ANALYSIS / "stage9-prepare.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def run_polish(approved_limit: float | None) -> None:
    require_approved_limit("polish", approved_limit)
    require_local_inputs()
    model = verify_model("polish")
    transcript = read_json(TRANSCRIPT)
    known = read_json(ROOT / "knowledge" / "polish-replacements.json")
    result = api_client().complete_json(
        job_id=JOB_ID,
        stage="polish_correction",
        model=MODELS["polish"],
        messages=[
            {
                "role": "system",
                "content": (
                    "Jesteś rygorystycznym korektorem polskiej transkrypcji sportowej. "
                    "Nie parafrazuj, nie skracaj i nie poprawiaj stylu mówcy. Poprawiaj tylko "
                    "udowodnione błędy rozpoznania mowy, fleksji, nazw własnych i interpunkcji. "
                    "Zachowaj kolejność oraz wszystkie wypowiedziane słowa. Nie zgaduj przy niepewności."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Skoryguj poniższy zapis. Zwróć pełny correctedText oraz wyłącznie konieczne "
                    "zamiany fraz. Słownik projektu: "
                    + json.dumps(known, ensure_ascii=False)
                    + "\n\nTRANSKRYPCJA:\n"
                    + str(transcript.get("text", ""))
                ),
            },
        ],
        schema_name="baron3x3_stage9_polish",
        schema=POLISH_SCHEMA,
        budget_limit_usd=JOB_BUDGET_USD,
        max_request_cost_usd=REQUEST_LIMITS["polish"],
        max_completion_tokens=1800,
        token_limit_field="max_completion_tokens",
        reasoning_effort="medium",
        use_cache=True,
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )
    write_json(
        POLISH_RESULT,
        {
            "model": result.model,
            "requestId": result.request_id,
            "costUsd": result.cost_usd,
            "promptTokens": result.prompt_tokens,
            "completionTokens": result.completion_tokens,
            "catalogPricing": model.get("pricing", {}),
            "result": result.data,
        },
    )
    print(f"Korekta zapisana: {POLISH_RESULT}; koszt {result.cost_usd:.8f} USD")


def video_data_url(path: Path) -> str:
    return "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def run_video(approved_limit: float | None) -> None:
    require_approved_limit("video", approved_limit)
    require_local_inputs()
    if not PROXY.is_file():
        raise SystemExit("Najpierw uruchom bezpłatne: stage9.py prepare")
    model = verify_model("video")
    result = api_client().complete_json(
        job_id=JOB_ID,
        stage="video_analysis",
        model=MODELS["video"],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Przeanalizuj cały pionowy materiał wraz z dźwiękiem jako reżyser montażu. "
                            "Nie twórz jeszcze planu cięć. Oceń ciągłość obrazu, mimikę, energię, pauzy, "
                            "akcenty i momenty wspierające zatwierdzoną historię: lider to nie liczba "
                            "punktów, tylko głos i energia na boisku, na przykładzie Adriana Boguckiego. "
                            "Podawaj timestampy względem oryginału w milisekundach i nie zgaduj."
                        ),
                    },
                    {"type": "video_url", "video_url": {"url": video_data_url(PROXY)}},
                ],
            }
        ],
        schema_name="baron3x3_stage9_video",
        schema=VIDEO_SCHEMA,
        budget_limit_usd=JOB_BUDGET_USD,
        max_request_cost_usd=REQUEST_LIMITS["video"],
        max_completion_tokens=1800,
        token_limit_field="max_tokens",
        reasoning_effort="low",
        use_cache=True,
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )
    write_json(
        VIDEO_RESULT,
        {
            "source": SOURCE.name,
            "proxy": PROXY.name,
            "model": result.model,
            "requestId": result.request_id,
            "costUsd": result.cost_usd,
            "promptTokens": result.prompt_tokens,
            "completionTokens": result.completion_tokens,
            "catalogPricing": model.get("pricing", {}),
            "result": result.data,
        },
    )
    print(f"Analiza wideo zapisana: {VIDEO_RESULT}; koszt {result.cost_usd:.8f} USD")


def run_plan(approved_limit: float | None) -> None:
    require_approved_limit("plan", approved_limit)
    require_local_inputs()
    if not POLISH_RESULT.is_file() or not VIDEO_RESULT.is_file():
        raise SystemExit("Plan wymaga najpierw zapisanej korekty polskiego i analizy wideo.")
    model = verify_model("plan")
    transcript = read_json(TRANSCRIPT)
    words = [word for segment in transcript.get("segments", []) for word in segment.get("words", [])]
    evidence = {
        "userInstructions": read_json(JOB).get("instructions", ""),
        "correctedTranscript": read_json(POLISH_RESULT)["result"],
        "timedWords": words,
        "videoAnalysis": read_json(VIDEO_RESULT)["result"],
        "framing": read_json(FRAMING),
        "rules": {
            "duration": "25–40 seconds; only exceed if required for a complete thought",
            "captions": "green-word, no top title",
            "broll": "none; assets are empty",
            "cuts": "every boundary must preserve a complete spoken word",
            "story": "approved: leadership is voice and energy, not point total, shown through Adrian Bogucki",
        },
    }
    result = api_client().complete_json(
        job_id=JOB_ID,
        stage="edit_plan",
        model=MODELS["plan"],
        messages=[
            {
                "role": "system",
                "content": (
                    "Jesteś głównym reżyserem krótkich polskich rolek sportowych. Zaprojektuj jeden "
                    "spójny, energiczny montaż. Używaj wyłącznie dostarczonych timestampów słów. "
                    "Nie wymyślaj wypowiedzi ani ujęć. Każdy start ma przypadać przed pełnym słowem, "
                    "a każdy koniec po pełnym słowie. Nie renderuj i nie opisuj komend."
                ),
            },
            {
                "role": "user",
                "content": "Przygotuj złoty plan historii zgodny z danymi:\n" + json.dumps(evidence, ensure_ascii=False),
            },
        ],
        schema_name="baron3x3_stage9_director_plan",
        schema=PLAN_SCHEMA,
        budget_limit_usd=JOB_BUDGET_USD,
        max_request_cost_usd=REQUEST_LIMITS["plan"],
        max_completion_tokens=4000,
        token_limit_field="max_completion_tokens",
        reasoning_effort="xhigh",
        use_cache=True,
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )
    write_json(
        PLAN_RESULT,
        {
            "model": result.model,
            "requestId": result.request_id,
            "costUsd": result.cost_usd,
            "promptTokens": result.prompt_tokens,
            "completionTokens": result.completion_tokens,
            "catalogPricing": model.get("pricing", {}),
            "result": result.data,
        },
    )
    print(f"Plan reżyserski zapisany: {PLAN_RESULT}; koszt {result.cost_usd:.8f} USD")


def candidate() -> None:
    require_local_inputs()
    if not PLAN_RESULT.is_file():
        raise SystemExit("Brak planu reżyserskiego.")
    transcript = read_json(TRANSCRIPT)
    words = [word for segment in transcript.get("segments", []) for word in segment.get("words", [])]
    director = read_json(PLAN_RESULT)["result"]
    framing = read_json(FRAMING).get("ranges", [])
    stable_scale = min(
        (float(item.get("recommendedScale", 1.08)) for item in framing),
        default=1.08,
    )
    translations = []
    for item in framing:
        match = str(item.get("recommendedTranslate", "0px 0px")).replace("px", "").split()
        if len(match) == 2:
            translations.append((float(match[0]), float(match[1])))
    stable_translate = "0px 0px"
    if translations:
        stable_translate = (
            f"{round(sum(x for x, _ in translations) / len(translations))}px "
            f"{round(sum(y for _, y in translations) / len(translations))}px"
        )
    ranges: list[dict[str, Any]] = []
    for index, item in enumerate(director["sourceRanges"]):
        ranges.append(
            {
                "sourceStartMs": int(item["sourceStartMs"]),
                "sourceEndMs": int(item["sourceEndMs"]),
                "reason": item["reason"],
                "scaleFrom": stable_scale,
                "scaleTo": stable_scale,
                "objectPosition": "50% 50%",
                "translate": stable_translate,
            }
        )
    plan = {
        "version": 1,
        "status": "needs-review",
        "instructions": read_json(JOB).get("instructions", ""),
        "captionStyle": "green-word",
        "sourceRanges": ranges,
        "overlays": [],
        "notes": [
            "Kandydat etapu 9; nie renderować przed akceptacją użytkownika.",
            f"Stałe kadrowanie we wszystkich cięciach: scale {stable_scale}, translate {stable_translate}; zapobiega skokom kadru.",
            f"Hook: {director['hook']}",
            f"Łuk historii: {director['arc']}",
            *director.get("captionNotes", []),
            *director.get("qaNotes", []),
        ],
    }
    validate_plan(CANDIDATE, plan)
    validate_word_boundaries(CANDIDATE, ranges, words)
    actual_duration = sum(item["sourceEndMs"] - item["sourceStartMs"] for item in ranges)
    if not 25000 <= actual_duration <= 42000:
        raise SystemExit(f"Plan ma nieprawidłową długość {actual_duration} ms.")
    write_json(CANDIDATE, {**plan, "validatedDurationMs": actual_duration})
    print(f"Kandydat przeszedł lokalną walidację: {CANDIDATE} ({actual_duration / 1000:.2f} s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "polish", "video", "plan", "candidate"])
    parser.add_argument("--approved-limit", type=float)
    args = parser.parse_args()
    actions = {
        "prepare": lambda: prepare(),
        "polish": lambda: run_polish(args.approved_limit),
        "video": lambda: run_video(args.approved_limit),
        "plan": lambda: run_plan(args.approved_limit),
        "candidate": lambda: candidate(),
    }
    actions[args.action]()


if __name__ == "__main__":
    main()
