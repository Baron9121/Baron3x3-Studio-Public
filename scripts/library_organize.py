#!/usr/bin/env python3
"""Organise saved Instagram media with a vision model through OpenRouter.

The source folders are immutable.  Media is hard-linked into ``images`` and
``video`` where possible (or copied only when the filesystem does not support
hard links).  A hidden JSON manifest preserves earlier results; the only
human-facing catalogue in each destination is ``README.md``.

This program never reads an API key from a project file.  It uses the existing
macOS Keychain loader and the controlled OpenRouter client, which also keeps a
per-job cost ledger and stops before exceeding the explicit budget.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.openrouter_client import OpenRouterClient
    from scripts.openrouter_keychain import load_openrouter_key
except ModuleNotFoundError:  # Direct execution as scripts/library_organize.py.
    from openrouter_client import OpenRouterClient
    from openrouter_keychain import load_openrouter_key


DEFAULT_ROOT = Path("assets/library/Baron3x3")
MODEL = "google/gemini-3.7-flash"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "players": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "team": {"type": "string"},
        "tournament": {"type": "string"},
        "year": {"type": "string"},
        "action": {"type": "string"},
        "confidence": {"type": "string", "enum": ["wysoka", "średnia", "niska"]},
        "evidence": {"type": "string"},
    },
    "required": ["title", "players", "team", "tournament", "year", "action", "confidence", "evidence"],
    "additionalProperties": False,
}


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _safe_slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    folded = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return folded[:110] or "material-3x3"


def _media_type(path: Path) -> str | None:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return "image"
    if path.suffix.lower() in VIDEO_EXTENSIONS:
        return "video"
    return None


def _mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".heic":
        return "image/heic"
    if suffix in {".mov", ".m4v"}:
        return "video/quicktime"
    if suffix == ".webm":
        return "video/webm"
    return "video/mp4"


def _data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_mime(path)};base64,{encoded}"


def _source_context(folder: Path) -> dict[str, str]:
    raw = _read_json(folder / "source.json", {})
    user = raw.get("user") or {}
    return {
        "post_date": str(raw.get("taken_at") or "nieustalone"),
        "author": str(user.get("full_name") or "nieustalone"),
        "account": str(user.get("username") or "nieustalone"),
        "caption": str(raw.get("caption_text") or "brak"),
        "source_url": f"https://www.instagram.com/p/{raw.get('code')}/" if raw.get("code") else "nieustalone",
    }


def _folders(root: Path, limit: int) -> list[Path]:
    selected = [item for item in root.iterdir() if item.is_dir() and item.name.isdigit()]
    return sorted(selected, key=lambda item: item.name)[:limit]


def _analyse(client: OpenRouterClient, *, job_id: str, media: Path, context: dict[str, str], budget: float, reserve: float, model: str) -> dict[str, Any]:
    kind = _media_type(media)
    assert kind is not None
    prompt = f"""Jesteś precyzyjnym archiwistą materiałów z koszykówki 3x3. Przeanalizuj ZAŁĄCZONY pojedynczy {'film' if kind == 'video' else 'obraz'} oraz poniższe metadane posta.

Zadanie: utwórz krótki, przyjazny tytuł po polsku oraz ustal: imiona i nazwiska graczy widocznych lub jednoznacznie wskazanych, zespół, oficjalną nazwę turnieju i rok. Opisz główną akcję. Korzystaj z obrazu, tekstu na ekranie, strojów, banerów oraz podpisu. Nie rozpoznawaj twarzy na podstawie podobieństwa i nie zgaduj. Gdy pole nie jest pewne, wpisz dokładnie „nieustalone”; dla grafiki bez osoby użyj players=[]. Rok wydarzenia może pochodzić z grafiki lub metadanych, ale nie zamieniaj daty publikacji w datę wydarzenia bez zaznaczenia tego w evidence.

