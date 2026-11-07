#!/usr/bin/env python3
"""Local MP4 -> accurate Polish transcript -> reviewed edit plan -> Remotion."""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

if __package__:
    from .asset_catalog import refresh_catalog
else:
    from asset_catalog import refresh_catalog


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
ASSETS = ROOT / "assets"
INSTRUCTIONS = ROOT / "instructions" / "jobs"
PUBLIC = ROOT / "remotion" / "public"
PUBLIC_INPUT = PUBLIC / "input"
PUBLIC_ASSETS = PUBLIC / "assets"
PUBLIC_SFX = PUBLIC / "sfx"
SFX_ASSETS = ASSETS / "sfx"
JOB_FILE = PUBLIC / "job.json"
WHISPER_PYTHON = ROOT / ".venv" / "bin" / "python"
GLOSSARY_FILE = ROOT / "knowledge" / "polish-whisper-prompt.txt"
REPLACEMENTS_FILE = ROOT / "knowledge" / "polish-replacements.json"
DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"
LARGE_VIDEO_THRESHOLD_BYTES = 2 * 1024 * 1024 * 1024
FPS = 30
WIDTH = 1080
HEIGHT = 1920
OVERLAY_PRESENTATIONS = {
    "full", "editorial", "archive", "split", "stack", "cutout"
}
OVERLAY_MOTIONS = {"push-in", "pull-out", "pan-left", "pan-right", "still"}


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def probe(source: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,codec_name,profile,pix_fmt,"
            "color_range,color_space,color_transfer,color_primaries",
            "-of",
            "json",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    video = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if not video:
        raise RuntimeError("Plik nie zawiera strumienia wideo.")
    return {
        "durationMs": round(float(data["format"]["duration"]) * 1000),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "codec": str(video.get("codec_name", "")),
        "profile": str(video.get("profile", "")),
        "pixelFormat": str(video.get("pix_fmt", "")),
        "colorRange": str(video.get("color_range", "")),
        "colorSpace": str(video.get("color_space", "")),
        "colorTransfer": str(video.get("color_transfer", "")),
        "colorPrimaries": str(video.get("color_primaries", "")),
    }


def source_signature(source: Path) -> dict[str, Any]:
    stat = source.stat()
    return {"path": str(source), "size": stat.st_size, "mtimeNs": stat.st_mtime_ns}


def read_source_color_metadata(source: Path) -> dict[str, Any]:
    """Read camera MakerNotes in addition to ordinary video stream tags."""
    stream = probe(source)
    exiftool = shutil.which("exiftool")
    maker: dict[str, Any] = {}
    if exiftool:
        completed = subprocess.run(
            [
                exiftool, "-j", "-G1", "-s",
                "-Make", "-Model", "-CanonFirmwareVersion", "-ToneCurve",
                "-PictureStyle", "-ColorSpace", "-ISO", "-RecommendedExposureIndex",
                "-ColorProfiles", "-ColorPrimaries", "-TransferCharacteristics",
                "-MatrixCoefficients", "-VideoFullRangeFlag", str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        rows = json.loads(completed.stdout)
        maker = rows[0] if rows else {}
        maker.pop("SourceFile", None)
    return {"stream": stream, "makerNotes": maker}


def choose_color_pipeline(
    metadata: dict[str, Any], profile_override: str = "auto"
) -> dict[str, Any]:
    """Choose an input transform from evidence, never from camera name alone."""
    allowed = {
        "auto", "bt709-direct", "canon-log-2-cinema-gamut", "canon-log-3-cinema-gamut"
    }
    if profile_override not in allowed:
        raise ValueError(
            "sourceColorProfile musi być jednym z: " + ", ".join(sorted(allowed))
        )
    maker = metadata.get("makerNotes", {})
    stream = metadata.get("stream", {})
    model = str(maker.get("IFD0:Model") or maker.get("UserData:Model") or "")
    tone_curve = str(maker.get("Canon:ToneCurve", ""))
    maker_space = str(maker.get("Canon:ColorSpace", ""))
    iso = maker.get("ExifIFD:RecommendedExposureIndex", maker.get("ExifIFD:ISO"))
    evidence = {
        "cameraModel": model or None,
        "toneCurve": tone_curve or None,
        "makerColorSpace": maker_space or None,
        "iso": iso,
        "matrix": stream.get("colorSpace") or None,
        "transfer": stream.get("colorTransfer") or None,
        "primaries": stream.get("colorPrimaries") or None,
        "range": stream.get("colorRange") or None,
    }

    selected = profile_override
    reason = "Jawny profil wejściowy ustawiony w planie."
    if selected == "auto":
        direct_stream = stream.get("colorTransfer") in {"bt709", "iec61966-2-1"}
        # Generic Canon still-photo MakerNotes (ToneCurve/ColorSpace) may say
        # Standard/sRGB even when a Cinema EOS MP4 contains a flat Log image.
        # Only an explicit transfer tag is sufficient for an automatic direct
        # Rec.709 decision; otherwise require a clip-specific override.
        if direct_stream:
            selected = "bt709-direct"
            reason = (
                "MakerNotes i parametry strumienia wskazują materiał display-referred "
                "BT.709; LUT Canon Log nie jest stosowany."
            )
        else:
            raise ValueError(
                "Nie można jednoznacznie ustalić gammy z metadanych. Ustaw w planie "
                "sourceColorProfile na bt709-direct, canon-log-2-cinema-gamut albo "
                "canon-log-3-cinema-gamut po sprawdzeniu ustawień kamery."
            )

    lut_name = None
    if selected.startswith("canon-log"):
        lut_name = {
            "canon-log-2-cinema-gamut": "canon/CinemaGamut_CanonLog2-to-Canon709_33_Ver.1.0.cube",
            "canon-log-3-cinema-gamut": "canon/CinemaGamut_CanonLog3-to-Canon709_33_Ver.1.0.cube",
        }[selected]
        lut_path = ASSETS / "luts" / lut_name
        if not lut_path.is_file():
            raise FileNotFoundError(
                f"Brak oficjalnego LUT-u Canona: {lut_path}. Pipeline nie zastąpi go zgadywanym filtrem."
            )
    return {
        "mode": "metadata-auto" if profile_override == "auto" else "explicit-override",
        "inputProfile": selected,
        "outputProfile": "bt709",
        "lut": lut_name,
        "evidence": evidence,
        "reason": reason,
    }


def prepare_whisper_input(source: Path, job_dir: Path, force: bool) -> Path:
    """Avoid repeatedly decoding a huge 4K file inside Whisper.

    The 16 kHz mono PCM proxy preserves the bandwidth used by speech models and
    is tiny compared with the source. Small clips continue through unchanged.
    """
    if source.stat().st_size < LARGE_VIDEO_THRESHOLD_BYTES:
        return source
    audio_path = job_dir / "whisper-audio.wav"
    meta_path = job_dir / "whisper-audio-meta.json"
    expected_meta = {"version": 1, "source": source_signature(source), "sampleRate": 16000, "channels": 1}
    if not force and audio_path.is_file() and read_json(meta_path) == expected_meta:
        print("Whisper: używam zapisanego lekkiego proxy audio.")
        return audio_path
    job_dir.mkdir(parents=True, exist_ok=True)
    temporary = job_dir / "whisper-audio.tmp.wav"
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(temporary),
        ]
    )
    temporary.replace(audio_path)
    write_json(meta_path, expected_meta)
    print(f"Whisper: utworzono lokalne proxy audio {audio_path.name}.")
    return audio_path


def transcribe(
    source: Path,
    job_dir: Path,
    model: str,
    language: str,
    force: bool,
) -> dict[str, Any]:
    raw_path = job_dir / "raw-production.json"
    meta_path = job_dir / "transcription-meta.json"
    expected_meta = {"model": model, "language": language, "source": source_signature(source)}
    specialist_meta = job_dir / "specialist-transcription.json"
    if specialist_meta.exists():
        import hashlib
        signature = read_json(specialist_meta)
        if signature["sourceSha256"] != hashlib.sha256(source.read_bytes()).hexdigest() or signature["rawSha256"] != hashlib.sha256(raw_path.read_bytes()).hexdigest():
            raise ValueError("Zmienione źródło lub transkrypcja specjalisty; ponów weryfikację.")
        return read_json(raw_path)


    if not force and raw_path.is_file() and read_json(meta_path) == expected_meta:
        print("Transkrypcja: używam zapisanej analizy (bez ponownego liczenia).")
        return read_json(raw_path)

    prompt = GLOSSARY_FILE.read_text(encoding="utf-8").strip() if GLOSSARY_FILE.is_file() else ""
    command = [
        str(WHISPER_PYTHON),
        "-m",
        "mlx_whisper.cli",
        str(source),
        "--model",
        model,
        "--language",
        language,
        "--word-timestamps",
        "True",
        "--output-format",
        "json",
        "--output-dir",
        str(job_dir),
        "--output-name",
        "raw-production",
        "--verbose",
        "False",
    ]
    if prompt:
        command.extend(["--initial-prompt", prompt])
    run(command)
    write_json(meta_path, expected_meta)
    return read_json(raw_path)


def normalized_token(value: str) -> str:
    return re.sub(r"[^0-9a-ząćęłńóśźż]", "", value.casefold())


def load_replacements(job_name: str) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for path in [REPLACEMENTS_FILE, INSTRUCTIONS / f"{job_name}.replacements.json"]:
        data = read_json(path, {})
        if not isinstance(data, dict):
            raise ValueError(f"Korekty muszą być obiektem JSON: {path}")
        replacements.update({str(key): str(value) for key, value in data.items()})
    return replacements


def apply_phrase_replacements(words: list[dict[str, Any]], replacements: dict[str, str]) -> None:
    for incorrect, corrected in replacements.items():
        wrong_tokens = incorrect.split()
        right_tokens = corrected.split()
        wanted = [normalized_token(token) for token in wrong_tokens]
        start = 0
        while start <= len(words) - len(wanted):
            candidate = [normalized_token(words[start + offset]["text"]) for offset in range(len(wanted))]
            if candidate == wanted:
                original = words[start : start + len(wanted)]
                phrase_start = original[0]["startMs"]
                phrase_end = original[-1]["endMs"]
                duration = max(1, phrase_end - phrase_start)
                confidence = round(
                    sum(float(word["confidence"]) for word in original) / len(original), 4
                )
                replacement_words = []
                for offset, replacement in enumerate(right_tokens):
                    token_start = phrase_start + round((duration * offset) / len(right_tokens))
                    token_end = phrase_start + round((duration * (offset + 1)) / len(right_tokens))
                    replacement_words.append(
                        {
                            "text": replacement,
                            "startMs": token_start,
                            "endMs": token_end,
                            "confidence": confidence,
                        }
                    )
                words[start : start + len(wanted)] = replacement_words
                start += len(replacement_words)
            else:
                start += 1


def normalize_transcript(
    raw: dict[str, Any],
    source: Path,
    replacements: dict[str, str],
    timing_corrections: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized_segments: list[dict[str, Any]] = []
    all_words: list[dict[str, Any]] = []

    for segment in raw.get("segments", []):
        for word in segment.get("words", []):
            all_words.append(
                {
                    "text": word["word"].strip(),
                    "startMs": round(float(word["start"]) * 1000),
                    "endMs": round(float(word["end"]) * 1000),
                    "confidence": round(float(word.get("probability", 0)), 4),
                }
            )

    apply_phrase_replacements(all_words, replacements)
    for correction in timing_corrections or []:
        expected_text = str(correction["text"]).casefold()
        old_start = int(correction["originalStartMs"])
        old_end = int(correction["originalEndMs"])
        matching = [
            word
            for word in all_words
            if word["text"].casefold() == expected_text
            and int(word["startMs"]) == old_start
            and int(word["endMs"]) == old_end
        ]
        if len(matching) != 1:
            raise ValueError(
                f"Korekta czasu {correction!r} nie wskazuje dokładnie jednego słowa."
            )
        matching[0]["startMs"] = int(correction.get("startMs", old_start))
        matching[0]["endMs"] = int(correction.get("endMs", old_end))
        if matching[0]["endMs"] <= matching[0]["startMs"]:
            raise ValueError(f"Nieprawidłowa korekta czasu słowa: {correction!r}")

    for index, segment in enumerate(raw.get("segments", [])):
        start_ms = round(float(segment["start"]) * 1000)
        end_ms = round(float(segment["end"]) * 1000)
        words = [word for word in all_words if word["startMs"] >= start_ms and word["endMs"] <= end_ms]
        normalized_segments.append(
            {
                "id": index,
                "text": " ".join(word["text"] for word in words),
                "startMs": start_ms,
                "endMs": end_ms,
                "words": words,
            }
        )

    transcript = {
        "version": 2,
        "source": source.name,
        "language": raw.get("language"),
        "text": " ".join(word["text"] for word in all_words),
        "segments": normalized_segments,
    }
    return transcript, all_words


def timestamp_label(milliseconds: int) -> str:
    minutes, remainder = divmod(max(0, milliseconds), 60000)
    seconds, millis = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def write_transcript_compact(path: Path, transcript: dict[str, Any]) -> None:
    lines = [
        "# Kompaktowa transkrypcja z timestampami",
        "",
        "Każdy wiersz odpowiada segmentowi Whispera. Dokładne granice słów pozostają w `transcript.json` i sprawdza je lokalny walidator.",
        "",
    ]
    previous_text = ""
    repeated = 0
    for segment in transcript.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        if text == previous_text:
            repeated += 1
            continue
        if repeated:
            lines.append(f"[poprzedni segment powtórzony jeszcze {repeated}× — możliwa halucynacja/szum]")
            repeated = 0
        lines.append(
            f"[{timestamp_label(int(segment['startMs']))}–{timestamp_label(int(segment['endMs']))}] {text}"
        )
        previous_text = text
    if repeated:
        lines.append(f"[poprzedni segment powtórzony jeszcze {repeated}× — możliwa halucynacja/szum]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_plan(job_name: str, instructions_text: str | None) -> tuple[Path, dict[str, Any]]:
    plan_path = INSTRUCTIONS / f"{job_name}.json"
    plan = read_json(plan_path)
    if plan is None:
        plan = {
            "version": 1,
            "status": "needs-instructions",
            "instructions": instructions_text or "",
            "captionStyle": "green-word",
            "storyPlan": {"hook": "", "arc": "", "payoff": "", "languageReviewed": False},
            "minimumSceneDurationMs": 3000,
            "allowRepeatedAssets": False,
            "sourceRanges": [],
            "overlays": [],
            "effectCues": [],
            "soundEffects": [],
            "notes": [
                "Cursor: uzupełnij sourceRanges na podstawie promptu i transkrypcji.",
                "Nie ustawiaj statusu ready bez zamkniętej historii i pełnych słów na granicach cięć.",
            ],
        }
        write_json(plan_path, plan)
    elif instructions_text is not None:
        plan["instructions"] = instructions_text
        plan["status"] = "needs-review"
        write_json(plan_path, plan)
    return plan_path, plan


CAPTION_STYLES = {"green-word", "white-outline"}
ZOOM_LEVELS = {"wide", "medium", "close"}
ZOOM_EFFECTS = {"smooth", "blur", "rgb", "split"}
EFFECT_CUE_TYPES = {
    "flash",
    "whip",
    "light-leak",
    "film-frame",
    "rec",
    "stat-card",
    "kinetic-text",
    "audio-waveform",
}
SOUND_EFFECT_TYPES = {"whoosh", "impact", "click", "dragon-whoosh", "dragon-camera"}
SOUND_EFFECT_DEFAULT_VOLUMES = {"dragon-whoosh": 0.14, "dragon-camera": 0.12, "whoosh": 0.14, "impact": 0.22, "click": 0.09}
SOUND_EFFECT_MAX_VOLUMES = {"dragon-whoosh": 0.18, "dragon-camera": 0.18, "whoosh": 0.18, "impact": 0.24, "click": 0.12}
SOUND_EFFECT_FILES = {
    "dragon-whoosh": "dragon-whoosh-short.wav",
    "dragon-camera": "dragon-camera.wav",
    "whoosh": "whoosh-soft.wav",
    "impact": "impact-low.wav",
    "click": "click.wav",
}
POSITION_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?%\s+-?\d+(?:\.\d+)?%$")
TRANSLATE_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?px\s+-?\d+(?:\.\d+)?px$")


def validate_plan(plan_path: Path, plan: dict[str, Any]) -> None:
    """Reject malformed agent output before it reaches Remotion."""
    if "cropping" in plan:
        raise ValueError(
            f"{plan_path}: pole 'cropping' nie jest obsługiwane. "
            "Kadrowanie ustaw w każdym sourceRanges przez scaleFrom, scaleTo, objectPosition i translate."
        )

    status = plan.get("status")
    if status not in {"needs-instructions", "needs-review", "ready"}:
        raise ValueError(f"{plan_path}: nieprawidłowy status: {status!r}")

    caption_style = plan.get("captionStyle", "green-word")
    if caption_style not in CAPTION_STYLES:
        allowed = ", ".join(sorted(CAPTION_STYLES))
        raise ValueError(f"{plan_path}: captionStyle musi być jednym z: {allowed}")

    color_grade = plan.get("colorGrade", {})
    if not isinstance(color_grade, dict):
        raise ValueError(f"{plan_path}: colorGrade musi być obiektem JSON.")
    grade_limits = {
        "contrast": (0.8, 1.3),
        "saturation": (0.7, 1.4),
        "brightness": (0.8, 1.2),
        "sepia": (0.0, 0.15),
    }
    for key, (minimum, maximum) in grade_limits.items():
        value = color_grade.get(key, 1.0 if key != "sepia" else 0.0)
        if not isinstance(value, (int, float)) or not minimum <= float(value) <= maximum:
            raise ValueError(
                f"{plan_path}: colorGrade.{key} musi być liczbą od {minimum} do {maximum}."
            )

    ranges = plan.get("sourceRanges")
    if not isinstance(ranges, list):
        raise ValueError(f"{plan_path}: sourceRanges musi być listą.")
    if status == "ready" and not ranges:
        raise ValueError(f"{plan_path}: status ready wymaga co najmniej jednego sourceRanges.")

    for index, item in enumerate(ranges, start=1):
        label = f"{plan_path}: sourceRanges[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} musi być obiektem JSON.")
        for key in ("sourceStartMs", "sourceEndMs"):
            if not isinstance(item.get(key), int):
                raise ValueError(f"{label}.{key} musi być liczbą całkowitą w milisekundach.")
        for key in ("scaleFrom", "scaleTo"):
            value = item.get(key, 1.0)
            if not isinstance(value, (int, float)) or not 1.0 <= float(value) <= 2.0:
                raise ValueError(f"{label}.{key} musi być liczbą od 1.0 do 2.0.")
        position = item.get("objectPosition", "50% 50%")
        if not isinstance(position, str) or not POSITION_PATTERN.fullmatch(position.strip()):
            raise ValueError(f"{label}.objectPosition musi mieć format np. '50% 42%'.")
        translate = item.get("translate", "0px 0px")
        if not isinstance(translate, str) or not TRANSLATE_PATTERN.fullmatch(translate.strip()):
            raise ValueError(f"{label}.translate musi mieć format np. '100px 10px'.")

    overlays = plan.get("overlays", [])
    if not isinstance(overlays, list):
        raise ValueError(f"{plan_path}: overlays musi być listą.")
    minimum_scene_duration = int(plan.get("minimumSceneDurationMs", 0))
    if minimum_scene_duration < 0:
        raise ValueError(f"{plan_path}: minimumSceneDurationMs nie może być ujemne.")
    seen_asset_ids: set[str] = set()
    allow_repeated_assets = bool(plan.get("allowRepeatedAssets", False))
    for index, item in enumerate(overlays, start=1):
        label = f"{plan_path}: overlays[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} musi być obiektem JSON.")
        start = item.get("timelineStartMs")
        end = item.get("timelineEndMs")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError(f"{label} wymaga poprawnych timelineStartMs i timelineEndMs.")
        if end - start < minimum_scene_duration:
            raise ValueError(
                f"{label} trwa krócej niż minimumSceneDurationMs={minimum_scene_duration}."
            )
        asset_id = item.get("assetId")
        if asset_id and not allow_repeated_assets:
            normalized_asset_id = str(asset_id)
            if normalized_asset_id in seen_asset_ids:
                raise ValueError(f"{label}: powtórzony assetId {normalized_asset_id}.")
            seen_asset_ids.add(normalized_asset_id)
        presentation = item.get("presentation", "full")
        if presentation not in OVERLAY_PRESENTATIONS:
            raise ValueError(
                f"{label}.presentation musi być jednym z: {sorted(OVERLAY_PRESENTATIONS)}"
            )
        if item.get("motion", "push-in") not in OVERLAY_MOTIONS:
            raise ValueError(f"{label}.motion musi być jednym z: {sorted(OVERLAY_MOTIONS)}")
        has_secondary = bool(item.get("secondaryAssetId") or item.get("secondaryAssetFile"))
        collage_ids = item.get("collageAssetIds", [])
        if not isinstance(collage_ids, list) or not all(
            isinstance(asset_id, str) and asset_id.strip() for asset_id in collage_ids
        ):
            raise ValueError(f"{label}.collageAssetIds musi być listą niepustych assetId.")
        if presentation in {"split", "stack"} and not has_secondary:
            raise ValueError(f"{label} typu {presentation} wymaga drugiego materiału.")
        if has_secondary and presentation not in {"split", "stack"}:
            raise ValueError(f"{label}: drugi materiał jest dozwolony tylko dla split albo stack.")
        if presentation == "paper-collage":
            if has_secondary:
                raise ValueError(f"{label}: paper-collage używa collageAssetIds, nie secondaryAssetId.")
            if not 2 <= len(collage_ids) <= 4:
                raise ValueError(f"{label}: paper-collage wymaga 2–4 dodatkowych zdjęć.")
            normalized_collage_ids = [str(asset_id) for asset_id in collage_ids]
            if len(set(normalized_collage_ids)) != len(normalized_collage_ids):
                raise ValueError(f"{label}: paper-collage nie może powtarzać zdjęć.")
            if asset_id and str(asset_id) in normalized_collage_ids:
                raise ValueError(f"{label}: główne zdjęcie nie może powtarzać się w collageAssetIds.")
            for collage_id in normalized_collage_ids:
                if not allow_repeated_assets and collage_id in seen_asset_ids:
                    raise ValueError(f"{label}: powtórzony assetId {collage_id}.")
                seen_asset_ids.add(collage_id)
        elif collage_ids:
            raise ValueError(f"{label}: collageAssetIds jest dozwolone tylko dla paper-collage.")
        for position_key in ("objectPosition", "secondaryObjectPosition"):
            position = item.get(position_key, "50% 50%")
            if not isinstance(position, str) or not POSITION_PATTERN.fullmatch(position.strip()):
                raise ValueError(f"{label}.{position_key} musi mieć format np. '50% 42%'.")
        secondary_start = item.get("secondarySourceStartMs", 0)
        if not isinstance(secondary_start, int) or secondary_start < 0:
            raise ValueError(f"{label}.secondarySourceStartMs musi być nieujemną liczbą całkowitą.")
        for text_key, max_length in (("headline", 70), ("kicker", 32)):
            value = item.get(text_key, "")
            if not isinstance(value, str) or len(value.strip()) > max_length:
                raise ValueError(f"{label}.{text_key} musi być tekstem do {max_length} znaków.")
        accent = item.get("accentColor", "#ff174f")
        if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            raise ValueError(f"{label}.accentColor musi być kolorem HEX, np. '#ff174f'.")
        for fade_key in ("fadeIn", "fadeOut"):
            if not isinstance(item.get(fade_key, True), bool):
                raise ValueError(f"{label}.{fade_key} musi być wartością true albo false.")

    visual_beats = plan.get("visualBeats", [])
    if not isinstance(visual_beats, list):
        raise ValueError(f"{plan_path}: visualBeats musi być listą.")
    previous_end = 0
    for index, item in enumerate(visual_beats, start=1):
        label = f"{plan_path}: visualBeats[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} musi być obiektem JSON.")
        start = item.get("timelineStartMs")
        end = item.get("timelineEndMs")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            raise ValueError(f"{label} wymaga poprawnych timelineStartMs i timelineEndMs.")
        if start != previous_end:
            raise ValueError(f"{label} musi zaczynać się dokładnie w {previous_end} ms.")
        if item.get("zoomLevel") not in ZOOM_LEVELS:
            raise ValueError(f"{label}.zoomLevel musi być jednym z: {sorted(ZOOM_LEVELS)}")
        if item.get("transitionEffect", "smooth") not in ZOOM_EFFECTS:
            raise ValueError(f"{label}.transitionEffect musi być jednym z: {sorted(ZOOM_EFFECTS)}")
        previous_end = end

    effect_cues = plan.get("effectCues", [])
    if not isinstance(effect_cues, list):
        raise ValueError(f"{plan_path}: effectCues musi być listą.")
    for index, item in enumerate(effect_cues, start=1):
        label = f"{plan_path}: effectCues[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} musi być obiektem JSON.")
        start = item.get("timelineStartMs")
        end = item.get("timelineEndMs")
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError(f"{label} wymaga poprawnych timelineStartMs i timelineEndMs.")
        if item.get("type") not in EFFECT_CUE_TYPES:
            raise ValueError(f"{label}.type musi być jednym z: {sorted(EFFECT_CUE_TYPES)}")
        intensity = item.get("intensity", 1.0)
        if not isinstance(intensity, (int, float)) or not 0.1 <= float(intensity) <= 1.5:
            raise ValueError(f"{label}.intensity musi być liczbą od 0.1 do 1.5.")
        if item.get("direction", "right") not in {"left", "right"}:
            raise ValueError(f"{label}.direction musi być 'left' albo 'right'.")
        if item.get("placement", "center") not in {"top", "top-left", "top-right", "center"}:
            raise ValueError(
                f"{label}.placement musi być jednym z: top, top-left, top-right, center."
            )
        if item.get("type") == "stat-card" and not str(item.get("value", "")).strip():
            raise ValueError(f"{label} typu stat-card wymaga pola value.")
        if item.get("type") == "kinetic-text" and not str(item.get("value", "")).strip():
            raise ValueError(f"{label} typu kinetic-text wymaga pola value.")

    sound_effects = plan.get("soundEffects", [])
    if not isinstance(sound_effects, list):
        raise ValueError(f"{plan_path}: soundEffects musi być listą.")
    for index, item in enumerate(sound_effects, start=1):
        label = f"{plan_path}: soundEffects[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} musi być obiektem JSON.")
        if item.get("type") not in SOUND_EFFECT_TYPES:
            raise ValueError(f"{label}.type musi być jednym z: {sorted(SOUND_EFFECT_TYPES)}")
        if not isinstance(item.get("timelineStartMs"), int) or item["timelineStartMs"] < 0:
            raise ValueError(f"{label}.timelineStartMs musi być nieujemną liczbą całkowitą.")
        if 'durationMs' in item and (not isinstance(item['durationMs'], (int,float)) or not 0 < item['durationMs'] <= 3000):
            raise ValueError('soundEffects.durationMs musi być > 0 i <= 3000')
        effect_type = str(item["type"])
        volume = item.get("volume", SOUND_EFFECT_DEFAULT_VOLUMES[effect_type])
        maximum = SOUND_EFFECT_MAX_VOLUMES[effect_type]
        if not isinstance(volume, (int, float)) or not 0 <= float(volume) <= maximum:
            raise ValueError(f"{label}.volume dla {effect_type} musi być liczbą od 0 do {maximum}.")
        speech_ducking = item.get("speechDucking", 0.72)
        if not isinstance(speech_ducking, (int, float)) or not 0.4 <= float(speech_ducking) <= 1:
            raise ValueError(f"{label}.speechDucking musi być liczbą od 0.4 do 1.")


