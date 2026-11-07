#!/usr/bin/env python3
"""Create a local, review-first B-roll proposal from transcript and asset notes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .asset_catalog import refresh_catalog
else:
    from asset_catalog import refresh_catalog


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
JOBS = ROOT / "instructions" / "jobs"
PLANNER_ID = "baron3x3-broll-v1"
MIN_BEAT_MS = 1_400
MAX_BEAT_MS = 5_500
MAX_OVERLAY_MS = 4_500
MIN_SELECTION_SCORE = 10

STOPWORDS = {
    "3x3",
    "akcja",
    "aren",
    "bardzo",
    "boisko",
    "dobra",
    "dobry",
    "druzyn",
    "fiba",
    "film",
    "gra",
    "jest",
    "koszyk",
    "materi",
    "mecz",
    "mocn",
    "pionow",
    "polska",
    "przeci",
    "reprez",
    "turniej",
    "ujecie",
    "wideo",
    "zawod",
    "zespol",
}

FIELD_WEIGHTS = {
    "osoby": 12,
    "zespol": 9,
    "rywal": 9,
    "miejsce": 7,
    "wydarzenie": 6,
    "tagi": 4,
    "zastosowanie": 3,
    "opis": 2,
}

ACTION_QUERY_ROOTS = {
    "akcja",
    "akcji",
    "boisk",
    "mecz",
    "obrec",
    "obron",
    "punkt",
    "punkto",
    "rzut",
    "wsad",
    "zbiore",
}
ACTION_ASSET_ROOTS = ACTION_QUERY_ROOTS | {
    "atlety",
    "dunk",
    "fizycz",
    "kontes",
    "wykonc",
}

FALLBACK_EFFECT_TYPES = {"kinetic-text", "audio-waveform"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize(value: str) -> str:
    value = value.casefold().replace("ł", "l")
    value = value.translate(str.maketrans("ąćęńóśźż", "acenoszz"))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def token_root(token: str) -> str:
    """Return a conservative root that catches common Polish case endings."""
    token = normalize(token)
    if token.startswith("koleg"):
        return "koleg"
    if token.startswith("leszn"):
        return "leszn"
    if len(token) >= 5:
        return token[:6]
    return token


def meaningful_roots(value: str) -> set[str]:
    roots = {token_root(token) for token in normalize(value).split()}
    stopword_roots = {token_root(stop) for stop in STOPWORDS}
    return {
        root
        for root in roots
        if len(root) >= 4
        and root not in stopword_roots
    }


def proper_noun_roots(value: str) -> set[str]:
    """Find likely named entities without pretending to be a full Polish NER model."""
    tokens = re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9]+", value)
    return {
        token_root(token)
        for index, token in enumerate(tokens)
        if index > 0 and token[:1].isupper() and len(token_root(token)) >= 4
    }


def parse_note_fields(notes: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in notes.splitlines():
        match = re.match(r"^-\s+([^:]+):\s*(.+)$", line.strip())
        if match:
            fields[normalize(match.group(1))] = match.group(2).strip()
    return fields


def timeline_words(transcript: dict[str, Any], ranges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_words = [
        word
        for segment in transcript.get("segments", [])
        for word in segment.get("words", [])
    ]
    result: list[dict[str, Any]] = []
    cursor = 0
    for range_index, source_range in enumerate(ranges):
        source_start = int(source_range["sourceStartMs"])
        source_end = int(source_range["sourceEndMs"])
        selected = [
            word
            for word in source_words
            if int(word["startMs"]) >= source_start and int(word["endMs"]) <= source_end
        ]
        for word in selected:
            result.append(
                {
                    "text": str(word["text"]),
                    "timelineStartMs": cursor + int(word["startMs"]) - source_start,
                    "timelineEndMs": cursor + int(word["endMs"]) - source_start,
                    "rangeIndex": range_index,
                }
            )
        cursor += source_end - source_start
    return result


def split_beats(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split selected narration on thought boundaries without cutting words."""
    if not words:
        return []
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        if current and word["rangeIndex"] != current[-1]["rangeIndex"]:
            groups.append(current)
            current = []
        current.append(word)
        duration = int(current[-1]["timelineEndMs"]) - int(current[0]["timelineStartMs"])
        sentence_end = bool(re.search(r"[.!?][\"'”’)]*$", str(word["text"])))
        soft_end = bool(re.search(r"[,;:][\"'”’)]*$", str(word["text"])))
        if sentence_end or (duration >= MIN_BEAT_MS and soft_end) or duration >= MAX_BEAT_MS:
            groups.append(current)
            current = []
    if current:
        groups.append(current)

    beats: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        if not group:
            continue
        beats.append(
            {
                "id": f"beat-{index:03d}",
                "text": " ".join(str(word["text"]) for word in group),
                "timelineStartMs": int(group[0]["timelineStartMs"]),
                "timelineEndMs": int(group[-1]["timelineEndMs"]),
            }
        )
    return beats


