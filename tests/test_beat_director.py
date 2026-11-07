from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.beat_director import application_from_proposal, make_story_proxy, validate_proposal


class BeatDirectorTests(unittest.TestCase):
    def package(self):
        return {
            "timelineDurationMs": 4000,
            "timelineBeats": [
                {"id": "beat-001", "text": "Mocny hook", "timelineStartMs": 0, "timelineEndMs": 1800},
                {"id": "beat-002", "text": "12 punktów", "timelineStartMs": 1900, "timelineEndMs": 4000},
            ],
            "assets": [
                {"assetId": "asset-good", "name": "Akcja", "kind": "video", "durationMs": 10000},
                {"assetId": "photo-main", "name": "Emocja", "kind": "image", "durationMs": 10000},
                {"assetId": "photo-team", "name": "Drużyna", "kind": "image", "durationMs": 10000},
                {"assetId": "photo-action", "name": "Akcja foto", "kind": "image", "durationMs": 10000},
            ],
        }

    def proposal(self):
        common = {
            "narrativeFunction": "hook",
            "energy": 4,
            "zoomLevel": "wide",
            "brollPresentation": "full",
            "brollMotion": "still",
            "secondaryAssetId": "",
            "collageAssetIds": [],
            "secondaryAssetSourceStartMs": 0,
            "editorialHeadline": "",
            "editorialKicker": "",
            "transitionEffect": "smooth",
            "visualEffect": "none",
            "soundEffect": "none",
            "soundVolume": 0.0,
            "statValue": "",
            "statLabel": "",
            "reason": "semantyczny powód",
            "referenceEvidence": "wzorzec z referencji",
            "confidence": 0.9,
        }
        return {
            "overallStrategy": "strategia",
            "referenceMatch": "wysoka",
            "missingAssets": [],
            "qualityRisks": [],
            "beats": [
                {
                    **common,
                    "beatId": "beat-001",
                    "timelineStartMs": 0,
                    "timelineEndMs": 1800,
                    "onScreen": "broll",
                    "assetId": "asset-good",
                    "assetSourceStartMs": 1000,
                },
                {
                    **common,
                    "beatId": "beat-002",
                    "timelineStartMs": 1900,
                    "timelineEndMs": 4000,
                    "narrativeFunction": "proof",
                    "onScreen": "stat-card",
                    "assetId": "",
                    "assetSourceStartMs": 0,
                    "visualEffect": "none",
                    "soundEffect": "impact",
                    "soundVolume": 0.22,
                    "statValue": "12",
                    "statLabel": "PUNKTÓW",
                },
            ],
        }

    def test_validates_known_assets_and_exact_timeline(self):
        validate_proposal(self.proposal(), self.package())

    def test_rejects_invented_asset(self):
        proposal = self.proposal()
        proposal["beats"][0]["assetId"] = "invented"
        with self.assertRaisesRegex(ValueError, "nieistniejący"):
            validate_proposal(proposal, self.package())

    def test_rejects_changed_beat_boundary(self):
        proposal = self.proposal()
        proposal["beats"][0]["timelineEndMs"] = 1700
        with self.assertRaisesRegex(ValueError, "zmienił granice"):
            validate_proposal(proposal, self.package())

    def test_builds_complete_application_without_rendering(self):
        result = application_from_proposal(self.proposal(), 4000)
        self.assertEqual(result["visualBeats"][0]["timelineStartMs"], 0)
        self.assertEqual(result["visualBeats"][-1]["timelineEndMs"], 4000)
        self.assertEqual(result["overlays"][0]["assetId"], "asset-good")
        self.assertEqual(result["overlays"][0]["presentation"], "full")
        self.assertEqual(result["overlays"][0]["motion"], "still")
        self.assertEqual(result["effectCues"][0]["type"], "stat-card")
        self.assertEqual(result["soundEffects"][0]["type"], "impact")
        self.assertTrue(result["referenceBuildingBlocksRequired"])

    def test_merges_adjacent_smooth_beats_with_the_same_zoom(self):
        proposal = self.proposal()
        proposal["beats"][1]["zoomLevel"] = proposal["beats"][0]["zoomLevel"]
        proposal["beats"][1]["transitionEffect"] = "smooth"
        result = application_from_proposal(proposal, 4000)
        self.assertEqual(len(result["visualBeats"]), 1)
        self.assertEqual(result["visualBeats"][0]["timelineStartMs"], 0)
        self.assertEqual(result["visualBeats"][0]["timelineEndMs"], 4000)

    def test_rejects_second_strong_effect_on_stat_card(self):
        proposal = self.proposal()
        proposal["beats"][1]["visualEffect"] = "light-leak"
        with self.assertRaisesRegex(ValueError, "drugiego silnego efektu"):
            validate_proposal(proposal, self.package())

    def test_rejects_disabled_paper_collage(self):
        proposal = self.proposal()
        beat = proposal["beats"][0]
        beat["assetId"] = "photo-main"
        beat["brollPresentation"] = "paper-collage"
        beat["collageAssetIds"] = ["photo-team", "photo-action"]

        with self.assertRaisesRegex(ValueError, "niedozwolona prezentacja"):
            validate_proposal(proposal, self.package())

    def test_rejects_unapproved_experimental_split(self):
        proposal = self.proposal()
        proposal["beats"][0]["brollPresentation"] = "split"
        proposal["beats"][0]["secondaryAssetId"] = "photo-main"
        with self.assertRaisesRegex(ValueError, "niedozwolona prezentacja"):
            validate_proposal(proposal, self.package())

    def test_story_proxy_uses_only_approved_ranges_and_returns_source_map(self):
        ranges = [
            {"sourceStartMs": 436780, "sourceEndMs": 442640},
            {"sourceStartMs": 448840, "sourceEndMs": 461580},
        ]
        captured = []

        def fake_run(command, **kwargs):
            captured.extend(command)
            Path(command[-1]).write_bytes(b"proxy")

        with TemporaryDirectory() as directory, patch("scripts.beat_director.subprocess.run", fake_run):
            destination = Path(directory) / "target-proxy.mp4"
            mapping = make_story_proxy(Path("large-source.mp4"), destination, 6, ranges)

            self.assertTrue(destination.is_file())
            self.assertEqual(captured.count("-i"), 2)
            self.assertIn("436.780", captured)
            self.assertIn("5.860", captured)
            self.assertIn("448.840", captured)
            self.assertIn("12.740", captured)
            self.assertEqual(mapping[0]["proxyStartMs"], 0)
            self.assertEqual(mapping[1]["proxyStartMs"], 5860)
            self.assertEqual(mapping[1]["sourceEndMs"], 461580)


if __name__ == "__main__":
    unittest.main()
