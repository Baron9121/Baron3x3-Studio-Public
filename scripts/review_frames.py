#!/usr/bin/env python3
"""Extract representative frames from the ranges already selected in a job plan."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1080
HEIGHT = 1920


def analyze_faces(frames_by_range: list[list[Path]]) -> list[dict[str, object]]:
    os.environ.setdefault("GLOG_minloglevel", "2")
    import mediapipe as mp
    import numpy as np
    from PIL import Image

    analyses: list[dict[str, object]] = []
    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as face_mesh:
        for range_index, paths in enumerate(frames_by_range, start=1):
            samples: list[dict[str, object]] = []
            for path in paths:
                image = np.asarray(Image.open(path).convert("RGB"))
                result = face_mesh.process(image)
                if not result.multi_face_landmarks:
                    raise RuntimeError(f"Nie wykryto twarzy na klatce: {path}")
                nose = result.multi_face_landmarks[0].landmark[1]
                samples.append(
                    {
                        "file": path.name,
                        "noseXPercent": round(nose.x * 100, 2),
                        "noseYPercent": round(nose.y * 100, 2),
                    }
                )

            nose_x = statistics.median(float(sample["noseXPercent"]) for sample in samples) / 100
            nose_y = statistics.median(float(sample["noseYPercent"]) for sample in samples) / 100
            minimum_scale = max(
                0.5 / nose_x,
                0.5 / (1 - nose_x),
                0.5 / nose_y,
                0.5 / (1 - nose_y),
            )
            scale = min(2.0, max(1.0, math.ceil(minimum_scale * 1.03 * 100) / 100))
            translate_x = round((0.5 - nose_x) * WIDTH * scale)
            translate_y = round((0.5 - nose_y) * HEIGHT * scale)
            analyses.append(
                {
                    "rangeIndex": range_index,
                    "samples": samples,
                    "medianNoseXPercent": round(nose_x * 100, 2),
                    "medianNoseYPercent": round(nose_y * 100, 2),
                    "recommendedScale": scale,
                    "recommendedTranslate": f"{translate_x}px {translate_y}px",
                }
            )
    return analyses


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="MP4 from input/ or an absolute path")
    args = parser.parse_args()

    source_arg = Path(args.source).expanduser()
    source = source_arg if source_arg.is_absolute() else ROOT / "input" / source_arg
    source = source.resolve()
    if not source.is_file() or source.suffix.lower() != ".mp4":
        raise FileNotFoundError(f"Nie znaleziono wejściowego MP4: {source}")

    plan_path = ROOT / "instructions" / "jobs" / f"{source.stem}.json"
    if not plan_path.is_file():
        raise FileNotFoundError(f"Najpierw utwórz plan: {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    ranges = plan.get("sourceRanges", [])
    if not ranges:
        raise ValueError("Plan nie zawiera sourceRanges; nie wiadomo, które klatki sprawdzać.")

    output_dir = ROOT / "analysis" / source.stem / "review-frames"
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    frames_by_range: list[list[Path]] = []
    for range_index, item in enumerate(ranges, start=1):
        start = int(item["sourceStartMs"])
        end = int(item["sourceEndMs"])
        times = (start + 250, (start + end) // 2, max(start, end - 250))
        range_frames: list[Path] = []
        for frame_index, timestamp_ms in enumerate(times, start=1):
            destination = output_dir / f"range-{range_index:02d}-frame-{frame_index:02d}.png"
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{timestamp_ms / 1000:.3f}",
                    "-i",
                    str(source),
                    "-frames:v",
                    "1",
                    str(destination),
                ],
                cwd=ROOT,
                check=True,
            )
            created.append(destination)
            range_frames.append(destination)
        frames_by_range.append(range_frames)

    analysis = {
        "version": 1,
        "source": source.name,
        "coordinateSystem": "percent from left/top; nose landmark 1; median of three frames per sourceRange",
        "ranges": analyze_faces(frames_by_range),
    }
    analysis_path = output_dir.parent / "framing-analysis.json"
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Klatki do oceny kadrowania:")
    for path in created:
        print(path)
    print(f"Lokalny pomiar twarzy: {analysis_path}")
    print("Model ma użyć pomiaru i obejrzeć wszystkie klatki, a dopiero potem zmienić kadrowanie w istniejących sourceRanges.")


if __name__ == "__main__":
    main()
