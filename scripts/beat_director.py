#!/usr/bin/env python3
"""Semantic, review-first director for Baron3x3 reels.

The expensive stages are explicit and cached: reference analysis, target
analysis and the final directorial proposal. Applying a proposal never calls
an API and always requires --approved.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .asset_catalog import refresh_catalog
    from .broll_planner import parse_note_fields, split_beats, timeline_words
    from .openrouter_client import OpenRouterClient, validate_schema
    from .openrouter_keychain import load_openrouter_key
    from .pipeline import EFFECT_CUE_TYPES, SOUND_EFFECT_TYPES, ZOOM_LEVELS
    from .style_memory import compile_contract
else:
    from asset_catalog import refresh_catalog
    from broll_planner import parse_note_fields, split_beats, timeline_words
    from openrouter_client import OpenRouterClient, validate_schema
    from openrouter_keychain import load_openrouter_key
    from pipeline import EFFECT_CUE_TYPES, SOUND_EFFECT_TYPES, ZOOM_LEVELS
    from style_memory import compile_contract


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
JOBS = ROOT / "instructions" / "jobs"
CATALOG_URL = "https://openrouter.ai/api/v1/models"
DIRECTOR_ID = "baron3x3-semantic-director-v1"
REFERENCE_MODEL = "google/gemini-3.1-pro-preview"
TARGET_MODEL = "google/gemini-3.1-pro-preview"
DIRECTOR_MODEL = "openai/gpt-5.6-sol-pro"
# User-approved ceiling $5.00 for reel #1 director retries (2026-09-20).
TOTAL_BUDGET_USD = 5.00
REQUEST_LIMITS = {"reference": 0.35, "target": 0.25, "director": 0.35}
REFERENCE_DEFAULT = Path(
    "/Users/bartoszperz/Downloads/"
    "AQO86fk2RarBnal8SNffIFUY599MjFul48AqX_QCRFNZEXG0N0WTPS3ru69-"
    "wNLsSrMrWIOnnJBX4bc6tcIhHOjC_BGgjGQb60Sex4A.mp4"
)


REFERENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "editorialIdentity": {"type": "string"},
        "pacing": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "typicalShotMinMs": {"type": "integer", "minimum": 100, "maximum": 15000},
                "typicalShotMaxMs": {"type": "integer", "minimum": 100, "maximum": 20000},
                "density": {"type": "integer", "minimum": 1, "maximum": 5},
            },
            "required": ["summary", "typicalShotMinMs", "typicalShotMaxMs", "density"],
            "additionalProperties": False,
        },
        "patterns": {
            "type": "array",
            "minItems": 5,
            "maxItems": 18,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "evidenceStartMs": {"type": "integer", "minimum": 0, "maximum": 180000},
                    "evidenceEndMs": {"type": "integer", "minimum": 0, "maximum": 180000},
                    "observation": {"type": "string"},
                    "useWhen": {"type": "string"},
                    "avoidWhen": {"type": "string"},
                },
                "required": [
                    "name",
                    "evidenceStartMs",
                    "evidenceEndMs",
                    "observation",
                    "useWhen",
                    "avoidWhen",
                ],
                "additionalProperties": False,
            },
        },
        "brollPolicy": {"type": "string"},
        "captionStyle": {"type": "string"},
        "soundDesign": {"type": "string"},
        "motionAndColor": {"type": "string"},
        "qualityBar": {"type": "array", "minItems": 3, "maxItems": 12, "items": {"type": "string"}},
        "prohibitions": {"type": "array", "minItems": 2, "maxItems": 12, "items": {"type": "string"}},
    },
    "required": [
        "editorialIdentity",
        "pacing",
        "patterns",
        "brollPolicy",
        "captionStyle",
        "soundDesign",
        "motionAndColor",
        "qualityBar",
        "prohibitions",
    ],
    "additionalProperties": False,
}


TARGET_SCHEMA = {
    "type": "object",
    "properties": {
        "storySummary": {"type": "string"},
        "deliveryAndEmotion": {"type": "string"},
        "visualContinuity": {"type": "string"},
        "usableVisualMoments": {
            "type": "array",
            "minItems": 3,
            "maxItems": 18,
            "items": {
                "type": "object",
                "properties": {
                    "sourceStartMs": {"type": "integer", "minimum": 0, "maximum": 600000},
                    "sourceEndMs": {"type": "integer", "minimum": 0, "maximum": 600000},
                    "observation": {"type": "string"},
                    "editorialUse": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["sourceStartMs", "sourceEndMs", "observation", "editorialUse", "confidence"],
                "additionalProperties": False,
            },
        },
        "semanticFacts": {"type": "array", "minItems": 2, "maxItems": 20, "items": {"type": "string"}},
        "risks": {"type": "array", "maxItems": 12, "items": {"type": "string"}},
    },
    "required": [
        "storySummary",
        "deliveryAndEmotion",
        "visualContinuity",
        "usableVisualMoments",
        "semanticFacts",
        "risks",
    ],
    "additionalProperties": False,
}


DIRECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "overallStrategy": {"type": "string"},
        "referenceMatch": {"type": "string"},
        "beats": {
            "type": "array",
            "minItems": 1,
            "maxItems": 80,
            "items": {
                "type": "object",
                "properties": {
                    "beatId": {"type": "string"},
                    "timelineStartMs": {"type": "integer", "minimum": 0, "maximum": 600000},
                    "timelineEndMs": {"type": "integer", "minimum": 0, "maximum": 600000},
                    "narrativeFunction": {
                        "type": "string",
                        "enum": ["hook", "setup", "proof", "contrast", "escalation", "payoff"],
                    },
                    "energy": {"type": "integer", "minimum": 1, "maximum": 5},
                    "onScreen": {"type": "string", "enum": ["host", "broll", "stat-card"]},
                    "assetId": {"type": "string"},
                    "assetSourceStartMs": {"type": "integer", "minimum": 0, "maximum": 600000},
                    "brollPresentation": {
                        "type": "string",
                        "enum": ["full", "editorial", "archive"],
                    },
                    "brollMotion": {
                        "type": "string",
                        "enum": ["push-in", "pull-out", "pan-left", "pan-right", "still"],
                    },
                    "secondaryAssetId": {"type": "string"},
                    "collageAssetIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 4,
                    },
                    "secondaryAssetSourceStartMs": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 600000,
                    },
                    "editorialHeadline": {"type": "string", "maxLength": 70},
                    "editorialKicker": {"type": "string", "maxLength": 32},
                    "zoomLevel": {"type": "string", "enum": sorted(ZOOM_LEVELS)},
                    "transitionEffect": {
                        "type": "string",
                        "enum": ["smooth", "blur", "rgb", "split"],
                    },
                    "visualEffect": {
                        "type": "string",
                        "enum": ["none", "flash", "whip", "light-leak", "film-frame", "rec"],
                    },
                    "soundEffect": {
                        "type": "string",
                        "enum": ["none", "whoosh", "impact", "click"],
                    },
                    "soundVolume": {"type": "number", "minimum": 0, "maximum": 0.24},
                    "statValue": {"type": "string"},
                    "statLabel": {"type": "string"},
                    "reason": {"type": "string"},
                    "referenceEvidence": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": [
                    "beatId",
                    "timelineStartMs",
                    "timelineEndMs",
                    "narrativeFunction",
                    "energy",
                    "onScreen",
                    "assetId",
                    "assetSourceStartMs",
                    "brollPresentation",
                    "brollMotion",
                    "secondaryAssetId",
                    "collageAssetIds",
                    "secondaryAssetSourceStartMs",
                    "editorialHeadline",
                    "editorialKicker",
                    "zoomLevel",
                    "transitionEffect",
                    "visualEffect",
                    "soundEffect",
                    "soundVolume",
                    "statValue",
                    "statLabel",
                    "reason",
                    "referenceEvidence",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
        "missingAssets": {"type": "array", "maxItems": 15, "items": {"type": "string"}},
        "qualityRisks": {"type": "array", "maxItems": 15, "items": {"type": "string"}},
    },
    "required": ["overallStrategy", "referenceMatch", "beats", "missingAssets", "qualityRisks"],
    "additionalProperties": False,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def plan_signature(plan: dict[str, Any]) -> str:
    relevant = {
        "sourceRanges": plan.get("sourceRanges", []),
        "instructions": plan.get("instructions", ""),
        "captionStyle": plan.get("captionStyle", "green-word"),
    }
    return hashlib.sha256(
        json.dumps(relevant, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def data_url(path: Path) -> str:
    return "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def make_proxy(source: Path, destination: Path, fps: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vf",
            f"fps={fps},scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "31",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        check=True,
        cwd=ROOT,
    )


def make_story_proxy(
    source: Path,
    destination: Path,
    fps: int,
    source_ranges: list[dict[str, Any]],
) -> list[dict[str, int]]:
    """Create a small proxy from only the approved story ranges.

    Seeking happens before each input, so a long 4K source is not decoded from
    the beginning once per selected range. The returned map lets a video model
    translate proxy time back to the original source time.
    """
    if not source_ranges:
        raise ValueError("Proxy historii wymaga co najmniej jednego sourceRange.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    building = destination.with_name(f"{destination.stem}.building{destination.suffix}")
    building.unlink(missing_ok=True)

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    timeline_map: list[dict[str, int]] = []
    proxy_cursor = 0
    for item in source_ranges:
        start = int(item["sourceStartMs"])
        end = int(item["sourceEndMs"])
        if start < 0 or end <= start:
            raise ValueError(f"Nieprawidłowy zakres proxy historii: {start}-{end} ms.")
        duration = end - start
        command.extend(
            [
                "-ss",
                f"{start / 1000:.3f}",
                "-t",
                f"{duration / 1000:.3f}",
                "-i",
                str(source),
            ]
        )
        timeline_map.append(
            {
                "proxyStartMs": proxy_cursor,
                "proxyEndMs": proxy_cursor + duration,
                "sourceStartMs": start,
                "sourceEndMs": end,
            }
        )
        proxy_cursor += duration

    filters: list[str] = []
    concat_inputs: list[str] = []
    for index in range(len(source_ranges)):
        filters.append(
            f"[{index}:v]fps={fps},scale=360:640:force_original_aspect_ratio=decrease,"
            f"pad=360:640:(ow-iw)/2:(oh-ih)/2,setsar=1,setpts=PTS-STARTPTS[v{index}]"
        )
        filters.append(f"[{index}:a]aresample=48000,asetpts=PTS-STARTPTS[a{index}]")
        concat_inputs.append(f"[v{index}][a{index}]")
    filters.append(
        f"{''.join(concat_inputs)}concat=n={len(source_ranges)}:v=1:a=1[vout][aout]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "31",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            str(building),
        ]
    )
    try:
        subprocess.run(command, check=True, cwd=ROOT)
        building.replace(destination)
    except Exception:
        building.unlink(missing_ok=True)
        raise
    return timeline_map


def verify_model(model_id: str, needs_video: bool) -> dict[str, Any]:
    with urllib.request.urlopen(CATALOG_URL, timeout=30) as response:
        catalog = json.loads(response.read().decode("utf-8"))
    model = next((item for item in catalog.get("data", []) if item.get("id") == model_id), None)
    if not model:
        raise RuntimeError(f"Model nie istnieje w katalogu OpenRouter: {model_id}")
    parameters = set(model.get("supported_parameters", []))
    required = {"reasoning_effort", "response_format", "structured_outputs"}
    if not required.issubset(parameters):
        raise RuntimeError(f"Model nie obsługuje: {sorted(required - parameters)}")
    modalities = set(model.get("architecture", {}).get("input_modalities", []))
    if needs_video and "video" not in modalities:
        raise RuntimeError(f"Model nie obsługuje wideo: {model_id}")
    return model


def api_client() -> OpenRouterClient:
    key = load_openrouter_key()
    if not key:
        raise RuntimeError(
            "To jest opcjonalna, bezpośrednia ścieżka API i nie ma dostępu do sekretu Cline. "
            "W VS Code użyj workflow Cline; nie podawaj klucza ponownie."
        )
    return OpenRouterClient(api_key=key, max_attempts=1, timeout_seconds=360)


def require_approved_budget(value: float | None) -> None:
    if value is None or abs(value - TOTAL_BUDGET_USD) > 1e-9:
        raise RuntimeError(
            f"Płatne etapy wymagają jednej jawnej zgody na łączny limit {TOTAL_BUDGET_USD:.2f} USD. "
            f"Użyj --approved-budget {TOTAL_BUDGET_USD:.2f}."
        )


def paths(job_name: str) -> dict[str, Path]:
    directory = ANALYSIS / job_name / "director"
    return {
        "directory": directory,
        "package": directory / "input-package.json",
        "target_proxy": directory / "target-proxy.mp4",
        "reference_proxy": directory / "reference-proxy.mp4",
        "reference": directory / "reference-style.json",
        "target": directory / "target-analysis.json",
        "proposal": directory / "proposal.json",
        "cline_proposal": directory / "cline-proposal.json",
        "report": directory / "proposal.md",
    }


def prepare(job_name: str, reference: Path) -> dict[str, Any]:
    source = ROOT / "input" / f"{job_name}.mp4"
    transcript_path = ANALYSIS / job_name / "transcript.json"
    plan_path = JOBS / f"{job_name}.json"
    for required in (source, transcript_path, plan_path, reference):
        if not required.is_file():
            raise FileNotFoundError(required)
    transcript = read_json(transcript_path)
    plan = read_json(plan_path)
    if plan.get("status") != "ready":
        raise ValueError("Reżyser wymaga zatwierdzonego planu historii ze statusem ready.")
    catalog = refresh_catalog(ROOT)
    timeline = split_beats(timeline_words(transcript, plan.get("sourceRanges", [])))
    available_assets = []
    for item in catalog.get("items", []):
        if item.get("status") != "available":
            continue
        fields = parse_note_fields(str(item.get("userNotes", "")))
        available_assets.append(
            {
                "assetId": str(item["id"]),
                "name": str(item["name"]),
                "kind": str(item["kind"]),
                "durationMs": int(item.get("durationMs") or 0),
                "description": fields,
                "stock": item.get("stock"),
            }
        )
    output_paths = paths(job_name)
    target_proxy_timeline = make_story_proxy(
        source,
        output_paths["target_proxy"],
        6,
        plan.get("sourceRanges", []),
    )
    make_proxy(reference, output_paths["reference_proxy"], 4)
    package = {
        "version": 1,
        "director": DIRECTOR_ID,
        "createdAt": utc_now(),
        "job": job_name,
        "source": str(source),
        "reference": str(reference),
        "planSignature": plan_signature(plan),
        "timelineDurationMs": sum(
            int(item["sourceEndMs"]) - int(item["sourceStartMs"])
            for item in plan.get("sourceRanges", [])
        ),
        "targetProxyTimeline": target_proxy_timeline,
        "instructions": plan.get("instructions", ""),
        "styleContract": {
            "zoomTransitions": (
                "Grupuj beaty tekstowe w stabilne bloki obrazu trwające domyślnie 4–7 s; 3 s jest minimum "
                "dla mocnej puenty. Każdy blok po otwarciu ma animowany zoom i przejście do około 0,64 s. "
                "Nie zmieniaj zoomu co 1–2 s i nie zwracaj serii samych smooth. Stosuj blur jako optyczny zoom blur, rgb jako "
                "subtelną aberrację bez kolorowych pasów oraz split jako krótkie rozdzielenie obrazu."
            ),
            "statCards": (
                "Karta trwa tylko podczas wypowiadania statystyk, zwykle 2,0–3,0 s. Liczby liczą od "
                "zera przez około 0,9 s, kolejne metryki są przesunięte o około 0,24 s, a jednostki "
                "pojawiają się po zakończeniu liczenia. Styl: czarne tło, biało-różowo-czerwony gradient "
                "liczb, miękka poświata i krótki błysk wejściowy."
            ),
            "soundDesign": (
                "Whoosh tylko na wybranych mocnych zmianach skali; impact na wejściu ważnej karty. "
                "Whoosh maks. 0.18, impact maks. 0.24, click maks. 0.12. Mowa pozostaje nadrzędna; "
                "nie dodawaj SFX na każdym cięciu."
            ),
            "brollPresentation": (
                "Dla B-rollu wybierz full, editorial albo archive. Full jest dla pionowego klipu akcji; "
                "editorial zachowuje całe zdjęcie lub szeroki kadr na rozmytym tle; archive jest wyłącznie "
                "dla prawdziwego materiału archiwalnego lub wspomnieniowego. Split, stack, cutout i paper-collage "
                "są wyłączone decyzjami użytkownika i nie wolno ich wybierać automatycznie. Ruch wybierz jako push-in, "
                "pull-out, pan-left, pan-right lub still i uzasadnij sensem wypowiedzi."
            ),
            "learnedPreferences": compile_contract(),
        },
        "timelineBeats": timeline,
        "assets": available_assets,
        "models": {
            "reference": REFERENCE_MODEL,
            "target": TARGET_MODEL,
            "director": DIRECTOR_MODEL,
            "reasoning": "xhigh",
        },
        "budget": {
            "totalLimitUsd": TOTAL_BUDGET_USD,
            "requestReservationsUsd": REQUEST_LIMITS,
            "paidCallsExecuted": 0,
        },
    }
    write_json(output_paths["package"], package)
    return package


def run_reference(job_name: str, approved_budget: float | None) -> dict[str, Any]:
    require_approved_budget(approved_budget)
    output_paths = paths(job_name)
    package = read_json(output_paths["package"])
    verify_model(REFERENCE_MODEL, True)
    result = api_client().complete_json(
        job_id=f"director-{job_name}",
        stage="reference_analysis",
        model=REFERENCE_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Jesteś reżyserem krótkich pionowych materiałów sportowych. Obejrzyj całą "
                            "rolkę referencyjną, analizując obraz i dźwięk. Zbuduj precyzyjne DNA stylu: "
                            "rytm, relację host–B-roll, karty statystyk, rodzaje przejść, ruch zdjęć, "
                            "napisy i sound design. Każdy wzorzec poprzyj rzeczywistym timestampem. "
                            "Oddziel cechy profesjonalne od efektów, których nie należy kopiować. "
                            "Nie opisuj fabuły zamiast montażu. Wypełnij wszystkie pola schematu, "
                            "zwięźle, bez długich opisów i bez pomijania soundDesign. Zwróć wyłącznie JSON zgodny ze schematem."
                        ),
                    },
                    {"type": "video_url", "video_url": {"url": data_url(output_paths["reference_proxy"])}},
                ],
            }
        ],
        schema_name="baron3x3_reference_style",
        schema=REFERENCE_SCHEMA,
        budget_limit_usd=TOTAL_BUDGET_USD,
        max_request_cost_usd=REQUEST_LIMITS["reference"],
        max_completion_tokens=8000,
        token_limit_field="max_tokens",
        reasoning_effort="xhigh",
        use_cache=True,
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )
    artifact = {"model": result.model, "costUsd": result.cost_usd, "analysis": result.data}
    write_json(output_paths["reference"], artifact)
    return artifact


def run_target(job_name: str, approved_budget: float | None) -> dict[str, Any]:
    require_approved_budget(approved_budget)
    output_paths = paths(job_name)
    package = read_json(output_paths["package"])
    verify_model(TARGET_MODEL, True)
    result = api_client().complete_json(
        job_id=f"director-{job_name}",
        stage="video_analysis_hard",
        model=TARGET_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Przeanalizuj proxy złożone wyłącznie z zatwierdzonych fragmentów materiału "
                            "docelowego jako reżyser sportowych rolek. "
                            "Rozpoznaj emocję i energię wypowiedzi, ciągłość obrazu, gesty, momenty nadające "
                            "się na hosta oraz fakty semantyczne. Zwracane timestampy muszą odnosić się do "
                            "oryginalnego pliku źródłowego; przelicz je według targetProxyTimeline. "
                            "Nie wymyślaj faktów ani osób. Oto zatwierdzona historia i beaty osi montażu:\n"
                            + json.dumps(
                                {
                                    "instructions": package["instructions"],
                                    "timelineBeats": package["timelineBeats"],
                                    "targetProxyTimeline": package["targetProxyTimeline"],
                                },
                                ensure_ascii=False,
                            )
                        ),
                    },
                    {"type": "video_url", "video_url": {"url": data_url(output_paths["target_proxy"])}},
                ],
            }
        ],
        schema_name="baron3x3_target_analysis",
        schema=TARGET_SCHEMA,
        budget_limit_usd=TOTAL_BUDGET_USD,
        max_request_cost_usd=REQUEST_LIMITS["target"],
        max_completion_tokens=8000,
        token_limit_field="max_tokens",
        reasoning_effort="xhigh",
        use_cache=True,
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )
    artifact = {"model": result.model, "costUsd": result.cost_usd, "analysis": result.data}
    write_json(output_paths["target"], artifact)
    return artifact


def compact_style_rules() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("broll.md", "transitions.md", "effects.md", "audio.md", "captions.md"):
        path = ROOT / "knowledge" / name
        result[name] = path.read_text(encoding="utf-8")
    result["style-memory"] = compile_contract()
    return result


def validate_proposal(proposal: dict[str, Any], package: dict[str, Any]) -> None:
    wanted = {item["id"]: item for item in package["timelineBeats"]}
    available = {item["assetId"]: item for item in package["assets"]}
    received: set[str] = set()
    for item in proposal.get("beats", []):
        beat_id = item["beatId"]
        if beat_id not in wanted or beat_id in received:
            raise ValueError(f"Nieznany albo powtórzony beatId: {beat_id}")
        received.add(beat_id)
        original = wanted[beat_id]
        if item["timelineStartMs"] != original["timelineStartMs"] or item["timelineEndMs"] != original["timelineEndMs"]:
            raise ValueError(f"Model zmienił granice beatu {beat_id}.")
        if item["onScreen"] == "broll":
            if not item["assetId"] or item["assetId"] not in available:
                raise ValueError(f"Beat {beat_id} wskazuje nieistniejący assetId.")
            asset = available[item["assetId"]]
            source_start = int(item["assetSourceStartMs"])
            beat_duration = int(item["timelineEndMs"]) - int(item["timelineStartMs"])
            if asset.get("kind") != "image" and source_start + beat_duration > int(asset.get("durationMs") or 0):
                raise ValueError(f"Beat {beat_id} wychodzi poza długość przebitki.")
            if item["brollPresentation"] not in {"full", "editorial", "archive"}:
                raise ValueError(f"Beat {beat_id}: niedozwolona prezentacja B-rollu.")
            if item["brollMotion"] not in {"push-in", "pull-out", "pan-left", "pan-right", "still"}:
                raise ValueError(f"Beat {beat_id}: niedozwolony ruch B-rollu.")
            secondary_id = item["secondaryAssetId"]
            collage_ids = item.get("collageAssetIds", [])
            if item["brollPresentation"] in {"split", "stack"}:
                if not secondary_id or secondary_id not in available:
                    raise ValueError(f"Beat {beat_id}: kompozycja wieloelementowa wymaga drugiego assetId.")
                secondary = available[secondary_id]
                secondary_start = int(item["secondaryAssetSourceStartMs"])
                if secondary_start + beat_duration > int(secondary.get("durationMs") or 0):
                    raise ValueError(f"Beat {beat_id}: druga przebitka wychodzi poza długość materiału.")
            elif secondary_id:
                raise ValueError(f"Beat {beat_id}: drugi asset jest dozwolony tylko dla split albo stack.")
            if item["brollPresentation"] == "paper-collage":
                if not 2 <= len(collage_ids) <= 4:
                    raise ValueError(f"Beat {beat_id}: paper-collage wymaga 2–4 dodatkowych zdjęć.")
                all_collage_ids = [item["assetId"], *collage_ids]
                if len(set(all_collage_ids)) != len(all_collage_ids):
                    raise ValueError(f"Beat {beat_id}: paper-collage nie może powtarzać zdjęć.")
                for collage_id in collage_ids:
                    collage_asset = available.get(collage_id)
                    if collage_asset is None or collage_asset.get("kind") != "image":
                        raise ValueError(f"Beat {beat_id}: paper-collage wymaga istniejących zdjęć.")
                if asset.get("kind") != "image":
                    raise ValueError(f"Beat {beat_id}: główny materiał paper-collage musi być zdjęciem.")
            elif collage_ids:
                raise ValueError(f"Beat {beat_id}: collageAssetIds jest tylko dla paper-collage.")
            if item["brollPresentation"] == "cutout":
                name = str(asset.get("name", "")).casefold()
                if asset.get("kind") != "image" or not name.endswith((".png", ".webp", ".avif")):
                    raise ValueError(f"Beat {beat_id}: cutout wymaga przezroczystego PNG/WebP/AVIF.")
        elif item["assetId"]:
            raise ValueError(f"Beat {beat_id} nie jest B-rollem, ale zawiera assetId.")
        if item["onScreen"] == "stat-card" and (not item["statValue"] or not item["statLabel"]):
            raise ValueError(f"Beat {beat_id}: karta statystyczna wymaga liczby i opisu.")
        if item["onScreen"] == "stat-card" and item["visualEffect"] != "none":
            raise ValueError(f"Beat {beat_id}: karta statystyczna nie może nakładać drugiego silnego efektu.")
        if item["visualEffect"] not in EFFECT_CUE_TYPES | {"none"}:
            raise ValueError(f"Beat {beat_id}: niedozwolony efekt.")
        if item["soundEffect"] not in SOUND_EFFECT_TYPES | {"none"}:
            raise ValueError(f"Beat {beat_id}: niedozwolony SFX.")
        sound_caps = {"whoosh": 0.18, "impact": 0.24, "click": 0.12}
        if item["soundEffect"] != "none" and float(item["soundVolume"]) > sound_caps[item["soundEffect"]]:
            raise ValueError(f"Beat {beat_id}: SFX przekracza bezpieczny limit głośności.")
    if received != set(wanted):
        raise ValueError("Model musi podjąć decyzję dla każdego beatu osi montażu.")


def run_director(job_name: str, approved_budget: float | None) -> dict[str, Any]:
    require_approved_budget(approved_budget)
    output_paths = paths(job_name)
    package = read_json(output_paths["package"])
    reference = read_json(output_paths["reference"])
    target = read_json(output_paths["target"])
    verify_model(DIRECTOR_MODEL, False)
    result = api_client().complete_json(
        job_id=f"director-{job_name}",
        stage="edit_plan_pro",
        model=DIRECTOR_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Jesteś głównym reżyserem montażu Baron3x3. Maksymalizuj jakość, rytm i semantyczną "
                    "zgodność obrazu z wypowiedzią. Nie używaj efektu tylko dlatego, że istnieje. Brak "
                    "przebitki jest lepszy niż przebitka o innej osobie lub zdarzeniu. Nie zmieniaj czasów "
                    "beatów. Używaj wyłącznie podanych assetId. Zwróć wyłącznie ścisły JSON.\n"
                    "TWARDE REGUŁY: dla beatu z onScreen=stat-card ustaw visualEffect=none (zakaz drugiego "
                    "silnego efektu; dozwolony co najwyżej soundEffect=impact bez dodatkowego efektu wizualnego). "
                    "Nie stosuj efektywności do kart statystycznych. Dla onScreen=host używaj tylko oświetlenia/zoomu, "
                    "nie nakładaj assetId. Zweryfikuj każdy beat względem tych zasad."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "Zaprojektuj kompletną reżyserię obrazu i SFX dla każdego beatu.",
                        "referenceStyle": reference["analysis"],
                        "targetAnalysis": target["analysis"],
                        "approvedStory": package["instructions"],
                        "timelineBeats": package["timelineBeats"],
                        "availableAssets": package["assets"],
                        "hardRules": compact_style_rules(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        schema_name="baron3x3_semantic_director",
        schema=DIRECTOR_SCHEMA,
        budget_limit_usd=TOTAL_BUDGET_USD,
        max_request_cost_usd=REQUEST_LIMITS["director"],
        max_completion_tokens=12000,
        reasoning_effort="low",
        use_cache=True,
        enable_provider_prompt_cache=True,
        enable_response_healing=True,
    )
    validate_proposal(result.data, package)
    artifact = {
        "version": 1,
        "director": DIRECTOR_ID,
        "status": "needs-review",
        "createdAt": utc_now(),
        "job": job_name,
        "planSignature": package["planSignature"],
        "model": result.model,
        "costUsd": result.cost_usd,
        "proposal": result.data,
    }
    write_json(output_paths["proposal"], artifact)
    output_paths["report"].write_text(render_report(artifact, package), encoding="utf-8")
    return artifact


def import_cline_proposal(job_name: str) -> dict[str, Any]:
    """Validate a proposal written by Cline without reading its API key."""
    output_paths = paths(job_name)
    package = read_json(output_paths["package"])
    raw = read_json(output_paths["cline_proposal"])
    validate_schema(raw, DIRECTOR_SCHEMA)
    validate_proposal(raw, package)
    artifact = {
        "version": 1,
        "director": DIRECTOR_ID,
        "status": "needs-review",
        "createdAt": utc_now(),
        "job": job_name,
        "planSignature": package["planSignature"],
        "model": "external import — model unverified",
        "costUsd": None,
        "costSource": "Cline UI",
        "proposal": raw,
    }
    provenance_path = output_paths["cline_proposal"].parent / "specialist-provenance.json"
    if provenance_path.exists():
        provenance = read_json(provenance_path)
        if provenance.get("proposalSha256") == hashlib.sha256(output_paths["cline_proposal"].read_bytes()).hexdigest():
            artifact.update(model=provenance["model"], costUsd=provenance["costUsd"], costSource="controlled specialist ledger")
    write_json(output_paths["proposal"], artifact)
    output_paths["report"].write_text(render_report(artifact, package), encoding="utf-8")
    return artifact


def render_report(artifact: dict[str, Any], package: dict[str, Any]) -> str:
    proposal = artifact["proposal"]
    assets = {item["assetId"]: item for item in package["assets"]}
    texts = {item["id"]: item["text"] for item in package["timelineBeats"]}
    cost = artifact.get("costUsd")
    cost_label = f"{cost:.6f} USD" if isinstance(cost, (int, float)) else "widoczny w Cline"
    lines = [
        f"# Reżyser beatów — {artifact['job']}",
        "",
        f"Status: **{artifact['status']}** · model: `{artifact['model']}` · koszt planu: **{cost_label}**",
        "",
        "Plan montażu nie został zmieniony. Zastosowanie wymaga jawnego `--approved`.",
        "",
        "## Strategia",
        "",
        proposal["overallStrategy"],
        "",
        f"Zgodność z referencją: {proposal['referenceMatch']}",
        "",
        "## Timeline",
        "",
    ]
    for item in proposal["beats"]:
        start = item["timelineStartMs"] / 1000
        end = item["timelineEndMs"] / 1000
        lines.extend(
            [
                f"### {item['beatId']} · {start:.2f}–{end:.2f} s · energia {item['energy']}/5",
                "",
                f"> {texts[item['beatId']]}",
                "",
                f"- Funkcja: `{item['narrativeFunction']}`",
                f"- Obraz: `{item['onScreen']}`",
            ]
        )
        if item["assetId"]:
            lines.append(f"- Przebitka: `{item['assetId']}` — `{assets[item['assetId']]['name']}`")
            lines.append(f"- Start przebitki: {item['assetSourceStartMs'] / 1000:.2f} s")
            lines.append(
                f"- Prezentacja/ruch: `{item['brollPresentation']}` / `{item['brollMotion']}`"
            )
            if item["secondaryAssetId"]:
                lines.append(
                    f"- Drugi materiał: `{item['secondaryAssetId']}` — "
                    f"`{assets[item['secondaryAssetId']]['name']}`"
                )
            if item.get("collageAssetIds"):
                lines.append(
                    "- Zdjęcia kolażu: "
                    + ", ".join(
                        f"`{asset_id}` — `{assets[asset_id]['name']}`"
                        for asset_id in item["collageAssetIds"]
                    )
                )
            if item["editorialHeadline"]:
                lines.append(
                    f"- Hasło: **{item['editorialHeadline']}**"
                    + (f" · {item['editorialKicker']}" if item["editorialKicker"] else "")
                )
        if item["onScreen"] == "stat-card":
            lines.append(f"- Karta: **{item['statValue']}** — {item['statLabel']}")
        lines.extend(
            [
                f"- Kadr/przejście: `{item['zoomLevel']}` / `{item['transitionEffect']}`",
                f"- Efekt/SFX: `{item['visualEffect']}` / `{item['soundEffect']}` ({item['soundVolume']:.2f})",
                f"- Decyzja: {item['reason']}",
                f"- Dowód z referencji: {item['referenceEvidence']}",
                f"- Pewność: {item['confidence']:.2f}",
                "",
            ]
        )
    lines.extend(["## Braki", ""])
    lines.extend([f"- {item}" for item in proposal["missingAssets"]] or ["- Brak."])
    lines.extend(["", "## Ryzyka jakości", ""])
    lines.extend([f"- {item}" for item in proposal["qualityRisks"]] or ["- Brak."])
    lines.extend(
        [
            "",
            "## Akceptacja",
            "",
            f"`npm run director:apply -- {artifact['job']}.mp4 --approved`",
            "",
            "Ta komenda nie wywołuje API i nie renderuje filmu.",
            "",
        ]
    )
    return "\n".join(lines)


def application_from_proposal(proposal: dict[str, Any], timeline_duration: int) -> dict[str, Any]:
    beats = sorted(proposal["beats"], key=lambda item: item["timelineStartMs"])
    visual_beats: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    effect_cues: list[dict[str, Any]] = []
    sound_effects: list[dict[str, Any]] = []
    effect_durations = {"flash": 260, "whip": 520, "light-leak": 750}
    for index, item in enumerate(beats):
        start = 0 if index == 0 else int(item["timelineStartMs"])
        end = int(beats[index + 1]["timelineStartMs"]) if index + 1 < len(beats) else timeline_duration
        visual_beat = {
            "timelineStartMs": start,
            "timelineEndMs": end,
            "zoomLevel": item["zoomLevel"],
            "transitionEffect": item["transitionEffect"],
            "reason": f"{DIRECTOR_ID}: {item['reason']}",
        }
        # Beaty opisują sens wypowiedzi, ale nie każdy beat jest osobną sceną.
        # Kolejne fragmenty o tej samej skali i bez nowego efektu przejścia
        # tworzą jeden stabilny blok obrazu. Zapobiega to mikrozoomom 1–2 s.
        if (
            visual_beats
            and visual_beats[-1]["zoomLevel"] == visual_beat["zoomLevel"]
            and visual_beat["transitionEffect"] == "smooth"
        ):
            visual_beats[-1]["timelineEndMs"] = end
            visual_beats[-1]["reason"] += f" / {item['reason']}"
        else:
            visual_beats.append(visual_beat)
        if item["onScreen"] == "broll":
            overlays.append(
                {
                    "assetId": item["assetId"],
                    "timelineStartMs": int(item["timelineStartMs"]),
                    "timelineEndMs": int(item["timelineEndMs"]),
                    "sourceStartMs": int(item["assetSourceStartMs"]),
                    "objectPosition": "50% 50%",
                    "presentation": item["brollPresentation"],
                    "motion": item["brollMotion"],
                    "secondaryAssetId": item["secondaryAssetId"] or None,
                    "collageAssetIds": list(item.get("collageAssetIds", [])),
                    "secondarySourceStartMs": int(item["secondaryAssetSourceStartMs"]),
                    "headline": item["editorialHeadline"],
                    "kicker": item["editorialKicker"],
                    "accentColor": "#ff174f",
                    "reason": item["reason"],
                    "generatedBy": DIRECTOR_ID,
                    "beatId": item["beatId"],
                }
            )
        if item["onScreen"] == "stat-card":
            effect_cues.append(
                {
                    "type": "stat-card",
                    "timelineStartMs": int(item["timelineStartMs"]),
                    "timelineEndMs": int(item["timelineEndMs"]),
                    "value": item["statValue"],
                    "label": item["statLabel"],
                    "accentColor": "#ff174f",
                    "intensity": 1.0,
                    "generatedBy": DIRECTOR_ID,
                }
            )
        visual_effect = item["visualEffect"]
        if visual_effect != "none":
            start_ms = int(item["timelineStartMs"])
            end_ms = min(
                int(item["timelineEndMs"]),
                start_ms + effect_durations.get(visual_effect, int(item["timelineEndMs"]) - start_ms),
            )
            effect_cues.append(
                {
                    "type": visual_effect,
                    "timelineStartMs": start_ms,
                    "timelineEndMs": end_ms,
                    "intensity": 1.0,
                    "direction": "right" if index % 2 == 0 else "left",
                    "generatedBy": DIRECTOR_ID,
                }
            )
        if item["soundEffect"] != "none":
            sound_effects.append(
                {
                    "type": item["soundEffect"],
                    "timelineStartMs": int(item["timelineStartMs"]),
                    "volume": float(item["soundVolume"]),
                    "speechDucking": 0.72,
                    "generatedBy": DIRECTOR_ID,
                }
            )
    return {
        "visualBeats": visual_beats,
        "overlays": overlays,
        "effectCues": effect_cues,
        "soundEffects": sound_effects,
        "referenceBuildingBlocksRequired": bool(overlays)
        or any(item.get("type") == "stat-card" for item in effect_cues),
    }


def apply(job_name: str, approved: bool) -> dict[str, Any]:
    if not approved:
        raise ValueError("Brak jawnej akceptacji. Użyj --approved po przeczytaniu raportu.")
    output_paths = paths(job_name)
    package = read_json(output_paths["package"])
    artifact = read_json(output_paths["proposal"])
    plan_path = JOBS / f"{job_name}.json"
    plan = read_json(plan_path)
    if artifact.get("status") != "needs-review":
        raise ValueError("Raport został już zastosowany albo nie jest gotowy do akceptacji.")
    if artifact.get("planSignature") != plan_signature(plan):
        raise ValueError("Plan historii zmienił się po utworzeniu propozycji. Uruchom reżysera ponownie.")
    application = application_from_proposal(artifact["proposal"], package["timelineDurationMs"])
    for field in ("overlays", "effectCues", "soundEffects"):
        manual = [item for item in plan.get(field, []) if item.get("generatedBy") != DIRECTOR_ID]
        plan[field] = manual + application[field]
    plan["visualBeats"] = application["visualBeats"]
    plan["referenceBuildingBlocksRequired"] = application[
        "referenceBuildingBlocksRequired"
    ]
    notes = list(plan.get("notes", []))
    notes.append("Semantic Director: zaakceptowana reżyseria beatów została zastosowana.")
    plan["notes"] = notes
    artifact["status"] = "approved"
    artifact["appliedAt"] = utc_now()
    write_json(plan_path, plan)
    write_json(output_paths["proposal"], artifact)
    output_paths["report"].write_text(render_report(artifact, package), encoding="utf-8")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["prepare", "reference", "target", "plan", "import-cline", "apply", "status"],
    )
    parser.add_argument("source", help="Nazwa MP4 z input/ albo nazwa joba")
    parser.add_argument("--reference", type=Path, default=REFERENCE_DEFAULT)
    parser.add_argument("--approved-budget", type=float)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    job_name = Path(args.source).stem
    output_paths = paths(job_name)
    if args.command == "prepare":
        package = prepare(job_name, args.reference.expanduser().resolve())
        print(f"Pakiet reżyserski: {output_paths['package']}")
        print(f"Beaty: {len(package['timelineBeats'])} · materiały: {len(package['assets'])} · koszt API: 0 USD")
    elif args.command == "reference":
        artifact = run_reference(job_name, args.approved_budget)
        print(f"Analiza referencji: {output_paths['reference']} · koszt: {artifact['costUsd']:.6f} USD")
    elif args.command == "target":
        artifact = run_target(job_name, args.approved_budget)
        print(f"Analiza materiału: {output_paths['target']} · koszt: {artifact['costUsd']:.6f} USD")
    elif args.command == "plan":
        artifact = run_director(job_name, args.approved_budget)
        print(f"Raport do akceptacji: {output_paths['report']} · koszt: {artifact['costUsd']:.6f} USD")
    elif args.command == "import-cline":
        import_cline_proposal(job_name)
        print(f"Propozycja Cline zwalidowana: {output_paths['report']}")
        print("Plan i render nie zostały zmienione.")
    elif args.command == "apply":
        apply(job_name, args.approved)
        print(f"Reżyseria wpisana do planu: {JOBS / f'{job_name}.json'}")
        print("Render nie został uruchomiony.")
    else:
        print(
            json.dumps(
                {
                    "package": output_paths["package"].is_file(),
                    "reference": output_paths["reference"].is_file(),
                    "target": output_paths["target"].is_file(),
                    "proposal": output_paths["proposal"].is_file(),
                    "report": output_paths["report"].is_file(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
