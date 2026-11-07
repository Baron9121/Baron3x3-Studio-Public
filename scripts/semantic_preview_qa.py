#!/usr/bin/env python3
"""Prepare a compact, reference-aware semantic preview QA package."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    from scripts.broll_planner import split_beats, timeline_words
    from scripts.openrouter_client import validate_schema
except ModuleNotFoundError:
    from broll_planner import split_beats, timeline_words
    from openrouter_client import validate_schema


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
JOBS = ROOT / "instructions" / "jobs"
OUTPUT = ROOT / "output"
REFERENCE = Path("/Users/bartoszperz/Downloads/AQO86fk2RarBnal8SNffIFUY599MjFul48AqX_QCRFNZEXG0N0WTPS3ru69-wNLsSrMrWIOnnJBX4bc6tcIhHOjC_BGgjGQb60Sex4A.mp4")
REFERENCE_SHEETS = [
    ANALYSIS / "reference" / "effects-v1" / "contact-01.jpg",
    ANALYSIS / "reference" / "effects-v1" / "contact-02.jpg",
]

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "needs-fixes", "fail"]},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "issues": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "startMs": {"type": "integer", "minimum": 0},
                    "endMs": {"type": "integer", "minimum": 0},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "category": {"type": "string", "enum": ["semantics", "reveal", "action", "captions", "framing", "rhythm", "effects", "sound", "reference-match"]},
                    "evidence": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["startMs", "endMs", "severity", "category", "evidence", "fix"],
                "additionalProperties": False,
            },
        },
        "referenceComparison": {
            "type": "object",
            "properties": {
                "matched": {"type": "array", "items": {"type": "string"}},
                "missing": {"type": "array", "items": {"type": "string"}},
                "shouldNotCopy": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["matched", "missing", "shouldNotCopy"],
            "additionalProperties": False,
        },
        "recommendedNextAction": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["verdict", "score", "summary", "strengths", "issues", "referenceComparison", "recommendedNextAction", "confidence"],
    "additionalProperties": False,
}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def make_sheet(source: Path, destination: Path, start: int) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        "fps=1,scale=270:480:force_original_aspect_ratio=decrease,"
        "pad=270:480:(ow-iw)/2:(oh-ih)/2:black,tile=5x4"
    )
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", "20", "-i", str(source), "-vf", vf, "-frames:v", "1", "-y", str(destination)],
        check=True,
    )
    with Image.open(destination) as opened:
        sheet = opened.convert("RGB")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    for index in range(20):
        x = (index % 5) * 270 + 8
        y = (index // 5) * 480 + 8
        label = f"{start + index:02d}s"
        draw.rounded_rectangle((x - 4, y - 4, x + 49, y + 24), radius=3, fill=(0, 0, 0))
        draw.text((x, y), label, fill=(255, 255, 255), font=font)
    sheet.save(destination, quality=92)


def prepare(job_name: str) -> dict[str, Any]:
    render = OUTPUT / f"{job_name}-render.mp4"
    plan_path = JOBS / f"{job_name}.json"
    transcript_path = ANALYSIS / job_name / "transcript.json"
    for required in [render, plan_path, transcript_path, REFERENCE, *REFERENCE_SHEETS]:
        if not required.is_file():
            raise FileNotFoundError(required)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    directory = ANALYSIS / job_name / "preview-qa" / "semantic"
    import math
    seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(render)]))
    sheets = []
    for start in range(0, math.ceil(seconds), 20):
        sheet = directory / f"preview-{start:04d}-{start+20:04d}.jpg"
        make_sheet(render, sheet, start)
        sheets.append(sheet)
    package = {
        "version": 1,
        "job": job_name,
        "budgetLimitUsd": 0.10,
        "model": "google/gemini-3.1-pro-preview",
        "reasoningEffort": "medium",
        "previewSheets": [str(path.relative_to(ROOT)) for path in sheets],
        "referenceSheets": [str(path.relative_to(ROOT)) for path in REFERENCE_SHEETS],
        "timelineBeats": split_beats(timeline_words(transcript, plan.get("sourceRanges", []))),
        "overlays": plan.get("overlays", []),
        "visualBeats": plan.get("visualBeats", []),
        "effectCues": plan.get("effectCues", []),
        "soundEffects": plan.get("soundEffects", []),
        "hardRequirements": [
            "Oceniaj aktualny preview, a nie sam plan.",
            "Nie obniżaj oceny za wolniejsze sceny niż referencja: użytkownik jawnie wymaga minimum 3 sekund.",
            "Adrian nie może pojawić się przed wypowiedzeniem imienia i nazwiska; stock Bordeaux przed ujawnieniem jest prawidłowy.",
            "Akcja wsadu i blok muszą dochodzić do kulminacji.",
            "Napisy i plansze nie mogą zasłaniać twarzy; plansze LIDER i GŁOS Z BOISKA mają być nad głową.",
            "Nie proponuj split/stack/cutout bez jawnego przykładu z referencji.",
            "Wymień tylko poprawki mające widoczny dowód w dostarczonych klatkach lub osi czasu.",
        ],
    }
    write_json(directory / "input.json", package)
    write_json(directory / "schema.json", SCHEMA)
    return package


def import_cline_review(job_name: str, actual_cost_usd: float) -> dict[str, Any]:
    directory = ANALYSIS / job_name / "preview-qa" / "semantic"
    input_path = directory / "input.json"
    review_path = directory / "review-gemini-cline.json"
    for required in [input_path, review_path]:
        if not required.is_file():
            raise FileNotFoundError(required)
    package = json.loads(input_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    validate_schema(review, SCHEMA)
    budget = float(package["budgetLimitUsd"])
    if actual_cost_usd < 0 or actual_cost_usd > budget:
        raise ValueError(f"Actual cost {actual_cost_usd:.6f} USD exceeds budget {budget:.2f} USD")
    manifest = {
        "version": 1,
        "job": job_name,
        "provider": "OpenRouter via Cline",
        "model": package["model"],
        "reasoningEffort": package["reasoningEffort"],
        "budgetLimitUsd": budget,
        "actualCostUsd": actual_cost_usd,
        "verdict": review["verdict"],
        "score": review["score"],
        "confidence": review["confidence"],
        "reviewFile": str(review_path.relative_to(ROOT)),
        "inputs": package["previewSheets"] + package["referenceSheets"],
        "renderOrJobModified": False,
    }
    write_json(directory / "manifest.json", manifest)
    issue_lines = [
        f"- **{issue['severity']} · {issue['category']} · {issue['startMs'] / 1000:.2f}–{issue['endMs'] / 1000:.2f} s:** "
        f"{issue['evidence']} Propozycja: {issue['fix']}"
        for issue in review["issues"]
    ] or ["- Brak zgłoszonych problemów."]
    report = "\n".join(
        [
            "# Semantyczna kontrola preview — Adrian Bogucki",
            "",
            f"**Wynik:** {review['verdict']} · {review['score']}/100 · pewność {review['confidence']:.0%}",
            f"**Koszt:** {actual_cost_usd:.4f} USD / limit {budget:.2f} USD",
            f"**Model:** `{package['model']}` · reasoning `{package['reasoningEffort']}`",
            "",
            review["summary"],
            "",
            "## Wykryte problemy",
            "",
            *issue_lines,
            "",
            "## Następne działanie",
            "",
            review["recommendedNextAction"],
            "",
            "Kontrola nie zmieniła aktywnego planu ani renderu.",
            "",
        ]
    )
    (directory / "review.md").write_text(report, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("filename")
    parser.add_argument("--import-cline", action="store_true")
    parser.add_argument("--cost", type=float)
    args = parser.parse_args()
    if args.import_cline:
        if args.cost is None:
            parser.error("--import-cline requires --cost")
        manifest = import_cline_review(Path(args.filename).stem, args.cost)
        print(json.dumps(manifest, ensure_ascii=False))
        return
    package = prepare(Path(args.filename).stem)
    print(json.dumps({"prepared": True, "previewSheets": package["previewSheets"], "budgetLimitUsd": package["budgetLimitUsd"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
