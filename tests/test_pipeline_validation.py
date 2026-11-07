from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.pipeline import (
    browser_compatible_video,
    choose_color_pipeline,
    build_effect_cues,
    build_visual_beats,
    normalize_transcript,
    timeline_captions,
    validate_plan,
    validate_word_boundaries,
)


class RenderCompatibilityTests(unittest.TestCase):
    def test_accepts_browser_safe_h264(self) -> None:
        self.assertTrue(browser_compatible_video({"codec": "h264", "pixelFormat": "yuv420p"}))

    def test_rejects_camera_hevc_422_10_bit(self) -> None:
        self.assertFalse(browser_compatible_video({"codec": "hevc", "pixelFormat": "yuv422p10le"}))

    def test_c70_generic_standard_tags_do_not_override_unknown_transfer(self) -> None:
        with self.assertRaisesRegex(ValueError, "Nie można jednoznacznie"):
            choose_color_pipeline({
                "stream": {
                    "colorSpace": "bt709",
                    "colorTransfer": "",
                    "colorPrimaries": "",
                    "colorRange": "pc",
                },
                "makerNotes": {
                    "IFD0:Model": "Canon EOS C70",
                    "Canon:ToneCurve": "Standard",
                    "Canon:ColorSpace": "sRGB",
                    "ExifIFD:RecommendedExposureIndex": 160,
                },
            })

    def test_explicit_canon_log3_uses_official_lut(self) -> None:
        decision = choose_color_pipeline(
            {"stream": {}, "makerNotes": {"IFD0:Model": "Canon EOS C70"}},
            "canon-log-3-cinema-gamut",
        )
        self.assertEqual(decision["inputProfile"], "canon-log-3-cinema-gamut")
        self.assertEqual(
            decision["lut"],
            "canon/CinemaGamut_CanonLog3-to-Canon709_33_Ver.1.0.cube",
        )

    def test_ambiguous_gamma_requires_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "Nie można jednoznacznie"):
            choose_color_pipeline({
                "stream": {"colorSpace": "bt709", "colorTransfer": ""},
                "makerNotes": {"IFD0:Model": "Canon EOS C70"},
            })


class WordTimingCorrectionTests(unittest.TestCase):
    def test_repairs_whisper_word_spanning_a_long_pause(self) -> None:
        raw = {
            "language": "pl",
            "segments": [{
                "start": 1.0,
                "end": 8.0,
                "words": [{
                    "word": " mocniejszym",
                    "start": 2.0,
                    "end": 7.0,
                    "probability": 1.0,
                }],
            }],
        }
        _, words = normalize_transcript(
            raw,
            Path("source.mp4"),
            {},
            [{
                "text": "mocniejszym",
                "originalStartMs": 2000,
                "originalEndMs": 7000,
                "startMs": 2000,
                "endMs": 3200,
            }],
        )
        self.assertEqual(words[0]["endMs"], 3200)


class WordBoundaryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan_path = Path(tempfile.gettempdir()) / "baron3x3-plan.json"
        self.words = [
            {"text": "Pełne", "startMs": 100, "endMs": 400},
            {"text": "słowa.", "startMs": 450, "endMs": 800},
        ]

    def test_accepts_word_edges(self) -> None:
        validate_word_boundaries(
            self.plan_path,
            [{"sourceStartMs": 100, "sourceEndMs": 800}],
            self.words,
        )

    def test_accepts_boundary_in_silence(self) -> None:
        validate_word_boundaries(
            self.plan_path,
            [{"sourceStartMs": 50, "sourceEndMs": 825}],
            self.words,
        )

    def test_rejects_mid_word_start(self) -> None:
        with self.assertRaisesRegex(ValueError, "przecina słowo"):
            validate_word_boundaries(
                self.plan_path,
                [{"sourceStartMs": 200, "sourceEndMs": 800}],
                self.words,
            )

    def test_rejects_mid_word_end(self) -> None:
        with self.assertRaisesRegex(ValueError, "przecina słowo"):
            validate_word_boundaries(
                self.plan_path,
                [{"sourceStartMs": 100, "sourceEndMs": 700}],
                self.words,
            )


