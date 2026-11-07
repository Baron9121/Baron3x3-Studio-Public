#!/usr/bin/env python3
"""Validated, local memory of explicit Baron3x3 style decisions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = ROOT / "knowledge" / "style-memory.json"
EXAMPLES = ROOT / "examples"
ANALYSIS = ROOT / "analysis"
JOBS = ROOT / "instructions" / "jobs"
OUTPUT = ROOT / "output"
STATUSES = {"accepted", "rejected", "experimental"}
SCOPES = {"global", "interview", "job"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_memory(memory: dict[str, Any]) -> None:
    if memory.get("version") != 1:
        raise ValueError("Pamięć stylu musi mieć version=1.")
    decisions = memory.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("Pamięć stylu nie zawiera decyzji.")
    seen: set[str] = set()
    for item in decisions:
        decision_id = str(item.get("id", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", decision_id) or decision_id in seen:
            raise ValueError(f"Nieprawidłowe albo powtórzone id decyzji: {decision_id}")
        seen.add(decision_id)
        if item.get("status") not in STATUSES:
            raise ValueError(f"{decision_id}: nieprawidłowy status.")
        if item.get("scope") not in SCOPES:
            raise ValueError(f"{decision_id}: nieprawidłowy scope.")
        if not item.get("userConfirmed"):
            raise ValueError(f"{decision_id}: brak jawnego potwierdzenia użytkownika.")
        if not str(item.get("reason", "")).strip():
            raise ValueError(f"{decision_id}: brak powodu decyzji.")
        if not isinstance(item.get("rules"), list) or not all(
            isinstance(rule, str) and rule.strip() for rule in item["rules"]
        ):
            raise ValueError(f"{decision_id}: reguły muszą być niepustą listą tekstów.")
        if not isinstance(item.get("evidence"), list) or not item["evidence"]:
            raise ValueError(f"{decision_id}: brak dowodu lub przykładu.")
        if item["status"] != "accepted" and item.get("autoApply"):
            raise ValueError(f"{decision_id}: tylko zaakceptowana decyzja może mieć autoApply=true.")


def load_memory(path: Path = MEMORY_PATH) -> dict[str, Any]:
    memory = read_json(path)
    validate_memory(memory)
    return memory


def compile_contract(memory: dict[str, Any] | None = None) -> dict[str, Any]:
    source = memory or load_memory()
    validate_memory(source)
    accepted = [item for item in source["decisions"] if item["status"] == "accepted" and item["autoApply"]]
    rejected = [item for item in source["decisions"] if item["status"] == "rejected"]
    experimental = [item for item in source["decisions"] if item["status"] == "experimental"]
    return {
        "version": source["version"],
        "baselineExample": source.get("baselineExample"),
        "acceptedRules": [
            {"decisionId": item["id"], "module": item["module"], "rules": item["rules"]}
            for item in accepted
        ],
        "hardBans": [
            {"decisionId": item["id"], "module": item["module"], "rules": item["rules"], "reason": item["reason"]}
            for item in rejected
        ],
        "disabledExperiments": [
            {"decisionId": item["id"], "module": item["module"], "rules": item["rules"]}
            for item in experimental
        ],
    }


def local_qa_passed(report: dict[str, Any]) -> bool:
    return report.get("verdict") in {"pass-local-qa", "pass-local-gates-needs-semantic-review"}


def add_decision(memory: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(memory)
    if any(item.get("id") == decision.get("id") for item in updated["decisions"]):
        raise ValueError(f"Decyzja {decision.get('id')} już istnieje; nie nadpisuję historii po cichu.")
    updated["decisions"].append(decision)
    updated["updatedAt"] = datetime.now(timezone.utc).isoformat()
    validate_memory(updated)
    return updated


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(job_name: str, slug: str, title: str) -> Path:
    memory = load_memory()
    plan_path = JOBS / f"{job_name}.json"
    transcript_path = ANALYSIS / job_name / "transcript.json"
    edl_path = ANALYSIS / job_name / "edl.json"
    qa_path = ANALYSIS / job_name / "preview-qa" / "local-report.json"
    semantic_path = ANALYSIS / job_name / "preview-qa" / "semantic" / "review-gemini-cline.json"
    attention_path = ANALYSIS / job_name / "attention-map" / "attention-map.json"
    render_path = OUTPUT / f"{job_name}-render.mp4"
    for required in (plan_path, transcript_path, edl_path, qa_path, semantic_path, attention_path, render_path):
        if not required.is_file():
            raise FileNotFoundError(required)
    if read_json(plan_path).get("status") != "ready":
        raise ValueError("Przykład można zamrozić dopiero dla planu ze statusem ready.")
    if not local_qa_passed(read_json(qa_path)):
        raise ValueError("Przykład nie przeszedł lokalnego preview QA.")
    semantic = read_json(semantic_path)
    if semantic.get("verdict") != "pass":
        raise ValueError("Przykład nie przeszedł kontroli semantycznej.")
    if read_json(attention_path).get("verdict") != "pass-attention-safety":
        raise ValueError("Przykład nie przeszedł attention QA.")

    destination = EXAMPLES / slug
    destination.mkdir(parents=True, exist_ok=True)
    for source, name in ((plan_path, "job.json"), (transcript_path, "transcript.json"), (edl_path, "edl.json")):
        write_json(destination / name, read_json(source))
    accepted = [item for item in memory["decisions"] if item["status"] == "accepted"]
    manifest = {
        "version": 1,
        "status": "approved",
        "title": title,
        "job": job_name,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "render": str(render_path.relative_to(ROOT)),
        "renderSha256": sha256(render_path),
        "styleDecisionIds": [item["id"] for item in accepted],
        "qa": {
            "preview": str(qa_path.relative_to(ROOT)),
            "attention": str(attention_path.relative_to(ROOT)),
            "semantic": str(semantic_path.relative_to(ROOT)),
            "semanticScore": semantic.get("score"),
        },
    }
    write_json(destination / "manifest.json", manifest)
    notes = [
        f"# {title}",
        "",
        "Status: **zaakceptowany wzorzec bazowy**",
        "",
        "Render pozostaje w `output/`; przykład przechowuje plan, EDL i transkrypcję bez kopiowania dużego MP4.",
        "",
        "## Potwierdzone decyzje",
        "",
    ]
    notes.extend(f"- `{item['id']}` — {item['reason']}" for item in accepted)
    notes.extend([
        "",
        "## Porównanie kolejnej rolki",
        "",
        "Kolejną rolkę porównuj z tym przykładem pod względem historii, polszczyzny, hooka, rytmu, semantyki B-rollu, pełnych kulminacji, napisów, kadrowania, efektów i czytelności audio.",
        "Odrzucone moduły z pamięci stylu są twardymi zakazami, a nie punktami do ponownego testowania.",
        "",
    ])
    (destination / "notes.md").write_text("\n".join(notes), encoding="utf-8")
    return destination


def status_text(memory: dict[str, Any]) -> str:
    counts = {status: sum(item["status"] == status for item in memory["decisions"]) for status in STATUSES}
    return (
        f"Pamięć stylu poprawna: {len(memory['decisions'])} decyzji · "
        f"zaakceptowane {counts['accepted']} · odrzucone {counts['rejected']} · "
        f"eksperymentalne {counts['experimental']} · baza {memory.get('baselineExample')}."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    subparsers.add_parser("status")
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("job")
    snapshot_parser.add_argument("--slug", required=True)
    snapshot_parser.add_argument("--title", required=True)
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--id", required=True)
    record_parser.add_argument("--module", required=True)
    record_parser.add_argument("--status", choices=sorted(STATUSES), required=True)
    record_parser.add_argument("--scope", choices=sorted(SCOPES), default="global")
    record_parser.add_argument("--reason", required=True)
    record_parser.add_argument("--rule", action="append", required=True)
    record_parser.add_argument("--evidence", action="append", required=True)
    record_parser.add_argument("--user-confirmed", action="store_true")
    record_parser.add_argument("--auto-apply", action="store_true")
    args = parser.parse_args()
    memory = load_memory()
    if args.command in {"validate", "status"}:
        print(status_text(memory))
    elif args.command == "snapshot":
        destination = snapshot(Path(args.job).stem, args.slug, args.title)
        print(f"Zamrożony przykład: {destination}")
    else:
        decision = {
            "id": args.id,
            "module": args.module,
            "status": args.status,
            "scope": args.scope,
            "userConfirmed": args.user_confirmed,
            "autoApply": args.auto_apply,
            "reason": args.reason,
            "rules": args.rule,
            "evidence": args.evidence,
        }
        updated = add_decision(memory, decision)
        write_json(MEMORY_PATH, updated)
        print(f"Zapisano decyzję {args.id} ze statusem {args.status}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
