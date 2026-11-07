#!/usr/bin/env python3
"""Controlled OpenRouter client for Baron3x3 pipeline stages.

The client never executes model-generated commands. It accepts only structured
JSON, keeps secrets out of artifacts, and checks a per-job budget before every
network request.
"""

from __future__ import annotations

import math
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
RETRYABLE_STATUSES = {408, 429, 500, 502, 503}

MODEL_ROUTES = {
    "video_analysis": "google/gemini-3.7-flash",
    "video_analysis_hard": "google/gemini-3.1-pro-preview",
    "reference_analysis": "google/gemini-3.1-pro-preview",
    "polish_correction": "openai/gpt-5.6-terra",
    "polish_correction_hard": "openai/gpt-5.6-sol",
    "edit_plan": "openai/gpt-5.6-sol",
    "edit_plan_pro": "openai/gpt-5.6-sol-pro",
    "preview_qa": "google/gemini-3.7-flash",
    "preview_qa_hard": "google/gemini-3.1-pro-preview",
    "final_story_check": "openai/gpt-5.6-sol",
}


class OpenRouterError(RuntimeError):
    pass


class MissingApiKey(OpenRouterError):
    pass


class BudgetExceeded(OpenRouterError):
    pass


class ResponseValidationError(OpenRouterError):
    pass


class TransportError(OpenRouterError):
    pass


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: dict[str, Any]


Transport = Callable[[str, dict[str, str], dict[str, Any], float], TransportResponse]


@dataclass(frozen=True)
class CompletionResult:
    data: dict[str, Any]
    model: str
    request_id: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    attempts: int
    cache_hit: bool


def model_for(stage: str) -> str:
    try:
        return MODEL_ROUTES[stage]
    except KeyError as exc:
        raise ValueError(f"Nieznany etap routingu modelu: {stage}") from exc


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def redact_secrets(text: str, api_key: str | None = None) -> str:
    redacted = text.replace(api_key, "[REDACTED]") if api_key else text
    return re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[REDACTED]", redacted)


