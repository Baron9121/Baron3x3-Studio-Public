from __future__ import annotations

import unittest

from scripts.preview_qa import evaluate, overlapping_strong_effects, parse_rate


def valid_plan():
    return {
        "sourceRanges": [{"sourceStartMs": 1000, "sourceEndMs": 7000}],
        "minimumSceneDurationMs": 3000,
        "captionStyle": "green-word",
        "visualBeats": [
            {"timelineStartMs": 0, "timelineEndMs": 3000},
            {"timelineStartMs": 3000, "timelineEndMs": 6000},
        ],
        "overlays": [
            {"assetId": "a", "timelineStartMs": 0, "timelineEndMs": 3000},
            {"assetId": "b", "timelineStartMs": 3000, "timelineEndMs": 6000, "fadeOut": False},
        ],
        "effectCues": [{"type": "stat-card", "timelineStartMs": 1000, "timelineEndMs": 2500}],
        "soundEffects": [],
    }


def valid_probe():
    return {
        "format": {"duration": "6.000"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1080, "height": 1920, "avg_frame_rate": "30/1"},
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
        ],
    }


class PreviewQaTests(unittest.TestCase):
    def test_parse_fractional_rate(self):
        self.assertAlmostEqual(parse_rate("30000/1001"), 29.97002997)

    def test_valid_preview_needs_semantic_review(self):
        result = evaluate(valid_plan(), valid_probe())
        self.assertEqual(result["verdict"], "pass-local-gates-needs-semantic-review")
        self.assertTrue(result["semanticReview"]["required"])

    def test_allows_approved_talking_head_when_assets_are_semantically_wrong(self):
        plan = valid_plan()
        plan["overlays"] = []
        plan["effectCues"] = []
        plan["referenceBuildingBlocksRequired"] = False
        result = evaluate(plan, valid_probe())
        self.assertEqual(result["verdict"], "pass-local-gates-needs-semantic-review")

    def test_short_scene_and_duplicate_fail(self):
        plan = valid_plan()
        plan["overlays"][0]["timelineEndMs"] = 2000
        plan["overlays"][1]["assetId"] = "a"
        result = evaluate(plan, valid_probe())
        failed = {item["id"] for item in result["checks"] if not item["passed"]}
        self.assertIn("scene-minimum", failed)

    def test_short_a_roll_fails(self):
        plan = valid_plan()
        plan["sourceRanges"] = [{"sourceStartMs": 1000, "sourceEndMs": 2500}]
        result = evaluate(plan, valid_probe())
        failed = {item["id"] for item in result["checks"] if not item["passed"]}
        self.assertIn("scene-minimum-a-roll", failed)

    def test_detects_overlapping_strong_effects(self):
        effects = [
            {"type": "flash", "timelineStartMs": 100, "timelineEndMs": 500},
            {"type": "whip", "timelineStartMs": 400, "timelineEndMs": 800},
        ]
        self.assertEqual(overlapping_strong_effects(effects), [("flash", "whip")])

    def test_paper_reveal_is_a_strong_effect(self):
        effects = [
            {"type": "paper-reveal", "timelineStartMs": 100, "timelineEndMs": 1000},
            {"type": "light-leak", "timelineStartMs": 900, "timelineEndMs": 1200},
        ]
        self.assertEqual(
            overlapping_strong_effects(effects),
            [("paper-reveal", "light-leak")],
        )


if __name__ == "__main__":
    unittest.main()
