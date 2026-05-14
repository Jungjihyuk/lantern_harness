"""session_start hook — 세션 시작 시 AGENTS.md 합성 + state 초기화 + trace.

책임 (manifest.yaml 의 roles):
  - prefix_injection: compose 의 cognition entries 를 모아 runtime/AGENTS.resolved.md 생성
  - status_init:      runtime/sessions/<id>/ 의 상태 파일 초기화
  - trace_log:        session_start 이벤트 trace 기록

stdin envelope:
  {"hook_type": "session_start", "session_id": "...", "project_root": "...", ...}

stdout: {"decision": "allow"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.compose import Compose
from lib.manifest import parse_manifest
from lib.resolver import Resolver

from lib.hooks._common import (
    active_roles,
    append_trace,
    emit_allow_and_exit,
    load_context,
    read_envelope,
    utc_now,
)

HOOK_ID = "session_start"


def render_agents_md(compose: Compose, resolver: Resolver, project_root: Path) -> str:
    """compose 의 cognition 도메인 entries 로부터 AGENTS.md 본문 합성."""
    parts: list[str] = []
    parts.append("# AGENTS.md")
    parts.append("")
    parts.append("> 매 세션 자동 생성 — compose.yaml 의 cognition 도메인에서 derived.")
    parts.append("")

    # 1. instructions — 본문 직접 누적
    instr_bodies: list[str] = []
    for e in compose.entries:
        if e.domain != "cognition" or e.section != "instructions":
            continue
        try:
            manifest_path = resolver.resolve(e.id)
            m = parse_manifest(manifest_path)
            body_path = manifest_path.parent / m.entry
            if body_path.exists():
                instr_bodies.append(body_path.read_text(encoding="utf-8", errors="replace").strip())
        except Exception:
            continue
    if instr_bodies:
        parts.append("\n\n".join(instr_bodies))
        parts.append("")

    # 2. context.required
    req = [e for e in compose.entries
           if e.domain == "cognition" and e.section == "context.required"]
    if req:
        parts.append("## Required Context")
        parts.append("> 작업 시작 전 반드시 읽을 문서:")
        parts.append("")
        for e in req:
            src = e.extras.get("src_path", "")
            label = e.extras.get("label", "") or e.id
            parts.append(f"- {label}: `{src}`")
        parts.append("")

    # 3. context.triggered  (= Conditional Required — 강제 + 행동 지침)
    trig = [e for e in compose.entries
            if e.domain == "cognition" and e.section == "context.triggered"]
    if trig:
        parts.append("## Conditional Required Context")
        parts.append("> 편집 path 가 `when` 패턴과 매칭하면 강제 읽기 + 그 안의 행동 지침 따르기:")
        parts.append("")
        for e in trig:
            when = e.extras.get("when", "")
            src = e.extras.get("src_path", "")
            label = e.extras.get("label", "") or e.id
            parts.append(f"- `{when}` → `{src}` ({label})")
        parts.append("")

    # 4. context.suggested  (= Suggested — 자율 참고, lazy)
    sug = [e for e in compose.entries
           if e.domain == "cognition" and e.section == "context.suggested"]
    if sug:
        parts.append("## Suggested Context")
        parts.append("> 필요 시 자율 참고 (lazy, 안 봐도 됨):")
        parts.append("")
        for e in sug:
            src = e.extras.get("src_path", "")
            label = e.extras.get("label", "") or e.id
            parts.append(f"- {label}: `{src}`")
        parts.append("")

    # 5. rules — 본문 직접 누적
    rule_bodies: list[str] = []
    for e in compose.entries:
        if e.domain != "cognition" or e.section != "rules":
            continue
        try:
            manifest_path = resolver.resolve(e.id)
            m = parse_manifest(manifest_path)
            body_path = manifest_path.parent / m.entry
            if body_path.exists():
                rule_bodies.append(body_path.read_text(encoding="utf-8", errors="replace").strip())
        except Exception:
            continue
    if rule_bodies:
        parts.append("## Hard Rules")
        parts.append("")
        parts.append("\n\n".join(rule_bodies))
        parts.append("")

    return "\n".join(parts)


def init_session_state(project_root: Path, session_id: str, compose: Compose) -> None:
    """runtime/sessions/<session_id>/ 의 상태 파일 초기화."""
    sess_dir = project_root / ".harness" / "runtime" / "sessions" / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)

    # meta.json
    (sess_dir / "meta.json").write_text(json.dumps({
        "session_id": session_id,
        "started_at": utc_now(),
    }, indent=2, ensure_ascii=False))

    # required-status.json — required entries 의 읽음 추적
    req_status = {}
    for e in compose.entries:
        if e.domain == "cognition" and e.section == "context.required":
            src = e.extras.get("src_path")
            if src:
                req_status[src] = {
                    "status": "unread",
                    "on_deny": e.extras.get("on_deny", "self_correct"),
                }
    (sess_dir / "required-status.json").write_text(
        json.dumps(req_status, indent=2, ensure_ascii=False))

    # cognitive-guard.json — 누적 카운터
    (sess_dir / "cognitive-guard.json").write_text(json.dumps({
        "changed_files": [],
        "diff_lines_total": 0,
        "new_files_total": 0,
        "edit_history": [],
        "bypass_used": False,
    }, indent=2))

    # decisions.jsonl + prompts.jsonl — 빈 파일 생성
    (sess_dir / "decisions.jsonl").touch()
    (sess_dir / "prompts.jsonl").touch()


def main() -> int:
    envelope = read_envelope()
    session_id = envelope.get("session_id") or "unknown"
    project_root_str = envelope.get("project_root") or "."
    project_root = Path(project_root_str).resolve()

    ctx = load_context(project_root)
    if ctx is None:
        # No harness configured — silent pass
        return emit_allow_and_exit()

    compose, resolver = ctx
    roles = active_roles(compose, HOOK_ID)

    # role: prefix_injection — AGENTS.md 합성
    if "prefix_injection" in roles:
        try:
            agents_md = render_agents_md(compose, resolver, project_root)
            resolved_path = project_root / ".harness" / "runtime" / "AGENTS.resolved.md"
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            resolved_path.write_text(agents_md, encoding="utf-8")
        except Exception:
            pass  # silent — hook 가 LLM 차단해선 안 됨

    # role: status_init
    if "status_init" in roles:
        try:
            init_session_state(project_root, session_id, compose)
        except Exception:
            pass

    # role: trace_log
    if "trace_log" in roles:
        try:
            append_trace(project_root, session_id, {
                "hook": HOOK_ID,
                "session_id": session_id,
            })
        except Exception:
            pass

    return emit_allow_and_exit()


if __name__ == "__main__":
    sys.exit(main())
