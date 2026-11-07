#!/usr/bin/env python3
"""One-shot paid smoke test for the controlled OpenRouter client."""

from __future__ import annotations

import getpass
import json
import os

from openrouter_client import OpenRouterClient


MODEL = "openai/gpt-5.6-luna"
SCHEMA = {
    "type": "object",
    "properties": {
        "project": {"type": "string"},
        "status": {"type": "string", "enum": ["ok"]},
    },
    "required": ["project", "status"],
    "additionalProperties": False,
}


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY") or getpass.getpass(
        "Wklej klucz OpenRouter (nie będzie widoczny ani zapisany): "
    )
    if not api_key:
        raise SystemExit("Nie podano klucza. Test nie został wysłany.")

    client = OpenRouterClient(api_key=api_key, max_attempts=1)
    result = client.complete_json(
        job_id="api-text-smoke",
        stage="edit_plan",
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "Zwróć wyłącznie JSON zgodny ze schematem. "
                    "Ustaw project na Baron3x3-Local, a status na ok."
                ),
            }
        ],
        schema_name="baron3x3_api_smoke",
        schema=SCHEMA,
        budget_limit_usd=0.02,
        max_request_cost_usd=0.02,
        max_completion_tokens=64,
        use_cache=False,
    )
    print(json.dumps(result.data, ensure_ascii=False))
    print(
        f"model={result.model} prompt_tokens={result.prompt_tokens} "
        f"completion_tokens={result.completion_tokens} cost_usd={result.cost_usd:.8f} "
        f"attempts={result.attempts}"
    )


if __name__ == "__main__":
    main()
