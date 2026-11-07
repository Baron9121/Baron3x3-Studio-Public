from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.openrouter_client import (
    BudgetExceeded,
    OpenRouterClient,
    ResponseValidationError,
    TransportResponse,
    redact_secrets,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "folder": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["folder", "confidence"],
    "additionalProperties": False,
}


def valid_response(cost: float = 0.001) -> TransportResponse:
    return TransportResponse(
        200,
        {
            "id": "test-request",
            "model": "openai/gpt-5.6-luna",
            "choices": [{"message": {"content": json.dumps({"folder": "Baron3x3-Local", "confidence": 1})}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20, "cost": cost},
        },
    )


class ClientTests(unittest.TestCase):
    def make_client(self, transport):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        return OpenRouterClient(
            api_key="sk-or-v1-FAKE-TEST-KEY",
            transport=transport,
            ledger_dir=root / "costs",
            cache_dir=root / "cache",
            error_dir=root / "errors",
            sleep=lambda _: None,
        ), root

    def call(self, client, **overrides):
        arguments = {
            "job_id": "smoke",
            "stage": "edit_plan",
            "model": "openai/gpt-5.6-luna",
            "messages": [{"role": "user", "content": "Podaj folder"}],
            "schema_name": "folder_test",
            "schema": SCHEMA,
            "budget_limit_usd": 0.02,
            "max_request_cost_usd": 0.01,
        }
        arguments.update(overrides)
        return client.complete_json(**arguments)

    def test_valid_json_is_accepted_and_cost_is_recorded(self):
        captured = {}

        def transport(endpoint, headers, payload, timeout):
            captured.update({"endpoint": endpoint, "headers": headers, "payload": payload, "timeout": timeout})
            return valid_response()

        client, root = self.make_client(transport)
        result = self.call(client)
        self.assertEqual(result.data["folder"], "Baron3x3-Local")
        self.assertEqual(result.cost_usd, 0.001)
        self.assertNotIn("tools", captured["payload"])
        self.assertEqual(captured["payload"]["response_format"]["type"], "json_schema")
        self.assertTrue(captured["payload"]["response_format"]["json_schema"]["strict"])
        self.assertTrue(captured["payload"]["provider"]["require_parameters"])
        ledger = json.loads((root / "costs" / "smoke.json").read_text())
        self.assertEqual(ledger["spentUsd"], 0.001)
        self.assertNotIn("FAKE-TEST-KEY", json.dumps(ledger))

    def test_invalid_json_is_rejected_and_billed(self):
        client, root = self.make_client(
            lambda *_: TransportResponse(
                200,
                {
                    "id": "bad",
                    "model": "test",
                    "choices": [{"message": {"content": '{"folder":"Baron3x3-Local"}'}}],
                    "usage": {"cost": 0.001},
                },
            )
        )
        with self.assertRaises(ResponseValidationError):
            self.call(client)
        ledger = json.loads((root / "costs" / "smoke.json").read_text())
        self.assertEqual(ledger["spentUsd"], 0.001)
        self.assertEqual(ledger["calls"][0]["status"], "invalid_response")
        diagnostics = list((root / "errors").glob("*.json"))
        self.assertEqual(len(diagnostics), 1)

    def test_budget_is_checked_before_transport(self):
        called = False

        def transport(*_):
            nonlocal called
            called = True
            return valid_response()

        client, _ = self.make_client(transport)
        with self.assertRaises(BudgetExceeded):
            self.call(client, budget_limit_usd=0.005, max_request_cost_usd=0.01)
        self.assertFalse(called)

    def test_retry_only_for_transient_status(self):
        responses = [TransportResponse(429, {"error": {"message": "rate limit"}}), valid_response()]
        client, _ = self.make_client(lambda *_: responses.pop(0))
        result = self.call(client)
        self.assertEqual(result.attempts, 2)

    def test_local_cache_avoids_second_transport_call(self):
        calls = 0

        def transport(*_):
            nonlocal calls
            calls += 1
            return valid_response()

        client, _ = self.make_client(transport)
        self.call(client)
        cached = self.call(client)
        self.assertTrue(cached.cache_hit)
        self.assertEqual(cached.cost_usd, 0)
        self.assertEqual(calls, 1)

    def test_secret_redaction(self):
        secret = "sk-" + "or-v1-" + "THIS-MUST-NOT-LEAK"
        self.assertEqual(redact_secrets(f"error {secret}", secret), "error [REDACTED]")

    def test_provider_prompt_cache_can_be_disabled_for_video(self):
        captured = {}

        def transport(_endpoint, _headers, payload, _timeout):
            captured.update(payload)
            return valid_response()

        client, _ = self.make_client(transport)
        self.call(client, enable_provider_prompt_cache=False)
        self.assertNotIn("cache_control", captured)
        self.assertTrue(captured["provider"]["require_parameters"])

    def test_gemini_can_use_supported_max_tokens_field(self):
        captured = {}

        def transport(_endpoint, _headers, payload, _timeout):
            captured.update(payload)
            return valid_response()

        client, _ = self.make_client(transport)
        self.call(client, token_limit_field="max_tokens")
        self.assertEqual(captured["max_tokens"], 1200)
        self.assertNotIn("max_completion_tokens", captured)

    def test_response_healing_plugin_can_be_enabled(self):
        captured = {}

        def transport(_endpoint, _headers, payload, _timeout):
            captured.update(payload)
            return valid_response()

        client, _ = self.make_client(transport)
        self.call(client, enable_response_healing=True)
        self.assertEqual(captured["plugins"], [{"id": "response-healing"}])

    def test_reasoning_effort_is_sent_explicitly(self):
        captured = {}

        def transport(_endpoint, _headers, payload, _timeout):
            captured.update(payload)
            return valid_response()

        client, _ = self.make_client(transport)
        self.call(client, reasoning_effort="low")
        self.assertEqual(captured["reasoning_effort"], "low")


if __name__ == "__main__":
    unittest.main()
