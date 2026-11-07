#!/usr/bin/env python3
"""Check the saved OpenRouter credential without exposing it or calling a model."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from openrouter_keychain import load_openrouter_key


STATUS_PATH = Path(__file__).resolve().parents[1] / "analysis" / "openrouter-auth-check.json"


def report(value: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(value))


def main() -> None:
    try:
        key = load_openrouter_key()
    except Exception as exc:
        report({"authenticated": False, "keychainError": str(exc)})
        raise SystemExit(1)
    if not key:
        report({"authenticated": False, "keychainError": "Brak klucza OpenRouter w macOS Keychain."})
        raise SystemExit(1)
    shape = {
        "length": len(key),
        "startsExpected": key.startswith("sk-or-v1-"),
        "hasWhitespace": any(character.isspace() for character in key),
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(raw).get("error", {}).get("message", "")
        except json.JSONDecodeError:
            message = raw[:160]
        report({"credential": shape, "httpStatus": exc.code, "authenticated": False, "error": message})
        raise SystemExit(1)
    data = body.get("data", {})
    report(
        {
            "credential": shape,
            "httpStatus": response.status,
            "authenticated": True,
            "labelPresent": bool(data.get("label")),
            "isFreeTier": data.get("is_free_tier"),
        }
    )


if __name__ == "__main__":
    main()
