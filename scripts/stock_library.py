#!/usr/bin/env python3
"""Review-first search and download for free stock with a durable license record."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if __package__:
    from .asset_catalog import refresh_catalog
else:
    from asset_catalog import refresh_catalog


ROOT = Path(__file__).resolve().parents[1]
SEARCH_DIR = ROOT / "analysis" / "stock" / "searches"
LIBRARY_DIR = ROOT / "assets" / "library" / "stock"
REGISTRY_JSON = ROOT / "assets" / "STOCK-LICENSES.json"
REGISTRY_MD = ROOT / "assets" / "STOCK-LICENSES.md"
PEXELS_KEYCHAIN_SERVICE = "Baron3x3-Local-Pexels"
USER_AGENT = "Baron3x3-Local/1.0 (local video editing workflow)"
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
ALLOWED_COMMONS_LICENSES = (
    "cc0",
    "public domain",
    "cc by ",
    "cc by-sa ",
)
QUERY_ALIASES = {
    "warsaw": ["Warszawa", "Warszawie"],
    "copenhagen": ["Kopenhaga", "Kopenhadze"],
    "antwerp": ["Antwerpia", "Antwerpii"],
    "city": ["miasto"],
    "skyline": ["panorama miasta"],
    "aerial": ["z lotu ptaka"],
    "arena": ["arena", "hala", "stadion"],
}


def read_json(path: Path, fallback: Any) -> Any:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def slug(value: str, maximum: int = 60) -> str:
    normalized = value.casefold().replace("ł", "l")
    normalized = normalized.translate(str.maketrans("ąćęńóśźż", "acenoszz"))
    result = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return (result[:maximum].rstrip("-") or "stock")


def expanded_keywords(query: str) -> str:
    keywords = [query]
    normalized = set(re.findall(r"[a-z0-9]+", query.casefold()))
    for source, aliases in QUERY_ALIASES.items():
        if source in normalized:
            keywords.extend(aliases)
    return ", ".join(dict.fromkeys(keywords))


def pexels_title_from_url(url: str, fallback: str) -> str:
    segments = [segment for segment in urllib.parse.urlparse(url).path.split("/") if segment]
    raw = segments[-1] if segments else ""
    raw = re.sub(r"-\d+$", "", raw)
    title = re.sub(r"[-_]+", " ", urllib.parse.unquote(raw)).strip()
    return title[:1].upper() + title[1:] if title else fallback


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def orientation(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "unknown"
    if width == height:
        return "square"
    return "portrait" if height > width else "landscape"


def commons_license_allowed(name: str) -> bool:
    normalized = clean_html(name).casefold().replace("-", "-")
    if "noncommercial" in normalized or "no derivatives" in normalized:
        return False
    if re.search(r"\bnc\b|\bnd\b", normalized):
        return False
    return normalized == "cc0" or any(normalized.startswith(prefix) for prefix in ALLOWED_COMMONS_LICENSES)


def extension_from_url(url: str, fallback: str) -> str:
    path = urllib.parse.urlparse(url).path
    suffix = Path(urllib.parse.unquote(path)).suffix.casefold()
    if re.fullmatch(r"\.[a-z0-9]{2,5}", suffix):
        return suffix
    return fallback


def search_commons(
    query: str,
    media_type: str,
    limit: int,
    requester: Callable[[str, dict[str, str] | None], dict[str, Any]] = fetch_json,
) -> tuple[list[dict[str, Any]], int]:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": str(min(50, max(limit * 3, 10))),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": "1920",
        "origin": "*",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    data = requester(url, None)
    candidates: list[dict[str, Any]] = []
    rejected = 0
    for page in data.get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        mime = str(info.get("mime") or "")
        kind = "video" if mime.startswith("video/") else "image" if mime.startswith("image/") else ""
        if kind != media_type:
            continue
        metadata = info.get("extmetadata") or {}
        meta = lambda key: clean_html(str((metadata.get(key) or {}).get("value") or ""))
        license_name = meta("LicenseShortName")
        if not commons_license_allowed(license_name):
            rejected += 1
            continue
        original_url = str(info.get("url") or "")
        download_url = str(info.get("thumburl") or original_url)
        if not download_url.startswith("https://"):
            rejected += 1
            continue
        title = str(page.get("title") or "").removeprefix("File:")
        author = meta("Artist") or "autor podany na stronie Wikimedia Commons"
        license_url = meta("LicenseUrl")
        requires_attribution = license_name.casefold() not in {"cc0", "public domain"}
        attribution = (
            f"{title} — {author}, {license_name}, Wikimedia Commons"
            if requires_attribution
            else f"{title} — {license_name}, Wikimedia Commons"
        )
        width = int(info["thumbwidth"] if info.get("thumbwidth") else info.get("width") or 0)
        height = int(info["thumbheight"] if info.get("thumbheight") else info.get("height") or 0)
        candidates.append(
            {
                "id": f"commons:{page['pageid']}",
                "provider": "Wikimedia Commons",
                "providerKey": "commons",
                "mediaType": kind,
                "title": title,
                "description": meta("ImageDescription") or f"Wynik wyszukiwania: {query}",
                "query": query,
                "keywords": expanded_keywords(f"{title} {query}"),
                "author": author,
                "authorUrl": "",
                "sourcePage": f"https://commons.wikimedia.org/?curid={page['pageid']}",
                "originalUrl": original_url,
                "downloadUrl": download_url,
                "width": width or None,
                "height": height or None,
                "durationMs": None,
                "orientation": orientation(width, height),
                "licenseName": license_name,
                "licenseUrl": license_url,
                "licenseRequiresAttribution": requires_attribution,
                "attribution": attribution,
                "usageWarning": "Przed publikacją sprawdź osoby, znaki towarowe i aktualny opis pliku.",
                "suggestedFilename": f"commons-{page['pageid']}-{slug(Path(title).stem)}{extension_from_url(download_url, '.jpg')}",
            }
        )
        if len(candidates) >= limit:
            break
    return candidates, rejected


def get_pexels_api_key() -> str | None:
    value = os.environ.get("PEXELS_API_KEY", "").strip()
    if value:
        return value
    if sys.platform != "darwin":
        return None
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            getpass.getuser(),
            "-s",
            PEXELS_KEYCHAIN_SERVICE,
            "-w",
        ],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def best_pexels_video_file(files: list[dict[str, Any]], orientation: str = "portrait") -> dict[str, Any] | None:
    mp4 = [item for item in files if item.get("file_type") == "video/mp4" and item.get("link")]
    if not mp4:
        return None
    if orientation == "landscape":
        # A 9:16 crop from landscape needs height >= 1920 (4K); take the smallest such file.
        tall = [item for item in mp4 if int(item.get("height") or 0) >= 1920 and int(item.get("width") or 0) > int(item.get("height") or 0)]
        return min(tall, key=lambda item: int(item.get("height") or 0)) if tall else max(mp4, key=lambda item: int(item.get("height") or 0))
    # Portrait first, then the file closest to 1080 px wide: 4K files only cost download time.
    return max(
        mp4,
        key=lambda item: (
            int((item.get("height") or 0) > (item.get("width") or 0)),
            int((item.get("width") or 0) >= 720),
            int((item.get("width") or 0) >= 1080),
            -abs(int(item.get("width") or 0) - 1080),
        ),
    )


def search_pexels(
    query: str,
    media_type: str,
    limit: int,
    api_key: str,
    requester: Callable[[str, dict[str, str] | None], dict[str, Any]] = fetch_json,
    page: int = 1,
    orientation_filter: str = "portrait",
) -> tuple[list[dict[str, Any]], int]:
    endpoint = "videos/search" if media_type == "video" else "search"
    params = {
        "query": query,
        "orientation": orientation_filter,
        "locale": "pl-PL",
        "per_page": str(min(80, limit)),
        "page": str(page),
    }
    url = f"https://api.pexels.com/v1/{endpoint}?" + urllib.parse.urlencode(params)
    data = requester(url, {"Authorization": api_key})
    source_items = data.get("videos", []) if media_type == "video" else data.get("photos", [])
    candidates: list[dict[str, Any]] = []
    for item in source_items:
        contributor = item.get("user") or item.get("photographer") or "autor Pexels"
        contributor_url = item.get("user", {}).get("url", "") if isinstance(item.get("user"), dict) else item.get("photographer_url", "")
        if isinstance(contributor, dict):
            contributor = contributor.get("name") or "autor Pexels"
        if media_type == "video":
            selected_file = best_pexels_video_file(item.get("video_files", []), orientation_filter)
            if not selected_file:
                continue
            download_url = str(selected_file["link"])
            width = int(selected_file.get("width") or item.get("width") or 0)
            height = int(selected_file.get("height") or item.get("height") or 0)
            duration_ms = round(float(item.get("duration") or 0) * 1000) or None
            suffix = ".mp4"
            title = pexels_title_from_url(
                str(item.get("url") or ""), f"Wideo Pexels {item['id']}"
            )
            pictures = item.get("video_pictures") or []
            # "image" is the full-size poster; video_pictures can be tiny thumbnails.
            preview_url = str(item.get("image") or (pictures[len(pictures) // 2].get("picture") if pictures else "") or "")
        else:
            sources = item.get("src") or {}
            download_url = str(sources.get("large2x") or sources.get("original") or "")
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            duration_ms = None
            suffix = extension_from_url(download_url, ".jpg")
            title = str(item.get("alt") or f"{query} — zdjęcie Pexels {item['id']}")
            preview_url = str(sources.get("medium") or sources.get("large") or download_url)
        if not download_url.startswith("https://"):
            continue
        candidates.append(
            {
                "id": f"pexels:{item['id']}",
                "provider": "Pexels",
                "providerKey": "pexels",
                "mediaType": media_type,
                "title": title,
                "description": title,
                "query": query,
                "keywords": expanded_keywords(title),
                "semanticStatus": "source-title-only-needs-visual-review",
                "author": str(contributor),
                "authorUrl": str(contributor_url),
                "sourcePage": str(item.get("url") or "https://www.pexels.com"),
                "originalUrl": download_url,
                "downloadUrl": download_url,
                "previewUrl": preview_url,
                "width": width or None,
                "height": height or None,
                "durationMs": duration_ms,
                "orientation": orientation(width, height),
                "licenseName": "Pexels License",
                "licenseUrl": "https://www.pexels.com/license/",
                "licenseRequiresAttribution": False,
                "attribution": f"{media_type.capitalize()} by {contributor} via Pexels",
                "usageWarning": "Nie sugeruj poparcia przez widoczne osoby lub marki; nie używaj materiału jako znaku towarowego.",
                "suggestedFilename": f"pexels-{item['id']}-{slug(title if media_type == 'video' else query)}{suffix}",
            }
        )
    return candidates, 0


def search_id(provider: str, media_type: str, query: str) -> str:
    digest = hashlib.sha256(f"{provider}\0{media_type}\0{query}".encode("utf-8")).hexdigest()[:10]
    return f"{provider}-{media_type}-{slug(query, 36)}-{digest}"


def render_search_report(report: dict[str, Any]) -> str:
    lines = [
        f"# Darmowe stocki — {report['query']}",
        "",
        f"Źródło: **{report['provider']}** · typ: **{report['mediaType']}** · koszt API: **0 USD**",
        "",
        "To jest lista do przeglądu. Żaden plik nie został jeszcze pobrany.",
        "",
    ]
    if report.get("providerKey") == "pexels":
        lines.extend(
            [
                "**Ważne:** Pexels dopasowuje wyniki wyszukiwarką. Samo zapytanie nie potwierdza, że film przedstawia wskazane miasto. Sprawdź obraz i stronę źródłową.",
                "",
            ]
        )
    if report.get("rejectedByLicense"):
        lines.append(f"Odrzucone z powodu licencji lub metadanych: {report['rejectedByLicense']}.")
        lines.append("")
    for index, item in enumerate(report["results"], start=1):
        if item.get("previewUrl"):
            preview = ["", f"![Podgląd wyniku {index}]({item['previewUrl']})", ""]
        else:
            preview = []
        lines.extend(
            [
                f"## {index}. {item['title']}",
                *preview,
                "",
                f"- ID: `{item['id']}`",
                f"- Autor: {item['author']}",
                f"- Licencja: [{item['licenseName']}]({item['licenseUrl']})",
                f"- Format: {item['orientation']}, {item.get('width') or '?'}×{item.get('height') or '?'}",
                f"- Strona źródłowa: {item['sourcePage']}",
                f"- Podpis: {item['attribution']}",
                f"- Uwaga: {item['usageWarning']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Pobranie po akceptacji",
            "",
            f"`npm run stock:download -- ID_WYNIKU --search-id {report['searchId']} --approved`",
            "",
            "Pobrany plik trafi do `assets/library/stock/`, a pełne źródło i licencja do `assets/STOCK-LICENSES.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def probe_download(path: Path) -> dict[str, Any]:
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
        (item for item in data.get("streams", []) if item.get("width") and item.get("height")),
        {},
    )
    duration = data.get("format", {}).get("duration")
    return {
        "width": int(stream.get("width") or 0) or None,
        "height": int(stream.get("height") or 0) or None,
        "durationMs": round(float(duration) * 1000) if duration else None,
    }


def download_file(
    url: str,
    destination: Path,
    maximum_bytes: int = MAX_DOWNLOAD_BYTES,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> str:
    if not url.startswith("https://"):
        raise ValueError("Dozwolone są wyłącznie źródła HTTPS.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    total = 0
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=60) as response, temporary.open("wb") as output:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > maximum_bytes:
                raise ValueError("Plik przekracza limit 250 MB.")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum_bytes:
                    raise ValueError("Plik przekracza limit 250 MB.")
                output.write(chunk)
                digest.update(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return digest.hexdigest()


def find_candidate(search_identifier: str, candidate_id: str) -> tuple[dict[str, Any], Path]:
    report_path = SEARCH_DIR / f"{search_identifier}.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"Nie znaleziono raportu wyszukiwania: {report_path}")
    report = read_json(report_path, {})
    candidate = next((item for item in report.get("results", []) if item.get("id") == candidate_id), None)
    if not candidate:
        raise ValueError(f"Wyniku {candidate_id!r} nie ma w raporcie {search_identifier!r}.")
    return candidate, report_path


def render_registry(registry: dict[str, Any]) -> str:
    lines = [
        "# Rejestr darmowych materiałów stockowych",
        "",
        "Rejestr techniczny. Przed publikacją nadal sprawdź kontekst użycia, osoby i znaki towarowe.",
        "",
    ]
    for item in registry.get("items", []):
        lines.extend(
            [
                f"## {item['title']}",
                "",
                f"- Plik: `{item['localPath']}`",
                f"- Provider ID: `{item['id']}`",
                f"- Opis katalogowy: {item.get('description', item['title'])}",
                f"- Status opisu: {item.get('semanticStatus', 'metadane źródłowe')}",
                f"- Źródło: [{item['provider']}]({item['sourcePage']})",
                f"- Autor: {item['author']}",
                f"- Licencja: [{item['licenseName']}]({item['licenseUrl']})",
                f"- Sugerowany podpis: {item['attribution']}",
                f"- Wymagane przypisanie autora: {'tak' if item['licenseRequiresAttribution'] else 'nie'}",
                f"- Data pobrania: {item['downloadedAt']}",
                f"- SHA-256: `{item['sha256']}`",
                f"- Kontrola przed publikacją: {item['usageWarning']}",
                "",
            ]
        )
    return "\n".join(lines)


def register_download(candidate: dict[str, Any], destination: Path, digest: str) -> dict[str, Any]:
    registry = read_json(REGISTRY_JSON, {"version": 1, "items": []})
    entry = {
        **{key: value for key, value in candidate.items() if key not in {"downloadUrl", "previewUrl"}},
        "localPath": destination.relative_to(ROOT).as_posix(),
        "absolutePath": str(destination.resolve()),
        "downloadedAt": utc_now(),
        "sha256": digest,
        "publicationReviewRequired": True,
    }
    items = [item for item in registry.get("items", []) if item.get("id") != candidate["id"]]
    items.append(entry)
    registry = {"version": 1, "updatedAt": utc_now(), "items": items}
    write_json(REGISTRY_JSON, registry)
    REGISTRY_MD.write_text(render_registry(registry), encoding="utf-8")
    return entry


def search_command(args: argparse.Namespace) -> None:
    if args.provider == "commons":
        results, rejected = search_commons(args.query, args.type, args.limit)
        provider_name = "Wikimedia Commons"
    else:
        api_key = get_pexels_api_key()
        if not api_key:
            raise RuntimeError(
                "Brak darmowego klucza Pexels. Zapisz go w pęku kluczy zgodnie z docs/STOCK.md."
            )
        results, rejected = search_pexels(args.query, args.type, args.limit, api_key)
        provider_name = "Pexels"
    identifier = search_id(args.provider, args.type, args.query)
    report = {
        "version": 1,
        "searchId": identifier,
        "status": "needs-review",
        "generatedAt": utc_now(),
        "provider": provider_name,
        "providerKey": args.provider,
        "mediaType": args.type,
        "query": args.query,
        "costUsd": 0,
        "rejectedByLicense": rejected,
        "results": results,
    }
    write_json(SEARCH_DIR / f"{identifier}.json", report)
    (SEARCH_DIR / f"{identifier}.md").write_text(render_search_report(report), encoding="utf-8")
    print(f"Raport: {SEARCH_DIR / f'{identifier}.md'}")
    print(f"Search ID: {identifier}")
    print(f"Wyniki dopuszczone licencyjnie: {len(results)} · koszt API: 0 USD")
    print("Żaden plik nie został pobrany.")


def download_command(args: argparse.Namespace) -> None:
    if not args.approved:
        raise ValueError("Pobieranie wymaga jawnego --approved po sprawdzeniu raportu.")
    candidate, _ = find_candidate(args.search_id, args.candidate_id)
    provider_dir = LIBRARY_DIR / str(candidate["providerKey"])
    destination = provider_dir / str(candidate["suggestedFilename"])
    if destination.is_file():
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    else:
        digest = download_file(str(candidate["downloadUrl"]), destination)
    metadata = probe_download(destination)
    candidate.update({key: value for key, value in metadata.items() if value is not None})
    entry = register_download(candidate, destination, digest)
    refresh_catalog(ROOT)
    print(f"Pobrano: {destination}")
    print(f"Licencja: {entry['licenseName']} · źródło zapisane w {REGISTRY_MD}")
    print("Materiał dodano do katalogu. Render nie został uruchomiony.")


def status_command(_args: argparse.Namespace) -> None:
    pexels_ready = bool(get_pexels_api_key())
    print("Wikimedia Commons: gotowe (bez klucza)")
    print(f"Pexels: {'gotowe' if pexels_ready else 'wymaga darmowego klucza API'}")
    print(f"Pobrane i zarejestrowane stocki: {len(read_json(REGISTRY_JSON, {'items': []}).get('items', []))}")
    print("Koszt modeli API: 0 USD")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Wyszukaj i utwórz raport bez pobierania")
    search_parser.add_argument("query")
    search_parser.add_argument("--provider", choices=["commons", "pexels"], default="commons")
    search_parser.add_argument("--type", choices=["image", "video"], default="image")
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.set_defaults(handler=search_command)

    download_parser = subparsers.add_parser("download", help="Pobierz zatwierdzony wynik")
    download_parser.add_argument("candidate_id")
    download_parser.add_argument("--search-id", required=True)
    download_parser.add_argument("--approved", action="store_true")
    download_parser.set_defaults(handler=download_command)

    status_parser = subparsers.add_parser("status", help="Sprawdź gotowość providerów bez ujawniania kluczy")
    status_parser.set_defaults(handler=status_command)

    args = parser.parse_args()
    try:
        args.handler(args)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"Błąd: {exc}\n")


if __name__ == "__main__":
    main()
