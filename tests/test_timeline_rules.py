from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.timeline_rules import apply_timeline_rules

ROOT = Path(__file__).resolve().parents[1]


def _ov(asset: str, start: int, end: int) -> dict:
    return {"assetId": asset, "timelineStartMs": start, "timelineEndMs": end}


class TimelineRulesTests(unittest.TestCase):
    def test_hook_lock_removes_overlays_in_hook(self):
        hook = 15560
        overlays = [
            _ov("baronmatte", 120, 6920),
            _ov("jimmer-video-a", 14999, 23278),
            _ov("jimmer-video-b", 23278, 30278),
            _ov("img-warszawa", 60000, 66000),
        ]
        result = apply_timeline_rules(overlays, hook_end_ms=hook)
        self.assertEqual([o["assetId"] for o in result], ["jimmer-video-b", "img-warszawa"])

    def test_bridge_small_gaps_merges_brolls(self):
        overlays = [
            _ov("a", 15000, 20000),
            _ov("b", 20000, 26000),
            _ov("c", 26000, 32000),
        ]
        result = apply_timeline_rules(overlays, hook_end_ms=0)
        # przerwy 0 ms < 3000 ms => nie ma A-rolla pomiedzy; wszystkie zostaja przylegajace
        self.assertEqual([o["assetId"] for o in result], ["a", "b", "c"])
        self.assertEqual(result[0]["timelineEndMs"], result[1]["timelineStartMs"])

    def test_no_change_when_gaps_large_but_rule_applies_to_real_plan(self):
        # Plan #2: wszystkie overlaye >= 3000 ms po hook-lock => funkcja nie usuwa zadnego
        plan = json.loads(
            (ROOT / "instructions/jobs/#2.json").read_text(encoding="utf-8")
        )
        hook = int(plan.get("hookLockUntilMs", 0))
        overlays = plan.get("overlays", [])
        result = apply_timeline_rules(overlays, hook_end_ms=hook)
        self.assertTrue(result)  # cos zostaje (przebitki po hooku)
        for o in result:
            self.assertGreaterEqual(o["timelineStartMs"], hook)


if __name__ == "__main__":
    unittest.main()