class CaptionPaginationTests(unittest.TestCase):
    def make_words(self, texts: list[str]) -> list[dict[str, object]]:
        return [
            {
                "text": text,
                "startMs": index * 200,
                "endMs": (index + 1) * 200,
                "confidence": 1.0,
            }
            for index, text in enumerate(texts)
        ]

    def paginate(self, texts: list[str]) -> list[list[str]]:
        words = self.make_words(texts)
        captions = timeline_captions(
            words,
            [
                {
                    "sourceStartMs": 0,
                    "sourceEndMs": len(words) * 200,
                    "timelineStartMs": 0,
                }
            ],
        )
        pages: list[list[str]] = []
        current: list[str] = []
        for caption in captions:
            current.append(str(caption["text"]).strip())
            if caption.get("pageBreakAfter"):
                pages.append(current)
                current = []
        self.assertEqual(current, [])
        return pages

    def test_breaks_after_three_words(self) -> None:
        self.assertEqual(
            self.paginate(["Jeden", "dwa", "trzy", "cztery", "pięć"]),
            [["Jeden", "dwa", "trzy"], ["cztery", "pięć"]],
        )

    def test_balances_four_word_phrase_into_two_pairs(self) -> None:
        self.assertEqual(
            self.paginate(["Pilnuje", "komunikacji", "i", "koncentracji."]),
            [["Pilnuje", "komunikacji"], ["i", "koncentracji"]],
        )

    def test_punctuation_starts_next_word_on_new_page(self) -> None:
        self.assertEqual(
            self.paginate(["i", "koncentracji.", "Dlatego", "jest", "ważny"]),
            [["i", "koncentracji"], ["Dlatego", "jest", "ważny"]],
        )

    def test_comma_ends_page(self) -> None:
        self.assertEqual(
            self.paginate(["Raz", "dwa,", "potem", "trzy"]),
            [["Raz", "dwa"], ["potem", "trzy"]],
        )

    def test_keeps_exclamation_and_question_marks(self) -> None:
        self.assertEqual(
            self.paginate(["Naprawdę?", "Tak!", "Dobrze."]),
            [["Naprawdę?"], ["Tak!"], ["Dobrze"]],
        )


class VisualBeatTests(unittest.TestCase):
    def test_fallback_is_deterministic_and_covers_timeline(self) -> None:
        first = build_visual_beats([], 38000)
        second = build_visual_beats([], 38000)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["timelineStartMs"], 0)
        self.assertEqual(first[-1]["timelineEndMs"], 38000)
        for left, right in zip(first, first[1:]):
            self.assertEqual(left["timelineEndMs"], right["timelineStartMs"])
        for beat in first:
            duration = beat["timelineEndMs"] - beat["timelineStartMs"]
            self.assertGreaterEqual(duration, 3000)
            self.assertLessEqual(duration, 6000)