def validate_word_boundaries(
    plan_path: Path,
    ranges: list[dict[str, Any]],
    words: list[dict[str, Any]],
) -> None:
    """Reject any ready-plan boundary that cuts through a spoken word.

    A boundary may sit exactly on a word edge or inside genuine silence. This
    keeps natural breaths possible while making a mid-word cut impossible.
    """
    if not words:
        raise ValueError(f"{plan_path}: brak timestampów słów do walidacji cięć.")

    for index, item in enumerate(ranges, start=1):
        start = int(item["sourceStartMs"])
        end = int(item["sourceEndMs"])
        for boundary_name, boundary in (("sourceStartMs", start), ("sourceEndMs", end)):
            crossing = [
                word
                for word in words
                if int(word["startMs"]) < boundary < int(word["endMs"])
            ]
            if crossing:
                word = crossing[0]
                raise ValueError(
                    f"{plan_path}: sourceRanges[{index}].{boundary_name}={boundary} ms "
                    f"przecina słowo {word['text']!r} "
                    f"({word['startMs']}–{word['endMs']} ms)."
                )

        selected = [
            word
            for word in words
            if int(word["startMs"]) >= start and int(word["endMs"]) <= end
        ]
        if not selected:
            raise ValueError(f"{plan_path}: sourceRanges[{index}] nie zawiera żadnego pełnego słowa.")