def _default_transport(
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> TransportResponse:
    request = urllib.request.Request(endpoint, data=_json_bytes(payload), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return TransportResponse(response.status, json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"error": {"message": raw[:500]}}
        return TransportResponse(exc.code, body)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TransportError(str(exc)) from exc


def validate_schema(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the strict JSON Schema subset used by this project."""
    expected = schema.get("type")
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if expected in checks and not checks[expected](value):
        raise ResponseValidationError(f"{path}: oczekiwano typu {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ResponseValidationError(f"{path}: wartość nie należy do enum")

    if expected == "object":
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                raise ResponseValidationError(f"{path}: brak wymaganego pola {name}")
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(properties)
            if extras:
                raise ResponseValidationError(f"{path}: niedozwolone pola: {', '.join(sorted(extras))}")
        for name, item in value.items():
            if name in properties:
                validate_schema(item, properties[name], f"{path}.{name}")
    elif expected == "array":
        if len(value) < schema.get("minItems", 0):
            raise ResponseValidationError(f"{path}: za mało elementów")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ResponseValidationError(f"{path}: za dużo elementów")
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], f"{path}[{index}]")
    elif expected in {"number", "integer"}:
        if "minimum" in schema and value < schema["minimum"]:
            raise ResponseValidationError(f"{path}: wartość poniżej minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ResponseValidationError(f"{path}: wartość powyżej maksimum")
    elif expected == "string" and "pattern" in schema and not re.search(schema["pattern"], value):
        raise ResponseValidationError(f"{path}: tekst nie pasuje do wzorca")


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 60,
        max_attempts: int = 2,
        transport: Transport = _default_transport,
        ledger_dir: Path | None = None,
        cache_dir: Path | None = None,
        error_dir: Path | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.transport = transport
        self.ledger_dir = ledger_dir or ROOT / "analysis" / "api-costs"
        self.cache_dir = cache_dir or ROOT / "analysis" / "api-cache"
        self.error_dir = error_dir or ROOT / "analysis" / "api-errors"
        self.sleep = sleep

    def _ledger_path(self, job_id: str) -> Path:
        safe_job_id = re.sub(r"[^A-Za-z0-9._-]+", "-", job_id).strip("-")
        if not safe_job_id:
            raise ValueError("Pusty identyfikator joba")
        return self.ledger_dir / f"{safe_job_id}.json"

    def _read_ledger(self, job_id: str) -> dict[str, Any]:
        path = self._ledger_path(job_id)
        if not path.is_file():
            return {"jobId": job_id, "spentUsd": 0.0, "calls": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def complete_json(
        self,
        *,
        job_id: str,
        stage: str,
        messages: list[dict[str, Any]],
        schema_name: str,
        schema: dict[str, Any],
        budget_limit_usd: float,
        max_request_cost_usd: float,
        model: str | None = None,
        max_completion_tokens: int = 1200,
        token_limit_field: str = "max_completion_tokens",
        reasoning_effort: str | None = None,
        use_cache: bool = True,
        enable_provider_prompt_cache: bool = True,
        enable_response_healing: bool = False,
    ) -> CompletionResult:
        if not self.api_key:
            raise MissingApiKey("Brak OPENROUTER_API_KEY w środowisku")
        if self.max_attempts < 1 or self.max_attempts > 2:
            raise ValueError("max_attempts musi mieścić się w zakresie 1–2")
        selected_model = model or model_for(stage)
        if token_limit_field not in {"max_completion_tokens", "max_tokens"}:
            raise ValueError("token_limit_field musi być max_completion_tokens albo max_tokens")
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            "provider": {"require_parameters": True},
            "session_id": f"baron3x3:{job_id}:{stage}"[:256],
        }
        payload[token_limit_field] = max_completion_tokens
        if enable_provider_prompt_cache:
            payload["cache_control"] = {"type": "ephemeral"}
        if enable_response_healing:
            payload["plugins"] = [{"id": "response-healing"}]
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        cache_hash = hashlib.sha256(_json_bytes(payload)).hexdigest()
        cache_path = self.cache_dir / f"{cache_hash}.json"
        if use_cache and cache_path.is_file():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            validate_schema(cached["data"], schema)
            return CompletionResult(
                data=cached["data"], model=cached["model"], request_id=cached["requestId"],
                prompt_tokens=0, completion_tokens=0, cost_usd=0.0, attempts=0, cache_hit=True,
            )

        ledger = self._read_ledger(job_id)
        if ledger.get("unresolvedCost"):
            raise BudgetExceeded("Nierozliczony koszt poprzedniego żądania; wymagane rozliczenie przed kolejnym wywołaniem")
        spent = float(ledger.get("spentUsd", 0.0))
        if max_request_cost_usd <= 0 or spent + max_request_cost_usd > budget_limit_usd + 1e-12:
            raise BudgetExceeded(
                f"Limit joba {budget_limit_usd:.4f} USD; wydano {spent:.4f} USD; "
                f"rezerwacja kolejnego żądania {max_request_cost_usd:.4f} USD"
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Metadata": "enabled",
            "X-Title": "Baron3x3-Local",
        }
        started = time.monotonic()
        response: TransportResponse | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.transport(self.endpoint, headers, payload, self.timeout_seconds)
            except TransportError:
                if attempt == self.max_attempts:
                    raise
                self.sleep(0.5 * attempt)
                continue
            if response.status in RETRYABLE_STATUSES and attempt < self.max_attempts:
                self.sleep(0.5 * attempt)
                continue
            break
        assert response is not None
        if response.status != 200:
            message = str(response.body.get("error", {}).get("message", f"HTTP {response.status}"))
            raise OpenRouterError(redact_secrets(message, self.api_key))

        usage = response.body.get("usage", {})
        try:
            cost = float(usage["cost"])
            if not math.isfinite(cost) or cost < 0:
                raise ValueError("Invalid cost")
        except (KeyError, TypeError, ValueError):
            ledger["unresolvedCost"] = True
            ledger.setdefault("calls", []).append({"stage": stage, "model": selected_model, "requestId": response.body.get("id"), "costUsd": None, "status": "cost-unknown"})
            _write_json_atomic(self._ledger_path(job_id), ledger)
            raise BudgetExceeded("API nie podało poprawnego kosztu. Zapisano koszt nieznany; zatrzymano kolejne wydatki.")
        call = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "requestedModel": selected_model,
            "model": str(response.body.get("model", selected_model)),
            "requestId": str(response.body.get("id", "unknown")),
            "promptTokens": int(usage.get("prompt_tokens", 0)),
            "completionTokens": int(usage.get("completion_tokens", 0)),
            "costUsd": cost,
            "attempts": attempt,
            "durationMs": round((time.monotonic() - started) * 1000),
        }
        choices = response.body.get("choices", [])
        first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        call["finishReason"] = first_choice.get("finish_reason")
        call["nativeFinishReason"] = first_choice.get("native_finish_reason")
        completion_details = usage.get("completion_tokens_details", {})
        if isinstance(completion_details, dict):
            call["reasoningTokens"] = int(completion_details.get("reasoning_tokens", 0) or 0)
        try:
            content = response.body["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, dict):
                raise ResponseValidationError("Odpowiedź nie jest obiektem JSON")
            validate_schema(parsed, schema)
        except (
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ResponseValidationError,
        ) as exc:
            call["status"] = "invalid_response"
            ledger.setdefault("calls", []).append(call)
            ledger["spentUsd"] = round(spent + cost, 10)
            ledger["budgetLimitUsd"] = budget_limit_usd
            _write_json_atomic(self._ledger_path(job_id), ledger)

            raw_content = locals().get("content", "")
            safe_content = redact_secrets(str(raw_content), self.api_key)
            diagnostic = {
                "timestamp": call["timestamp"],
                "jobId": job_id,
                "stage": stage,
                "model": call["model"],
                "requestId": call["requestId"],
                "costUsd": cost,
                "errorType": type(exc).__name__,
                "finishReason": call["finishReason"],
                "nativeFinishReason": call["nativeFinishReason"],
                "reasoningTokens": call.get("reasoningTokens", 0),
                "contentSha256": hashlib.sha256(safe_content.encode("utf-8")).hexdigest(),
                "contentPreview": safe_content[:4000],
            }
            _write_json_atomic(self.error_dir / f"{job_id}-{call['requestId']}.json", diagnostic)
            raise ResponseValidationError("Nieprawidłowa odpowiedź OpenRoutera") from exc

        call["status"] = "success"
        ledger.setdefault("calls", []).append(call)
        ledger["spentUsd"] = round(spent + cost, 10)
        ledger["budgetLimitUsd"] = budget_limit_usd
        _write_json_atomic(self._ledger_path(job_id), ledger)

        cached_value = {
            "data": parsed,
            "model": call["model"],
            "requestId": call["requestId"],
        }
        if use_cache:
            _write_json_atomic(cache_path, cached_value)
        return CompletionResult(
            data=parsed,
            model=call["model"],
            request_id=call["requestId"],
            prompt_tokens=call["promptTokens"],
            completion_tokens=call["completionTokens"],
            cost_usd=cost,
            attempts=attempt,
            cache_hit=False,
        )
