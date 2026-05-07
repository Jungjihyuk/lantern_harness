#!/usr/bin/env python3
"""Ralph run state 관리.

상태 위치: <project>/.harness/runtime/ralph/runs/<run-id>/state.json

명령:
    state.py create <project_root> <task_path>           새 run 시작 (run-id stdout)
    state.py append <project_root> <run-id> <iter-json>   iteration 추가
    state.py finish <project_root> <run-id> <status>      완료 표시 (passed/failed/aborted)
    state.py status <project_root> [<run-id>]             상태 조회 (run-id 생략 시 latest)
    state.py list <project_root>                          모든 run 목록
    state.py active <project_root>                        현재 실행 중 run-id (lock)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def runs_dir(project_root: Path) -> Path:
    p = project_root / ".harness" / "runtime" / "ralph" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lock_file(project_root: Path) -> Path:
    return project_root / ".harness" / "runtime" / "ralph" / "active.lock"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_create(project_root: Path, task_path: str):
    rid = datetime.now().strftime("%Y%m%dT%H%M%S")
    rdir = runs_dir(project_root) / rid
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "prompts").mkdir(exist_ok=True)
    (rdir / "responses").mkdir(exist_ok=True)
    (rdir / "verify-results").mkdir(exist_ok=True)
    state = {
        "run_id": rid,
        "started_at": now_iso(),
        "task_path": task_path,
        "status": "running",  # running | passed | failed | aborted
        "iterations": [],
    }
    (rdir / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    # lock
    lock_file(project_root).write_text(rid, encoding="utf-8")
    print(rid)


def cmd_append(project_root: Path, rid: str, iter_json: str):
    sf = runs_dir(project_root) / rid / "state.json"
    s = json.loads(sf.read_text(encoding="utf-8"))
    s["iterations"].append(json.loads(iter_json))
    s["last_updated"] = now_iso()
    sf.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_finish(project_root: Path, rid: str, status: str):
    sf = runs_dir(project_root) / rid / "state.json"
    s = json.loads(sf.read_text(encoding="utf-8"))
    s["status"] = status
    s["finished_at"] = now_iso()
    sf.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    # lock 해제
    lf = lock_file(project_root)
    if lf.is_file() and lf.read_text(encoding="utf-8").strip() == rid:
        lf.unlink()


def cmd_status(project_root: Path, rid: str | None):
    runs = runs_dir(project_root)
    if rid is None:
        candidates = sorted([d for d in runs.iterdir() if d.is_dir()], key=lambda p: p.name, reverse=True)
        if not candidates:
            print("(ralph run 없음)")
            return
        rid = candidates[0].name
    sf = runs / rid / "state.json"
    if not sf.is_file():
        print(f"run {rid} 없음")
        return
    s = json.loads(sf.read_text(encoding="utf-8"))
    print(f"run_id:      {s['run_id']}")
    print(f"status:      {s['status']}")
    print(f"started:     {s['started_at']}")
    print(f"task:        {s.get('task_path', '')}")
    print(f"iterations:  {len(s['iterations'])}")
    for it in s["iterations"][-5:]:
        verdict = it.get("verify", "?")
        print(f"  #{it['n']}  verify={verdict}  ({it.get('duration_s', '?')}s)")


def cmd_list(project_root: Path):
    runs = runs_dir(project_root)
    rows = []
    for d in sorted(runs.iterdir() if runs.is_dir() else [], key=lambda p: p.name, reverse=True):
        sf = d / "state.json"
        if not sf.is_file():
            continue
        s = json.loads(sf.read_text(encoding="utf-8"))
        rows.append({
            "rid": s["run_id"],
            "status": s["status"],
            "iters": len(s["iterations"]),
            "started": s["started_at"],
        })
    if not rows:
        print("(없음)")
        return
    print(f"{'run_id':<22} {'status':<10} {'iters':>6}  started")
    for r in rows[:20]:
        print(f"{r['rid']:<22} {r['status']:<10} {r['iters']:>6}  {r['started']}")


def cmd_active(project_root: Path):
    lf = lock_file(project_root)
    if lf.is_file():
        print(lf.read_text(encoding="utf-8").strip())


def main():
    if len(sys.argv) < 3:
        sys.stderr.write(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    project_root = Path(sys.argv[2]).resolve()
    if cmd == "create":
        if len(sys.argv) < 4:
            sys.exit(1)
        cmd_create(project_root, sys.argv[3])
    elif cmd == "append":
        if len(sys.argv) < 5:
            sys.exit(1)
        cmd_append(project_root, sys.argv[3], sys.argv[4])
    elif cmd == "finish":
        if len(sys.argv) < 5:
            sys.exit(1)
        cmd_finish(project_root, sys.argv[3], sys.argv[4])
    elif cmd == "status":
        rid = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_status(project_root, rid)
    elif cmd == "list":
        cmd_list(project_root)
    elif cmd == "active":
        cmd_active(project_root)
    else:
        sys.stderr.write(f"unknown: {cmd}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