def copy_or_link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def prepare_public_media(source: Path) -> str:
    destination = PUBLIC_INPUT / source.name
    copy_or_link(source, destination)
    return f"input/{destination.name}"


def browser_compatible_video(metadata: dict[str, Any]) -> bool:
    """Return true only for source formats Chromium can decode reliably."""
    return metadata.get("codec") == "h264" and metadata.get("pixelFormat") in {
        "yuv420p", "yuvj420p"
    }


def prepare_render_source(
    source: Path,
    job_dir: Path,
    edits: list[dict[str, Any]],
    metadata: dict[str, Any],
    color_pipeline: dict[str, Any],
) -> tuple[Path, list[dict[str, Any]], dict[str, Any]]:
    """Create a cached H.264 proxy containing only approved ranges when needed.

    Remotion renders through Chromium, which cannot reliably decode camera HEVC
    4:2:2 10-bit (for example Apple HEVC Rext). Keeping only the approved ranges
    makes the conversion fast and avoids duplicating a very large master file.
    """
    if browser_compatible_video(metadata) and not color_pipeline.get("lut"):
        return source, edits, metadata

    proxy = job_dir / "render-source.mp4"
    meta_path = job_dir / "render-source-meta.json"
    rotation = "clockwise" if metadata["width"] > metadata["height"] else "none"
    expected_meta = {
        "version": 1,
        "source": source_signature(source),
        "ranges": [
            {"startMs": item["sourceStartMs"], "endMs": item["sourceEndMs"]}
            for item in edits
        ],
        "rotation": rotation,
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "codec": "h264",
        "pixelFormat": "yuv420p",
        "colorPipeline": color_pipeline,
    }
    if not proxy.is_file() or read_json(meta_path) != expected_meta:
        temporary = job_dir / "render-source.building.mp4"
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for edit in edits:
            start = int(edit["sourceStartMs"]) / 1000
            duration = (int(edit["sourceEndMs"]) - int(edit["sourceStartMs"])) / 1000
            command.extend(["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source)])

        filters: list[str] = []
        concat_inputs: list[str] = []
        rotation_filter = "transpose=clock," if rotation == "clockwise" else ""
        lut_filter = ""
        if color_pipeline.get("lut"):
            lut_path = ASSETS / "luts" / str(color_pipeline["lut"])
            escaped_lut = str(lut_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
            lut_filter = f"lut3d=file='{escaped_lut}',"
        for index in range(len(edits)):
            filters.append(
                f"[{index}:v]{rotation_filter}{lut_filter}scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},fps={FPS},setsar=1,setpts=PTS-STARTPTS[v{index}]"
            )
            filters.append(
                f"[{index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
            concat_inputs.append(f"[v{index}][a{index}]")
        filters.append(
            "".join(concat_inputs)
            + f"concat=n={len(edits)}:v=1:a=1[outv][outa]"
        )
        command.extend(
            [
                "-filter_complex", ";".join(filters),
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
                "-movflags", "+faststart", str(temporary),
            ]
        )
        print(
            "Render: tworzę lokalny proxy H.264 tylko z zatwierdzonych fragmentów "
            f"({metadata.get('codec')} {metadata.get('profile')} {metadata.get('pixelFormat')})."
        )
        run(command)
        temporary.replace(proxy)
        write_json(meta_path, expected_meta)
    else:
        print("Render: używam zapisanego kompatybilnego proxy H.264.")

    proxy_edits: list[dict[str, Any]] = []
    for edit in edits:
        mapped = dict(edit)
        mapped["sourceStartMs"] = int(edit["timelineStartMs"])
        mapped["sourceEndMs"] = int(edit["timelineEndMs"])
        proxy_edits.append(mapped)
    proxy_metadata = probe(proxy)
    return proxy, proxy_edits, proxy_metadata


def build_edits(ranges: list[dict[str, Any]], duration_ms: int) -> tuple[list[dict[str, Any]], int]:
    edits: list[dict[str, Any]] = []
    timeline_cursor = 0
    for index, item in enumerate(ranges):
        start = int(item["sourceStartMs"])
        end = int(item["sourceEndMs"])
        if start < 0 or end > duration_ms or end <= start:
            raise ValueError(f"Nieprawidłowy zakres źródłowy: {item}")
        clip_duration = end - start
        edits.append(
            {
                "id": f"clip-{index + 1:03d}",
                "sourceStartMs": start,
                "sourceEndMs": end,
                "timelineStartMs": timeline_cursor,
                "timelineEndMs": timeline_cursor + clip_duration,
                "reason": item.get("reason", "user-plan"),
                "scaleFrom": float(item.get("scaleFrom", item.get("scale", 1.0))),
                "scaleTo": float(item.get("scaleTo", item.get("scale", 1.0))),
                "objectPosition": str(item.get("objectPosition", "50% 50%")),
                "translate": str(item.get("translate", "0px 0px")),
            }
        )
        timeline_cursor += clip_duration
    return edits, timeline_cursor


def build_visual_beats(items: list[dict[str, Any]], timeline_duration: int) -> list[dict[str, Any]]:
    if not items:
        generator = random.Random(timeline_duration)
        beats: list[dict[str, Any]] = []
        cursor = 0
        previous_level = "wide"
        while cursor < timeline_duration:
            remaining = timeline_duration - cursor
            if remaining <= 6000:
                duration = remaining
            elif remaining < 9000:
                duration = remaining // 2
            else:
                duration = generator.randint(3000, 6000)
            if not beats:
                level = "wide"
            else:
                level = generator.choice(sorted(ZOOM_LEVELS - {previous_level}))
            beats.append(
                {
                    "timelineStartMs": cursor,
                    "timelineEndMs": cursor + duration,
                    "zoomLevel": level,
                    "transitionEffect": (
                        generator.choice(["blur", "rgb", "split"])
                        if level == "close"
                        else "smooth"
                    ),
                    "reason": "deterministic-fallback-3-6s",
                }
            )
            previous_level = level
            cursor += duration
        return beats
    if int(items[-1]["timelineEndMs"]) != timeline_duration:
        raise ValueError(
            "visualBeats musi pokrywać całą oś czasu; "
            f"ostatni koniec to {items[-1]['timelineEndMs']} ms zamiast {timeline_duration} ms."
        )
    return [
        {
            "timelineStartMs": int(item["timelineStartMs"]),
            "timelineEndMs": int(item["timelineEndMs"]),
            "zoomLevel": str(item["zoomLevel"]),
            "transitionEffect": str(item.get("transitionEffect", "smooth")),
            "reason": str(item.get("reason", "visual-rhythm")),
        }
        for item in items
    ]


def build_effect_cues(
    items: list[dict[str, Any]], timeline_duration: int
) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        start = int(item["timelineStartMs"])
        end = int(item["timelineEndMs"])
        if end > timeline_duration:
            raise ValueError(
                f"effectCues[{index + 1}] kończy się poza osią czasu ({end} > {timeline_duration})."
            )
        cue = {
            "id": str(item.get("id", f"effect-{index + 1:03d}")),
            "type": str(item["type"]),
            "timelineStartMs": start,
            "timelineEndMs": end,
            "intensity": float(item.get("intensity", 1.0)),
        }
        for key in ("direction", "value", "label", "accentColor", "placement"):
            if key in item:
                cue[key] = str(item[key])
        cues.append(cue)
    return cues


def build_sound_effects(
    items: list[dict[str, Any]], timeline_duration: int
) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        start = int(item["timelineStartMs"])
        if start >= timeline_duration:
            raise ValueError(
                f"soundEffects[{index + 1}] zaczyna się poza osią czasu ({start} >= {timeline_duration})."
            )
        effect_type = str(item["type"])
        filename = SOUND_EFFECT_FILES[effect_type]
        source = SFX_ASSETS / filename
        if not source.is_file():
            raise FileNotFoundError(f"Brak lokalnego efektu dźwiękowego: {source}")
        destination = PUBLIC_SFX / filename
        copy_or_link(source, destination)
        effects.append(
            {
                "id": str(item.get("id", f"sfx-{index + 1:03d}")),
                "type": effect_type,
                "publicFile": f"sfx/{filename}",
                **({"durationMs": item["durationMs"]} if "durationMs" in item else {}),
                "timelineStartMs": start,
                "volume": float(item.get("volume", SOUND_EFFECT_DEFAULT_VOLUMES[effect_type])),
                "speechDucking": float(item.get("speechDucking", 0.72)),
            }
        )
    return effects


def caption_page_break_indexes(words: list[dict[str, Any]]) -> set[int]:
    """Balance each punctuated phrase into pages containing two or three words."""
    breaks: set[int] = set()
    phrase_start = 0
    for index, word in enumerate(words):
        punctuation_break = bool(re.search(r"[.,!?;:…][\"'”’)]*$", word["text"]))
        if not punctuation_break and index != len(words) - 1:
            continue

        cursor = phrase_start
        remaining = index - phrase_start + 1
        while remaining > 0:
            if remaining <= 3:
                page_size = remaining
            elif remaining == 4:
                page_size = 2
            else:
                page_size = 3
            cursor += page_size
            breaks.add(cursor - 1)
            remaining -= page_size
        phrase_start = index + 1
    return breaks


def timeline_captions(words: list[dict[str, Any]], edits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Move word timestamps onto the edit timeline and mark caption pages.

    Baron3x3 pages contain at most three words. Sentence punctuation, commas,
    and edit boundaries always end the current page so a new phrase can never
    be attached to the previous one (for example: "i koncentracji." / "Dlatego").
    """
    captions: list[dict[str, Any]] = []
    for edit in edits:
        matching = [
            word
            for word in words
            if word["startMs"] >= edit["sourceStartMs"] and word["endMs"] <= edit["sourceEndMs"]
        ]
        page_break_indexes = caption_page_break_indexes(matching)
        for index, word in enumerate(matching):
            start_ms = edit["timelineStartMs"] + word["startMs"] - edit["sourceStartMs"]
            end_ms = edit["timelineStartMs"] + word["endMs"] - edit["sourceStartMs"]
            caption = {
                "text": " " + re.sub(r"[.,:;…]+$", "", str(word["text"])),
                "startMs": start_ms,
                "endMs": end_ms,
                "timestampMs": start_ms,
                "confidence": word["confidence"],
            }
            if index in page_break_indexes:
                caption["pageBreakAfter"] = True
            captions.append(caption)
    return captions


def build_overlays(
    items: list[dict[str, Any]],
    timeline_duration: int,
    asset_catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    overlays: list[dict[str, Any]] = []
    catalog_by_id = {
        str(item.get("id")): item
        for item in (asset_catalog or {}).get("items", [])
        if isinstance(item, dict) and item.get("id")
    }
    for index, item in enumerate(items):
        catalog_item: dict[str, Any] | None = None
        selected_id = item.get("assetId")
        if selected_id is not None:
            catalog_item = catalog_by_id.get(str(selected_id))
            if catalog_item is None:
                raise FileNotFoundError(f"Nie znaleziono assetId w katalogu: {selected_id}")
            if catalog_item.get("status") != "available":
                raise FileNotFoundError(f"Materiał z katalogu jest niedostępny: {selected_id}")
            asset = Path(str(catalog_item["absolutePath"])).resolve()
        elif item.get("assetFile"):
            asset = (ASSETS / str(item["assetFile"])).resolve()
            if ASSETS.resolve() not in asset.parents:
                raise ValueError(f"Przebitka musi znajdować się w assets/: {item['assetFile']}")
        else:
            raise ValueError(f"Przebitka {index + 1} wymaga assetId albo assetFile.")
        if not asset.is_file():
            raise FileNotFoundError(f"Nie znaleziono przebitki: {asset}")
        start = int(item["timelineStartMs"])
        end = int(item["timelineEndMs"])
        if start < 0 or end > timeline_duration or end <= start:
            raise ValueError(f"Nieprawidłowy czas przebitki: {item}")
        kind = str(catalog_item.get("kind")) if catalog_item else (
            "image" if asset.suffix.casefold() in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".tif", ".tiff"} else "video"
        )
        public_name = f"{selected_id}-{asset.name}" if selected_id else asset.name
        destination = PUBLIC_ASSETS / public_name
        copy_or_link(asset, destination)
        presentation = str(item.get("presentation", "full"))
        if presentation == "cutout" and (
            kind != "image" or asset.suffix.casefold() not in {".png", ".webp", ".avif"}
        ):
            raise ValueError(
                "Prezentacja cutout wymaga obrazu PNG, WebP albo AVIF z przezroczystym tłem."
            )

        secondary_id = item.get("secondaryAssetId")
        secondary_catalog_item: dict[str, Any] | None = None
        secondary_asset: Path | None = None
        if secondary_id:
            secondary_catalog_item = catalog_by_id.get(str(secondary_id))
            if secondary_catalog_item is None:
                raise FileNotFoundError(f"Nie znaleziono secondaryAssetId w katalogu: {secondary_id}")
            if secondary_catalog_item.get("status") != "available":
                raise FileNotFoundError(f"Drugi materiał jest niedostępny: {secondary_id}")
            secondary_asset = Path(str(secondary_catalog_item["absolutePath"])).resolve()
        elif item.get("secondaryAssetFile"):
            secondary_asset = (ASSETS / str(item["secondaryAssetFile"])).resolve()
            if ASSETS.resolve() not in secondary_asset.parents:
                raise ValueError("Druga przebitka musi znajdować się w assets/.")

        secondary_kind: str | None = None
        secondary_public_file: str | None = None
        if secondary_asset is not None:
            if not secondary_asset.is_file():
                raise FileNotFoundError(f"Nie znaleziono drugiej przebitki: {secondary_asset}")
            secondary_kind = (
                str(secondary_catalog_item.get("kind"))
                if secondary_catalog_item
                else (
                    "image"
                    if secondary_asset.suffix.casefold()
                    in {".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".tif", ".tiff"}
                    else "video"
                )
            )
            secondary_public_name = (
                f"{secondary_id}-{secondary_asset.name}" if secondary_id else secondary_asset.name
            )
            secondary_destination = PUBLIC_ASSETS / secondary_public_name
            copy_or_link(secondary_asset, secondary_destination)
            secondary_public_file = f"assets/{secondary_destination.name}"
        collage_assets: list[dict[str, Any]] = []
        for collage_id in item.get("collageAssetIds", []):
            collage_catalog_item = catalog_by_id.get(str(collage_id))
            if collage_catalog_item is None:
                raise FileNotFoundError(f"Nie znaleziono collageAssetId w katalogu: {collage_id}")
            if collage_catalog_item.get("status") != "available":
                raise FileNotFoundError(f"Zdjęcie kolażu jest niedostępne: {collage_id}")
            if collage_catalog_item.get("kind") != "image":
                raise ValueError(f"paper-collage obsługuje wyłącznie zdjęcia: {collage_id}")
            collage_asset = Path(str(collage_catalog_item["absolutePath"])).resolve()
            if not collage_asset.is_file():
                raise FileNotFoundError(f"Nie znaleziono zdjęcia kolażu: {collage_asset}")
            collage_public_name = f"{collage_id}-{collage_asset.name}"
            collage_destination = PUBLIC_ASSETS / collage_public_name
            copy_or_link(collage_asset, collage_destination)
            collage_assets.append(
                {
                    "assetId": str(collage_id),
                    "kind": "image",
                    "publicFile": f"assets/{collage_destination.name}",
                    "objectPosition": "50% 50%",
                }
            )
        overlays.append(
            {
                "id": f"overlay-{index + 1:03d}",
                "assetId": str(selected_id) if selected_id is not None else None,
                "kind": kind,
                "publicFile": f"assets/{destination.name}",
                "timelineStartMs": start,
                "timelineEndMs": end,
                "sourceStartMs": int(item.get("sourceStartMs", 0)),
                "objectPosition": str(item.get("objectPosition", "50% 50%")),
                "presentation": presentation,
                "motion": str(item.get("motion", "push-in")),
                "headline": str(item.get("headline", "")),
                "kicker": str(item.get("kicker", "")),
                "accentColor": str(item.get("accentColor", "#ff174f")),
                "fadeIn": bool(item.get("fadeIn", True)),
                "fadeOut": bool(item.get("fadeOut", True)),
                "secondaryAssetId": str(secondary_id) if secondary_id else None,
                "secondaryKind": secondary_kind,
                "secondaryPublicFile": secondary_public_file,
                "secondarySourceStartMs": int(item.get("secondarySourceStartMs", 0)),
                "secondaryObjectPosition": str(
                    item.get("secondaryObjectPosition", "50% 50%")
                ),
                "collageAssets": collage_assets,
                "sourceName": asset.name,
                "stockSourcePage": catalog_item.get("stock", {}).get("sourcePage")
                if catalog_item and catalog_item.get("stock")
                else None,
                "stockLicense": catalog_item.get("stock", {}).get("licenseName")
                if catalog_item and catalog_item.get("stock")
                else None,
                "stockAttribution": catalog_item.get("stock", {}).get("attribution")
                if catalog_item and catalog_item.get("stock")
                else None,
            }
        )
    return overlays


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="MP4 z folderu input/ albo pełna ścieżka")
    parser.add_argument("--language", default="pl")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--instructions", help="Dodatkowe instrukcje dla tego materiału")
    parser.add_argument("--instructions-file", type=Path)
    parser.add_argument("--force-transcribe", action="store_true")
    parser.add_argument("--draft-render", action="store_true", help="Techniczny render całego pliku")
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()

    source_arg = Path(args.source).expanduser()
    source = source_arg if source_arg.is_absolute() else ROOT / "input" / source_arg
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Nie znaleziono pliku: {source}")
    if source.suffix.lower() != ".mp4":
        raise ValueError("Pipeline przyjmuje obecnie pliki MP4.")
    if not WHISPER_PYTHON.is_file():
        raise RuntimeError("Brak lokalnego MLX Whisper. Uruchom instalację z README.md.")
    if args.instructions and args.instructions_file:
        raise ValueError("Użyj --instructions albo --instructions-file, nie obu naraz.")

    asset_catalog = refresh_catalog(ROOT)
    available_assets = sum(
        item.get("status") == "available" for item in asset_catalog.get("items", [])
    )
    print(f"Katalog materiałów: odświeżony ({available_assets} dostępnych plików).")

    instructions_text = args.instructions
    if args.instructions_file:
        instructions_text = args.instructions_file.expanduser().read_text(encoding="utf-8")

    metadata = probe(source)
    job_name = source.stem
    job_dir = ANALYSIS / job_name
    job_dir.mkdir(parents=True, exist_ok=True)
    whisper_input = prepare_whisper_input(source, job_dir, args.force_transcribe)
    raw = transcribe(whisper_input, job_dir, args.model, args.language, args.force_transcribe)
    plan_path, plan = ensure_plan(job_name, instructions_text)
    transcript, words = normalize_transcript(
        raw,
        source,
        load_replacements(job_name),
        plan.get("wordTimingCorrections", []),
    )
    write_json(job_dir / "transcript.json", transcript)
    write_transcript_compact(job_dir / "transcript-compact.md", transcript)

    validate_plan(plan_path, plan)
    ranges = plan.get("sourceRanges", [])
    if not ranges and args.draft_render:
        ranges = [
            {
                "sourceStartMs": 0,
                "sourceEndMs": metadata["durationMs"],
                "reason": "technical-draft-only",
            }
        ]
    if not ranges:
        print(f"Plan montażu wymaga uzupełnienia: {plan_path}")
        print("Pipeline nie wyrenderował ponownie pełnego, niepociętego materiału.")
        return
    if plan.get("status") != "ready" and not args.draft_render:
        print(f"Plan nie ma statusu ready: {plan_path}")
        print("Najpierw sprawdź cięcia, korektę napisów i instrukcje użytkownika.")
        return

    validate_word_boundaries(plan_path, ranges, words)

    # Zastosuj reguły układania scen (hook-lock + bridge small gaps) na dzień dobry.
    from timeline_rules import apply_timeline_rules

    hook_end_ms = int(plan.get("hookLockUntilMs", 0))
    plan_overlays = plan.get("overlays", [])
    planned_overlays = (
        apply_timeline_rules(plan_overlays, hook_end_ms=hook_end_ms)
        if plan_overlays
        else []
    )

    edits, timeline_duration = build_edits(ranges, metadata["durationMs"])
    captions = timeline_captions(words, edits)
    visual_beats = build_visual_beats(plan.get("visualBeats", []), timeline_duration)
    overlays = build_overlays(planned_overlays, timeline_duration, asset_catalog)
    effect_cues = build_effect_cues(plan.get("effectCues", []), timeline_duration)
    sound_effects = build_sound_effects(plan.get("soundEffects", []), timeline_duration)
    color_metadata = read_source_color_metadata(source)
    color_pipeline = choose_color_pipeline(
        color_metadata, str(plan.get("sourceColorProfile", "auto"))
    )
    write_json(job_dir / "source-color.json", {**color_metadata, "decision": color_pipeline})
    render_source, render_edits, render_metadata = prepare_render_source(
        source, job_dir, edits, metadata, color_pipeline
    )
    public_file = prepare_public_media(render_source)
    job = {
        "version": 2,
        "source": {
            "file": source.name,
            "publicFile": public_file,
            "renderProxy": render_source != source,
            "original": metadata,
            "colorPipeline": color_pipeline,
            **render_metadata,
        },
        "assetCatalog": {
            "file": "assets/MATERIALY.md",
            "indexFile": "analysis/assets/catalog.json",
            "generatedAt": asset_catalog.get("generatedAt"),
            "availableCount": available_assets,
        },
        "timeline": {
            "fps": FPS,
            "width": WIDTH,
            "height": HEIGHT,
            "durationMs": timeline_duration,
            "durationInFrames": max(1, round((timeline_duration / 1000) * FPS)),
        },
        "captionStyle": plan.get("captionStyle", "green-word"),
        "colorGrade": plan.get(
            "colorGrade",
            {"contrast": 1.0, "saturation": 1.0, "brightness": 1.0, "sepia": 0.0},
        ),
        "instructions": plan.get("instructions", ""),
        "edits": render_edits,
        "visualBeats": visual_beats,
        "overlays": overlays,
        "effectCues": effect_cues,
        "soundEffects": sound_effects,
        "captions": captions,
    }
    write_json(job_dir / "captions.json", captions)
    write_json(job_dir / "edl.json", job)
    write_json(JOB_FILE, job)

    print(f"Transkrypcja: {job_dir / 'transcript.json'}")
    print(f"Plan: {plan_path}")
    print(f"EDL: {job_dir / 'edl.json'}")
    if not args.no_render:
        suffix = "draft" if args.draft_render else "render"
        output = ROOT / "output" / f"{job_name}-{suffix}.mp4"
        render_target = (
            output
            if args.draft_render
            else ROOT / "output" / f"{job_name}-preview-check.mp4"
        )
        run(
            [
                "npm",
                "exec",
                "--",
                "remotion",
                "render",
                "remotion/src/index.ts",
                "BaronReel",
                str(render_target),
                "--codec=h264",
                "--crf=18",
                "--pixel-format=yuv420p",
                "--audio-bitrate=256k",
                "--concurrency=4",
                "--overwrite",
            ]
        )
        if not args.draft_render:
            run(
                [
                    str(WHISPER_PYTHON),
                    "scripts/attention_map.py",
                    source.name,
                    "--render",
                    str(render_target),
                ]
            )
            run(
                [
                    str(WHISPER_PYTHON),
                    "scripts/preview_qa.py",
                    source.name,
                    "--render",
                    str(render_target),
                ]
            )
            render_target.replace(output)
        print(f"Render: {output}")


if __name__ == "__main__":
    main()