def split_beats_at_reveal(
    beats: list[dict[str, Any]], words: list[dict[str, Any]], reveal_ms: int | None
) -> list[dict[str, Any]]:
    """Keep the subject hidden until their name is actually spoken."""
    if reveal_ms is None:
        return beats
    result: list[dict[str, Any]] = []
    for beat in beats:
        start = int(beat["timelineStartMs"])
        end = int(beat["timelineEndMs"])
        if not start < reveal_ms < end:
            result.append(dict(beat))
            continue
        beat_words = [
            word
            for word in words
            if int(word["timelineStartMs"]) >= start
            and int(word["timelineEndMs"]) <= end
        ]
        for group in (
            [word for word in beat_words if int(word["timelineEndMs"]) <= reveal_ms],
            [word for word in beat_words if int(word["timelineStartMs"]) >= reveal_ms],
        ):
            if group:
                result.append(
                    {
                        "text": " ".join(str(word["text"]) for word in group),
                        "timelineStartMs": int(group[0]["timelineStartMs"]),
                        "timelineEndMs": int(group[-1]["timelineEndMs"]),
                    }
                )
    for index, beat in enumerate(result, start=1):
        beat["id"] = f"beat-{index:03d}"
    return result


def field_matches(text: str, fields: dict[str, str]) -> tuple[int, list[dict[str, Any]]]:
    query_roots = meaningful_roots(text)
    score = 0
    evidence: list[dict[str, Any]] = []
    for field, weight in FIELD_WEIGHTS.items():
        value = fields.get(field)
        if not value:
            continue
        matched = sorted(query_roots & meaningful_roots(value))
        if not matched:
            continue
        contribution = weight + max(0, len(matched) - 1) * max(1, weight // 3)
        score += contribution
        evidence.append(
            {
                "field": field,
                "value": value,
                "matchedRoots": matched,
                "score": contribution,
            }
        )
    return score, evidence


def candidate_relevance(
    text: str,
    fields: dict[str, str],
    evidence: list[dict[str, Any]],
    story_subject_roots: set[str] | None = None,
    before_reveal: bool = False,
) -> dict[str, Any]:
    """Separate a real scene/action match from a match on the subject's name."""
    identity_roots = meaningful_roots(fields.get("osoby", ""))
    descriptive_fields = {"tagi", "opis", "zastosowanie"}
    semantic_roots = {
        root
        for item in evidence
        if item["field"] != "osoby"
        for root in item["matchedRoots"]
        if root not in identity_roots
    }
    descriptive_field_count = len(
        {
            item["field"]
            for item in evidence
            if item["field"] in descriptive_fields
            and any(root not in identity_roots for root in item["matchedRoots"])
        }
    )
    semantic_score = sum(
        int(item["score"])
        for item in evidence
        if item["field"] != "osoby"
        and any(root not in identity_roots for root in item["matchedRoots"])
    )
    negative_roots = meaningful_roots(fields.get("nie uzywaj gdy", ""))
    query_roots = meaningful_roots(text)
    raw_negative_matches = query_roots & negative_roots
    generic_negative_roots = {"akcja", "akcji", "zdani", "wypow", "mater", "konkr"}
    negative_matches = sorted(
        raw_negative_matches
        if raw_negative_matches - generic_negative_roots
        else (raw_negative_matches if len(raw_negative_matches) >= 2 else set())
    )

    person_roots = meaningful_roots(fields.get("osoby", ""))
    subject_match = bool(story_subject_roots and story_subject_roots & person_roots)
    explicit_person_match = bool(
        any(item["field"] == "osoby" for item in evidence)
    )
    subject_conflict = bool(
        story_subject_roots
        and person_roots
        and not (story_subject_roots & person_roots)
        and not explicit_person_match
    )
    premature_reveal = bool(before_reveal and subject_match)

    named_roots = proper_noun_roots(text) - person_roots
    asset_context_roots = meaningful_roots(
        " ".join(fields.get(name, "") for name in ("miejsce", "wydarzenie", "zespol", "rywal"))
    )
    context_mismatch_roots = sorted(
        named_roots - asset_context_roots
        if named_roots and (fields.get("miejsce") or fields.get("wydarzenie"))
        else set()
    )

    role_text = " ".join(
        fields.get(name, "") for name in ("tagi", "zastosowanie", "opis")
    )
    role_roots = meaningful_roots(role_text)
    intro_suitability = len(role_roots & {"portre", "przeds", "tozsam"})
    evidence_fields = {item["field"] for item in evidence}
    match_tier = (
        3
        if subject_match and not before_reveal
        else 2
        if "zespol" in evidence_fields
        else 1
        if "miejsce" in evidence_fields
        else 0
    )
    return {
        "semanticRoots": sorted(semantic_roots),
        "semanticScore": semantic_score,
        "descriptiveFieldCount": descriptive_field_count,
        "negativeMatches": negative_matches,
        "subjectConflict": subject_conflict,
        "subjectMatch": subject_match,
        "prematureReveal": premature_reveal,
        "contextMismatchRoots": context_mismatch_roots,
        "introSuitability": intro_suitability,
        "matchTier": match_tier,
    }


def selection_is_safe(
    score: int,
    evidence: list[dict[str, Any]],
    is_reviewed_stock: bool = False,
    relevance: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    relevance = relevance or {}
    if relevance.get("prematureReveal"):
        return False, "bohater pozostaje ukryty do chwili wypowiedzenia imienia i nazwiska"
    if relevance.get("subjectConflict"):
        return False, "materiał pokazuje inną osobę niż bohater prowadzonej historii"
    if relevance.get("contextMismatchRoots") and not relevance.get("subjectMatch"):
        return False, "materiał pochodzi z innego miejsca lub wydarzenia niż zdanie"
    if relevance.get("negativeMatches"):
        return False, "opis materiału jawnie wyklucza ten kontekst"
    fields = {item["field"] for item in evidence}
    matched_roots = {root for item in evidence for root in item["matchedRoots"]}
    if is_reviewed_stock and matched_roots and score >= 7:
        return True, "zgodność opisu zatwierdzonego stocku"
    if "osoby" in fields and score >= MIN_SELECTION_SCORE:
        return True, "zgodność osoby"
    contextual_fields = fields & {"zespol", "rywal", "miejsce", "wydarzenie"}
    descriptive_fields = fields & {"tagi", "opis", "zastosowanie"}
    contextual_roots = {
        root
        for item in evidence
        if item["field"] in contextual_fields
        for root in item["matchedRoots"]
    }
    descriptive_roots = {
        root
        for item in evidence
        if item["field"] in descriptive_fields
        for root in item["matchedRoots"]
    }
    independent_description = descriptive_roots - contextual_roots
    if (
        relevance.get("descriptiveFieldCount", 0) >= 2
        and relevance.get("semanticScore", 0) >= 7
    ):
        return True, "zgodność konkretnej czynności lub funkcji materiału"
    if contextual_fields and independent_description and score >= MIN_SELECTION_SCORE:
        return True, "zgodność kontekstu i treści ujęcia"
    if len(contextual_fields) >= 2 and score >= MIN_SELECTION_SCORE:
        return True, "zgodność co najmniej dwóch elementów kontekstu"
    return False, "za mało niezależnych dowodów; lepszy brak przebitki niż luźne dopasowanie"


TIME_RANGE_PATTERN = re.compile(
    r"(?P<start>\d{1,2}:\d{2})(?:\.\d+)?\s*[–-]\s*(?P<end>\d{1,2}:\d{2})(?:\.\d+)?"
    r"(?:\s*[—-]\s*(?P<label>[^;]+))?"
)


def timestamp_ms(value: str) -> int:
    minutes, seconds = value.split(":", 1)
    return (int(minutes) * 60 + int(seconds)) * 1000


def best_source_ranges(fields: dict[str, str], duration_ms: int | None) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for match in TIME_RANGE_PATTERN.finditer(fields.get("najlepsze fragmenty", "")):
        start = timestamp_ms(match.group("start"))
        end = timestamp_ms(match.group("end"))
        if duration_ms is not None:
            end = min(end, duration_ms)
        if end > start:
            ranges.append(
                {
                    "startMs": start,
                    "endMs": end,
                    "label": (match.group("label") or "").strip(),
                }
            )
    if not ranges and duration_ms:
        ranges.append({"startMs": 0, "endMs": duration_ms, "label": ""})
    return ranges


def choose_source_window(
    asset: dict[str, Any], fields: dict[str, str], beat_text: str, requested_ms: int
) -> tuple[int, int]:
    # Catalogs expose still images as one 40 ms probe frame. A photo is not a
    # 40 ms clip: it can remain on the edited timeline for the whole beat.
    if asset.get("kind") == "image":
        return 0, requested_ms
    ranges = best_source_ranges(fields, asset.get("durationMs"))
    if not ranges:
        return 0, requested_ms
    beat_roots = meaningful_roots(beat_text)
    selected = max(
        ranges,
        key=lambda item: (
            len(beat_roots & meaningful_roots(str(item["label"]))),
            int(item["endMs"]) - int(item["startMs"]),
        ),
    )
    available_ms = int(selected["endMs"]) - int(selected["startMs"])
    return int(selected["startMs"]), min(requested_ms, available_ms)


def intervals_overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def visual_fallback_for_beat(
    beat: dict[str, Any], reveal_ms: int | None
) -> dict[str, Any]:
    """Choose a restrained fallback only when its meaning is explicit."""
    start = int(beat["timelineStartMs"])
    end = int(beat["timelineEndMs"])
    text = str(beat["text"])
    roots = meaningful_roots(text)
    if beat.get("stockSuggestion"):
        city = str(beat["stockSuggestion"])
        return {
            "beatId": beat["id"],
            "type": "stock-needed",
            "timelineStartMs": start,
            "timelineEndMs": end,
            "query": f"{city} France city establishing shot",
            "reason": f"narrator wskazuje konkretne miasto; potrzebny stock {city}, nie losowa dekoracja",
            "confidence": "high",
            "renderable": False,
        }
    if roots & {"punkt", "punkto"}:
        return {
            "beatId": beat["id"],
            "type": "kinetic-text",
            "timelineStartMs": start,
            "timelineEndMs": end,
            "label": "LIDER",
            "value": "TO NIE TYLKO PUNKTY",
            "accentColor": "#ff174f",
            "reason": "animacja wizualizuje kontrast tezy bez ujawniania bohatera",
            "confidence": "high",
            "renderable": True,
        }
    if roots & {"transm", "slycha", "glos", "komuni"}:
        return {
            "beatId": beat["id"],
            "type": "audio-waveform",
            "timelineStartMs": start,
            "timelineEndMs": end,
            "label": "GŁOS Z BOISKA",
            "accentColor": "#ff174f",
            "reason": "fala dźwiękowa bezpośrednio ilustruje słyszalny głos lub transmisję",
            "confidence": "high",
            "renderable": True,
        }
    if reveal_ms is not None and start < reveal_ms:
        return {
            "beatId": beat["id"],
            "type": "speaker-hold",
            "timelineStartMs": start,
            "timelineEndMs": end,
            "direction": "utrzymaj prowadzącego i istniejący spokojny zoom; nie zdradzaj bohatera",
            "reason": "kontrolowane budowanie ciekawości jest mocniejsze niż generyczny stock",
            "confidence": "high",
            "renderable": False,
        }
    return {
        "beatId": beat["id"],
        "type": "intentional-hold",
        "timelineStartMs": start,
        "timelineEndMs": end,
        "direction": "pozostaw aktualny obraz bez dodatkowej warstwy",
        "reason": "brak wystarczająco konkretnej metafory; efekt byłby dekoracyjny",
        "confidence": "high",
        "renderable": False,
    }


def plan_signature(plan: dict[str, Any]) -> str:
    relevant = {
        "sourceRanges": plan.get("sourceRanges", []),
        "instructions": plan.get("instructions", ""),
    }
    encoded = json.dumps(relevant, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_report(
    job_name: str,
    transcript: dict[str, Any],
    plan: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    words = timeline_words(transcript, plan.get("sourceRanges", []))
    available_assets = [
        item
        for item in catalog.get("items", [])
        if item.get("status") == "available" and item.get("userNotes")
    ]
    beats = split_beats(words)
    narration = " ".join(str(beat["text"]) for beat in beats)
    narration_roots = meaningful_roots(narration)
    story_subject_roots: set[str] = set()
    for asset in available_assets:
        fields = parse_note_fields(str(asset.get("userNotes", "")))
        people = meaningful_roots(fields.get("osoby", ""))
        if people and len(people & narration_roots) >= 2:
            story_subject_roots.update(people & narration_roots)
    reveal_ms = next(
        (
            int(word["timelineStartMs"])
            for word in words
            if token_root(str(word["text"])) in story_subject_roots
        ),
        None,
    )
    beats = split_beats_at_reveal(beats, words, reveal_ms)
    proposed: list[dict[str, Any]] = []
    covered_ms = 0
    usage_counts: dict[str, int] = {}
    occupied = [
        (int(item["timelineStartMs"]), int(item["timelineEndMs"]))
        for item in plan.get("overlays", [])
        if isinstance(item, dict)
        and isinstance(item.get("timelineStartMs"), int)
        and isinstance(item.get("timelineEndMs"), int)
    ]

    for beat in beats:
        candidates: list[dict[str, Any]] = []
        for asset in available_assets:
            fields = parse_note_fields(str(asset.get("userNotes", "")))
            score, evidence = field_matches(beat["text"], fields)
            before_reveal = bool(
                reveal_ms is not None and int(beat["timelineStartMs"]) < reveal_ms
            )
            person_roots = meaningful_roots(fields.get("osoby", ""))
            subject_match = bool(story_subject_roots & person_roots)
            query_is_action = bool(meaningful_roots(beat["text"]) & ACTION_QUERY_ROOTS)
            asset_is_action = bool(
                meaningful_roots(
                    " ".join(
                        fields.get(name, "")
                        for name in ("opis", "tagi", "zastosowanie")
                    )
                )
                & ACTION_ASSET_ROOTS
            )
            if score <= 0 and subject_match and not before_reveal and query_is_action and asset_is_action:
                score = MIN_SELECTION_SCORE
                evidence = [
                    {
                        "field": "osoby",
                        "value": fields.get("osoby", ""),
                        "matchedRoots": sorted(story_subject_roots & person_roots),
                        "score": MIN_SELECTION_SCORE,
                        "inheritedContext": True,
                    }
                ]
            if score <= 0:
                continue
            relevance = candidate_relevance(
                beat["text"],
                fields,
                evidence,
                story_subject_roots,
                before_reveal,
            )
            safe, decision_reason = selection_is_safe(
                score, evidence, bool(asset.get("stock")), relevance
            )
            candidates.append(
                {
                    "assetId": asset["id"],
                    "name": asset["name"],
                    "kind": asset["kind"],
                    "score": score,
                    "safe": safe,
                    "decisionReason": decision_reason,
                    "evidence": evidence,
                    **relevance,
                    "stock": {
                        "sourcePage": asset.get("stock", {}).get("sourcePage"),
                        "licenseName": asset.get("stock", {}).get("licenseName"),
                        "licenseUrl": asset.get("stock", {}).get("licenseUrl"),
                        "attribution": asset.get("stock", {}).get("attribution"),
                    }
                    if asset.get("stock")
                    else None,
                }
            )
        candidates.sort(
            key=lambda item: (
                not item["safe"],
                bool(item["subjectConflict"]),
                bool(item["contextMismatchRoots"]),
                bool(item["negativeMatches"]),
                -int(item["matchTier"]),
                -int(item["semanticScore"]),
                -int(item["descriptiveFieldCount"]),
                usage_counts.get(str(item["assetId"]), 0),
                -int(item["introSuitability"]),
                -int(item["score"]),
                item["assetId"],
            )
        )
        beat["candidates"] = candidates[:3]
        beat_duration = int(beat["timelineEndMs"]) - int(beat["timelineStartMs"])
        selected = next((candidate for candidate in candidates if candidate["safe"]), None)
        conflicts_with_existing = any(
            intervals_overlap(
                int(beat["timelineStartMs"]),
                int(beat["timelineEndMs"]),
                start,
                end,
            )
            for start, end in occupied
        )
        reveal_beat = bool(
            reveal_ms is not None and int(beat["timelineStartMs"]) == reveal_ms
        )
        duration_is_usable = beat_duration >= MIN_BEAT_MS or (
            reveal_beat and beat_duration >= 800
        )
        if selected and duration_is_usable and not conflicts_with_existing:
            asset = next(item for item in available_assets if item["id"] == selected["assetId"])
            fields = parse_note_fields(str(asset.get("userNotes", "")))
            requested_duration = min(beat_duration, MAX_OVERLAY_MS)
            source_start, overlay_duration = choose_source_window(
                asset, fields, beat["text"], requested_duration
            )
            overlay = {
                "assetId": selected["assetId"],
                "timelineStartMs": int(beat["timelineStartMs"]),
                "timelineEndMs": int(beat["timelineStartMs"]) + overlay_duration,
                "sourceStartMs": source_start,
                "objectPosition": "50% 50%",
                "presentation": "editorial" if asset.get("kind") == "image" else "full",
                "motion": "push-in" if asset.get("kind") == "image" else "still",
                "reason": (
                    "ciągłość ujawnionego bohatera; materiał ilustracyjny, nie dowód miejsca ani konkretnej akcji: "
                    + beat["text"]
                    if any(item.get("inheritedContext") for item in selected["evidence"])
                    else f"{selected['decisionReason']}: {beat['text']}"
                ),
                "generatedBy": PLANNER_ID,
                "beatId": beat["id"],
            }
            if asset.get("stock"):
                overlay["stockSourcePage"] = asset["stock"].get("sourcePage")
                overlay["stockLicense"] = asset["stock"].get("licenseName")
                overlay["stockAttribution"] = asset["stock"].get("attribution")
            if (
                proposed
                and proposed[-1]["assetId"] == overlay["assetId"]
                and int(overlay["timelineStartMs"]) - int(proposed[-1]["timelineEndMs"]) <= 500
            ):
                previous = proposed[-1]
                combined_end = min(
                    int(previous["timelineStartMs"]) + MAX_OVERLAY_MS,
                    int(overlay["timelineEndMs"]),
                )
                if combined_end > int(previous["timelineEndMs"]):
                    extension = combined_end - int(previous["timelineEndMs"])
                    previous["timelineEndMs"] = combined_end
                    previous["reason"] += f"; kontynuacja: {beat['text']}"
                    covered_ms += extension
                    beat["selection"] = previous
                    beat["decision"] = "kontynuacja tej samej przebitki bez ponownego wejścia"
                    continue
            beat["selection"] = overlay
            proposed.append(overlay)
            covered_ms += overlay_duration
            usage_counts[str(selected["assetId"])] = (
                usage_counts.get(str(selected["assetId"]), 0) + 1
            )
        else:
            beat["selection"] = None
            if conflicts_with_existing:
                beat["decision"] = "fragment jest już przykryty ręcznie ustawioną przebitką"
            else:
                beat["decision"] = (
                    candidates[0]["decisionReason"]
                    if candidates
                    else "brak powiązanego materiału w katalogu"
                )
            location_match = re.search(
                r"\b(?:w|we)\s+([A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż-]+)",
                str(beat["text"]),
            )
            if location_match:
                beat["stockSuggestion"] = location_match.group(1)

    timeline_duration = sum(
        int(item["sourceEndMs"]) - int(item["sourceStartMs"])
        for item in plan.get("sourceRanges", [])
    )
    fallbacks = [
        visual_fallback_for_beat(beat, reveal_ms)
        for beat in beats
        if beat.get("selection") is None
    ]
    proposed_effect_cues = [
        {
            "id": f"fallback-{item['beatId']}",
            "type": item["type"],
            "timelineStartMs": item["timelineStartMs"],
            "timelineEndMs": item["timelineEndMs"],
            "intensity": 0.9,
            "label": item.get("label", ""),
            "value": item.get("value", ""),
            "accentColor": item.get("accentColor", "#ff174f"),
            "reason": item["reason"],
            "generatedBy": PLANNER_ID,
        }
        for item in fallbacks
        if item["type"] in FALLBACK_EFFECT_TYPES and item["renderable"]
    ]
    return {
        "version": 1,
        "planner": PLANNER_ID,
        "status": "needs-review",
        "generatedAt": utc_now(),
        "job": job_name,
        "costUsd": 0,
        "planSignature": plan_signature(plan),
        "policy": {
            "reviewRequiredBeforeApply": True,
            "minimumSelectionScore": MIN_SELECTION_SCORE,
            "maximumOverlayMs": MAX_OVERLAY_MS,
            "rule": "Brak B-rollu jest lepszy niż luźno powiązany materiał.",
            "subjectRevealMs": reveal_ms,
            "priority": ["bohater", "zespol", "miasto"],
        },
        "coverage": {
            "timelineDurationMs": timeline_duration,
            "coveredDurationMs": covered_ms,
            "coveragePercent": round((covered_ms / timeline_duration) * 100, 1)
            if timeline_duration
            else 0,
            "beats": len(beats),
            "proposedOverlays": len(proposed),
            "uncoveredBeats": sum(beat["selection"] is None for beat in beats),
            "fallbackDecisions": len(fallbacks),
            "renderableFallbacks": len(proposed_effect_cues),
            "missingStock": sum(item["type"] == "stock-needed" for item in fallbacks),
        },
        "proposedOverlays": proposed,
        "visualFallbacks": fallbacks,
        "proposedEffectCues": proposed_effect_cues,
        "beats": beats,
    }


def render_markdown(report: dict[str, Any]) -> str:
    coverage = report["coverage"]
    lines = [
        f"# Plan przebitek — {report['job']}",
        "",
        f"Status: **{report['status']}** · koszt API: **0 USD**",
        "",
        (
            f"Pokrycie: **{coverage['coveragePercent']}%** "
            f"({coverage['proposedOverlays']} propozycji na {coverage['beats']} fragmentów narracji)."
        ),
        "",
        "Pipeline nie zmienił planu montażu. Przebitki zostaną wpisane dopiero po jawnej akceptacji.",
        "",
        "Pojedyncze zdjęcia i wideo aren są zwykłymi przebitkami. BaronMattePhotos stosuj tylko do zaplanowanej wspólnej sekwencji co najmniej dwóch fotografii.",
        "",
        "## Propozycje",
        "",
    ]
    if not report["proposedOverlays"]:
        lines.extend(["Brak wystarczająco pewnych propozycji.", ""])
    for beat in report["beats"]:
        lines.append(
            f"### {beat['id']} · {beat['timelineStartMs'] / 1000:.2f}–{beat['timelineEndMs'] / 1000:.2f} s"
        )
        lines.append("")
        lines.append(f"> {beat['text']}")
        lines.append("")
        selection = beat.get("selection")
        if selection:
            candidate = next(
                item for item in beat["candidates"] if item["assetId"] == selection["assetId"]
            )
            label = (
                "Kontynuacja bez drugiego wejścia"
                if beat.get("decision") == "kontynuacja tej samej przebitki bez ponownego wejścia"
                else "Propozycja"
            )
            lines.append(f"- {label}: `{selection['assetId']}` — `{candidate['name']}`")
            lines.append(
                f"- Oś rolki: {selection['timelineStartMs'] / 1000:.2f}–{selection['timelineEndMs'] / 1000:.2f} s"
            )
            lines.append(f"- Start materiału: {selection['sourceStartMs'] / 1000:.2f} s")
            lines.append(f"- Powód: {selection['reason']}")
            if candidate.get("stock"):
                stock = candidate["stock"]
                lines.append(
                    f"- Licencja: [{stock['licenseName']}]({stock['licenseUrl']})"
                )
                lines.append(f"- Źródło: {stock['sourcePage']}")
                lines.append(f"- Podpis: {stock['attribution']}")
        else:
            lines.append(f"- Bez przebitki: {beat.get('decision', 'brak dopasowania')}")
            if beat.get("stockSuggestion"):
                lines.append(
                    f"- Brakujący materiał: stock miasta `{beat['stockSuggestion']}`"
                )
            if beat.get("candidates"):
                candidate = beat["candidates"][0]
                lines.append(
                    f"- Najbliższy kandydat: `{candidate['assetId']}` ({candidate['score']} pkt), ale nie został wybrany"
                )
        lines.append("")
    lines.extend(["## Przemyślane zastępstwa braków", ""])
    fallbacks = report.get("visualFallbacks", [])
    if not fallbacks:
        lines.extend(["Każdy fragment narracji ma bezpieczną propozycję materiału.", ""])
    for item in fallbacks:
        lines.append(
            f"- {item['timelineStartMs'] / 1000:.2f}–{item['timelineEndMs'] / 1000:.2f} s "
            f"· `{item['type']}` — {item['reason']}"
        )
        if item.get("query"):
            lines.append(f"  - Zapytanie stockowe: `{item['query']}`")
        if item.get("label") or item.get("value"):
            lines.append(
                f"  - Treść: `{item.get('label', '')}` / `{item.get('value', '')}`"
            )
    lines.append("")
    lines.extend(
        [
            "## Akceptacja",
            "",
            f"Po obejrzeniu raportu: `npm run broll:apply -- {report['job']}.mp4 --approved`",
            "",
            "Ta komenda wymaga jawnej flagi akceptacji i nie uruchamia renderu.",
            "",
        ]
    )
    return "\n".join(lines)


def apply_report(report: dict[str, Any], plan: dict[str, Any], approved: bool) -> dict[str, Any]:
    if not approved:
        raise ValueError("Brak jawnej akceptacji. Dodaj --approved dopiero po zatwierdzeniu raportu.")
    if report.get("planSignature") != plan_signature(plan):
        raise ValueError("Plan montażu zmienił się od utworzenia raportu. Wygeneruj B-roll Plan ponownie.")
    manual = [
        item
        for item in plan.get("overlays", [])
        if item.get("generatedBy") != PLANNER_ID
    ]
    plan["overlays"] = manual + list(report.get("proposedOverlays", []))
    manual_effects = [
        item
        for item in plan.get("effectCues", [])
        if item.get("generatedBy") != PLANNER_ID
    ]
    plan["effectCues"] = manual_effects + list(report.get("proposedEffectCues", []))
    notes = list(plan.get("notes", []))
    marker = "B-roll Planner: zaakceptowane propozycje wpisano do overlays."
    if marker not in notes:
        notes.append(marker)
    plan["notes"] = notes
    report["status"] = "approved"
    report["appliedAt"] = utc_now()
    report["appliedOverlays"] = len(report.get("proposedOverlays", []))
    report["appliedEffectCues"] = len(report.get("proposedEffectCues", []))
    return plan


def resolve_job_name(source: str) -> str:
    return Path(source).stem


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Nazwa MP4 z input/ albo nazwa joba")
    parser.add_argument("--apply", action="store_true", help="Wpisz wcześniej przygotowane propozycje do planu")
    parser.add_argument("--approved", action="store_true", help="Jawne potwierdzenie akceptacji raportu")
    args = parser.parse_args()

    job_name = resolve_job_name(args.source)
    transcript_path = ANALYSIS / job_name / "transcript.json"
    plan_path = JOBS / f"{job_name}.json"
    report_path = ANALYSIS / job_name / "broll-plan.json"
    markdown_path = ANALYSIS / job_name / "broll-plan.md"
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Brak transkrypcji: {transcript_path}")
    if not plan_path.is_file():
        raise FileNotFoundError(f"Brak planu montażu: {plan_path}")

    plan = read_json(plan_path)
    if args.apply:
        if not report_path.is_file():
            raise FileNotFoundError(f"Najpierw wygeneruj raport: {report_path}")
        report = read_json(report_path)
        plan = apply_report(report, plan, args.approved)
        write_json(plan_path, plan)
        write_json(report_path, report)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"Zaakceptowane przebitki wpisane do planu: {len(report.get('proposedOverlays', []))}")
        print(f"Plan: {plan_path}")
        print("Render nie został uruchomiony.")
        return

    if args.approved:
        raise ValueError("Flaga --approved ma sens tylko razem z --apply.")
    catalog = refresh_catalog(ROOT)
    report = build_report(job_name, read_json(transcript_path), plan, catalog)
    write_json(report_path, report)
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"Raport JSON: {report_path}")
    print(f"Raport do sprawdzenia: {markdown_path}")
    print(
        f"Propozycje: {report['coverage']['proposedOverlays']} · "
        f"pokrycie: {report['coverage']['coveragePercent']}% · koszt API: 0 USD"
    )
    print("Plan montażu nie został zmieniony.")


if __name__ == "__main__":
    main()
