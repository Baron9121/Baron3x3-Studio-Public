from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.stock_library import (
    best_pexels_video_file,
    download_file,
    search_commons,
    search_pexels,
)


class StockLibraryTests(unittest.TestCase):
    def test_commons_keeps_attribution_license_and_rejects_nc(self) -> None:
        response = {
            "query": {
                "pages": [
                    {
                        "pageid": 10,
                        "title": "File:Warsaw.jpg",
                        "imageinfo": [
                            {
                                "mime": "image/jpeg",
                                "url": "https://upload.wikimedia.org/warsaw.jpg",
                                "thumburl": "https://upload.wikimedia.org/1920px-warsaw.jpg",
                                "thumbwidth": 1080,
                                "thumbheight": 1920,
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                                    "Artist": {"value": "<b>Jan Kowalski</b>"},
                                    "ImageDescription": {"value": "Panorama Warszawy"},
                                },
                            }
                        ],
                    },
                    {
                        "pageid": 11,
                        "title": "File:Rejected.jpg",
                        "imageinfo": [
                            {
                                "mime": "image/jpeg",
                                "url": "https://upload.wikimedia.org/rejected.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-NC 4.0"}
                                },
                            }
                        ],
                    },
                ]
            }
        }

        results, rejected = search_commons(
            "Warsaw skyline", "image", 8, requester=lambda _url, _headers: response
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(rejected, 1)
        self.assertEqual(results[0]["id"], "commons:10")
        self.assertTrue(results[0]["licenseRequiresAttribution"])
        self.assertIn("Jan Kowalski", results[0]["attribution"])

    def test_pexels_prefers_usable_portrait_mp4(self) -> None:
        chosen = best_pexels_video_file(
            [
                {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "https://x/land.mp4"},
                {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "https://x/portrait.mp4"},
                {"file_type": "video/webm", "width": 1080, "height": 1920, "link": "https://x/no.webm"},
            ]
        )
        self.assertEqual(chosen["link"], "https://x/portrait.mp4")

    def test_pexels_normalizes_video_result_and_never_exposes_key(self) -> None:
        response = {
            "videos": [
                {
                    "id": 55,
                    "url": "https://www.pexels.com/pl-pl/video/nocne-miasto-z-lotu-ptaka-55/",
                    "duration": 9,
                    "user": {"name": "Anna", "url": "https://www.pexels.com/@anna"},
                    "video_files": [
                        {
                            "file_type": "video/mp4",
                            "width": 1080,
                            "height": 1920,
                            "link": "https://videos.pexels.com/55.mp4",
                        }
                    ],
                }
            ]
        }
        seen_headers = {}

        def requester(_url, headers):
            seen_headers.update(headers)
            return response

        results, _ = search_pexels("Warsaw", "video", 4, "SECRET", requester=requester)

        self.assertEqual(seen_headers["Authorization"], "SECRET")
        self.assertNotIn("SECRET", str(results))
        self.assertEqual(results[0]["orientation"], "portrait")
        self.assertEqual(results[0]["durationMs"], 9000)
        self.assertEqual(results[0]["title"], "Nocne miasto z lotu ptaka")
        self.assertNotIn("Warsaw", results[0]["keywords"])

    def test_approved_download_helper_streams_and_hashes_without_api(self) -> None:
        payload = b"test-media-bytes"

        class FakeResponse:
            headers = {"Content-Length": str(len(payload))}

            def __init__(self):
                self.sent = False

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                if self.sent:
                    return b""
                self.sent = True
                return payload

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "stock.jpg"
            digest = download_file(
                "https://example.com/stock.jpg",
                destination,
                opener=lambda _request, timeout: FakeResponse(),
            )

            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
