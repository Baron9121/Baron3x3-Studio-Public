#!/usr/bin/env python3
"""Build a local, human-readable catalog of reusable video and image assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CONFIG_RELATIVE = Path("assets/sources.json")
CATALOG_RELATIVE = Path("assets/MATERIALY.md")
INDEX_RELATIVE = Path("analysis/assets/catalog.json")
STOCK_REGISTRY_RELATIVE = Path("assets/STOCK-LICENSES.json")
GENERATED_START = "<!-- BARON3X3:AUTOMATIC:START -->"
GENERATED_END = "<!-- BARON3X3:AUTOMATIC:END -->"
MANUAL_START = "<!-- BARON3X3:USER-NOTES:START -->"
MANUAL_END = "<!-- BARON3X3:USER-NOTES:END -->"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".heic", ".tif", ".tiff"}
IGNORED_NAMES = {".DS_Store"}
MAX_FILES = 20_000


def read_json(path: Path, fallback: Any) -> Any:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_timestamp(timestamp: float | None = None) -> str:
    moment = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.now(timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize(value: str) -> str:
    value = value.casefold().replace("ł", "l")
    replacements = str.maketrans("ąćęńóśźż", "acenoszz")
    value = value.translate(replacements)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def auto_description(path: Path) -> str:
    value = re.sub(r"[_-]+", " ", path.stem)
    return re.sub(r"\s+", " ", value).strip()


def quick_fingerprint(path: Path) -> str:
    """Hash a small sample so large source videos are not reread on each scan."""
    size = path.stat().st_size
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))
    with path.open("rb") as stream:
        digest.update(stream.read(1024 * 1024))
        if size > 1024 * 1024:
            stream.seek(max(0, size - 1024 * 1024))
            digest.update(stream.read(1024 * 1024))
    return digest.hexdigest()


def probe_media(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    stream = next(
        (
            candidate
            for candidate in data.get("streams", [])
            if candidate.get("codec_type") == "video"
            or candidate.get("width") is not None
        ),
        {},
    )
    duration = data.get("format", {}).get("duration")
    return {
        "durationMs": round(float(duration) * 1000) if duration is not None else None,
        "width": int(stream["width"]) if stream.get("width") is not None else None,
        "height": int(stream["height"]) if stream.get("height") is not None else None,
    }


def validate_scan_root(project_root: Path, candidate: Path) -> Path:
    resolved = candidate.expanduser().resolve()
    home = Path.home().resolve()
    forbidden = {Path("/").resolve(), home, home / "Desktop", home / "Documents"}
    if resolved in forbidden:
        raise ValueError(f"Zbyt szeroki folder do skanowania: {resolved}")
    if "Baron3x3-Reels" in resolved.parts:
        raise ValueError("Stary folder Baron3x3-Reels nie może być źródłem katalogu.")
    if not resolved.is_dir():
        raise FileNotFoundError(f"Folder materiałów nie istnieje: {resolved}")
    return resolved


def load_sources(project_root: Path) -> list[dict[str, str]]:
    config_path = project_root / CONFIG_RELATIVE
    config = read_json(config_path, {"roots": [{"path": "assets/library", "label": "Biblioteka projektu"}]})
    roots = config.get("roots") if isinstance(config, dict) else None
    if not isinstance(roots, list) or not roots:
        raise ValueError(f"{config_path}: pole roots musi być niepustą listą.")

    sources: list[dict[str, str]] = []
    for number, item in enumerate(roots, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{config_path}: roots[{number}] musi być obiektem.")
        if item.get("enabled", True) is False:
            continue
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"{config_path}: roots[{number}].path jest wymagane.")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        resolved = validate_scan_root(project_root, candidate)
        sources.append(
            {
                "path": str(resolved),
                "label": str(item.get("label") or resolved.name),
            }
        )
    return sources


def media_kind(path: Path) -> str | None:
    suffix = path.suffix.casefold()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return None


def asset_id(source_label: str, relative_path: str) -> str:
    digest = hashlib.sha256(f"{source_label}\0{relative_path}".encode("utf-8")).hexdigest()
    return digest[:12]


def extract_manual_notes(markdown: str) -> str:
    if MANUAL_START in markdown and MANUAL_END in markdown:
        return markdown.split(MANUAL_START, 1)[1].split(MANUAL_END, 1)[0].strip("\n")
    return (
        "## Moje opisy\n\n"
        "Dopisuj opisy pod nagłówkiem z dokładną nazwą pliku lub ścieżką z tabeli.\n\n"
        "### Przykład.mp4\n\n"
        "- Opis: akcje konkretnego zawodnika podczas turnieju\n"
        "- Osoby: imię i nazwisko\n"
        "- Zespół: nazwa zespołu\n"
        "- Tagi: drybling, wsad, obrona, celebracja\n"
        "- Nie używaj, gdy: opcjonalne ograniczenie\n"
    )


def parse_manual_notes(notes: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    current: str | None = None
    lines: list[str] = []
    for line in notes.splitlines():
        if line.startswith("### "):
            if current:
                parsed[normalize(current)] = "\n".join(lines).strip()
            current = line[4:].strip().strip("`")
            lines = []
        elif current:
            lines.append(line)
    if current:
        parsed[normalize(current)] = "\n".join(lines).strip()
    return parsed


def stock_notes(entry: dict[str, Any]) -> str:
    query = str(entry.get("query") or "stock")
    keywords = str(entry.get("keywords") or query)
    description = str(entry.get("description") or entry.get("title") or query)
    return "\n".join(
        [
            f"- Opis: {description}",
            f"- Zastosowanie: neutralna przebitka stockowa opisana jako: {description}",
            f"- Tagi: {keywords}, stock, {entry.get('provider', '')}",
            f"- Wyszukano dla: {query}",
            f"- Źródło: {entry.get('sourcePage', '')}",
            f"- Autor: {entry.get('author', '')}",
            f"- Licencja: {entry.get('licenseName', '')} — {entry.get('licenseUrl', '')}",
            f"- Podpis: {entry.get('attribution', '')}",
            f"- Nie używaj bez kontroli: {entry.get('usageWarning', 'osoby i znaki towarowe')}",
        ]
    )


def markdown_escape(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def format_duration(duration_ms: int | None) -> str:
    if duration_ms is None:
        return "—"
    total_seconds = round(duration_ms / 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def render_catalog(items: list[dict[str, Any]], manual_notes: str, generated_at: str) -> str:
    available = sum(item["status"] == "available" for item in items)
    videos = sum(item["kind"] == "video" and item["status"] == "available" for item in items)
    images = sum(item["kind"] == "image" and item["status"] == "available" for item in items)
    missing = sum(item["status"] == "missing" for item in items)
    lines = [
        "# Katalog materiałów Baron3x3",
        "",
        "Ten plik jest automatycznie odświeżany przed uruchomieniem pipeline’u.",
        "Nie edytuj tabeli automatycznej. Własne opisy wpisuj w sekcji `Moje opisy` na dole pliku.",
        "",
        GENERATED_START,
        "",
        f"Ostatni skan: `{generated_at}`",
        "",
        f"Dostępne: **{available}** · Wideo: **{videos}** · Zdjęcia: **{images}** · Niedostępne: **{missing}**",
        "",
        "| ID | Typ | Plik | Opis z nazwy | Źródło | Czas | Wymiary | Status |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for item in sorted(items, key=lambda value: (value["status"] != "available", value["kind"], normalize(value["name"]))):
        dimensions = (
            f"{item['width']}×{item['height']}"
            if item.get("width") and item.get("height")
            else "—"
        )
        lines.append(
            "| {id} | {kind} | `{path}` | {description} | {source} | {duration} | {dimensions} | {status} |".format(
                id=markdown_escape(item["id"]),
                kind="wideo" if item["kind"] == "video" else "zdjęcie",
                path=markdown_escape(item["path"]),
                description=markdown_escape(item["autoDescription"]),
                source=markdown_escape(item["sourceLabel"]),
                duration=format_duration(item.get("durationMs")),
                dimensions=dimensions,
                status="dostępny" if item["status"] == "available" else "brak pliku",
            )
        )
    lines.extend(
        [
            "",
            GENERATED_END,
            "",
            MANUAL_START,
            manual_notes.rstrip(),
            MANUAL_END,
            "",
        ]
    )
    return "\n".join(lines)


def refresh_catalog(
    project_root: Path = ROOT,
    metadata_reader: Callable[[Path], dict[str, Any]] = probe_media,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    catalog_path = project_root / CATALOG_RELATIVE
    index_path = project_root / INDEX_RELATIVE
    previous = read_json(index_path, {"items": []})
    previous_items = {
        str(item.get("absolutePath")): item
        for item in previous.get("items", [])
        if isinstance(item, dict) and item.get("absolutePath")
    }
    existing_markdown = catalog_path.read_text(encoding="utf-8") if catalog_path.is_file() else ""
    manual_notes = extract_manual_notes(existing_markdown)
    parsed_notes = parse_manual_notes(manual_notes)
    stock_registry = read_json(project_root / STOCK_REGISTRY_RELATIVE, {"items": []})
    stock_by_path = {
        str(Path(str(entry.get("absolutePath"))).resolve()): entry
        for entry in stock_registry.get("items", [])
        if isinstance(entry, dict) and entry.get("absolutePath")
    }
    sources = load_sources(project_root)
    items: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for source in sources:
        source_root = Path(source["path"])
        for path in sorted(source_root.rglob("*")):
            if len(items) >= MAX_FILES:
                raise RuntimeError(f"Przekroczono bezpieczny limit {MAX_FILES} materiałów.")
            if not path.is_file() or path.name in IGNORED_NAMES:
                continue
            kind = media_kind(path)
            if kind is None:
                continue
            resolved = path.resolve()
            absolute = str(resolved)
            relative = resolved.relative_to(source_root).as_posix()
            stat = resolved.stat()
            cached = previous_items.get(absolute)
            unchanged = bool(
                cached
                and cached.get("sizeBytes") == stat.st_size
                and cached.get("modifiedNs") == stat.st_mtime_ns
            )
            metadata: dict[str, Any]
            error: str | None = None
            if unchanged:
                metadata = {
                    "durationMs": cached.get("durationMs"),
                    "width": cached.get("width"),
                    "height": cached.get("height"),
                }
                fingerprint = str(cached.get("fingerprint") or quick_fingerprint(resolved))
            else:
                try:
                    metadata = metadata_reader(resolved)
                except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
                    metadata = {"durationMs": None, "width": None, "height": None}
                    error = str(exc)
                fingerprint = quick_fingerprint(resolved)
            manual_note = parsed_notes.get(normalize(relative)) or parsed_notes.get(normalize(resolved.name)) or ""
            stock_entry = stock_by_path.get(absolute)
            generated_stock_note = stock_notes(stock_entry) if stock_entry else ""
            note = "\n".join(part for part in (generated_stock_note, manual_note) if part)
            item = {
                "id": asset_id(source["label"], relative),
                "kind": kind,
                "name": resolved.name,
                "path": relative,
                "absolutePath": absolute,
                "sourceLabel": source["label"],
                "sizeBytes": stat.st_size,
                "modifiedNs": stat.st_mtime_ns,
                "modifiedAt": utc_timestamp(stat.st_mtime),
                "fingerprint": fingerprint,
                "autoDescription": str(stock_entry.get("title")) if stock_entry else auto_description(resolved),
                "userNotes": note,
                "stock": stock_entry,
                "status": "available",
                "probeError": error,
                **metadata,
            }
            items.append(item)
            seen_paths.add(absolute)

    for absolute, old in previous_items.items():
        if absolute in seen_paths:
            continue
        missing = dict(old)
        missing["status"] = "missing"
        missing["userNotes"] = (
            parsed_notes.get(normalize(str(missing.get("path", ""))))
            or parsed_notes.get(normalize(str(missing.get("name", ""))))
            or missing.get("userNotes", "")
        )
        items.append(missing)

    generated_at = utc_timestamp()
    index = {
        "version": 1,
        "generatedAt": generated_at,
        "sources": sources,
        "items": items,
    }
    write_json(index_path, index)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(render_catalog(items, manual_notes, generated_at), encoding="utf-8")
    return index


def search_items(index: dict[str, Any], query: str) -> list[dict[str, Any]]:
    tokens = set(normalize(query).split())
    if not tokens:
        return []
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in index.get("items", []):
        if item.get("status") != "available":
            continue
        haystack = normalize(
            " ".join(
                str(item.get(key, ""))
                for key in ("name", "path", "autoDescription", "userNotes", "sourceLabel")
            )
        )
        score = sum(3 if token in normalize(str(item.get("name", ""))) else 1 for token in tokens if token in haystack)
        if score:
            ranked.append((score, item))
    return [item for _, item in sorted(ranked, key=lambda pair: (-pair[0], normalize(pair[1]["name"])))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search", help="Wyszukaj materiały po nazwie, osobie, zespole lub tagu")
    args = parser.parse_args()
    index = refresh_catalog(ROOT)
    print(f"Katalog: {ROOT / CATALOG_RELATIVE}")
    print(f"Indeks: {ROOT / INDEX_RELATIVE}")
    available = sum(item["status"] == "available" for item in index["items"])
    print(f"Dostępne materiały: {available}")
    if args.search:
        results = search_items(index, args.search)
        print(f"Wyniki dla {args.search!r}: {len(results)}")
        for item in results[:20]:
            print(f"- [{item['kind']}] {item['name']} ({item['sourceLabel']})")


if __name__ == "__main__":
    main()
