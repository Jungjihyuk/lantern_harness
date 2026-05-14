"""Hook 공통 헬퍼 — envelope 파싱, trace append, decision 응답."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lib.compose import Compose, parse_compose
from lib.resolver import Resolver


def read_envelope() -> dict:
    """stdin 의 JSON envelope 파싱. 빈 입력이면 {}."""
    data = sys.stdin.read()
    if not data.strip():
        return {}
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_standard_root() -> Optional[Path]:
    """install 된 ~/.harness/standard 우선, 없으면 dev fallback."""
    harness_home = Path(os.environ.get("HARNESS_HOME", Path.home() / ".harness"))
    if (harness_home / "standard").exists():
        return harness_home / "standard"
    dev = Path(__file__).resolve().parent.parent.parent / "standard"
    if dev.exists():
        return dev
    return None


def load_context(project_root: Path) -> Optional[tuple[Compose, Resolver]]:
    """compose + resolver 로드. 실패 시 None."""
    compose_path = project_root / ".harness" / "compose.yaml"
    if not compose_path.exists():
        return None
    standard_root = find_standard_root()
    if standard_root is None:
        return None
    know_how_root = project_root / ".harness" / "know-how"
    try:
        compose = parse_compose(compose_path)
        resolver = Resolver(standard_root=standard_root, know_how_root=know_how_root)
    except Exception:
        return None
    return compose, resolver


def active_roles(compose: Compose, hook_id: str) -> set[str]:
    """compose 에서 이 hook id 가 어느 role 로 활성화돼있는지."""
    roles: set[str] = set()
    for entry in compose.entries:
        if entry.id == hook_id and entry.section == "hooks":
            if entry.role:
                roles.add(entry.role)
    return roles


def append_trace(project_root: Path, session_id: str, event: dict) -> None:
    """runtime/traces/<session_id>.jsonl 에 한 줄 append."""
    trace_dir = project_root / ".harness" / "runtime" / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"{session_id}.jsonl"
    event = {"ts": utc_now(), **event}
    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def append_decision(project_root: Path, session_id: str, decision: dict) -> None:
    """runtime/sessions/<session_id>/decisions.jsonl 에 한 줄 append."""
    sess_dir = project_root / ".harness" / "runtime" / "sessions" / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    decision = {"ts": utc_now(), **decision}
    with open(sess_dir / "decisions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")


def emit_decision(decision: str, reason: Optional[str] = None, **extras) -> None:
    """stdout 으로 decision JSON 한 줄."""
    payload = {"decision": decision}
    if reason is not None:
        payload["reason"] = reason
    payload.update(extras)
    print(json.dumps(payload, ensure_ascii=False))


def emit_allow_and_exit() -> int:
    emit_decision("allow")
    return 0