Nazwa źródłowego pliku: {media.name}
Data publikacji: {context['post_date']}
Autor posta: {context['author']} (@{context['account']})
Podpis posta: {context['caption']}
Źródło: {context['source_url']}
"""
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.append({f"{kind}_url": {"url": _data_url(media)}, "type": f"{kind}_url"})
    result = client.complete_json(
        job_id=job_id,
        stage="video_analysis",
        model=model,
        messages=[{"role": "user", "content": content}],
        schema_name="baron3x3_library_asset",
        schema=SCHEMA,
        budget_limit_usd=budget,
        max_request_cost_usd=reserve,
        max_completion_tokens=700,
        token_limit_field="max_tokens",
        reasoning_effort="low",
        enable_provider_prompt_cache=False,
        enable_response_healing=True,
    )
    analysis = dict(result.data)
    analysis["model"] = result.model
    analysis["costUsd"] = result.cost_usd
    analysis["sourceUrl"] = context["source_url"]
    return analysis


def _place(source: Path, destination_dir: Path, title: str) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_slug(title)
    target = destination_dir / f"{stem}{source.suffix.lower()}"
    counter = 2
    while target.exists() and not os.path.samefile(source, target):
        target = destination_dir / f"{stem}-{counter}{source.suffix.lower()}"
        counter += 1
    if not target.exists():
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    return target


def _read_manifest(directory: Path) -> list[dict[str, Any]]:
    return _read_json(directory / ".catalog.json", [])


def _render_index(directory: Path, kind_label: str, entries: list[dict[str, Any]]) -> None:
    lines = [f"# {kind_label}", "", "Katalog automatycznie aktualizowany przez `npm run library:organize`.", ""]
    for entry in sorted(entries, key=lambda item: str(item["title"]).casefold()):
        people = ", ".join(entry.get("players") or []) or "nieustalone"
        lines.extend([
            f"## {entry['title']}", "",
            f"Plik: [{entry['file']}](<{entry['file']}>)", "",
            f"- Gracz/gracze: {people}",
            f"- Zespół: {entry['team']}",
            f"- Turniej: {entry['tournament']}",
            f"- Rok: {entry['year']}",
            f"- Opis: {entry['action']}",
            f"- Pewność: {entry['confidence']}",
            f"- Podstawa: {entry['evidence']}",
            "",
        ])
    (directory / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analizuje zapisane posty 3x3 przez OpenRouter i aktualizuje images/video.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Katalog z numerycznymi folderami postów.")
    parser.add_argument("--limit", type=int, required=True, help="Liczba pierwszych folderów do analizy.")
    parser.add_argument("--approved-budget", type=float, required=True, help="Jawnie zatwierdzony limit kosztu w USD.")
    parser.add_argument("--reserve-usd", type=float, required=True, help="Maksymalna rezerwacja kosztu pojedynczego pliku w USD.")
    parser.add_argument("--model", default=MODEL, help="Model vision przez OpenRouter.")
    parser.add_argument("--job-id", default=None, help="Identyfikator kosztów; domyślnie data i limit.")
    parser.add_argument("--dry-run", action="store_true", help="Pokazuje plan bez wywołań API i bez zmian w plikach.")
    args = parser.parse_args()
    if args.limit < 1 or args.approved_budget <= 0 or args.reserve_usd <= 0:
        parser.error("limit, approved-budget i reserve-usd muszą być dodatnie")
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"Nie istnieje katalog: {root}")
    folders = _folders(root, args.limit)
    media = [file for folder in folders for file in sorted(folder.iterdir()) if file.is_file() and _media_type(file)]
    estimated = len(media) * args.reserve_usd
    plan = {"root": str(root), "folders": [item.name for item in folders], "files": len(media), "model": args.model, "budgetUsd": args.approved_budget, "worstCaseReservationUsd": estimated}
    if estimated > args.approved_budget:
        raise SystemExit(json.dumps({**plan, "error": "Rezerwacja maksymalna przekracza zatwierdzony budżet."}, ensure_ascii=False))
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    key = load_openrouter_key()
    if not key:
        raise SystemExit("Brak klucza OpenRouter w Keychain. Nie wklejaj go do czatu ani pliku projektu.")
    job_id = args.job_id or f"library-organize-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    client = OpenRouterClient(api_key=key, max_attempts=1, timeout_seconds=150)
    manifests = {"image": _read_manifest(root / "images"), "video": _read_manifest(root / "video")}
    by_source = {kind: {item.get("source"): item for item in values} for kind, values in manifests.items()}
    for file in media:
        kind = _media_type(file)
        assert kind is not None
        source_key = str(file.resolve())
        if source_key in by_source[kind]:
            continue
        analysis = _analyse(client, job_id=job_id, media=file, context=_source_context(file.parent), budget=args.approved_budget, reserve=args.reserve_usd, model=args.model)
        target = _place(file, root / ("images" if kind == "image" else "video"), analysis["title"])
        entry = {"source": source_key, "file": target.name, **analysis}
        manifests[kind].append(entry)
        by_source[kind][source_key] = entry
        _write_json(root / ("images" if kind == "image" else "video") / ".catalog.json", manifests[kind])
        _render_index(root / ("images" if kind == "image" else "video"), "Zdjęcia" if kind == "image" else "Wideo", manifests[kind])
        print(json.dumps({"source": file.name, "target": target.name, "costUsd": analysis["costUsd"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
