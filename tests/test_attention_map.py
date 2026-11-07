from __future__ import annotations

import unittest

from scripts.attention_map import (
    Rect,
    evaluate_records,
    intersection_area,
    primary_face,
    recommended_title_zone,
)


class AttentionMapTests(unittest.TestCase):
    def test_intersection_area(self):
        self.assertEqual(intersection_area(Rect(0, 0, 100, 100), Rect(50, 50, 100, 100)), 2500)

    def test_title_moves_away_from_face(self):
        record = {
            "timestampMs": 1000,
            "faces": [{"x": 250, "y": 50, "width": 580, "height": 500}],
            "textLike": [],
            "salient": [],
            "roundCandidates": [],
        }
        placement, scores = recommended_title_zone(record)
        self.assertNotEqual(placement, "top")
        self.assertGreater(scores["top"], scores[placement])

    def test_unsafe_title_fails(self):
        plan = {
            "effectCues": [
                {
                    "id": "title",
                    "type": "kinetic-text",
                    "timelineStartMs": 1000,
                    "timelineEndMs": 2200,
                    "placement": "top",
                }
            ]
        }
        records = [
            {
                "timestampMs": 900,
                "faces": [{"x": 300, "y": 120, "width": 450, "height": 450}],
                "textLike": [],
                "salient": [],
                "roundCandidates": [],
            }
        ]
        result = evaluate_records(plan, records)
        self.assertEqual(result["verdict"], "fail-attention-safety")
        self.assertFalse(result["cueChecks"][0]["passed"])

    def test_safe_top_title_passes(self):
        plan = {
            "effectCues": [
                {
                    "id": "title",
                    "type": "kinetic-text",
                    "timelineStartMs": 1000,
                    "timelineEndMs": 2200,
                    "placement": "top",
                }
            ]
        }
        records = [
            {
                "timestampMs": 900,
                "faces": [{"x": 330, "y": 700, "width": 420, "height": 420}],
                "textLike": [],
                "salient": [],
                "roundCandidates": [],
            }
        ]
        result = evaluate_records(plan, records)
        self.assertEqual(result["verdict"], "pass-attention-safety")
        self.assertTrue(result["cueChecks"][0]["passed"])

    def test_small_background_face_does_not_fail_caption_gate(self):
        plan = {"effectCues": []}
        records = [
            {
                "timestampMs": 1000,
                "faces": [{"x": 520, "y": 1380, "width": 70, "height": 70}],
                "textLike": [],
                "salient": [],
                "roundCandidates": [],
            }
        ]
        result = evaluate_records(plan, records)
        self.assertEqual(result["verdict"], "pass-attention-safety")
        self.assertEqual(result["captionCollisions"], [])

    def test_primary_face_prefers_central_subject_over_larger_edge_face(self):
        record = {
            "faces": [
                {"x": 12, "y": 1400, "width": 215, "height": 215},
                {"x": 460, "y": 375, "width": 168, "height": 168},
            ]
        }
        self.assertEqual(primary_face(record), Rect(460, 375, 168, 168))

    def test_only_edge_face_still_fails_crop_gate(self):
        plan = {
            "effectCues": [],
            "overlays": [
                {"id": "edge-subject", "timelineStartMs": 0, "timelineEndMs": 1000}
            ],
        }
        records = [
            {
                "timestampMs": 500,
                "faces": [{"x": 5, "y": 500, "width": 260, "height": 260}],
                "textLike": [],
                "salient": [],
                "roundCandidates": [],
            }
        ]
        result = evaluate_records(plan, records)
        self.assertEqual(result["verdict"], "fail-attention-safety")
        self.assertFalse(result["cropChecks"][0]["passed"])

    def test_mostly_black_render_fails(self):
        plan = {"effectCues": []}
        records = [
            {
                "timestampMs": index * 1000,
                "visiblePixelRatio": 0.02,
                "faces": [],
                "textLike": [],
                "salient": [],
                "roundCandidates": [],
            }
            for index in range(5)
        ]
        result = evaluate_records(plan, records)
        self.assertEqual(result["verdict"], "fail-attention-safety")
        self.assertEqual(result["blackFrameRatio"], 1.0)


if __name__ == "__main__":
    unittest.main()
