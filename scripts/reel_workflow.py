#!/usr/bin/env python3
"""Local state machine for one-prompt Baron3x3 editing in VS Code/Cline."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .scenario_handoff import bind, check_scenario, write_review, check_review
    from .beat_director import application_from_proposal, DIRECTOR_ID
    from .beat_director import REFERENCE_DEFAULT, apply as apply_director
    from .beat_director import import_cline_proposal, prepare as prepare_director
    from .pipeline import validate_plan, validate_word_boundaries
    from .style_memory import load_memory
else:
    from scenario_handoff import bind, check_scenario, write_review, check_review
    from beat_director import application_from_proposal, DIRECTOR_ID
    from beat_director import REFERENCE_DEFAULT, apply as apply_director
    from beat_director import import_cline_proposal, prepare as prepare_director
    from pipeline import validate_plan, validate_word_boundaries
    from style_memory import load_memory


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"
ANALYSIS = ROOT / "analysis"
JOBS = ROOT / "instructions" / "jobs"
OUTPUT = ROOT / "output"
PYTHON = ROOT / ".venv" / "bin" / "python"
MAX_CLINE_STAGE_USD = 0.30


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def workflow_paths(job_name: str) -> dict[str, Path]:
    directory = ANALYSIS / job_name / "workflow"
    return {
        "directory": directory,
        "state": directory / "state.json",
        "report": directory / "NEXT.md",
        "prompt": JOBS / f"{job_name}.prompt.md",
        "plan": JOBS / f"{job_name}.json",
        "transcript": ANALYSIS / job_name / "transcript.json",
        "transcript_compact": ANALYSIS / job_name / "transcript-compact.md",
        "director_report": ANALYSIS / job_name / "director" / "proposal.md",
    }


def require_phase(job_name: str, expected: str) -> dict[str, Any]:
    state_path = workflow_paths(job_name)["state"]
    if not state_path.is_file():
        raise FileNotFoundError(f"Brak workflow dla {job_name}.")
    check_scenario(ROOT, job_name)
    state = read_json(state_path)
    if state.get("phase") != expected:
        raise ValueError(f"Oczekiwano stanu {expected}, obecny stan to {state.get('phase')}.")
    return state


def validate_stage_cost(cost: float | None) -> float | None:
    if cost is None:
        return None
    value = float(cost)
    if value < 0 or value > MAX_CLINE_STAGE_USD:
        raise ValueError(f"Koszt etapu musi mieścić się w zakresie 0–{MAX_CLINE_STAGE_USD:.2f} USD.")
    return round(value, 6)


def save_state(job_name: str, phase: str, next_action: str, **extra: Any) -> dict[str, Any]:
    paths = workflow_paths(job_name)
    previous = read_json(paths["state"]) if paths["state"].is_file() else {}
    history = list(previous.get("history", []))
    history.append({"phase": phase, "at": utc_now()})
    state = {
        "version": 1,
        "job": job_name,
        "phase": phase,
        "nextAction": next_action,
        "updatedAt": utc_now(),
        "costUsd": previous.get("costUsd", 0),
        "history": history,
        **extra,
    }
    write_json(paths["state"], state)
    write_next_report(state, paths["report"])
    return state


def write_next_report(state: dict[str, Any], path: Path) -> None:
    lines = [
        f"# Baron3x3 workflow — {state['job']}",
        "",
        f"Stan: **{state['phase']}**",
        f"Koszt zapisany: **{float(state.get('costUsd', 0)):.4f} USD**",
        "",
        "## Następna czynność",
        "",
        state["nextAction"],
        "",
        "Pipeline nie przechodzi sam przez punkt akceptacji i nie wykonuje automatycznych ponowień płatnego modelu.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def flatten_words(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    return [word for segment in transcript.get("segments", []) for word in segment.get("words", [])]


def validate_story_data(plan: dict[str, Any], transcript: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    if plan.get("status") != "needs-review":
        raise ValueError("Plan historii musi mieć status needs-review; nie ustawiaj ready przed akceptacją.")
    story = plan.get("storyPlan")
    if not isinstance(story, dict):
        raise ValueError("Brak storyPlan z hookiem, łukiem i puentą.")
    for field in ("hook", "arc", "payoff"):
        if not str(story.get(field, "")).strip():
            raise ValueError(f"storyPlan.{field} nie może być pusty.")
    if story.get("languageReviewed") is not True:
        raise ValueError("storyPlan.languageReviewed musi potwierdzać korektę polszczyzny.")
    ranges = plan.get("sourceRanges", [])
    if not ranges:
        raise ValueError("Plan historii nie zawiera sourceRanges.")
    validate_plan(plan_path, plan)
    validate_word_boundaries(plan_path, ranges, flatten_words(transcript))
    duration_ms = sum(int(item["sourceEndMs"]) - int(item["sourceStartMs"]) for item in ranges)
    return {
        "rangeCount": len(ranges),
        "durationMs": duration_ms,
        "hook": story["hook"],
        "arc": story["arc"],
        "payoff": story["payoff"],
        "wordBoundaries": "pass",
    }


def start(source_name: str, instructions: str, scenario: Path | None = None) -> dict[str, Any]:
    source = INPUT / Path(source_name).name
    if not source.is_file():
        raise FileNotFoundError(f"Nie znaleziono {source}.")
    if source.suffix.lower() != ".mp4":
        raise ValueError("Workflow przyjmuje obecnie plik MP4.")
    if not instructions.strip():
        raise ValueError("Dodatkowe instrukcje nie mogą być puste.")
    load_memory()
    job_name = source.stem
    paths = workflow_paths(job_name)
    if paths["state"].is_file() or (paths["plan"].is_file() and read_json(paths["plan"]).get("status") == "ready"):
        raise ValueError("Ten job już istnieje. Użyj reel:status; nie nadpisuję zatwierdzonej pracy.")
    if scenario is not None:
        instructions = bind(ROOT, job_name, scenario, instructions)
    paths["prompt"].parent.mkdir(parents=True, exist_ok=True)
    paths["prompt"].write_text(instructions.rstrip() + "\n", encoding="utf-8")
    subprocess.run(
        [
            str(PYTHON),
            str(ROOT / "scripts" / "pipeline.py"),
            source.name,
            "--instructions-file",
            str(paths["prompt"]),
            "--no-render",
        ],
        cwd=ROOT,
        check=True,
    )
    plan = read_json(paths["plan"])
    plan.setdefault(
        "storyPlan",
        {"hook": "", "arc": "", "payoff": "", "languageReviewed": False},
    )
    plan["status"] = "needs-instructions"
    write_json(paths["plan"], plan)
    return save_state(
        job_name,
        "awaiting-story-plan",
        (
            f"Cline ma przeczytać `{paths['prompt'].relative_to(ROOT)}`, "
            f"`{paths['transcript_compact'].relative_to(ROOT)}`, `knowledge/style-memory.json` i "
            f"`assets/MATERIALY.md`, a następnie uzupełnić storyPlan oraz sourceRanges w "
            f"`{paths['plan'].relative_to(ROOT)}` i ustawić wyłącznie `needs-review`. "
            f"Potem uruchomić `npm run reel:validate-story -- {source.name}`."
        ),
        instructionsFile=str(paths["prompt"].relative_to(ROOT)),
    )


def validate_story(job_name: str, cost: float | None = None) -> dict[str, Any]:
    paths = workflow_paths(job_name)
    require_phase(job_name, "awaiting-story-plan")
    checked_cost = validate_stage_cost(cost)
    result = validate_story_data(read_json(paths["plan"]), read_json(paths["transcript"]), paths["plan"])
    state = save_state(
        job_name,
        "awaiting-story-approval",
        (
            f"Pokazać użytkownikowi historię z `{paths['report'].relative_to(ROOT)}`. "
            f"Po jawnym zatwierdzeniu uruchomić `npm run reel:approve-story -- {job_name}.mp4 --approved`."
        ),
        storyValidation=result,
    )
    if checked_cost is not None:
        state["costUsd"] = checked_cost
        write_json(paths["state"], state)
        write_next_report(state, paths["report"])
    return state


def approve_story(job_name: str, approved: bool, reference: Path) -> dict[str, Any]:
    if not approved:
        raise ValueError("Akceptacja historii wymaga jawnej flagi --approved.")
    require_phase(job_name, "awaiting-story-approval")
    paths = workflow_paths(job_name)
    validation = validate_story_data(read_json(paths["plan"]), read_json(paths["transcript"]), paths["plan"])
    plan = read_json(paths["plan"])
    original_plan = json.loads(json.dumps(plan))
    plan["status"] = "ready"
    write_json(paths["plan"], plan)
    try:
        package = prepare_director(job_name, reference.expanduser().resolve())
    except Exception:
        write_json(paths["plan"], original_plan)
        raise
    return save_state(
        job_name,
        "awaiting-director-plan",
        (
            "Cline ma wykonać reżyserię według kompletnego `director/input-package.json`, zapisać "
            "wyłącznie `director/cline-proposal.json` i uruchomić "
            f"`npm run reel:import-director -- {job_name}.mp4 --cost KOSZT_Z_CLINE`."
        ),
        storyValidation=validation,
        directorPackage={"beats": len(package["timelineBeats"]), "assets": len(package["assets"])},
    )


def import_director(job_name: str, cost: float) -> dict[str, Any]:
    paths = workflow_paths(job_name)
    require_phase(job_name, "awaiting-director-plan")
    checked_cost = validate_stage_cost(cost)
    if checked_cost is None:
        raise ValueError("Import wymaga rzeczywistego kosztu Cline.")
    artifact = import_cline_proposal(job_name)
    package = read_json(ANALYSIS / job_name / "director/input-package.json")
    reviewed = read_json(paths["plan"])
    application = application_from_proposal(artifact["proposal"], package["timelineDurationMs"])
    for field in ("overlays", "effectCues", "soundEffects"):
        reviewed[field] = [x for x in reviewed.get(field, []) if x.get("generatedBy") != DIRECTOR_ID] + application[field]
    reviewed["visualBeats"] = application["visualBeats"]
    reviewed["referenceBuildingBlocksRequired"] = bool(reviewed.get("referenceBuildingBlocksRequired")) or application["referenceBuildingBlocksRequired"]
    review_signature = write_review(ROOT, job_name, reviewed)
    previous = read_json(paths["state"])
    total = round(float(previous.get("costUsd", 0)) + checked_cost, 6)
    state = save_state(
        job_name,
        "awaiting-director-approval",
        (
            f"Pokazać użytkownikowi `analysis/{job_name}/director/review-plan.md` oraz `{paths['director_report'].relative_to(ROOT)}`. Po jawnym "
            f"zatwierdzeniu uruchomić `npm run reel:approve-director -- {job_name}.mp4 --approved`."
        ),
        proposalStatus=artifact["status"],
        reviewSignature=review_signature,
    )
    state["costUsd"] = total
    write_json(paths["state"], state)
    write_next_report(state, paths["report"])
    return state


def approve_director(job_name: str, approved: bool) -> dict[str, Any]:
    if not approved:
        raise ValueError("Akceptacja reżyserii wymaga jawnej flagi --approved.")
    state = require_phase(job_name, "awaiting-director-approval")
    package = read_json(ANALYSIS / job_name / "director/input-package.json")
    artifact = read_json(ANALYSIS / job_name / "director/proposal.json")
    reviewed = read_json(workflow_paths(job_name)["plan"])
    application = application_from_proposal(artifact["proposal"], package["timelineDurationMs"])
    for field in ("overlays", "effectCues", "soundEffects"):
        reviewed[field] = [x for x in reviewed.get(field, []) if x.get("generatedBy") != DIRECTOR_ID] + application[field]
    reviewed["visualBeats"] = application["visualBeats"]
    reviewed["referenceBuildingBlocksRequired"] = bool(reviewed.get("referenceBuildingBlocksRequired")) or application["referenceBuildingBlocksRequired"]
    check_review(ROOT, job_name, reviewed, state.get("reviewSignature"))
    applied = apply_director(job_name, True)
    signature = write_review(ROOT, job_name, applied)
    return save_state(
        job_name,
        "ready-to-render",
        (
            f"Po osobnym poleceniu użytkownika „renderuj” uruchomić "
            f"`npm run reel:render -- {job_name}.mp4 --approved`."
        ),
        reviewSignature=signature,
    )


def render(job_name: str, approved: bool) -> dict[str, Any]:
    if not approved:
        raise ValueError("Render wymaga jawnej flagi --approved.")
    paths = workflow_paths(job_name)
    state = read_json(paths["state"])
    if state.get("phase") != "ready-to-render":
        raise ValueError("Workflow nie jest w stanie ready-to-render.")
    check_scenario(ROOT, job_name)
    if state.get("reviewSignature") or (paths["directory"] / "scenario-binding.json").exists():
        check_review(ROOT, job_name, read_json(paths["plan"]), state.get("reviewSignature"))
    subprocess.run(
        [str(PYTHON), str(ROOT / "scripts" / "pipeline.py"), f"{job_name}.mp4"],
        cwd=ROOT,
        check=True,
    )
    final_render = OUTPUT / f"{job_name}-render.mp4"
    if not final_render.is_file():
        raise RuntimeError("Pipeline zakończył się bez finalnego renderu.")
    return save_state(job_name, "complete", f"Gotowy render: `{final_render.relative_to(ROOT)}`.")


def print_state(state: dict[str, Any]) -> None:
    print(json.dumps({key: value for key, value in state.items() if key != "history"}, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["start", "validate-story", "approve-story", "import-director", "approve-director", "render", "status", "refresh-scenario", "revise-director"],
    )
    parser.add_argument("source")
    parser.add_argument("--scenario-file", type=Path)
    parser.add_argument("--instructions")
    parser.add_argument("--instructions-file", type=Path)
    parser.add_argument("--reference", type=Path, default=REFERENCE_DEFAULT)
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--cost", type=float)
    args = parser.parse_args()
    job_name = Path(args.source).stem
    if args.command == "start":
        if bool(args.instructions) == bool(args.instructions_file):
            raise ValueError("Podaj dokładnie jedno: --instructions albo --instructions-file.")
        instructions = args.instructions or args.instructions_file.expanduser().read_text(encoding="utf-8")
        state = start(args.source, instructions, args.scenario_file)
    elif args.command == "revise-director":
        check_scenario(ROOT, job_name)
        current = read_json(workflow_paths(job_name)["state"])
        if current["phase"] not in ("awaiting-director-approval", "ready-to-render", "awaiting-director-plan", "complete"):
            raise ValueError("Najpierw zatwierdź historię.")
        paths = workflow_paths(job_name)
        plan = read_json(paths["plan"])
        if plan.get("status") == "needs-review":
            validate_story_data(plan, read_json(paths["transcript"]), paths["plan"])
            plan["status"] = "ready"
            write_json(paths["plan"], plan)
            prepare_director(job_name, args.reference.expanduser().resolve())
        state = save_state(job_name, "awaiting-director-plan", "Przeczytaj director/input-package.json i workflow/scenario-snapshot.md, jeśli istnieje. Popraw director/cline-proposal.json oraz uruchom reel:import-director. Pokaż nowy review-plan.md przed akceptacją.")
    elif args.command == "refresh-scenario":
        paths = workflow_paths(job_name)
        binding = read_json(paths["directory"] / "scenario-binding.json")
        instructions = bind(ROOT, job_name, Path(binding["source"]), binding["baseInstructions"])
        plan = read_json(paths["plan"])
        plan["instructions"] = instructions
        plan["status"] = "needs-instructions"
        write_json(paths["plan"], plan)
        paths["prompt"].write_text(instructions, encoding="utf-8")
        state = save_state(job_name, "awaiting-story-plan", "Przeczytaj workflow/scenario-snapshot.md i transcript-compact.md; zaktualizuj historię według nowego briefu bez usuwania wcześniejszych korekt. Ustaw needs-review i uruchom reel:validate-story. Wcześniejsze akceptacje nie obowiązują.")
    elif args.command == "validate-story":
        state = validate_story(job_name, args.cost)
    elif args.command == "approve-story":
        state = approve_story(job_name, args.approved, args.reference)
    elif args.command == "import-director":
        if args.cost is None or args.cost < 0:
            raise ValueError("Import wymaga rzeczywistego --cost widocznego w Cline.")
        state = import_director(job_name, args.cost)
    elif args.command == "approve-director":
        state = approve_director(job_name, args.approved)
    elif args.command == "render":
        state = render(job_name, args.approved)
    else:
        path = workflow_paths(job_name)["state"]
        if not path.is_file():
            raise FileNotFoundError(f"Brak workflow dla {job_name}.")
        state = read_json(path)
    print_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
