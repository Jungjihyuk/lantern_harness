"""session_start hook — 세션 시작 시 AGENTS.md 합성 + state 초기화 + trace + snapshot + drift.

책임 (manifest.yaml 의 roles):
  - prefix_injection: compose 의 cognition entries 를 모아 runtime/AGENTS.resolved.md 생성
  - status_init:      runtime/sessions/<id>/ 의 상태 파일 초기화
  - trace_log:        session_start 이벤트 trace 기록
  - state_snapshot:   세션 시작 시점의 시스템 hash (compose / standard / know-how / git) 기록
  - drift_check:      이전 세션 snapshot 과 비교, 변경 항목 trace 에 안내

stdin envelope:
  {"hook_type": "session_start", "session_id": "...", "project_root": "...", ...}

stdout: {"decision": "allow"}
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
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

    # 1. prefix — 본문 직접 누적 (instructions / 외부 검증 / Hard Rules 통합)
    #    manifest 의 roles 에 'hard_rule' 포함되면 Hard Rules 그룹으로 분리.
    general_bodies: list[str] = []
    hard_rule_bodies: list[str] = []
    for e in compose.entries:
        if e.domain != "cognition" or e.section != "prefix":
            continue
        try:
            manifest_path = resolver.resolve(e.id)
            m = parse_manifest(manifest_path)
            body_path = manifest_path.parent / m.entry
            if not body_path.exists():
                continue
            body = body_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        # role 에 'hard_rule' 있거나 entry 의 role 이 'hard_rule' 이면 Hard Rules 그룹
        is_hard = "hard_rule" in (m.roles or []) or e.role == "hard_rule"
        if is_hard:
            hard_rule_bodies.append(body)
        else:
            general_bodies.append(body)
    if general_bodies:
        parts.append("\n\n".join(general_bodies))
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

    # 5. Hard Rules (prefix 안의 hard_rule role artifact)
    if hard_rule_bodies:
        parts.append("## Hard Rules")
        parts.append("")
        parts.append("\n\n".join(hard_rule_bodies))
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


# ─────────────────────── state_snapshot / drift_check ───────────────────────

def _max_mtime(root: Path) -> float:
    """root 아래 모든 file 의 최대 mtime. 없으면 0."""
    if not root.exists():
        return 0.0
    return max(
        (p.stat().st_mtime for p in root.rglob("*") if p.is_file()),
        default=0.0,
    )


def write_snapshot(project_root: Path, session_id: str) -> dict:
    """현재 시점의 시스템 hash 를 sessions/<id>/snapshot.json 에 기록. 결과 dict 반환."""
    snap: dict = {"timestamp": utc_now()}

    # compose.yaml SHA256 (short)
    compose_path = project_root / ".harness" / "compose.yaml"
    if compose_path.exists():
        snap["compose_sha"] = hashlib.sha256(compose_path.read_bytes()).hexdigest()[:16]

    # standard / know-how 최근 변경 mtime
    harness_home = Path(os.environ.get("HARNESS_HOME", Path.home() / ".harness"))
    standard_root = harness_home / "standard"
    if not standard_root.exists():
        dev = Path(__file__).resolve().parent.parent.parent / "standard"
        if dev.exists():
            standard_root = dev
    snap["standard_mtime"] = _max_mtime(standard_root)

    kh_root = project_root / ".harness" / "know-how"
    snap["know_how_mtime"] = _max_mtime(kh_root)

    # git anchor
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            snap["git_head"] = r.stdout.strip()
        r = subprocess.run(
            ["git", "-C", str(project_root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if r.returncode == 0:
            lines = r.stdout.strip().splitlines()
            snap["git_dirty"] = bool(lines)
            if lines:
                snap["git_diff_summary"] = "; ".join(lines[:5]) + (" ..." if len(lines) > 5 else "")
    except Exception:
        pass

    sess_dir = project_root / ".harness" / "runtime" / "sessions" / session_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    (sess_dir / "snapshot.json").write_text(
        json.dumps(snap, indent=2, ensure_ascii=False)
    )
    return snap


def find_previous_snapshot(project_root: Path, current_session_id: str):
    """이전 세션 중 가장 최근 snapshot.json 반환 (없으면 None)."""
    sessions_dir = project_root / ".harness" / "runtime" / "sessions"
    if not sessions_dir.exists():
        return None
    candidates = []
    for sess in sessions_dir.iterdir():
        if not sess.is_dir() or sess.name == current_session_id:
            continue
        snap_file = sess / "snapshot.json"
        if snap_file.exists():
            candidates.append((snap_file.stat().st_mtime, snap_file))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    try:
        return json.loads(candidates[0][1].read_text(encoding="utf-8"))
    except Exception:
        return None


def diff_snapshots(prev: dict, curr: dict) -> list[str]:
    """두 snapshot 비교, 변경 항목 list 반환."""
    changes = []
    if prev.get("compose_sha") != curr.get("compose_sha"):
        changes.append("compose.yaml")
    if prev.get("standard_mtime") != curr.get("standard_mtime"):
        changes.append("standard/")
    if prev.get("know_how_mtime") != curr.get("know_how_mtime"):
        changes.append("know-how/")
    p_head = (prev.get("git_head") or "")[:7]
    c_head = (curr.get("git_head") or "")[:7]
    if p_head != c_head:
        changes.append(f"git HEAD ({p_head or 'none'} → {c_head or 'none'})")
    return changes


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

    # role: state_snapshot — 현재 시점 hash 기록 (drift_check 가 활성이면 자동 선행)
    curr_snap = None
    if "state_snapshot" in roles or "drift_check" in roles:
        try:
            curr_snap = write_snapshot(project_root, session_id)
        except Exception:
            pass

    # role: drift_check — 이전 세션 snapshot 과 비교, 변경 항목 trace
    if "drift_check" in roles and curr_snap is not None:
        try:
            prev = find_previous_snapshot(project_root, session_id)
            if prev is not None:
                changes = diff_snapshots(prev, curr_snap)
                if changes:
                    append_trace(project_root, session_id, {
                        "hook": HOOK_ID,
                        "drift": True,
                        "changed": changes,
                        "from_timestamp": prev.get("timestamp"),
                    })
        except Exception:
            pass

    return emit_allow_and_exit()


if __name__ == "__main__":
    sys.exit(main())
