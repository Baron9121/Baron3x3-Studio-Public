#!/usr/bin/env python3
"""One-shot paid video+audio smoke test for the controlled OpenRouter client."""

from __future__ import annotations

import base64
import getpass
import json
import os
from pathlib import Path

try:
    from scripts.openrouter_client import OpenRouterClient
except ModuleNotFoundError:  # Direct execution from scripts/.
    from openrouter_client import OpenRouterClient


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "input" / "pipeline-smoke.mp4"
OUTPUT = ROOT / "analysis" / "api-smoke" / "video-audio-smoke.json"
MODEL = "google/gemini-3.7-flash"

SCHEMA = {
    "type": "object",
    "properties": {
        "visualDescription": {"type": "string"},
        "speechSummary": {"type": "string"},
        "heardPolishText": {"type": "string"},
        "timestamps": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "startSec": {"type": "number", "minimum": 0, "maximum": 3.2},
                    "endSec": {"type": "number", "minimum": 0, "maximum": 3.2},
                    "evidence": {"type": "string"},
                },
                "required": ["startSec", "endSec", "evidence"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "visualDescription",
        "speechSummary",
        "heardPolishText",
        "timestamps",
        "confidence",
    ],
    "additionalProperties": False,
}


def video_data_url(source: Path) -> str:
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return f"data:video/mp4;base64,{encoded}"


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Brak krótkiego pliku testowego: {SOURCE}")

    api_key = os.environ.get("OPENROUTER_API_KEY") or getpass.getpass(
        "Wklej klucz OpenRouter (nie będzie widoczny ani zapisany): "
    )
    if not api_key:
        raise SystemExit("Nie podano klucza. Test nie został wysłany.")

    client = OpenRouterClient(api_key=api_key, max_attempts=1, timeout_seconds=120)
    result = client.complete_json(
        job_id="api-video-smoke",
        stage="video_analysis",
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Przeanalizuj jednocześnie obraz i dźwięk tego około "
                            "trzysekundowego polskiego MP4. Opisz to, co faktycznie "
                            "widać, streść wypowiedź, zapisz możliwie dokładnie "
                            "usłyszany polski tekst i podaj 1–4 timestampy z dowodami. "
                            "Nie zgaduj treści niewidocznej ani niesłyszalnej. Zwróć "
                            "wyłącznie JSON zgodny ze schematem."
                        ),
                    },
                    {
                        "type": "video_url",
                        "video_url": {"url": video_data_url(SOURCE)},
                    },
                ],
            }
        ],
        schema_name="baron3x3_video_audio_smoke",
        schema=SCHEMA,
        budget_limit_usd=0.10,
        max_request_cost_usd=0.05,
        max_completion_tokens=1200,
        token_limit_field="max_tokens",
        reasoning_effort="low",
        use_cache=True,
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "source": SOURCE.name,
        "model": result.model,
        "requestId": result.request_id,
        "promptTokens": result.prompt_tokens,
        "completionTokens": result.completion_tokens,
        "costUsd": result.cost_usd,
        "attempts": result.attempts,
        "analysis": result.data,
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.data, ensure_ascii=False))
    print(
        f"model={result.model} prompt_tokens={result.prompt_tokens} "
        f"completion_tokens={result.completion_tokens} cost_usd={result.cost_usd:.8f} "
        f"attempts={result.attempts}"
    )


if __name__ == "__main__":
    main()
