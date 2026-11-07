from __future__ import annotations

import unittest

from scripts.broll_planner import (
    PLANNER_ID,
    apply_report,
    build_report,
    choose_source_window,
    parse_note_fields,
    split_beats,
    timeline_words,
)


def asset(asset_id: str, notes: str, duration_ms: int = 12_000) -> dict:
    return {
        "id": asset_id,
        "kind": "video",
        "name": f"{asset_id}.mp4",
        "status": "available",
        "durationMs": duration_ms,
        "userNotes": notes,
    }


class BrollPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Aleksandra", "startMs": 0, "endMs": 500},
                        {"text": "Zięmborska", "startMs": 500, "endMs": 1100},
                        {"text": "trafia", "startMs": 1100, "endMs": 1600},
                        {"text": "z", "startMs": 1600, "endMs": 1700},
                        {"text": "dystansu.", "startMs": 1700, "endMs": 2400},
                    ]
                }
            ]
        }
        self.plan = {
            "instructions": "dynamiczna rolka",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2400}],
            "overlays": [],
        }

    def test_maps_words_to_edited_timeline_and_splits_on_sentence(self) -> None:
        words = timeline_words(
            {
                "segments": [
                    {
                        "words": [
                            {"text": "Pierwsze.", "startMs": 1000, "endMs": 1800},
                            {"text": "Drugie.", "startMs": 3000, "endMs": 3800},
                        ]
                    }
                ]
            },
            [{"sourceStartMs": 1000, "sourceEndMs": 4000}],
        )
        beats = split_beats(words)

        self.assertEqual(words[0]["timelineStartMs"], 0)
        self.assertEqual(words[1]["timelineStartMs"], 2000)
        self.assertEqual([beat["text"] for beat in beats], ["Pierwsze.", "Drugie."])

    def test_exact_person_and_action_produce_safe_proposal(self) -> None:
        catalog = {
            "items": [
                asset(
                    "ziemborska",
                    "\n".join(
                        [
                            "- Opis: Aleksandra Zięmborska oddaje rzut z dystansu",
                            "- Osoby: Aleksandra Zięmborska",
                            "- Tagi: rzut z dystansu, celebracja",
                            "- Najlepsze fragmenty: 00:02–00:08 — rzut",
                        ]
                    ),
                )
            ]
        }

        report = build_report("test", self.transcript, self.plan, catalog)

        self.assertEqual(report["coverage"]["proposedOverlays"], 1)
        proposal = report["proposedOverlays"][0]
        self.assertEqual(proposal["assetId"], "ziemborska")
        self.assertEqual(proposal["sourceStartMs"], 2000)
        self.assertEqual(proposal["generatedBy"], PLANNER_ID)

    def test_single_team_reference_is_candidate_but_not_forced(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Przeciwko", "startMs": 0, "endMs": 700},
                        {"text": "Antwerpii", "startMs": 700, "endMs": 1500},
                        {"text": "zdobył", "startMs": 1500, "endMs": 1900},
                        {"text": "pięć", "startMs": 1900, "endMs": 2200},
                        {"text": "punktów.", "startMs": 2200, "endMs": 2800},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2800}],
            "overlays": [],
        }
        catalog = {
            "items": [
                asset(
                    "antwerp",
                    "- Zespół: Team Antwerp 3x3\n- Opis: wsad przeciwko Shanghai",
                )
            ]
        }

        report = build_report("test", transcript, plan, catalog)

        self.assertEqual(report["coverage"]["proposedOverlays"], 0)
        self.assertEqual(report["beats"][0]["candidates"][0]["assetId"], "antwerp")
        self.assertFalse(report["beats"][0]["candidates"][0]["safe"])

    def test_unrelated_asset_is_not_proposed(self) -> None:
        catalog = {
            "items": [asset("other", "- Osoby: Worthy De Jong\n- Tagi: wsad, Amsterdam")]
        }

        report = build_report("test", self.transcript, self.plan, catalog)

        self.assertEqual(report["coverage"]["proposedOverlays"], 0)

    def test_reviewed_stock_can_match_location_description(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Turniej", "startMs": 0, "endMs": 500},
                        {"text": "odbywa", "startMs": 500, "endMs": 900},
                        {"text": "się", "startMs": 900, "endMs": 1100},
                        {"text": "w", "startMs": 1100, "endMs": 1200},
                        {"text": "Warszawie.", "startMs": 1200, "endMs": 2000},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2000}],
            "overlays": [],
        }
        stock = asset(
            "warsaw",
            "- Opis: Panorama Warszawy\n- Zastosowanie: Warszawa skyline\n- Tagi: Warszawa, panorama, stock",
        )
        stock["kind"] = "image"
        stock["stock"] = {
            "sourcePage": "https://commons.wikimedia.org/?curid=10",
            "licenseName": "CC BY-SA 4.0",
            "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
            "attribution": "Jan Kowalski, CC BY-SA 4.0",
        }

        report = build_report("test", transcript, plan, {"items": [stock]})

        self.assertEqual(report["coverage"]["proposedOverlays"], 1)
        self.assertEqual(report["proposedOverlays"][0]["assetId"], "warsaw")
        self.assertEqual(report["proposedOverlays"][0]["stockLicense"], "CC BY-SA 4.0")

    def test_image_uses_requested_timeline_duration_not_probe_duration(self) -> None:
        image = asset("portrait", "- Osoby: Adrian Bogucki", duration_ms=40)
        image["kind"] = "image"

        self.assertEqual(choose_source_window(image, {}, "Adrian Bogucki", 2800), (0, 2800))

    def test_two_descriptive_fields_can_confirm_specific_action(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Pierwszy", "startMs": 0, "endMs": 500},
                        {"text": "gratuluje", "startMs": 500, "endMs": 1200},
                        {"text": "kolegom.", "startMs": 1200, "endMs": 2100},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2100}],
            "overlays": [],
        }
        photo = asset(
            "team-reaction",
            "- Opis: zawodnik rozmawia z kolegą\n"
            "- Zastosowanie: gratulowanie kolegom\n"
            "- Tagi: gratulacje, drużyna",
            duration_ms=40,
        )
        photo["kind"] = "image"

        report = build_report("test", transcript, plan, {"items": [photo]})

        self.assertEqual(report["coverage"]["proposedOverlays"], 1)
        self.assertEqual(report["proposedOverlays"][0]["timelineEndMs"], 2100)

    def test_negative_usage_note_blocks_wrong_context(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Adrian", "startMs": 0, "endMs": 500},
                        {"text": "dołącza", "startMs": 500, "endMs": 1000},
                        {"text": "do", "startMs": 1000, "endMs": 1100},
                        {"text": "Leszna.", "startMs": 1100, "endMs": 1900},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 1900}],
            "overlays": [],
        }
        portrait = asset(
            "generic-portrait",
            "- Osoby: Adrian Bogucki\n- Tagi: portret Adriana\n"
            "- Nie używaj, gdy: wypowiedź dotyczy Leszna",
            duration_ms=40,
        )
        portrait["kind"] = "image"

        report = build_report("test", transcript, plan, {"items": [portrait]})

        self.assertEqual(report["coverage"]["proposedOverlays"], 0)
        self.assertIn("wyklucza", report["beats"][0]["candidates"][0]["decisionReason"])

    def test_context_specific_asset_outranks_generic_identity_match(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Adrian", "startMs": 0, "endMs": 500},
                        {"text": "zostaje", "startMs": 500, "endMs": 900},
                        {"text": "kapitanem", "startMs": 900, "endMs": 1400},
                        {"text": "w", "startMs": 1400, "endMs": 1500},
                        {"text": "Lesznie.", "startMs": 1500, "endMs": 2200},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2200}],
            "overlays": [],
        }
        generic = asset(
            "generic",
            "- Osoby: Adrian Bogucki\n- Tagi: portret, przedstawienie bohatera",
            duration_ms=40,
        )
        specific = asset(
            "leszno",
            "- Osoby: Adrian Bogucki\n- Zespół: Polonia Leszno\n"
            "- Zastosowanie: finał zdania o Lesznie\n- Tagi: Leszno, klub",
            duration_ms=40,
        )
        generic["kind"] = "image"
        specific["kind"] = "image"

        report = build_report("test", transcript, plan, {"items": [generic, specific]})

        self.assertEqual(report["proposedOverlays"][0]["assetId"], "leszno")

    def test_subject_is_hidden_until_name_is_spoken(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Ten", "startMs": 0, "endMs": 300},
                        {"text": "lider", "startMs": 300, "endMs": 800},
                        {"text": "to", "startMs": 800, "endMs": 1000},
                        {"text": "Adrian", "startMs": 1000, "endMs": 1500},
                        {"text": "Bogucki.", "startMs": 1500, "endMs": 2200},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2200}],
            "overlays": [],
        }
        portrait = asset(
            "adrian",
            "- Osoby: Adrian Bogucki\n- Zastosowanie: lider, przedstawienie bohatera\n"
            "- Tagi: Adrian Bogucki, lider, portret",
            duration_ms=40,
        )
        portrait["kind"] = "image"

        report = build_report("test", transcript, plan, {"items": [portrait]})

        self.assertEqual(report["policy"]["subjectRevealMs"], 1000)
        self.assertEqual(report["proposedOverlays"][0]["timelineStartMs"], 1000)
        self.assertIsNone(report["beats"][0]["selection"])

    def test_same_subject_from_other_city_is_allowed_after_reveal(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Adrian", "startMs": 0, "endMs": 500},
                        {"text": "Bogucki", "startMs": 500, "endMs": 1000},
                        {"text": "zachwycił", "startMs": 1000, "endMs": 1600},
                        {"text": "w", "startMs": 1600, "endMs": 1700},
                        {"text": "Bordeaux.", "startMs": 1700, "endMs": 2400},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 2400}],
            "overlays": [],
        }
        vienna = asset(
            "vienna-adrian",
            "- Osoby: Adrian Bogucki\n- Miejsce: Wiedeń, Austria\n"
            "- Wydarzenie: turniej w Wiedniu\n- Tagi: Adrian Bogucki, akcja",
        )

        report = build_report("test", transcript, plan, {"items": [vienna]})

        self.assertEqual(report["proposedOverlays"][0]["assetId"], "vienna-adrian")
        self.assertTrue(report["beats"][0]["candidates"][0]["safe"])

    def test_apply_preserves_manual_overlays(self) -> None:
        catalog = {
            "items": [asset("ziemborska", "- Osoby: Aleksandra Zięmborska")]
        }
        report = build_report("test", self.transcript, self.plan, catalog)
        plan = dict(self.plan)
        plan["overlays"] = [{"assetId": "manual", "timelineStartMs": 0, "timelineEndMs": 1000}]
        report["planSignature"] = report["planSignature"]

        with self.assertRaisesRegex(ValueError, "akceptacji"):
            apply_report(report, plan, approved=False)

        # Overlay content is excluded from the signature so manual edits remain preserved.
        applied = apply_report(report, plan, approved=True)
        self.assertEqual(applied["overlays"][0]["assetId"], "manual")
        self.assertEqual(applied["overlays"][1]["assetId"], "ziemborska")

    def test_plans_only_semantically_supported_visual_fallbacks(self) -> None:
        transcript = {
            "segments": [
                {
                    "words": [
                        {"text": "Lider", "startMs": 0, "endMs": 500},
                        {"text": "nie", "startMs": 500, "endMs": 700},
                        {"text": "zdobywa", "startMs": 700, "endMs": 1200},
                        {"text": "najwięcej", "startMs": 1200, "endMs": 1700},
                        {"text": "punktów.", "startMs": 1700, "endMs": 2300},
                        {"text": "Podczas", "startMs": 2300, "endMs": 2700},
                        {"text": "transmisji", "startMs": 2700, "endMs": 3400},
                        {"text": "było", "startMs": 3400, "endMs": 3600},
                        {"text": "go", "startMs": 3600, "endMs": 3750},
                        {"text": "słychać.", "startMs": 3750, "endMs": 4400},
                    ]
                }
            ]
        }
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 4400}],
            "overlays": [],
        }

        report = build_report("test", transcript, plan, {"items": []})

        self.assertEqual(
            [item["type"] for item in report["proposedEffectCues"]],
            ["kinetic-text", "audio-waveform"],
        )
        self.assertEqual(report["coverage"]["renderableFallbacks"], 2)

    def test_apply_preserves_manual_effects_and_adds_fallbacks(self) -> None:
        report = build_report(
            "test",
            {
                "segments": [
                    {
                        "words": [
                            {"text": "Najwięcej", "startMs": 0, "endMs": 700},
                            {"text": "punktów.", "startMs": 700, "endMs": 1600},
                        ]
                    }
                ]
            },
            {
                "instructions": "",
                "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 1600}],
                "overlays": [],
            },
            {"items": []},
        )
        plan = {
            "instructions": "",
            "sourceRanges": [{"sourceStartMs": 0, "sourceEndMs": 1600}],
            "overlays": [],
            "effectCues": [
                {"type": "flash", "timelineStartMs": 0, "timelineEndMs": 150}
            ],
        }

        applied = apply_report(report, plan, approved=True)

        self.assertEqual(applied["effectCues"][0]["type"], "flash")
        self.assertEqual(applied["effectCues"][1]["type"], "kinetic-text")

    def test_parses_structured_manual_notes(self) -> None:
        fields = parse_note_fields("- Osoby: Aleksandra Zięmborska\n- Tagi: rzut, celebracja")
        self.assertEqual(fields["osoby"], "Aleksandra Zięmborska")
        self.assertIn("celebracja", fields["tagi"])


if __name__ == "__main__":
    unittest.main()
