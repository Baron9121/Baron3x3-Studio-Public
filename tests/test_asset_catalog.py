from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.asset_catalog import (
    GENERATED_END,
    GENERATED_START,
    MANUAL_END,
    MANUAL_START,
    refresh_catalog,
    search_items,
)
from scripts.pipeline import build_overlays


class AssetCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "assets" / "library"
        self.library.mkdir(parents=True)
        (self.root / "assets" / "sources.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "roots": [
                        {
                            "path": "assets/library",
                            "label": "Biblioteka testowa",
                            "enabled": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (self.root / "assets" / "MATERIALY.md").write_text(
            "\n".join(
                [
                    "# Katalog",
                    "",
                    GENERATED_START,
                    "stara tabela",
                    GENERATED_END,
                    "",
                    MANUAL_START,
                    "## Moje opisy",
                    "",
                    "### Amsterdam Rabobank - Worthy De Jong.mp4",
                    "",
                    "- Opis: akcje Worthy’ego de Jonga",
                    "- Tagi: drybling, Amsterdam",
                    MANUAL_END,
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def fake_probe(path: Path) -> dict[str, int | None]:
        if path.suffix == ".mp4":
            return {"durationMs": 12_500, "width": 1920, "height": 1080}
        return {"durationMs": None, "width": 1200, "height": 1600}

    def test_scans_video_and_image_and_preserves_user_notes(self) -> None:
        (self.library / "Amsterdam Rabobank - Worthy De Jong.mp4").write_bytes(b"video")
        (self.library / "worthy-portret.jpg").write_bytes(b"image")

        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)

        self.assertEqual(len(index["items"]), 2)
        video = next(item for item in index["items"] if item["kind"] == "video")
        image = next(item for item in index["items"] if item["kind"] == "image")
        self.assertEqual(video["durationMs"], 12_500)
        self.assertEqual(image["height"], 1600)
        self.assertIn("Worthy’ego", video["userNotes"])
        markdown = (self.root / "assets" / "MATERIALY.md").read_text(encoding="utf-8")
        self.assertIn("Amsterdam Rabobank - Worthy De Jong.mp4", markdown)
        self.assertIn("- Tagi: drybling, Amsterdam", markdown)

    def test_adds_new_files_and_marks_removed_files_missing(self) -> None:
        first = self.library / "pierwszy.mp4"
        first.write_bytes(b"first")
        refresh_catalog(self.root, metadata_reader=self.fake_probe)

        second = self.library / "drugi.jpg"
        second.write_bytes(b"second")
        first.unlink()
        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)

        statuses = {item["name"]: item["status"] for item in index["items"]}
        self.assertEqual(statuses["pierwszy.mp4"], "missing")
        self.assertEqual(statuses["drugi.jpg"], "available")

    def test_search_uses_filename_and_manual_description(self) -> None:
        (self.library / "Amsterdam Rabobank - Worthy De Jong.mp4").write_bytes(b"video")
        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)

        by_name = search_items(index, "Worthy De Jong")
        by_note = search_items(index, "drybling")

        self.assertEqual(by_name[0]["name"], "Amsterdam Rabobank - Worthy De Jong.mp4")
        self.assertEqual(by_note[0]["name"], "Amsterdam Rabobank - Worthy De Jong.mp4")

    def test_pipeline_resolves_catalog_asset_by_id(self) -> None:
        image_path = self.library / "worthy-portret.jpg"
        image_path.write_bytes(b"image")
        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)
        item = index["items"][0]

        import scripts.pipeline as pipeline

        previous_public_assets = pipeline.PUBLIC_ASSETS
        pipeline.PUBLIC_ASSETS = self.root / "remotion" / "public" / "assets"
        try:
            overlays = build_overlays(
                [
                    {
                        "assetId": item["id"],
                        "timelineStartMs": 0,
                        "timelineEndMs": 2000,
                        "presentation": "archive",
                        "motion": "pull-out",
                    }
                ],
                2000,
                index,
            )
        finally:
            pipeline.PUBLIC_ASSETS = previous_public_assets

        self.assertEqual(overlays[0]["kind"], "image")
        self.assertEqual(overlays[0]["assetId"], item["id"])
        self.assertEqual(overlays[0]["presentation"], "archive")
        self.assertEqual(overlays[0]["motion"], "pull-out")
        self.assertTrue((self.root / "remotion" / "public" / overlays[0]["publicFile"]).is_file())

    def test_pipeline_builds_two_asset_editorial_composition(self) -> None:
        first_path = self.library / "worthy-akcja.mp4"
        second_path = self.library / "worthy-portret.jpg"
        first_path.write_bytes(b"video")
        second_path.write_bytes(b"image")
        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)
        first = next(item for item in index["items"] if item["name"] == first_path.name)
        second = next(item for item in index["items"] if item["name"] == second_path.name)

        import scripts.pipeline as pipeline

        previous_public_assets = pipeline.PUBLIC_ASSETS
        pipeline.PUBLIC_ASSETS = self.root / "remotion" / "public" / "assets"
        try:
            overlays = build_overlays(
                [
                    {
                        "assetId": first["id"],
                        "secondaryAssetId": second["id"],
                        "timelineStartMs": 0,
                        "timelineEndMs": 2000,
                        "presentation": "split",
                        "headline": "WORTHY DE JONG",
                        "kicker": "BOHATER",
                    }
                ],
                2000,
                index,
            )
        finally:
            pipeline.PUBLIC_ASSETS = previous_public_assets

        overlay = overlays[0]
        self.assertEqual(overlay["presentation"], "split")
        self.assertEqual(overlay["secondaryAssetId"], second["id"])
        self.assertEqual(overlay["secondaryKind"], "image")
        self.assertEqual(overlay["headline"], "WORTHY DE JONG")
        self.assertTrue(
            (self.root / "remotion" / "public" / overlay["secondaryPublicFile"]).is_file()
        )

    def test_pipeline_builds_three_photo_paper_collage(self) -> None:
        for name in ("emocja.jpg", "druzyna.jpg", "akcja.jpg"):
            (self.library / name).write_bytes(b"image")
        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)
        by_name = {item["name"]: item for item in index["items"]}

        import scripts.pipeline as pipeline

        previous_public_assets = pipeline.PUBLIC_ASSETS
        pipeline.PUBLIC_ASSETS = self.root / "remotion" / "public" / "assets"
        try:
            overlays = build_overlays(
                [
                    {
                        "assetId": by_name["emocja.jpg"]["id"],
                        "collageAssetIds": [
                            by_name["druzyna.jpg"]["id"],
                            by_name["akcja.jpg"]["id"],
                        ],
                        "timelineStartMs": 0,
                        "timelineEndMs": 3000,
                        "presentation": "paper-collage",
                    }
                ],
                3000,
                index,
            )
        finally:
            pipeline.PUBLIC_ASSETS = previous_public_assets

        overlay = overlays[0]
        self.assertEqual(overlay["presentation"], "paper-collage")
        self.assertEqual(len(overlay["collageAssets"]), 2)
        self.assertTrue(all(item["kind"] == "image" for item in overlay["collageAssets"]))
        self.assertTrue(
            all(
                (self.root / "remotion" / "public" / item["publicFile"]).is_file()
                for item in overlay["collageAssets"]
            )
        )

    def test_stock_registry_description_is_searchable(self) -> None:
        stock = self.library / "stock" / "commons" / "warsaw.jpg"
        stock.parent.mkdir(parents=True)
        stock.write_bytes(b"image")
        (self.root / "assets" / "STOCK-LICENSES.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": [
                        {
                            "id": "commons:10",
                            "absolutePath": str(stock.resolve()),
                            "title": "Panorama Warszawy",
                            "description": "Widok centrum Warszawy z lotu ptaka",
                            "query": "Warszawa panorama",
                            "provider": "Wikimedia Commons",
                            "sourcePage": "https://commons.wikimedia.org/?curid=10",
                            "author": "Jan Kowalski",
                            "licenseName": "CC BY-SA 4.0",
                            "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
                            "attribution": "Jan Kowalski, CC BY-SA 4.0",
                            "usageWarning": "kontrola przed publikacją",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        index = refresh_catalog(self.root, metadata_reader=self.fake_probe)
        results = search_items(index, "centrum Warszawy")

        self.assertEqual(results[0]["name"], "warsaw.jpg")
        self.assertIn("CC BY-SA 4.0", results[0]["userNotes"])


if __name__ == "__main__":
    unittest.main()
