#!/usr/bin/env python3
"""Local attention-map and safe-layout QA for Baron3x3 previews.

The detector is intentionally conservative. Faces are hard-protected. Text-like,
salient and round regions are advisory unless the plan marks a region protected.
No network or paid API is used.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "instructions" / "jobs"
OUTPUT = ROOT / "output"
ANALYSIS = ROOT / "analysis"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)


ZONES = {
    "top": Rect(54, 54, 972, 470),
    "top-left": Rect(54, 90, 470, 560),
    "top-right": Rect(556, 90, 470, 560),
    "center": Rect(80, 500, 920, 610),
    "bottom-caption": Rect(72, 1260, 936, 300),
}
FRAME_AREA = 1080 * 1920


def intersection_area(first: Rect, second: Rect) -> int:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.width, second.x + second.width)
    bottom = min(first.y + first.height, second.y + second.height)
    return max(0, right - left) * max(0, bottom - top)


def overlap_fraction(subject: Rect, zone: Rect) -> float:
    return intersection_area(subject, zone) / max(1, subject.area)


def rect_from_cv(box: tuple[int, int, int, int] | list[int]) -> Rect:
    return Rect(*(int(value) for value in box))


def deduplicate(rectangles: list[Rect], threshold: float = 0.62) -> list[Rect]:
    kept: list[Rect] = []
    for candidate in sorted(rectangles, key=lambda item: item.area, reverse=True):
        if any(
            intersection_area(candidate, other) / max(1, min(candidate.area, other.area))
            >= threshold
            for other in kept
        ):
            continue
        kept.append(candidate)
    return kept


def detect_faces(frame: np.ndarray) -> list[Rect]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    boxes: list[Rect] = []
    for filename, neighbors in (
        ("haarcascade_frontalface_default.xml", 5),
        ("haarcascade_frontalface_alt2.xml", 4),
        ("haarcascade_profileface.xml", 5),
    ):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + filename)
        detected = cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=neighbors,
            minSize=(54, 54),
        )
        boxes.extend(rect_from_cv(tuple(box)) for box in detected)
        if "profile" in filename:
            flipped = cv2.flip(gray, 1)
            detected_flipped = cascade.detectMultiScale(
                flipped,
                scaleFactor=1.08,
                minNeighbors=neighbors,
                minSize=(54, 54),
            )
            width = frame.shape[1]
            boxes.extend(
                Rect(width - int(x) - int(w), int(y), int(w), int(h))
                for x, y, w, h in detected_flipped
            )
    frame_height, frame_width = frame.shape[:2]
    plausible = [
        item
        for item in boxes
        if item.width <= frame_width * 0.7 and item.height <= frame_height * 0.7
    ]
    return deduplicate(plausible)


def protected_faces(record: dict[str, Any]) -> list[Rect]:
    """Return foreground faces that are large enough to drive a hard layout gate."""
    faces = [Rect(**box) for box in record.get("faces", [])]
    return [item for item in faces if item.area >= FRAME_AREA * 0.01]


def primary_face(record: dict[str, Any]) -> Rect | None:
    """Choose the likely main subject instead of blindly taking the largest face."""
    faces = protected_faces(record)
    if not faces:
        return None

    target_x, target_y = 540.0, 850.0
    diagonal = float(np.hypot(540.0, 960.0))

    def score(face: Rect) -> float:
        center_x = face.x + face.width / 2
        center_y = face.y + face.height / 2
        center_distance = float(np.hypot(center_x - target_x, center_y - target_y)) / diagonal
        area_ratio = face.area / FRAME_AREA
        edge_penalty = 1.5 if center_x < 162 or center_x > 918 else 0.0
        lower_penalty = 1.0 if center_y > 1440 else 0.0
        return area_ratio * 8.0 - center_distance * 1.5 - edge_penalty - lower_penalty

    return max(faces, key=score)


def detect_textlike(frame: np.ndarray) -> list[Rect]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gradient = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
    _, binary = cv2.threshold(gradient, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    merged = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5)),
    )
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[Rect] = []
    frame_area = frame.shape[0] * frame.shape[1]
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        if area < frame_area * 0.00025 or area > frame_area * 0.09:
            continue
        if width / max(1, height) < 1.8 or height < 8:
            continue
        boxes.append(Rect(x, y, width, height))
    return sorted(boxes, key=lambda item: item.area, reverse=True)[:12]


def detect_salient(frame: np.ndarray) -> list[Rect]:
    detector = cv2.saliency.StaticSaliencySpectralResidual_create()
    success, saliency = detector.computeSaliency(frame)
    if not success:
        return []
    threshold = float(np.quantile(saliency, 0.91))
    mask = np.uint8(saliency >= threshold) * 255
    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)),
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = frame.shape[0] * frame.shape[1]
    boxes: list[Rect] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = width * height
        if frame_area * 0.003 <= area <= frame_area * 0.28:
            boxes.append(Rect(x, y, width, height))
    return sorted(boxes, key=lambda item: item.area, reverse=True)[:6]


def detect_round_candidates(frame: np.ndarray) -> list[Rect]:
    small = cv2.resize(frame, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (7, 7), 1.4)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.3,
        minDist=28,
        param1=110,
        param2=48,
        minRadius=8,
        maxRadius=58,
    )
    if circles is None:
        return []
    result: list[Rect] = []
    for x, y, radius in np.round(circles[0]).astype(int)[:8]:
        result.append(
            Rect(
                int((x - radius) * 2),
                int((y - radius) * 2),
                int(radius * 4),
                int(radius * 4),
            )
        )
    return result


def analyze_frame(frame: np.ndarray, timestamp_ms: int) -> dict[str, Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return {
        "timestampMs": timestamp_ms,
        "visiblePixelRatio": round(float(np.count_nonzero(gray > 18)) / gray.size, 4),
        "faces": [asdict(item) for item in detect_faces(frame)],
        "textLike": [asdict(item) for item in detect_textlike(frame)],
        "salient": [asdict(item) for item in detect_salient(frame)],
        "roundCandidates": [asdict(item) for item in detect_round_candidates(frame)],
    }


def zone_score(record: dict[str, Any], zone_name: str) -> float:
    zone = ZONES[zone_name]
    weighted = (("faces", 12.0), ("textLike", 1.0), ("salient", 0.35), ("roundCandidates", 0.25))
    return round(
        sum(
            weight * overlap_fraction(Rect(**box), zone)
            for field, weight in weighted
            for box in record.get(field, [])
        ),
        4,
    )


def recommended_title_zone(record: dict[str, Any]) -> tuple[str, dict[str, float]]:
    candidates = ("top", "top-left", "top-right", "center")
    scores = {name: zone_score(record, name) for name in candidates}
    penalties = {"top": 0.0, "top-left": 0.8, "top-right": 0.8, "center": 1.5}
    ranked = min(candidates, key=lambda name: (scores[name] + penalties[name], candidates.index(name)))
    return ranked, scores


def nearest_record(records: list[dict[str, Any]], timestamp_ms: int) -> dict[str, Any]:
    return min(records, key=lambda item: abs(int(item["timestampMs"]) - timestamp_ms))


def evaluate_records(plan: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    cue_results: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    black_frames = [
        item for item in records if float(item.get("visiblePixelRatio", 1.0)) < 0.08
    ]
    black_frame_ratio = len(black_frames) / max(1, len(records))
    if black_frame_ratio >= 0.5:
        hard_failures.append(
            "większość próbek renderu jest czarna — prawdopodobnie nieobsługiwany kodek źródła"
        )
    for index, cue in enumerate(plan.get("effectCues", [])):
        if cue.get("type") not in {"kinetic-text", "audio-waveform"}:
            continue
        start = int(cue["timelineStartMs"])
        record = nearest_record(records, max(0, start - 100))
        current = str(cue.get("placement", "center"))
        if current not in {"top", "top-left", "top-right", "center"}:
            current = "center"
        recommended, scores = recommended_title_zone(record)
        face_overlap = max(
            (overlap_fraction(face, ZONES[current]) for face in protected_faces(record)),
            default=0.0,
        )
        passed = face_overlap < 0.08
        cue_id = str(cue.get("id", f"effect-{index}"))
        if not passed:
            hard_failures.append(f"{cue_id}: plansza przecina twarz")
        cue_results.append(
            {
                "id": cue_id,
                "type": cue.get("type"),
                "currentPlacement": current,
                "recommendedPlacement": recommended,
                "zoneScores": scores,
                "maxFaceOverlap": round(face_overlap, 4),
                "passed": passed,
            }
        )

    caption_collisions: list[dict[str, Any]] = []
    for record in records:
        overlap = max(
            (overlap_fraction(face, ZONES["bottom-caption"]) for face in protected_faces(record)),
            default=0.0,
        )
        if overlap >= 0.14:
            caption_collisions.append(
                {"timestampMs": record["timestampMs"], "maxFaceOverlap": round(overlap, 4)}
            )
    collision_ratio = len(caption_collisions) / max(1, len(records))
    if collision_ratio > 0.2:
        hard_failures.append("dolna strefa napisów regularnie przecina twarz")

    crop_checks: list[dict[str, Any]] = []
    for index, overlay in enumerate(plan.get("overlays", [])):
        start = int(overlay.get("timelineStartMs", 0))
        end = int(overlay.get("timelineEndMs", start))
        record = nearest_record(records, (start + end) // 2)
        primary = primary_face(record)
        edge_margin = 22
        touches_edge = bool(
            primary
            and (
                primary.x <= edge_margin
                or primary.y <= edge_margin
                or primary.x + primary.width >= 1080 - edge_margin
                or primary.y + primary.height >= 1920 - edge_margin
            )
        )
        overlay_id = str(overlay.get("id", f"overlay-{index}"))
        if touches_edge:
            hard_failures.append(f"{overlay_id}: główna twarz dotyka krawędzi kadru")
        crop_checks.append(
            {
                "id": overlay_id,
                "timestampMs": record["timestampMs"],
                "primaryFace": asdict(primary) if primary else None,
                "passed": not touches_edge,
                "roundCandidatesNearEdge": sum(
                    Rect(**box).x <= edge_margin
                    or Rect(**box).y <= edge_margin
                    or Rect(**box).x + Rect(**box).width >= 1080 - edge_margin
                    or Rect(**box).y + Rect(**box).height >= 1920 - edge_margin
                    for box in record.get("roundCandidates", [])
                ),
            }
        )

    return {
        "version": 1,
        "verdict": "fail-attention-safety" if hard_failures else "pass-attention-safety",
        "costUsd": 0,
        "detector": {
            "faces": "OpenCV Haar — twarda ochrona",
            "textLike": "gradient/morfologia — wskazówka bez OCR",
            "salient": "OpenCV spectral residual — wskazówka",
            "roundCandidates": "Hough circles — kandydat, nie deklaracja piłki/obręczy/herbu",
        },
        "sampleCount": len(records),
        "blackFrameRatio": round(black_frame_ratio, 4),
        "cueChecks": cue_results,
        "captionCollisions": caption_collisions,
        "captionCollisionRatio": round(collision_ratio, 4),
        "cropChecks": crop_checks,
        "hardFailures": hard_failures,
        "frames": records,
    }


def sample_times(plan: dict[str, Any], duration_ms: int) -> list[int]:
    values = {0, max(0, duration_ms - 50)}
    values.update(range(1000, duration_ms, 2000))
    for item in plan.get("effectCues", []):
        start = int(item.get("timelineStartMs", 0))
        end = int(item.get("timelineEndMs", start))
        values.update({max(0, start - 100), min(duration_ms - 1, (start + end) // 2)})
    for item in plan.get("overlays", []):
        start = int(item.get("timelineStartMs", 0))
        end = int(item.get("timelineEndMs", start))
        values.add(min(duration_ms - 1, (start + end) // 2))
    return sorted(value for value in values if 0 <= value < duration_ms)


def read_frame(capture: cv2.VideoCapture, timestamp_ms: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
    success, frame = capture.read()
    if not success or frame is None:
        raise RuntimeError(f"Nie można odczytać klatki {timestamp_ms} ms.")
    return frame


def annotate(frame: np.ndarray, record: dict[str, Any]) -> np.ndarray:
    output = frame.copy()
    styles = {
        "faces": ((35, 245, 35), "TWARZ"),
        "textLike": ((255, 210, 40), "TEKST"),
        "salient": ((230, 90, 255), "UWAGA"),
        "roundCandidates": ((40, 180, 255), "OKRAG?"),
    }
    for field, (color, label) in styles.items():
        for box in record.get(field, []):
            rect = Rect(**box)
            cv2.rectangle(
                output,
                (rect.x, rect.y),
                (rect.x + rect.width, rect.y + rect.height),
                color,
                4 if field == "faces" else 2,
            )
            cv2.putText(
                output,
                label,
                (rect.x, max(24, rect.y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2,
                cv2.LINE_AA,
            )
    cv2.putText(
        output,
        f"{record['timestampMs'] / 1000:.2f}s",
        (24, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.15,
        (255, 255, 255),
        3,
        cv2.LINE_AA,
    )
    return output


def write_report(job_name: str, render_path: Path, result: dict[str, Any]) -> Path:
    directory = ANALYSIS / job_name / "attention-map"
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "attention-map.json"
    temporary = json_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(json_path)
    lines = [
        "# Lokalna mapa uwagi i bezpieczne kadrowanie",
        "",
        f"Render: `{render_path}`",
        f"Werdykt: **{result['verdict']}**",
        "Koszt API: **0 USD**",
        "",
        "## Plansze",
        "",
    ]
    for cue in result["cueChecks"]:
        lines.append(
            f"- {'OK' if cue['passed'] else 'BŁĄD'} `{cue['id']}`: "
            f"obecnie `{cue['currentPlacement']}`, rekomendacja `{cue['recommendedPlacement']}`, "
            f"kolizja twarzy {cue['maxFaceOverlap']:.1%}."
        )
    lines.extend(
        [
            "",
            "## Napisy",
            "",
            f"Kolizje twarzy w dolnej strefie: {len(result['captionCollisions'])}/{result['sampleCount']} próbek.",
            "",
            "## Kadrowanie przebitek",
            "",
        ]
    )
    for crop in result["cropChecks"]:
        lines.append(
            f"- {'OK' if crop['passed'] else 'BŁĄD'} `{crop['id']}`: "
            f"główna twarz {'wykryta' if crop['primaryFace'] else 'niewykryta'}, "
            f"kandydaci okrągli przy krawędzi: {crop['roundCandidatesNearEdge']}."
        )
    lines.extend(
        [
            "",
            "## Ograniczenia uczciwości",
            "",
            "- Piłka, obręcz i herb nie są nazywane automatycznie bez pewnego klasyfikatora.",
            "- Obiekty okrągłe, tekstowe i saliency są wskazówkami; twardo chronione są twarze oraz ręcznie oznaczone regiony.",
            "- Pełna kulminacja akcji nadal podlega regule źródłowego zakresu i kontroli semantycznej.",
            "",
        ]
    )
    (directory / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return directory


def run(filename: str, render_path: Path | None = None, debug_frames: bool = True) -> dict[str, Any]:
    job_name = Path(filename).stem
    plan_path = JOBS / f"{job_name}.json"
    selected_render = render_path or OUTPUT / f"{job_name}-render.mp4"
    if not plan_path.is_file():
        raise FileNotFoundError(plan_path)
    if not selected_render.is_file():
        raise FileNotFoundError(selected_render)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    capture = cv2.VideoCapture(str(selected_render))
    if not capture.isOpened():
        raise RuntimeError(f"Nie można otworzyć {selected_render}.")
    duration_ms = round(
        capture.get(cv2.CAP_PROP_FRAME_COUNT) / max(1.0, capture.get(cv2.CAP_PROP_FPS)) * 1000
    )
    frames: list[tuple[np.ndarray, dict[str, Any]]] = []
    for timestamp_ms in sample_times(plan, duration_ms):
        frame = read_frame(capture, timestamp_ms)
        record = analyze_frame(frame, timestamp_ms)
        frames.append((frame, record))
    capture.release()
    records = [record for _, record in frames]
    result = evaluate_records(plan, records)
    directory = write_report(job_name, selected_render, result)
    if debug_frames:
        debug = directory / "frames"
        debug.mkdir(parents=True, exist_ok=True)
        for frame, record in frames:
            cv2.imwrite(str(debug / f"{record['timestampMs']:06d}.jpg"), annotate(frame, record))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Nazwa MP4/MOV z input/.")
    parser.add_argument("--render", type=Path)
    parser.add_argument("--no-debug-frames", action="store_true")
    args = parser.parse_args()
    result = run(args.filename, args.render, not args.no_debug_frames)
    summary = {key: value for key, value in result.items() if key != "frames"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "pass-attention-safety" else 1


if __name__ == "__main__":
    raise SystemExit(main())
