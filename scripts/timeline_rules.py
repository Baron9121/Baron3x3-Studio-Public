"""Reguły układania scen na osi czasu (ustalenia użytkownika 2026-09).

- HOOK LOCK: do chwili wypowiedzenia nazwiska (hookEndMs) linia zawiera wyłącznie A-roll;
  każda przebitka rozpoczynająca się przed tą chwilą jest odrzucana.
- BRIDGE SMALL GAPS: jeśli przerwa między końcem poprzedniego a początkiem następnego
  B-rolla jest mniejsza niż `bridge_gap_ms` (domyślnie 3000 ms), NIE pokazujemy A-rolla
  pomiędzy nimi; poprzednia przebitka zostaje rozciągnięta tak, by stykała się z początkiem
  następnej (bezpośrednie przejście B-roll -> B-roll).
"""
from __future__ import annotations

from typing import Any


def apply_timeline_rules(
    overlays: list[dict[str, Any]],
    hook_end_ms: int = 0,
    bridge_gap_ms: int = 3000,
    fps: float = 30.0,
) -> list[dict[str, Any]]:
    """Zwraca nową, uporządkowaną listę overlayów po zastosowaniu reguł układania.

    Parametr `hook_end_ms` (początek osi, do którego trwa blokada) pozwala trzymać
    A-roll na hooku. Zmiany działają na kopii, nie modyfikują wejściowego planu.
    """
    if not overlays:
        return []

    bridge_frames = max(1, int(round(bridge_gap_ms / 1000.0 * fps)))

    def _normalized(item: dict[str, Any]) -> dict[str, Any]:
        return dict(item)

    # 1) HOOK LOCK — odrzuć każdą przebitkę, która zaczyna się przed końcem hooka.
    locked: list[dict[str, Any]] = []
    for item in overlays:
        start = int(item.get("timelineStartMs", 0))
        if start >= hook_end_ms:
            locked.append(_normalized(item))
        else:
            # przebitka startuje w obrębie hooka — wycinamy ją w całości
            pass

    if not locked:
        return []

    # 2) Sortuj wg czasu startu (stabilnie, zachowując oryginalną kolejność równych).
    locked.sort(key=lambda item: int(item.get("timelineStartMs", 0)))

    # 3) BRIDGE SMALL GAPS — scala B-rolle oddzielone zbyt małym dystansem.
    merged: list[dict[str, Any]] = [dict(locked[0])]
    for item in locked[1:]:
        prev = merged[-1]
        prev_end = int(prev.get("timelineEndMs", 0))
        cur_start = int(item.get("timelineStartMs", 0))
        # Dystans w klatkach między końcem poprzedniego a początkiem bieżącego.
        diff_frames = (cur_start - prev_end) / 1000.0 * fps
        if diff_frames < bridge_frames:
            # Za krótka przerwa: rozciągnij poprzednią przebitkę do startu bieżącej.
            prev["timelineEndMs"] = cur_start
            merged[-1] = prev
            merged.append(dict(item))
        else:
            # Przerwa >= 3 s — można tu wrócić A-roll.
            merged.append(dict(item))

    return merged