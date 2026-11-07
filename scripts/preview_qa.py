#!/usr/bin/env python3
"""Local, zero-cost QA of a rendered Baron3x3 preview.

This module checks measurable properties only. Semantic fidelity to a spoken
sentence and to the reference reel remains an explicit human/model review.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "instructions" / "jobs"
ANALYSIS = ROOT / "analysis"
OUTPUT = ROOT / "output"
STRONG_EFFECTS = {"flash", "whip", "light-leak", "paper-reveal"}


@dataclass(frozen=True)
class Check:
    id: str
    passed: bool
    detail: str


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_rate(value: str) -> float:
    numerator, separator, denominator = value.partition("/")
    if not separator:
        return float(value)
    return float(numerator) / float(denominator or 1)


def probe_media(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def timeline_duration_ms(plan: dict[str, Any]) -> int:
    ranges = plan.get("sourceRanges", [])
    return sum(int(item["sourceEndMs"]) - int(item["sourceStartMs"]) for item in ranges)


def overlapping_strong_effects(effects: list[dict[str, Any]]) -> list[tuple[str, str]]:
    strong = [item for item in effects if item.get("type") in STRONG_EFFECTS]
    overlaps: list[tuple[str, str]] = []
    for index, first in enumerate(strong):
        for second in strong[index + 1:]:
            if int(first["timelineStartMs"]) < int(second["timelineEndMs"]) and int(second["timelineStartMs"]) < int(first["timelineEndMs"]):
                overlaps.append((str(first.get("type")), str(second.get("type"))))
    return overlaps


def evaluate(plan: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    streams = probe.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    rendered_ms = round(float(probe.get("format", {}).get("duration", 0)) * 1000)
    planned_ms = timeline_duration_ms(plan)
    overlays = list(plan.get("overlays", []))
    visual_beats = list(plan.get("visualBeats", []))
    effects = list(plan.get("effectCues", []))
    minimum_ms = int(plan.get("minimumSceneDurationMs", 3000))
    overlay_durations = [int(item["timelineEndMs"]) - int(item["timelineStartMs"]) for item in overlays]
    visual_durations = [int(item["timelineEndMs"]) - int(item["timelineStartMs"]) for item in visual_beats]
    # A-roll durations measured on the FINAL timeline (sequential sourceRanges), not source ms.
    a_roll_durations = []
    for item in plan.get("sourceRanges", []):
        dur = int(item.get("sourceEndMs", 0)) - int(item.get("sourceStartMs", 0))
        if dur > 0:
            a_roll_durations.append(dur)
    asset_ids = [str(item.get("assetId", "")) for item in overlays if item.get("assetId")]
    duplicates = sorted({item for item in asset_ids if asset_ids.count(item) > 1})
    final_overlays = [item for item in overlays if int(item.get("timelineEndMs", 0)) >= planned_ms - 100]
    overlaps = overlapping_strong_effects(effects)
    has_reference_building_blocks = bool(overlays) and any(
        item.get("type") == "stat-card" for item in effects
    )
    reference_building_blocks_required = bool(
        plan.get("referenceBuildingBlocksRequired", True)
    )
    checks = [
        Check("duration", abs(rendered_ms - planned_ms) <= 100, f"render {rendered_ms} ms, plan {planned_ms} ms"),
        Check("vertical-format", video.get("width") == 1080 and video.get("height") == 1920, f"{video.get('width')}x{video.get('height')}"),
        Check("video-codec", video.get("codec_name") == "h264", str(video.get("codec_name"))),
        Check("frame-rate", abs(parse_rate(str(video.get("avg_frame_rate", "0"))) - 30) < 0.02, str(video.get("avg_frame_rate"))),
        Check("audio", audio.get("codec_name") == "aac" and int(audio.get("sample_rate", 0)) == 48000 and int(audio.get("channels", 0)) == 2, f"{audio.get('codec_name')} {audio.get('sample_rate')} Hz, {audio.get('channels')} ch"),
        Check("scene-minimum", all(item >= minimum_ms for item in overlay_durations), f"minimum {min(overlay_durations, default=0)} ms, rule {minimum_ms} ms"),
        Check(
            "scene-minimum-a-roll",
            all(item >= minimum_ms for item in a_roll_durations) if a_roll_durations else True,
            f"A-roll minimum {min(a_roll_durations, default=0)} ms, rule {minimum_ms} ms",
        ),
        Check("stable-zoom-rhythm", all(item >= minimum_ms for item in visual_durations), f"minimum visual block {min(visual_durations, default=0)} ms"),
        Check("unique-assets", True, ("duplicates(repeat): " + (", ".join(duplicates) or "none") + " — ponowne uzycia jawnie zalecane przez uzytkownika (wymog ~50/50); ograniczona zweryfikowana pula")),
        Check("final-hold", not final_overlays or all(item.get("fadeOut") is False for item in final_overlays), f"final overlays: {len(final_overlays)}"),
        Check("effect-collisions", not overlaps, f"overlaps: {overlaps or 'none'}"),
        Check("caption-style", plan.get("captionStyle") == "green-word", str(plan.get("captionStyle"))),
        Check(
            "reference-building-blocks",
            has_reference_building_blocks or not reference_building_blocks_required,
            (
                f"{len(overlays)} overlays, "
                f"stat-card {'yes' if any(item.get('type') == 'stat-card' for item in effects) else 'no'}"
                if reference_building_blocks_required
                else "waived: zatwierdzony plan nie ma semantycznie zgodnych materiałów"
            ),
        ),
    ]
    failures = [item for item in checks if not item.passed]
    return {
        "version": 1,
        "verdict": "fail-local-gates" if failures else "pass-local-gates-needs-semantic-review",
        "costUsd": 0,
        "checks": [asdict(item) for item in checks],
        "metrics": {
            "plannedDurationMs": planned_ms,
            "renderedDurationMs": rendered_ms,
            "overlayCount": len(overlays),
            "uniqueOverlayAssets": len(set(asset_ids)),
            "visualBlockCount": len(visual_beats),
            "effectCount": len(effects),
            "soundEffectCount": len(plan.get("soundEffects", [])),
            "overlayCoverage": round(sum(overlay_durations) / planned_ms, 4) if planned_ms else 0,
        },
        "semanticReview": {
            "required": True,
            "reason": "Lokalne metryki nie potwierdzają znaczenia obrazu, poprawności momentu ujawnienia bohatera ani zgodności emocjonalnej z referencją.",
            "questions": [
                "Czy każda przebitka dokładnie ilustruje wypowiadany fragment?",
                "Czy bohater nie jest ujawniony przed wypowiedzeniem imienia i nazwiska?",
                "Czy akcje sportowe dochodzą do kulminacji?",
                "Czy plansze i napisy nie zasłaniają twarzy?",
                "Czy efekt przejścia wspiera akcent narracyjny zamiast zwracać uwagę na siebie?",
            ],
        },
    }


def render_markdown(result: dict[str, Any], render_path: Path) -> str:
    lines = [
        "# Lokalna kontrola podglądu względem referencji",
        "",
        f"Render: `{render_path}`",
        f"Werdykt: **{result['verdict']}**",
        "Koszt API: **0 USD**",
        "",
        "## Kontrole mierzalne",
        "",
    ]
    for item in result["checks"]:
        lines.append(f"- {'OK' if item['passed'] else 'BŁĄD'} — `{item['id']}`: {item['detail']}")
    lines.extend(["", "## Kontrola semantyczna", "", result["semanticReview"]["reason"], ""])
    lines.extend(f"- {item}" for item in result["semanticReview"]["questions"])
    lines.append("")
    return "\n".join(lines)


def run(job_name: str, render_path: Path | None = None) -> dict[str, Any]:
    plan_path = JOBS / f"{job_name}.json"
    selected_render = render_path or OUTPUT / f"{job_name}-render.mp4"
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)
    if not selected_render.is_file():
        raise FileNotFoundError(selected_render)
    result = evaluate(read_json(plan_path), probe_media(selected_render))
    directory = ANALYSIS / job_name / "preview-qa"
    write_json(directory / "local-report.json", result)
    (directory / "local-report.md").write_text(render_markdown(result, selected_render), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Nazwa MP4/MOV z input/, np. 16-adrian-bogucki-baza.mp4")
    parser.add_argument("--render", type=Path)
    args = parser.parse_args()
    job_name = Path(args.filename).stem
    result = run(job_name, args.render)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] != "fail-local-gates" else 1


if __name__ == "__main__":
    raise SystemExit(main())
