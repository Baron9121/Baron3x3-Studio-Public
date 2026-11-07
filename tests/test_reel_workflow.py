from __future__ import annotations

import unittest
from pathlib import Path

from scripts.reel_workflow import validate_stage_cost, validate_story_data


class ReelWorkflowTests(unittest.TestCase):
    def transcript(self):
        return {
            "segments": [
                {
                    "words": [
                        {"text": "Mocny", "startMs": 0, "endMs": 400},
                        {"text": "hook", "startMs": 420, "endMs": 800},
                        {"text": "Puenta", "startMs": 1000, "endMs": 1500},
                    ]
                }
            ]
        }

    def plan(self):
        return {
            "version": 1,
            "status": "needs-review",
            "instructions": "krótka historia",
            "captionStyle": "green-word",
            "storyPlan": {
                "hook": "Mocny hook",
                "arc": "rozwinięcie",
                "payoff": "Puenta",
                "languageReviewed": True,
            },
            "sourceRanges": [
                {"sourceStartMs": 0, "sourceEndMs": 800, "reason": "hook"},
                {"sourceStartMs": 1000, "sourceEndMs": 1500, "reason": "puenta"},
            ],
            "overlays": [],
            "effectCues": [],
            "soundEffects": [],
        }

    def test_valid_story_stops_at_review_and_preserves_word_edges(self):
        result = validate_story_data(self.plan(), self.transcript(), Path("job.json"))
        self.assertEqual(result["wordBoundaries"], "pass")
        self.assertEqual(result["rangeCount"], 2)

    def test_ready_is_rejected_before_user_approval(self):
        plan = self.plan()
        plan["status"] = "ready"
        with self.assertRaisesRegex(ValueError, "needs-review"):
            validate_story_data(plan, self.transcript(), Path("job.json"))

    def test_missing_polish_review_is_rejected(self):
        plan = self.plan()
        plan["storyPlan"]["languageReviewed"] = False
        with self.assertRaisesRegex(ValueError, "polszczyzny"):
            validate_story_data(plan, self.transcript(), Path("job.json"))

    def test_mid_word_cut_is_rejected(self):
        plan = self.plan()
        plan["sourceRanges"][0]["sourceEndMs"] = 600
        with self.assertRaisesRegex(ValueError, "przecina słowo"):
            validate_story_data(plan, self.transcript(), Path("job.json"))

    def test_paid_stage_cost_is_capped(self):
        self.assertEqual(validate_stage_cost(0.3), 0.3)
        with self.assertRaisesRegex(ValueError, "0–0.30"):
            validate_stage_cost(0.3001)


if __name__ == "__main__":
    unittest.main()