class EffectCueTests(unittest.TestCase):
    def base_plan(self) -> dict[str, object]:
        return {
            "status": "ready",
            "captionStyle": "green-word",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 1000}],
            "visualBeats": [],
            "effectCues": [],
            "soundEffects": [],
        }

    def test_builds_normalized_cue(self) -> None:
        cues = build_effect_cues(
            [
                {
                    "type": "stat-card",
                    "timelineStartMs": 100,
                    "timelineEndMs": 900,
                    "value": "12",
                    "label": "punktów",
                    "placement": "top",
                }
            ],
            1000,
        )
        self.assertEqual(cues[0]["id"], "effect-001")
        self.assertEqual(cues[0]["value"], "12")
        self.assertEqual(cues[0]["placement"], "top")

    def test_rejects_sfx_above_type_specific_limit(self) -> None:
        plan = self.base_plan()
        plan["soundEffects"] = [
            {"type": "whoosh", "timelineStartMs": 100, "volume": 0.19}
        ]
        with self.assertRaisesRegex(ValueError, "dla whoosh"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_unsafe_speech_ducking(self) -> None:
        plan = self.base_plan()
        plan["soundEffects"] = [
            {
                "type": "impact",
                "timelineStartMs": 100,
                "volume": 0.22,
                "speechDucking": 0.3,
            }
        ]
        with self.assertRaisesRegex(ValueError, "speechDucking"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_aggressive_color_grade(self) -> None:
        plan = self.base_plan()
        plan["colorGrade"] = {
            "contrast": 1.8,
            "saturation": 1.0,
            "brightness": 1.0,
            "sepia": 0.0,
        }
        with self.assertRaisesRegex(ValueError, "colorGrade.contrast"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_unknown_effect_placement(self) -> None:
        plan = self.base_plan()
        plan["effectCues"] = [
            {
                "type": "audio-waveform",
                "timelineStartMs": 0,
                "timelineEndMs": 800,
                "placement": "over-face",
            }
        ]
        with self.assertRaisesRegex(ValueError, "placement"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_unknown_effect(self) -> None:
        plan = self.base_plan()
        plan["effectCues"] = [
            {"type": "random-filter", "timelineStartMs": 0, "timelineEndMs": 200}
        ]
        with self.assertRaisesRegex(ValueError, "effectCues"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_removed_school_style_glitch(self) -> None:
        plan = self.base_plan()
        plan["effectCues"] = [
            {"type": "glitch", "timelineStartMs": 0, "timelineEndMs": 200}
        ]
        with self.assertRaisesRegex(ValueError, "effectCues"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_stat_card_without_value(self) -> None:
        plan = self.base_plan()
        plan["effectCues"] = [
            {"type": "stat-card", "timelineStartMs": 0, "timelineEndMs": 800}
        ]
        with self.assertRaisesRegex(ValueError, "wymaga pola value"):
            validate_plan(Path("plan.json"), plan)

    def test_accepts_visual_fallback_effects(self) -> None:
        plan = self.base_plan()
        plan["effectCues"] = [
            {
                "type": "kinetic-text",
                "timelineStartMs": 0,
                "timelineEndMs": 800,
                "label": "LIDER",
                "value": "TO NIE TYLKO PUNKTY",
                "placement": "top-right",
            },
            {
                "type": "audio-waveform",
                "timelineStartMs": 800,
                "timelineEndMs": 1000,
                "label": "GŁOS Z BOISKA",
                "placement": "top-left",
            },
        ]

        validate_plan(Path("plan.json"), plan)

    def test_rejects_disabled_paper_reveal(self) -> None:
        plan = self.base_plan()
        plan["effectCues"] = [
            {
                "type": "paper-reveal",
                "timelineStartMs": 100,
                "timelineEndMs": 1000,
                "intensity": 0.85,
            }
        ]

        with self.assertRaisesRegex(ValueError, "musi być jednym z"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_effect_outside_timeline(self) -> None:
        with self.assertRaisesRegex(ValueError, "poza osią czasu"):
            build_effect_cues(
                [{"type": "flash", "timelineStartMs": 900, "timelineEndMs": 1100}],
                1000,
            )

    def test_accepts_supported_broll_treatment(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "example",
                "timelineStartMs": 0,
                "timelineEndMs": 900,
                "presentation": "editorial",
                "motion": "pan-left",
            }
        ]
        validate_plan(Path("plan.json"), plan)

    def test_rejects_disabled_paper_collage_with_unique_photos(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "main-photo",
                "collageAssetIds": ["team-photo", "action-photo"],
                "timelineStartMs": 0,
                "timelineEndMs": 1000,
                "presentation": "paper-collage",
            }
        ]
        with self.assertRaisesRegex(ValueError, "presentation musi być jednym z"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_disabled_paper_collage_before_asset_validation(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "main-photo",
                "collageAssetIds": ["same-photo", "same-photo"],
                "timelineStartMs": 0,
                "timelineEndMs": 1000,
                "presentation": "paper-collage",
            }
        ]
        with self.assertRaisesRegex(ValueError, "presentation musi być jednym z"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_overlay_shorter_than_configured_minimum(self) -> None:
        plan = self.base_plan()
        plan["minimumSceneDurationMs"] = 1000
        plan["overlays"] = [
            {
                "assetId": "first",
                "timelineStartMs": 0,
                "timelineEndMs": 900,
            }
        ]
        with self.assertRaisesRegex(ValueError, "minimumSceneDurationMs"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_repeated_asset_without_explicit_override(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {"assetId": "same", "timelineStartMs": 0, "timelineEndMs": 400},
            {"assetId": "same", "timelineStartMs": 400, "timelineEndMs": 800},
        ]
        with self.assertRaisesRegex(ValueError, "powtórzony assetId"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_non_boolean_overlay_fade(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "first",
                "timelineStartMs": 0,
                "timelineEndMs": 900,
                "fadeOut": "no",
            }
        ]
        with self.assertRaisesRegex(ValueError, "fadeOut"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_unknown_broll_treatment(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "example",
                "timelineStartMs": 0,
                "timelineEndMs": 900,
                "presentation": "random-collage",
            }
        ]
        with self.assertRaisesRegex(ValueError, "presentation"):
            validate_plan(Path("plan.json"), plan)

    def test_split_requires_second_asset(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "example",
                "timelineStartMs": 0,
                "timelineEndMs": 900,
                "presentation": "split",
            }
        ]
        with self.assertRaisesRegex(ValueError, "wymaga drugiego materiału"):
            validate_plan(Path("plan.json"), plan)

    def test_rejects_invalid_editorial_accent(self) -> None:
        plan = self.base_plan()
        plan["overlays"] = [
            {
                "assetId": "example",
                "timelineStartMs": 0,
                "timelineEndMs": 900,
                "accentColor": "red",
            }
        ]
        with self.assertRaisesRegex(ValueError, "kolorem HEX"):
            validate_plan(Path("plan.json"), plan)

if __name__ == "__main__":
    unittest.main()
